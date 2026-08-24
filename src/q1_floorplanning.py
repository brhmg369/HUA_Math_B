"""Q1 floorplanning solver for the HUA Math B problem.

The solver handles outline-free hard rectangular blocks. It scans every
integer candidate short-side width that can still improve the incumbent area
and uses a deterministic skyline strip-packing heuristic with rotations.

The scalar key is area + imbalance, where imbalance is in [0, 1). Because all
input dimensions are integer, the area term is lexicographically dominant.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - drawing remains optional
    Image = None
    ImageDraw = None
    ImageFont = None

try:
    from rectpack import (
        MaxRectsBaf,
        MaxRectsBlsf,
        MaxRectsBssf,
        SORT_AREA,
        SORT_LSIDE,
        SORT_RATIO,
        SORT_SSIDE,
        SkylineBlWm,
        SkylineMwflWm,
        newPacker,
    )
except Exception:  # pragma: no cover - rectpack is an optional enhancer
    MaxRectsBaf = None
    MaxRectsBlsf = None
    MaxRectsBssf = None
    SkylineBlWm = None
    SkylineMwflWm = None
    SORT_AREA = None
    SORT_LSIDE = None
    SORT_RATIO = None
    SORT_SSIDE = None
    newPacker = None


@dataclass(frozen=True)
class Block:
    name: str
    width: int
    height: int

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass(frozen=True)
class FreeRect:
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class SkylineNode:
    x: int
    y: int
    width: int

    @property
    def x2(self) -> int:
        return self.x + self.width


@dataclass(frozen=True)
class Placement:
    name: str
    x: int
    y: int
    width: int
    height: int
    original_width: int
    original_height: int

    @property
    def rotated(self) -> bool:
        return self.width == self.original_height and self.height == self.original_width

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height


@dataclass
class Layout:
    chip: str
    placements: list[Placement]
    width: int
    height: int
    total_block_area: int
    searched_widths: int
    tried_packings: int
    heuristic: str
    runtime_sec: float

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        short = min(self.width, self.height)
        long = max(self.width, self.height)
        return long / short if short else float("inf")

    @property
    def dead_space_area(self) -> int:
        return self.area - self.total_block_area

    @property
    def dead_space_ratio(self) -> float:
        return self.dead_space_area / self.total_block_area

    @property
    def area_lower_bound(self) -> int:
        return self.total_block_area

    @property
    def area_gap_to_lower_bound(self) -> float:
        return self.dead_space_area / self.total_block_area

    @property
    def imbalance(self) -> float:
        return abs(self.width - self.height) / max(self.width, self.height)

    @property
    def cost_key(self) -> float:
        return self.area + self.imbalance


def parse_blocks(path: Path) -> list[Block]:
    blocks: list[Block] = []
    point_pattern = re.compile(r"\((\d+),\s*(\d+)\)")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if " block " not in line:
            continue
        parts = line.split()
        name = parts[0]
        points = [tuple(map(int, p)) for p in point_pattern.findall(line)]
        if len(points) != 4:
            raise ValueError(f"Expected 4 points for block line: {line}")
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        if width <= 0 or height <= 0:
            raise ValueError(f"Non-positive block size in line: {line}")
        blocks.append(Block(name=name, width=width, height=height))
    return blocks


def orientation_options(block: Block, strip_width: int) -> list[tuple[int, int]]:
    options = [(block.width, block.height)]
    if block.width != block.height:
        options.append((block.height, block.width))
    feasible = [(w, h) for w, h in options if w <= strip_width]
    # Deterministic order helps reproducibility when scores tie.
    return sorted(set(feasible), key=lambda p: (p[0] * p[1], p[1], p[0]))


def intersects(a: FreeRect, p: Placement) -> bool:
    return not (p.x >= a.x2 or p.x2 <= a.x or p.y >= a.y2 or p.y2 <= a.y)


def contains(a: FreeRect, b: FreeRect) -> bool:
    return a.x <= b.x and a.y <= b.y and a.x2 >= b.x2 and a.y2 >= b.y2


def split_free_rect(free: FreeRect, placed: Placement) -> list[FreeRect]:
    if not intersects(free, placed):
        return [free]
    out: list[FreeRect] = []
    if placed.x > free.x:
        out.append(FreeRect(free.x, free.y, placed.x - free.x, free.height))
    if placed.x2 < free.x2:
        out.append(FreeRect(placed.x2, free.y, free.x2 - placed.x2, free.height))
    if placed.y > free.y:
        out.append(FreeRect(free.x, free.y, free.width, placed.y - free.y))
    if placed.y2 < free.y2:
        out.append(FreeRect(free.x, placed.y2, free.width, free.y2 - placed.y2))
    return [r for r in out if r.width > 0 and r.height > 0]


def prune_free_rectangles(free_rects: list[FreeRect]) -> list[FreeRect]:
    unique = list(dict.fromkeys(free_rects))
    keep: list[FreeRect] = []
    for i, rect in enumerate(unique):
        dominated = False
        for j, other in enumerate(unique):
            if i != j and contains(other, rect):
                dominated = True
                break
        if not dominated:
            keep.append(rect)
    return keep


def skyline_min_y(nodes: list[SkylineNode], index: int, rect_width: int, strip_width: int) -> int | None:
    x = nodes[index].x
    if x + rect_width > strip_width:
        return None
    width_left = rect_width
    y = 0
    j = index
    while width_left > 0:
        if j >= len(nodes):
            return None
        y = max(y, nodes[j].y)
        width_left -= nodes[j].width
        j += 1
    return y


def add_skyline_level(nodes: list[SkylineNode], index: int, x: int, y: int, width: int, height: int) -> list[SkylineNode]:
    top_y = y + height
    updated = nodes[:index] + [SkylineNode(x, top_y, width)] + nodes[index:]
    right = x + width
    i = index + 1
    while i < len(updated):
        node = updated[i]
        if node.x >= right:
            break
        overlap = right - node.x
        if node.width <= overlap:
            updated.pop(i)
            continue
        updated[i] = SkylineNode(node.x + overlap, node.y, node.width - overlap)
        break

    merged: list[SkylineNode] = []
    for node in updated:
        if node.width <= 0:
            continue
        if merged and merged[-1].y == node.y and merged[-1].x2 == node.x:
            prev = merged[-1]
            merged[-1] = SkylineNode(prev.x, prev.y, prev.width + node.width)
        else:
            merged.append(node)
    return merged


def skyline_pack(order: list[Block], strip_width: int) -> list[Placement] | None:
    nodes = [SkylineNode(0, 0, strip_width)]
    placements: list[Placement] = []
    used_width = 0
    used_height = 0

    for block in order:
        best: tuple[tuple[int, int, int, int, int, int], int, int, int, int] | None = None
        for index, node in enumerate(nodes):
            for width, height in orientation_options(block, strip_width):
                y = skyline_min_y(nodes, index, width, strip_width)
                if y is None:
                    continue
                candidate_width = max(used_width, node.x + width)
                candidate_height = max(used_height, y + height)
                candidate_area = candidate_width * candidate_height
                residual_width = strip_width - (node.x + width)
                score = (
                    candidate_area,
                    candidate_height,
                    y,
                    node.x,
                    abs(candidate_width - candidate_height),
                    residual_width,
                )
                if best is None or score < best[0]:
                    best = (score, index, node.x, y, width, height)
        if best is None:
            return None

        _, index, x, y, width, height = best
        placed = Placement(
            name=block.name,
            x=x,
            y=y,
            width=width,
            height=height,
            original_width=block.width,
            original_height=block.height,
        )
        placements.append(placed)
        used_width = max(used_width, placed.x2)
        used_height = max(used_height, placed.y2)
        nodes = add_skyline_level(nodes, index, x, y, width, height)

    return placements


def rectpack_variants() -> list[tuple[object, object, str]]:
    if newPacker is None:
        return []
    algos = [
        (MaxRectsBssf, "MaxRectsBssf"),
        (MaxRectsBaf, "MaxRectsBaf"),
    ]
    sorts = [
        (SORT_AREA, "SORT_AREA"),
        (SORT_LSIDE, "SORT_LSIDE"),
    ]
    return [(algo, sort, f"rectpack:{algo_name}:{sort_name}") for algo, algo_name in algos for sort, sort_name in sorts]


def rectpack_pack(blocks: list[Block], strip_width: int, pack_algo: object, sort_algo: object) -> list[Placement] | None:
    if newPacker is None:
        return None
    height_bound = sum(max(b.width, b.height) for b in blocks)
    packer = newPacker(pack_algo=pack_algo, sort_algo=sort_algo, rotation=True)
    block_by_name = {b.name: b for b in blocks}
    for block in blocks:
        packer.add_rect(block.width, block.height, block.name)
    packer.add_bin(strip_width, height_bound)
    packer.pack()
    rects = packer.rect_list()
    if len(rects) != len(blocks):
        return None
    placements: list[Placement] = []
    for _, x, y, width, height, name in rects:
        block = block_by_name[str(name)]
        placements.append(
            Placement(
                name=str(name),
                x=int(x),
                y=int(y),
                width=int(width),
                height=int(height),
                original_width=block.width,
                original_height=block.height,
            )
        )
    return placements


def layout_dimensions(placements: Iterable[Placement]) -> tuple[int, int]:
    placements = list(placements)
    if not placements:
        return 0, 0
    return max(p.x2 for p in placements), max(p.y2 for p in placements)


def canonicalize_orientation(placements: list[Placement]) -> list[Placement]:
    width, height = layout_dimensions(placements)
    if width <= height:
        return placements
    rotated: list[Placement] = []
    for p in placements:
        # Rotate the whole layout 90 degrees counterclockwise and translate
        # back to the first quadrant.
        rotated.append(
            Placement(
                name=p.name,
                x=p.y,
                y=width - p.x2,
                width=p.height,
                height=p.width,
                original_width=p.original_width,
                original_height=p.original_height,
            )
        )
    return rotated


def lexicographic_score(placements: list[Placement]) -> tuple[float, int, int, int]:
    width, height = layout_dimensions(placements)
    area = width * height
    imbalance = abs(width - height) / max(width, height)
    return (area + imbalance, area, abs(width - height), max(width, height))


def vertical_stack_layout(blocks: list[Block]) -> list[Placement]:
    y = 0
    placements: list[Placement] = []
    for block in sorted(blocks, key=lambda b: (-max(b.width, b.height), -b.area, b.name)):
        width, height = sorted((block.width, block.height))
        p = Placement(block.name, 0, y, width, height, block.width, block.height)
        placements.append(p)
        y += height
    return placements


def ordering_variants(blocks: list[Block]) -> dict[str, Callable[[Block], tuple]]:
    return {
        "area_desc": lambda b: (-b.area, -max(b.width, b.height), -min(b.width, b.height), b.name),
        "max_side_desc": lambda b: (-max(b.width, b.height), -b.area, -min(b.width, b.height), b.name),
        "min_side_desc": lambda b: (-min(b.width, b.height), -b.area, -max(b.width, b.height), b.name),
        "wide_first": lambda b: (-max(b.width, b.height), min(b.width, b.height), b.name),
        "square_first": lambda b: (abs(b.width - b.height), -b.area, b.name),
        "slender_first": lambda b: (-abs(b.width - b.height), -b.area, b.name),
    }


def solve_chip(chip: str, blocks_path: Path, use_rectpack: bool = True, rectpack_max_blocks: int = 200) -> Layout:
    start = time.perf_counter()
    blocks = parse_blocks(blocks_path)
    total_area = sum(b.area for b in blocks)
    min_width = max(min(b.width, b.height) for b in blocks)
    incumbent = canonicalize_orientation(vertical_stack_layout(blocks))
    best_key = lexicographic_score(incumbent)
    searched_widths = 0
    tried_packings = 0

    variants = ordering_variants(blocks)
    effective_rectpack = use_rectpack and len(blocks) <= rectpack_max_blocks
    rp_variants = rectpack_variants() if effective_rectpack else []
    best_heuristic = "vertical_stack_baseline"
    width = min_width
    while width <= int(math.floor(math.sqrt(best_key[1]))):
        searched_widths += 1
        for variant_name, key_fn in variants.items():
            order = sorted(blocks, key=key_fn)
            placements = skyline_pack(order, width)
            tried_packings += 1
            if placements is None:
                continue
            placements = canonicalize_orientation(placements)
            key = lexicographic_score(placements)
            if key < best_key:
                incumbent = placements
                best_key = key
                best_heuristic = f"skyline:{variant_name}:width={width}"
        for pack_algo, sort_algo, variant_name in rp_variants:
            placements = rectpack_pack(blocks, width, pack_algo, sort_algo)
            tried_packings += 1
            if placements is None:
                continue
            placements = canonicalize_orientation(placements)
            key = lexicographic_score(placements)
            if key < best_key:
                incumbent = placements
                best_key = key
                best_heuristic = f"{variant_name}:width={width}"
        width += 1

    final_width, final_height = layout_dimensions(incumbent)
    return Layout(
        chip=chip,
        placements=sorted(incumbent, key=lambda p: natural_key(p.name)),
        width=final_width,
        height=final_height,
        total_block_area=total_area,
        searched_widths=searched_widths,
        tried_packings=tried_packings,
        heuristic=best_heuristic,
        runtime_sec=time.perf_counter() - start,
    )


def natural_key(text: str) -> tuple[str, int]:
    match = re.match(r"([A-Za-z_]+)(\d+)$", text)
    if match:
        return (match.group(1), int(match.group(2)))
    return (text, -1)


def validate_layout(layout: Layout) -> dict[str, object]:
    placements = layout.placements
    names = [p.name for p in placements]
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    overlap_pairs: list[tuple[str, str]] = []
    for i, a in enumerate(placements):
        if a.x < 0 or a.y < 0 or a.width <= 0 or a.height <= 0:
            raise ValueError(f"Invalid placement: {a}")
        for b in placements[i + 1 :]:
            if not (a.x2 <= b.x or b.x2 <= a.x or a.y2 <= b.y or b.y2 <= a.y):
                overlap_pairs.append((a.name, b.name))
    placed_area = sum(p.width * p.height for p in placements)
    return {
        "chip": layout.chip,
        "num_blocks": len(placements),
        "duplicate_names": duplicate_names,
        "overlap_count": len(overlap_pairs),
        "overlap_pairs_preview": overlap_pairs[:10],
        "placed_area": placed_area,
        "total_block_area": layout.total_block_area,
        "area_conserved": placed_area == layout.total_block_area,
        "bounding_width": layout.width,
        "bounding_height": layout.height,
        "bounding_area": layout.area,
        "area_lower_bound": layout.area_lower_bound,
        "gap_to_area_lower_bound": layout.area_gap_to_lower_bound,
        "aspect_ratio": layout.aspect_ratio,
        "valid": not duplicate_names and not overlap_pairs and placed_area == layout.total_block_area,
    }


def color_for_name(name: str) -> tuple[int, int, int]:
    digest = hashlib.sha1(name.encode("utf-8")).digest()
    return (80 + digest[0] % 140, 80 + digest[1] % 140, 80 + digest[2] % 140)


def write_layout_csv(layout: Layout, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["block", "x", "y", "width", "height", "rotated", "original_width", "original_height"])
        for p in layout.placements:
            writer.writerow([p.name, p.x, p.y, p.width, p.height, int(p.rotated), p.original_width, p.original_height])


def write_layout_svg(layout: Layout, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pad = max(layout.width, layout.height) * 0.02 + 10
    label_threshold = 130
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {layout.width + 2 * pad} {layout.height + 2 * pad}">',
        '<rect x="0" y="0" width="{0}" height="{1}" fill="white" stroke="#111" stroke-width="2"/>'.format(layout.width, layout.height),
    ]
    for p in layout.placements:
        r, g, b = color_for_name(p.name)
        y_svg = layout.height - p.y - p.height
        parts.append(
            f'<rect x="{p.x}" y="{y_svg}" width="{p.width}" height="{p.height}" '
            f'fill="rgb({r},{g},{b})" fill-opacity="0.72" stroke="#202020" stroke-width="0.6"/>'
        )
        if len(layout.placements) <= label_threshold:
            parts.append(
                f'<text x="{p.x + p.width / 2:.2f}" y="{y_svg + p.height / 2:.2f}" '
                f'font-size="8" text-anchor="middle" dominant-baseline="middle" fill="#111">{p.name}</text>'
            )
    parts.append(
        f'<text x="0" y="{-pad / 3:.2f}" font-size="14" fill="#111">'
        f'{layout.chip}: W={layout.width}, H={layout.height}, Area={layout.area}, '
        f'Aspect={layout.aspect_ratio:.4f}</text>'
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_layout_png(layout: Layout, path: Path) -> None:
    if Image is None or ImageDraw is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    max_pixels = 1800
    margin = 60
    scale = min((max_pixels - 2 * margin) / layout.width, (max_pixels - 2 * margin) / layout.height)
    image_width = int(layout.width * scale + 2 * margin)
    image_height = int(layout.height * scale + 2 * margin)
    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.rectangle(
        [margin, margin, margin + layout.width * scale, margin + layout.height * scale],
        outline=(20, 20, 20),
        width=2,
    )
    for p in layout.placements:
        r, g, b = color_for_name(p.name)
        x1 = margin + p.x * scale
        y1 = margin + (layout.height - p.y - p.height) * scale
        x2 = margin + p.x2 * scale
        y2 = margin + (layout.height - p.y) * scale
        draw.rectangle([x1, y1, x2, y2], fill=(r, g, b), outline=(30, 30, 30), width=1)
        if len(layout.placements) <= 130 and min(p.width * scale, p.height * scale) >= 14:
            draw.text(((x1 + x2) / 2, (y1 + y2) / 2), p.name, fill=(0, 0, 0), anchor="mm", font=font)
    title = f"{layout.chip}: W={layout.width}, H={layout.height}, Area={layout.area}, Aspect={layout.aspect_ratio:.4f}"
    draw.text((margin, 18), title, fill=(0, 0, 0), font=font)
    image.save(path)


def write_summary(layouts: list[Layout], output_dir: Path) -> None:
    summary_path = output_dir / "q1_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "chip",
                "num_blocks",
                "total_block_area",
                "width",
                "height",
                "bounding_area",
                "aspect_ratio_long_over_short",
                "dead_space_area",
                "dead_space_ratio",
                "searched_widths",
                "tried_packings",
                "runtime_sec",
                "heuristic",
            ]
        )
        for layout in layouts:
            writer.writerow(
                [
                    layout.chip,
                    len(layout.placements),
                    layout.total_block_area,
                    layout.width,
                    layout.height,
                    layout.area,
                    f"{layout.aspect_ratio:.8f}",
                    layout.dead_space_area,
                    f"{layout.dead_space_ratio:.8f}",
                    layout.searched_widths,
                    layout.tried_packings,
                    f"{layout.runtime_sec:.4f}",
                    layout.heuristic,
                ]
            )


def write_validation(layouts: list[Layout], output_dir: Path) -> None:
    report = [validate_layout(layout) for layout in layouts]
    (output_dir / "q1_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def solve_all(
    data_dir: Path,
    output_dir: Path,
    chips: list[str],
    use_rectpack: bool = True,
    rectpack_max_blocks: int = 200,
) -> list[Layout]:
    output_dir.mkdir(parents=True, exist_ok=True)
    layouts: list[Layout] = []
    for chip in chips:
        print(f"Solving {chip}...", flush=True)
        blocks_path = data_dir / f"{chip}.blocks"
        layout = solve_chip(chip, blocks_path, use_rectpack=use_rectpack, rectpack_max_blocks=rectpack_max_blocks)
        validation = validate_layout(layout)
        if not validation["valid"]:
            raise RuntimeError(f"Invalid layout for {chip}: {validation}")
        layouts.append(layout)
        write_layout_csv(layout, output_dir / "layouts" / f"{chip}_q1_layout.csv")
        write_layout_svg(layout, output_dir / "figures" / f"{chip}_q1_layout.svg")
        write_layout_png(layout, output_dir / "figures" / f"{chip}_q1_layout.png")
        print(
            f"{chip}: area={layout.area}, W={layout.width}, H={layout.height}, "
            f"aspect={layout.aspect_ratio:.6f}, gap={layout.dead_space_ratio:.6%}, "
            f"tries={layout.tried_packings}, time={layout.runtime_sec:.2f}s"
        )
    write_summary(layouts, output_dir)
    write_validation(layouts, output_dir)
    return layouts


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve Q1 VLSI outline-free floorplanning.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("2026年第七届华数杯数学建模竞赛赛题") / "B题 VLSI布图规划设计" / "附件",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results") / "q1")
    parser.add_argument("--chips", nargs="+", default=["n100", "n200", "n300"])
    parser.add_argument("--no-rectpack", action="store_true", help="Disable optional rectpack enhancement.")
    parser.add_argument(
        "--rectpack-max-blocks",
        type=int,
        default=200,
        help="Use optional rectpack enhancement only when the chip has at most this many hard blocks.",
    )
    args = parser.parse_args()
    solve_all(
        args.data_dir,
        args.output_dir,
        args.chips,
        use_rectpack=not args.no_rectpack,
        rectpack_max_blocks=args.rectpack_max_blocks,
    )


if __name__ == "__main__":
    main()
