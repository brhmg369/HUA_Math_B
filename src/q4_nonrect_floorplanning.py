"""Q4 non-rectangular module floorplanning.

The Q4 demo has only four modules, so this script uses an exact grid-cell
enumeration instead of a stochastic heuristic. Each L/T/rectangular module is
represented as a set of unit cells. Rotations are generated exactly, placements
are checked by set intersection, and the enclosing outline is searched in
increasing area order.

For the instance in Fig. 3, the total module area is 24. A 6 by 4 tiling exists,
so the minimum enclosing area is certified as 24 by the area lower bound plus
the constructed layout.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - PNG output is optional.
    Image = None
    ImageDraw = None
    ImageFont = None


Cell = tuple[int, int]


@dataclass(frozen=True)
class OrientedShape:
    name: str
    rotation_deg: int
    cells: frozenset[Cell]

    @property
    def width(self) -> int:
        return max(x for x, _ in self.cells) + 1

    @property
    def height(self) -> int:
        return max(y for _, y in self.cells) + 1

    @property
    def area(self) -> int:
        return len(self.cells)


@dataclass(frozen=True)
class Placement:
    name: str
    rotation_deg: int
    x: int
    y: int
    width: int
    height: int
    cells: frozenset[Cell]
    local_cells: frozenset[Cell]

    @property
    def area(self) -> int:
        return len(self.cells)


@dataclass
class SearchResult:
    width: int
    height: int
    placements: list[Placement]
    search_log: list[dict[str, object]]
    explored_nodes: int
    runtime_sec: float

    @property
    def outline_area(self) -> int:
        return self.width * self.height

    @property
    def total_module_area(self) -> int:
        return sum(placement.area for placement in self.placements)

    @property
    def dead_area(self) -> int:
        return self.outline_area - self.total_module_area

    @property
    def aspect_ratio(self) -> float:
        return max(self.width, self.height) / min(self.width, self.height)


def normalize(cells: set[Cell] | frozenset[Cell]) -> frozenset[Cell]:
    min_x = min(x for x, _ in cells)
    min_y = min(y for _, y in cells)
    return frozenset((x - min_x, y - min_y) for x, y in cells)


def rotate_clockwise(cells: frozenset[Cell]) -> frozenset[Cell]:
    return normalize({(y, -x) for x, y in cells})


def base_shapes() -> dict[str, frozenset[Cell]]:
    return {
        # T-shape from Fig. 3: overall 4 by 4, top bar 4 by 2, stem 2 by 2.
        "b1": normalize(
            {
                (0, 2),
                (1, 2),
                (2, 2),
                (3, 2),
                (0, 3),
                (1, 3),
                (2, 3),
                (3, 3),
                (1, 0),
                (2, 0),
                (1, 1),
                (2, 1),
            }
        ),
        # L-shape from Fig. 3: overall 2 by 4, missing the upper-right 1 by 2.
        "b2": normalize({(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1)}),
        "b3": normalize({(0, 0), (1, 0)}),
        "b4": normalize({(0, 0), (0, 1), (0, 2), (0, 3)}),
    }


def oriented_shapes(shapes: dict[str, frozenset[Cell]]) -> dict[str, list[OrientedShape]]:
    result: dict[str, list[OrientedShape]] = {}
    for name, cells in shapes.items():
        variants: list[OrientedShape] = []
        seen: set[frozenset[Cell]] = set()
        current = normalize(cells)
        for rotation in (0, 90, 180, 270):
            if current not in seen:
                variants.append(OrientedShape(name=name, rotation_deg=rotation, cells=current))
                seen.add(current)
            current = rotate_clockwise(current)
        result[name] = variants
    return result


def rectangle_candidates(total_area: int, max_area: int) -> list[tuple[int, int]]:
    candidates: list[tuple[int, int]] = []
    for area in range(total_area, max_area + 1):
        for width in range(1, area + 1):
            if area % width:
                continue
            height = area // width
            candidates.append((width, height))
    return sorted(candidates, key=lambda item: (item[0] * item[1], abs(math.log(item[0] / item[1]))))


def placed_cells(shape: OrientedShape, x: int, y: int) -> frozenset[Cell]:
    return frozenset((x + dx, y + dy) for dx, dy in shape.cells)


def exact_pack_in_rectangle(
    width: int,
    height: int,
    orientations: dict[str, list[OrientedShape]],
    order: list[str],
) -> tuple[list[Placement] | None, int]:
    occupied: set[Cell] = set()
    placements: list[Placement] = []
    explored_nodes = 0

    def backtrack(index: int) -> bool:
        nonlocal explored_nodes
        if index == len(order):
            return True
        name = order[index]
        for shape in orientations[name]:
            if shape.width > width or shape.height > height:
                continue
            for y in range(height - shape.height + 1):
                for x in range(width - shape.width + 1):
                    explored_nodes += 1
                    cells = placed_cells(shape, x, y)
                    if occupied.intersection(cells):
                        continue
                    occupied.update(cells)
                    placements.append(
                        Placement(
                            name=name,
                            rotation_deg=shape.rotation_deg,
                            x=x,
                            y=y,
                            width=shape.width,
                            height=shape.height,
                            cells=cells,
                            local_cells=shape.cells,
                        )
                    )
                    if backtrack(index + 1):
                        return True
                    placements.pop()
                    occupied.difference_update(cells)
        return False

    if backtrack(0):
        return placements.copy(), explored_nodes
    return None, explored_nodes


def solve(max_area: int | None = None) -> SearchResult:
    start = time.perf_counter()
    shapes = base_shapes()
    orientations = oriented_shapes(shapes)
    total_area = sum(len(cells) for cells in shapes.values())
    max_extent = sum(max(max(x for x, _ in cells), max(y for _, y in cells)) + 1 for cells in shapes.values())
    max_area = max_area or total_area * max_extent
    order = sorted(shapes, key=lambda name: (-len(shapes[name]), name))
    search_log: list[dict[str, object]] = []
    explored_total = 0

    for width, height in rectangle_candidates(total_area, max_area):
        placements, explored = exact_pack_in_rectangle(width, height, orientations, order)
        explored_total += explored
        row = {
            "width": width,
            "height": height,
            "area": width * height,
            "feasible": placements is not None,
            "explored_nodes": explored,
        }
        search_log.append(row)
        if placements is not None:
            return SearchResult(
                width=width,
                height=height,
                placements=sorted(placements, key=lambda item: item.name),
                search_log=search_log,
                explored_nodes=explored_total,
                runtime_sec=time.perf_counter() - start,
            )
    raise RuntimeError("No feasible packing found within max_area")


def validate(result: SearchResult) -> dict[str, object]:
    names = [placement.name for placement in result.placements]
    all_cells: list[Cell] = [cell for placement in result.placements for cell in placement.cells]
    unique_cells = set(all_cells)
    overlap_count = len(all_cells) - len(unique_cells)
    out_of_bounds = [
        placement.name
        for placement in result.placements
        if any(x < 0 or y < 0 or x >= result.width or y >= result.height for x, y in placement.cells)
    ]
    missing = sorted(set(base_shapes()) - set(names))
    duplicate = sorted({name for name in names if names.count(name) > 1})
    total_area = sum(len(cells) for cells in base_shapes().values())
    area_lower_bound = total_area
    bounding_width = max(x for x, _ in unique_cells) + 1
    bounding_height = max(y for _, y in unique_cells) + 1
    return {
        "module_count": len(result.placements),
        "module_names": sorted(names),
        "missing_modules": missing,
        "duplicate_modules": duplicate,
        "width": result.width,
        "height": result.height,
        "outline_area": result.outline_area,
        "total_module_area": total_area,
        "placed_area": len(all_cells),
        "unique_occupied_area": len(unique_cells),
        "dead_area": result.dead_area,
        "area_lower_bound": area_lower_bound,
        "lower_bound_attained": result.outline_area == area_lower_bound,
        "bounding_width_from_cells": bounding_width,
        "bounding_height_from_cells": bounding_height,
        "overlap_cell_count": overlap_count,
        "out_of_bounds_modules": out_of_bounds,
        "area_conserved": len(all_cells) == total_area and len(unique_cells) == total_area,
        "valid": (
            not missing
            and not duplicate
            and not out_of_bounds
            and overlap_count == 0
            and len(all_cells) == total_area
            and len(unique_cells) == total_area
            and result.outline_area == area_lower_bound
        ),
    }


def cells_to_text(cells: frozenset[Cell]) -> str:
    return ";".join(f"({x},{y})" for x, y in sorted(cells))


def write_layout_csv(result: SearchResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "module",
                "x",
                "y",
                "rotation_deg",
                "bounding_width",
                "bounding_height",
                "area",
                "local_cells",
                "placed_cells",
            ],
        )
        writer.writeheader()
        for placement in result.placements:
            writer.writerow(
                {
                    "module": placement.name,
                    "x": placement.x,
                    "y": placement.y,
                    "rotation_deg": placement.rotation_deg,
                    "bounding_width": placement.width,
                    "bounding_height": placement.height,
                    "area": placement.area,
                    "local_cells": cells_to_text(placement.local_cells),
                    "placed_cells": cells_to_text(placement.cells),
                }
            )


def write_summary(result: SearchResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "module_count",
                "total_module_area",
                "area_lower_bound",
                "width",
                "height",
                "outline_area",
                "dead_area",
                "lower_bound_attained",
                "aspect_ratio",
                "explored_nodes",
                "runtime_sec",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "module_count": len(result.placements),
                "total_module_area": result.total_module_area,
                "area_lower_bound": result.total_module_area,
                "width": result.width,
                "height": result.height,
                "outline_area": result.outline_area,
                "dead_area": result.dead_area,
                "lower_bound_attained": result.outline_area == result.total_module_area,
                "aspect_ratio": f"{result.aspect_ratio:.8f}",
                "explored_nodes": result.explored_nodes,
                "runtime_sec": f"{result.runtime_sec:.6f}",
            }
        )


def write_search_log(result: SearchResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["width", "height", "area", "feasible", "explored_nodes"])
        writer.writeheader()
        writer.writerows(result.search_log)


def write_grid_txt(result: SearchResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    labels: dict[Cell, str] = {}
    for placement in result.placements:
        for cell in placement.cells:
            labels[cell] = placement.name
    rows: list[str] = []
    for y in range(result.height - 1, -1, -1):
        rows.append(" ".join(labels.get((x, y), "..").rjust(2) for x in range(result.width)))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def color_for(name: str) -> tuple[int, int, int]:
    palette = {
        "b1": (123, 174, 214),
        "b2": (230, 172, 98),
        "b3": (130, 190, 140),
        "b4": (205, 126, 135),
    }
    return palette[name]


def write_svg(result: SearchResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scale = 72
    margin = 52
    width_px = result.width * scale + 2 * margin
    height_px = result.height * scale + 2 * margin
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    for gx in range(result.width + 1):
        x = margin + gx * scale
        parts.append(f'<line x1="{x}" y1="{margin}" x2="{x}" y2="{height_px - margin}" stroke="#ddd" stroke-width="1"/>')
    for gy in range(result.height + 1):
        y = margin + gy * scale
        parts.append(f'<line x1="{margin}" y1="{y}" x2="{width_px - margin}" y2="{y}" stroke="#ddd" stroke-width="1"/>')
    parts.append(
        f'<rect x="{margin}" y="{margin}" width="{result.width * scale}" height="{result.height * scale}" '
        'fill="none" stroke="#111" stroke-width="3"/>'
    )
    for placement in result.placements:
        r, g, b = color_for(placement.name)
        for x, y in placement.cells:
            px = margin + x * scale
            py = margin + (result.height - y - 1) * scale
            parts.append(
                f'<rect x="{px}" y="{py}" width="{scale}" height="{scale}" '
                f'fill="rgb({r},{g},{b})" stroke="white" stroke-width="2"/>'
            )
        cx = margin + (sum(x + 0.5 for x, _ in placement.cells) / placement.area) * scale
        cy = margin + (result.height - sum(y + 0.5 for _, y in placement.cells) / placement.area) * scale
        parts.append(
            f'<text x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" dominant-baseline="middle" '
            'font-size="18" font-family="Arial" font-weight="700" fill="#111">'
            f'{placement.name}</text>'
        )
    parts.append(
        f'<text x="{margin}" y="{margin / 2}" font-size="16" font-family="Arial" fill="#111">'
        f'Q4 optimum: {result.width} x {result.height}, area={result.outline_area}</text>'
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_png(result: SearchResult, path: Path) -> None:
    if Image is None or ImageDraw is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    scale = 110
    margin = 70
    width_px = result.width * scale + 2 * margin
    height_px = result.height * scale + 2 * margin
    image = Image.new("RGB", (width_px, height_px), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 22) if ImageFont else None
        title_font = ImageFont.truetype("arial.ttf", 18) if ImageFont else None
    except Exception:
        font = None
        title_font = None
    for gx in range(result.width + 1):
        x = margin + gx * scale
        draw.line([(x, margin), (x, height_px - margin)], fill=(220, 220, 220), width=1)
    for gy in range(result.height + 1):
        y = margin + gy * scale
        draw.line([(margin, y), (width_px - margin, y)], fill=(220, 220, 220), width=1)
    draw.rectangle([margin, margin, width_px - margin, height_px - margin], outline=(15, 15, 15), width=3)
    for placement in result.placements:
        for x, y in placement.cells:
            px = margin + x * scale
            py = margin + (result.height - y - 1) * scale
            draw.rectangle([px, py, px + scale, py + scale], fill=color_for(placement.name), outline=(255, 255, 255), width=2)
        cx = margin + (sum(x + 0.5 for x, _ in placement.cells) / placement.area) * scale
        cy = margin + (result.height - sum(y + 0.5 for _, y in placement.cells) / placement.area) * scale
        text = placement.name
        bbox = draw.textbbox((0, 0), text, font=font)
        draw.text((cx - (bbox[2] - bbox[0]) / 2, cy - (bbox[3] - bbox[1]) / 2), text, fill=(0, 0, 0), font=font)
    draw.text((margin, 24), f"Q4 optimum: {result.width} x {result.height}, area={result.outline_area}", fill=(0, 0, 0), font=title_font)
    image.save(path)


def write_outputs(result: SearchResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_summary(result, output_dir / "q4_summary.csv")
    write_layout_csv(result, output_dir / "q4_layout.csv")
    write_search_log(result, output_dir / "q4_search_log.csv")
    write_grid_txt(result, output_dir / "q4_grid.txt")
    validation = validate(result)
    (output_dir / "q4_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    write_svg(result, output_dir / "figures" / "q4_optimal_layout.svg")
    write_png(result, output_dir / "figures" / "q4_optimal_layout.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve Q4 non-rectangular floorplanning demo exactly.")
    parser.add_argument("--output-dir", type=Path, default=Path("results") / "q4")
    parser.add_argument("--max-area", type=int, default=None)
    args = parser.parse_args()
    result = solve(max_area=args.max_area)
    write_outputs(result, args.output_dir)
    print(
        f"Q4: W={result.width}, H={result.height}, area={result.outline_area}, "
        f"dead_area={result.dead_area}, explored_nodes={result.explored_nodes}, "
        f"time={result.runtime_sec:.6f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
