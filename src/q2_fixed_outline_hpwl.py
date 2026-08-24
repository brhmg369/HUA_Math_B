"""Q2 fixed-outline HPWL floorplanning solver.

The model keeps the Q2 hard constraints explicit: every hard block is a
rotatable rectangle, all blocks must lie inside a fixed square outline, and
the objective is total HPWL over block centres and fixed terminals.

The implementation uses a two-stage deterministic heuristic:

1. a quadratic wirelength relaxation gives each block a target centre;
2. target-guided MaxRects legalisation plus one-block reinsertion reduces HPWL
   without using a spatial grid step.

The output is a checked feasible upper bound, not a proof of global optimality.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - visualisation remains optional
    Image = None
    ImageDraw = None
    ImageFont = None


@dataclass(frozen=True)
class Block:
    name: str
    width: int
    height: int
    index: int

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass(frozen=True)
class Terminal:
    name: str
    x: float
    y: float


@dataclass(frozen=True)
class Net:
    pins: tuple[str, ...]


@dataclass(frozen=True)
class Rect:
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

    @property
    def area(self) -> int:
        return self.width * self.height


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
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2

    @property
    def rotated(self) -> bool:
        return self.width == self.original_height and self.height == self.original_width


@dataclass
class Instance:
    chip: str
    blocks: list[Block]
    terminals: dict[str, Terminal]
    nets: list[Net]
    side: int
    requested_deadspace: float
    nets_by_block: list[list[int]]
    block_index: dict[str, int]
    terminal_coordinate_side: int

    @property
    def total_block_area(self) -> int:
        return sum(block.area for block in self.blocks)

    @property
    def outline_area(self) -> int:
        return self.side * self.side

    @property
    def actual_deadspace_ratio(self) -> float:
        return (self.outline_area - self.total_block_area) / self.total_block_area


@dataclass
class Layout:
    chip: str
    placements: dict[str, Placement]
    hpwl: float
    side: int
    total_block_area: int
    requested_deadspace: float
    actual_deadspace_ratio: float
    method: str
    refinement_method: str
    initial_hpwl: float
    improvement_passes: int
    accepted_moves: int
    runtime_sec: float


def natural_key(text: str) -> tuple[str, int]:
    match = re.match(r"([A-Za-z_]+)(\d+)$", text)
    if match:
        return (match.group(1), int(match.group(2)))
    return (text, -1)


def parse_blocks(path: Path) -> tuple[list[Block], list[str]]:
    blocks: list[Block] = []
    terminals: list[str] = []
    point_pattern = re.compile(r"\((\d+),\s*(\d+)\)")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if " block " in line:
            points = [tuple(map(int, p)) for p in point_pattern.findall(line)]
            if len(points) != 4:
                raise ValueError(f"Expected four points in block line: {line}")
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            width = max(xs) - min(xs)
            height = max(ys) - min(ys)
            blocks.append(Block(line.split()[0], width, height, len(blocks)))
        elif line.endswith(" terminal"):
            terminals.append(line.split()[0])
    return blocks, terminals


def parse_terminals(path: Path) -> dict[str, Terminal]:
    terminals: dict[str, Terminal] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parts = raw_line.split()
        if len(parts) < 3:
            continue
        terminals[parts[0]] = Terminal(parts[0], float(parts[1]), float(parts[2]))
    return terminals


def parse_nets(path: Path) -> list[Net]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    nets: list[Net] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("Num"):
            i += 1
            continue
        if not line.startswith("NetDegree"):
            raise ValueError(f"Unexpected line in netlist {path}: {line}")
        degree = int(line.split(":", 1)[1])
        pins = tuple(lines[i + 1 : i + 1 + degree])
        if len(pins) != degree:
            raise ValueError(f"Truncated net in {path}: {line}")
        nets.append(Net(pins))
        i += degree + 1
    return nets


def read_instance(data_dir: Path, chip: str, deadspace_ratio: float) -> Instance:
    blocks, terminal_names = parse_blocks(data_dir / f"{chip}.blocks")
    terminals = parse_terminals(data_dir / f"{chip}.pl")
    nets = parse_nets(data_dir / f"{chip}.nets")
    missing_terminals = sorted(set(terminal_names) - set(terminals), key=natural_key)
    if missing_terminals:
        raise ValueError(f"{chip} has terminals without coordinates: {missing_terminals[:8]}")
    block_index = {block.name: block.index for block in blocks}
    nets_by_block = [[] for _ in blocks]
    for net_id, net in enumerate(nets):
        for pin in net.pins:
            if pin in block_index:
                nets_by_block[block_index[pin]].append(net_id)
            elif pin not in terminals:
                raise ValueError(f"{chip} net pin {pin} is neither block nor terminal")
    total_area = sum(block.area for block in blocks)
    side = math.ceil(math.sqrt(total_area * (1.0 + deadspace_ratio)))
    terminal_side = int(max(max(t.x, t.y) for t in terminals.values())) if terminals else side
    max_block_side = max(max(block.width, block.height) for block in blocks)
    if max_block_side > side:
        raise ValueError(f"{chip} has a block side {max_block_side} larger than outline side {side}")
    return Instance(chip, blocks, terminals, nets, side, deadspace_ratio, nets_by_block, block_index, terminal_side)


def orientation_options(block: Block, side: int) -> list[tuple[int, int]]:
    options = {(block.width, block.height), (block.height, block.width)}
    return sorted((w, h) for w, h in options if w <= side and h <= side)


def overlaps_rect(a: Rect | Placement, b: Rect | Placement) -> bool:
    return not (a.x2 <= b.x or b.x2 <= a.x or a.y2 <= b.y or b.y2 <= a.y)


def contains_rect(a: Rect, b: Rect) -> bool:
    return a.x <= b.x and a.y <= b.y and a.x2 >= b.x2 and a.y2 >= b.y2


def split_free_rect(free: Rect, placed: Placement) -> list[Rect]:
    if not overlaps_rect(free, placed):
        return [free]
    pieces: list[Rect] = []
    if placed.x > free.x:
        pieces.append(Rect(free.x, free.y, placed.x - free.x, free.height))
    if placed.x2 < free.x2:
        pieces.append(Rect(placed.x2, free.y, free.x2 - placed.x2, free.height))
    if placed.y > free.y:
        pieces.append(Rect(free.x, free.y, free.width, placed.y - free.y))
    if placed.y2 < free.y2:
        pieces.append(Rect(free.x, placed.y2, free.width, free.y2 - placed.y2))
    return [rect for rect in pieces if rect.width > 0 and rect.height > 0]


def prune_free_rects(free_rects: list[Rect]) -> list[Rect]:
    unique = list(dict.fromkeys(free_rects))
    keep: list[Rect] = []
    for i, rect in enumerate(unique):
        dominated = False
        for j, other in enumerate(unique):
            if i != j and contains_rect(other, rect):
                dominated = True
                break
        if not dominated:
            keep.append(rect)
    return sorted(keep, key=lambda r: (r.y, r.x, r.width * r.height, r.width, r.height))


def update_free_rects(free_rects: list[Rect], placed: Placement) -> list[Rect]:
    updated: list[Rect] = []
    for free in free_rects:
        updated.extend(split_free_rect(free, placed))
    return prune_free_rects(updated)


def centers_for_layout(placements: dict[str, Placement], terminals: dict[str, Terminal]) -> dict[str, tuple[float, float]]:
    coords = {name: (terminal.x, terminal.y) for name, terminal in terminals.items()}
    for name, placement in placements.items():
        coords[name] = (placement.cx, placement.cy)
    return coords


def hpwl_from_coords(nets: Iterable[Net], coords: dict[str, tuple[float, float]]) -> float:
    total = 0.0
    for net in nets:
        xs: list[float] = []
        ys: list[float] = []
        for pin in net.pins:
            x, y = coords[pin]
            xs.append(x)
            ys.append(y)
        total += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return total


def total_hpwl(instance: Instance, placements: dict[str, Placement]) -> float:
    return hpwl_from_coords(instance.nets, centers_for_layout(placements, instance.terminals))


def net_hpwl_with_candidate(
    instance: Instance,
    net_id: int,
    placements: dict[str, Placement],
    candidate: Placement | None = None,
    require_all_blocks: bool = True,
) -> float:
    net = instance.nets[net_id]
    xs: list[float] = []
    ys: list[float] = []
    for pin in net.pins:
        if candidate is not None and pin == candidate.name:
            xs.append(candidate.cx)
            ys.append(candidate.cy)
        elif pin in instance.terminals:
            terminal = instance.terminals[pin]
            xs.append(terminal.x)
            ys.append(terminal.y)
        elif pin in placements:
            placement = placements[pin]
            xs.append(placement.cx)
            ys.append(placement.cy)
        elif require_all_blocks:
            return 0.0
    if len(xs) < 2:
        return 0.0
    return (max(xs) - min(xs)) + (max(ys) - min(ys))


def quadratic_targets(instance: Instance) -> dict[str, tuple[float, float]]:
    n = len(instance.blocks)
    q = np.zeros((n, n), dtype=float)
    bx = np.zeros(n, dtype=float)
    by = np.zeros(n, dtype=float)

    for net in instance.nets:
        pins = net.pins
        if len(pins) < 2:
            continue
        weight = 1.0 / (len(pins) - 1)
        for i in range(len(pins)):
            for j in range(i + 1, len(pins)):
                a = pins[i]
                b = pins[j]
                a_block = instance.block_index.get(a)
                b_block = instance.block_index.get(b)
                if a_block is not None and b_block is not None:
                    q[a_block, a_block] += weight
                    q[b_block, b_block] += weight
                    q[a_block, b_block] -= weight
                    q[b_block, a_block] -= weight
                elif a_block is not None and b in instance.terminals:
                    t = instance.terminals[b]
                    q[a_block, a_block] += weight
                    bx[a_block] += weight * t.x
                    by[a_block] += weight * t.y
                elif b_block is not None and a in instance.terminals:
                    t = instance.terminals[a]
                    q[b_block, b_block] += weight
                    bx[b_block] += weight * t.x
                    by[b_block] += weight * t.y

    for i in range(n):
        if q[i, i] == 0:
            q[i, i] = 1.0
            bx[i] = instance.side / 2
            by[i] = instance.side / 2

    try:
        xs = np.linalg.solve(q, bx)
        ys = np.linalg.solve(q, by)
    except np.linalg.LinAlgError:
        positive_diag = q.diagonal()[q.diagonal() > 0]
        scale = float(positive_diag.mean()) if positive_diag.size else 1.0
        stable_q = q + np.eye(n) * scale * 1e-10
        xs = np.linalg.lstsq(stable_q, bx, rcond=None)[0]
        ys = np.linalg.lstsq(stable_q, by, rcond=None)[0]

    out: dict[str, tuple[float, float]] = {}
    for block, x, y in zip(instance.blocks, xs, ys):
        out[block.name] = (float(np.clip(x, 0, instance.side)), float(np.clip(y, 0, instance.side)))
    return out


def block_degrees(instance: Instance) -> dict[str, float]:
    degrees: dict[str, float] = {block.name: 0.0 for block in instance.blocks}
    for net in instance.nets:
        if len(net.pins) < 2:
            continue
        weight = 1.0 / (len(net.pins) - 1)
        for pin in net.pins:
            if pin in degrees:
                degrees[pin] += weight
    return degrees


def median_or_value(values: list[float], default: float) -> float:
    if not values:
        return default
    return float(statistics.median(values))


def integer_positions_from_centres(centres: Iterable[float], low: int, high: int, size: int) -> set[int]:
    positions: set[int] = {low, high}
    for centre in centres:
        left = centre - size / 2
        for value in (math.floor(left), math.ceil(left)):
            positions.add(max(low, min(high, int(value))))
    return positions


def candidate_positions(
    instance: Instance,
    block: Block,
    width: int,
    height: int,
    free: Rect,
    placements: dict[str, Placement],
    targets: dict[str, tuple[float, float]],
    current: Placement | None = None,
) -> Iterable[tuple[int, int]]:
    x_low = free.x
    x_high = free.x2 - width
    y_low = free.y
    y_high = free.y2 - height
    if x_high < x_low or y_high < y_low:
        return []

    target_x, target_y = targets[block.name]
    centre_x_values = [target_x, free.x + free.width / 2]
    centre_y_values = [target_y, free.y + free.height / 2]
    if current is not None:
        centre_x_values.append(current.cx)
        centre_y_values.append(current.cy)

    fixed_pin_x: list[float] = []
    fixed_pin_y: list[float] = []
    for net_id in instance.nets_by_block[block.index]:
        for pin in instance.nets[net_id].pins:
            if pin == block.name:
                continue
            if pin in instance.terminals:
                terminal = instance.terminals[pin]
                fixed_pin_x.append(terminal.x)
                fixed_pin_y.append(terminal.y)
            elif pin in placements:
                placement = placements[pin]
                fixed_pin_x.append(placement.cx)
                fixed_pin_y.append(placement.cy)
    centre_x_values.extend(fixed_pin_x)
    centre_y_values.extend(fixed_pin_y)
    centre_x_values.append(median_or_value(fixed_pin_x, target_x))
    centre_y_values.append(median_or_value(fixed_pin_y, target_y))

    xs = integer_positions_from_centres(centre_x_values, x_low, x_high, width)
    ys = integer_positions_from_centres(centre_y_values, y_low, y_high, height)
    return ((x, y) for x in xs for y in ys)


def insertion_score(
    instance: Instance,
    block: Block,
    placement: Placement,
    free: Rect,
    placements: dict[str, Placement],
    targets: dict[str, tuple[float, float]],
    mode: str,
    exact: bool = False,
    old_contribution: float = 0.0,
) -> tuple[float, ...]:
    local_hpwl = 0.0
    for net_id in instance.nets_by_block[block.index]:
        local_hpwl += net_hpwl_with_candidate(
            instance,
            net_id,
            placements,
            candidate=placement,
            require_all_blocks=exact,
        )
    target_x, target_y = targets[block.name]
    target_distance = abs(placement.cx - target_x) + abs(placement.cy - target_y)
    area_fit = free.area - placement.width * placement.height
    short_fit = min(free.width - placement.width, free.height - placement.height)
    long_fit = max(free.width - placement.width, free.height - placement.height)
    rotation_flag = int(placement.rotated)
    exact_delta = local_hpwl - old_contribution
    if exact:
        return (exact_delta, target_distance, area_fit, short_fit, long_fit, placement.y, placement.x, rotation_flag)
    if mode == "target":
        return (target_distance, local_hpwl, area_fit, short_fit, long_fit, placement.y, placement.x, rotation_flag)
    if mode == "fit":
        return (area_fit, short_fit, target_distance, local_hpwl, long_fit, placement.y, placement.x, rotation_flag)
    return (local_hpwl, target_distance, area_fit, short_fit, long_fit, placement.y, placement.x, rotation_flag)


def choose_insertion(
    instance: Instance,
    block: Block,
    free_rects: list[Rect],
    placements: dict[str, Placement],
    targets: dict[str, tuple[float, float]],
    mode: str,
    current: Placement | None = None,
    exact: bool = False,
    old_contribution: float = 0.0,
) -> Placement | None:
    best: tuple[tuple[float, ...], Placement] | None = None
    for width, height in orientation_options(block, instance.side):
        for free in free_rects:
            if width > free.width or height > free.height:
                continue
            for x, y in candidate_positions(instance, block, width, height, free, placements, targets, current):
                candidate = Placement(block.name, x, y, width, height, block.width, block.height)
                score = insertion_score(
                    instance,
                    block,
                    candidate,
                    free,
                    placements,
                    targets,
                    mode,
                    exact=exact,
                    old_contribution=old_contribution,
                )
                if best is None or score < best[0]:
                    best = (score, candidate)
    return None if best is None else best[1]


def construct_layout(
    instance: Instance,
    order: list[Block],
    targets: dict[str, tuple[float, float]],
    mode: str,
) -> dict[str, Placement] | None:
    free_rects = [Rect(0, 0, instance.side, instance.side)]
    placements: dict[str, Placement] = {}
    for block in order:
        placement = choose_insertion(instance, block, free_rects, placements, targets, mode)
        if placement is None:
            return None
        placements[block.name] = placement
        free_rects = update_free_rects(free_rects, placement)
    return placements


def choose_shelf_orientation(block: Block, policy: str) -> tuple[int, int]:
    options = sorted({(block.width, block.height), (block.height, block.width)})
    if policy == "wide":
        return max(options, key=lambda item: (item[0], -item[1]))
    if policy == "native":
        return (block.width, block.height)
    return min(options, key=lambda item: (item[0], item[1]))


def projected_row_y(rows: list[dict[str, object]], side: int) -> list[int]:
    desired = [float(row["desired_y"]) for row in rows]
    heights = [int(row["height"]) for row in rows]
    if not rows:
        return []

    ys = [round(value) for value in desired]
    ys[0] = max(0, ys[0])
    for i in range(1, len(rows)):
        ys[i] = max(ys[i], ys[i - 1] + heights[i - 1])
    ys[-1] = min(ys[-1], side - heights[-1])
    for i in range(len(rows) - 2, -1, -1):
        ys[i] = min(ys[i], ys[i + 1] - heights[i])
    shift = -min(0, min(ys))
    ys = [value + shift for value in ys]
    overflow = max(0, ys[-1] + heights[-1] - side)
    if overflow:
        ys = [value - overflow for value in ys]
    return ys


def construct_shelf_layout(
    instance: Instance,
    order: list[Block],
    targets: dict[str, tuple[float, float]],
    orientation_policy: str,
) -> dict[str, Placement] | None:
    rows: list[dict[str, object]] = []
    current: list[tuple[Block, int, int]] = []
    used_width = 0
    row_height = 0

    for block in order:
        width, height = choose_shelf_orientation(block, orientation_policy)
        if width > instance.side or height > instance.side:
            return None
        if current and used_width + width > instance.side:
            rows.append({"items": current, "height": row_height})
            current = []
            used_width = 0
            row_height = 0
        current.append((block, width, height))
        used_width += width
        row_height = max(row_height, height)
    if current:
        rows.append({"items": current, "height": row_height})

    if sum(int(row["height"]) for row in rows) > instance.side:
        return None

    rows.sort(
        key=lambda row: median_or_value(
            [targets[item[0].name][1] for item in row["items"]], instance.side / 2
        )
    )
    for row in rows:
        row["items"] = sorted(row["items"], key=lambda item: (targets[item[0].name][0], item[0].index))
        row["desired_y"] = median_or_value(
            [targets[item[0].name][1] - int(row["height"]) / 2 for item in row["items"]],
            instance.side / 2 - int(row["height"]) / 2,
        )

    y_values = projected_row_y(rows, instance.side)
    placements: dict[str, Placement] = {}
    for row, y in zip(rows, y_values):
        items = list(row["items"])
        width_sum = sum(width for _, width, _ in items)
        slack = instance.side - width_sum
        base_positions: list[int] = []
        x = 0
        for _, width, _ in items:
            base_positions.append(x)
            x += width
        desired_offsets = [
            targets[block.name][0] - (base_x + width / 2) for base_x, (block, width, _) in zip(base_positions, items)
        ]
        offset = int(round(max(0, min(slack, median_or_value(desired_offsets, 0.0)))))
        for base_x, (block, width, height) in zip(base_positions, items):
            placements[block.name] = Placement(
                block.name,
                offset + base_x,
                y,
                width,
                height,
                block.width,
                block.height,
            )
    return placements


def build_placements_from_rows(
    instance: Instance,
    rows: list[dict[str, object]],
    targets: dict[str, tuple[float, float]],
) -> dict[str, Placement]:
    rows.sort(
        key=lambda row: median_or_value(
            [targets[item[0].name][1] for item in row["items"]], instance.side / 2
        )
    )
    for row in rows:
        row["items"] = sorted(row["items"], key=lambda item: (targets[item[0].name][0], item[0].index))
        row["desired_y"] = median_or_value(
            [targets[item[0].name][1] - int(row["height"]) / 2 for item in row["items"]],
            instance.side / 2 - int(row["height"]) / 2,
        )

    y_values = projected_row_y(rows, instance.side)
    placements: dict[str, Placement] = {}
    for row, y in zip(rows, y_values):
        items = list(row["items"])
        width_sum = sum(width for _, width, _ in items)
        slack = instance.side - width_sum
        base_positions: list[int] = []
        x = 0
        for _, width, _ in items:
            base_positions.append(x)
            x += width
        desired_offsets = [
            targets[block.name][0] - (base_x + width / 2) for base_x, (block, width, _) in zip(base_positions, items)
        ]
        offset = int(round(max(0, min(slack, median_or_value(desired_offsets, 0.0)))))
        for base_x, (block, width, height) in zip(base_positions, items):
            placements[block.name] = Placement(
                block.name,
                offset + base_x,
                y,
                width,
                height,
                block.width,
                block.height,
            )
    return placements


def construct_best_fit_shelf_layout(
    instance: Instance,
    targets: dict[str, tuple[float, float]],
    orientation_policy: str,
) -> dict[str, Placement] | None:
    oriented: list[tuple[Block, int, int]] = []
    for block in instance.blocks:
        width, height = choose_shelf_orientation(block, orientation_policy)
        if width > instance.side or height > instance.side:
            return None
        oriented.append((block, width, height))

    rows: list[dict[str, object]] = []
    for block, width, height in sorted(oriented, key=lambda item: (-item[2], -item[1] * item[2], item[0].index)):
        best_row: tuple[tuple[float, int, float, int], int] | None = None
        target_y = targets[block.name][1]
        for row_id, row in enumerate(rows):
            used_width = int(row["used_width"])
            if used_width + width > instance.side:
                continue
            old_height = int(row["height"])
            height_increase = max(0, height - old_height)
            new_remaining = instance.side - used_width - width
            row_target_y = median_or_value(
                [targets[item[0].name][1] for item in row["items"]], instance.side / 2
            )
            score = (height_increase, new_remaining, abs(target_y - row_target_y), row_id)
            if best_row is None or score < best_row[0]:
                best_row = (score, row_id)
        if best_row is None:
            rows.append({"items": [(block, width, height)], "height": height, "used_width": width})
        else:
            row = rows[best_row[1]]
            row["items"].append((block, width, height))
            row["height"] = max(int(row["height"]), height)
            row["used_width"] = int(row["used_width"]) + width

    if sum(int(row["height"]) for row in rows) > instance.side:
        return None
    return build_placements_from_rows(instance, rows, targets)


def free_rects_against_fixed(instance: Instance, fixed: dict[str, Placement]) -> list[Rect]:
    free_rects = [Rect(0, 0, instance.side, instance.side)]
    for placement in sorted(fixed.values(), key=lambda p: (p.y, p.x, p.name)):
        free_rects = update_free_rects(free_rects, placement)
    return free_rects


def block_hpwl_contribution(instance: Instance, block: Block, placements: dict[str, Placement]) -> float:
    return sum(net_hpwl_with_candidate(instance, net_id, placements, require_all_blocks=True) for net_id in instance.nets_by_block[block.index])


def local_refine(
    instance: Instance,
    placements: dict[str, Placement],
    targets: dict[str, tuple[float, float]],
    max_passes: int,
) -> tuple[dict[str, Placement], int, int]:
    current = dict(placements)
    accepted_moves = 0
    completed_passes = 0
    block_by_name = {block.name: block for block in instance.blocks}

    while completed_passes < max_passes:
        completed_passes += 1
        improved_this_pass = False
        order = sorted(
            instance.blocks,
            key=lambda b: (-block_hpwl_contribution(instance, b, current), -b.area, natural_key(b.name)),
        )
        for block in order:
            old = current[block.name]
            fixed = dict(current)
            del fixed[block.name]
            free_rects = free_rects_against_fixed(instance, fixed)
            old_contribution = block_hpwl_contribution(instance, block, current)
            candidate = choose_insertion(
                instance,
                block,
                free_rects,
                fixed,
                targets,
                mode="wire",
                current=old,
                exact=True,
                old_contribution=old_contribution,
            )
            if candidate is None:
                continue
            new_contribution = block_hpwl_contribution(instance, block, {**fixed, block.name: candidate})
            if new_contribution + 1e-9 < old_contribution:
                current[block.name] = candidate
                accepted_moves += 1
                improved_this_pass = True
        if not improved_this_pass:
            break
        # Keep a stable dictionary with valid block objects looked up once.
        current = {name: current[name] for name in sorted(current, key=lambda n: natural_key(block_by_name[n].name))}
    return current, completed_passes, accepted_moves


def relevant_centre_values(
    instance: Instance,
    block: Block,
    fixed: dict[str, Placement],
    current: Placement,
    targets: dict[str, tuple[float, float]],
) -> tuple[list[float], list[float]]:
    target_x, target_y = targets[block.name]
    xs = [target_x, current.cx, instance.side / 2]
    ys = [target_y, current.cy, instance.side / 2]
    fixed_pin_x: list[float] = []
    fixed_pin_y: list[float] = []
    for net_id in instance.nets_by_block[block.index]:
        for pin in instance.nets[net_id].pins:
            if pin == block.name:
                continue
            if pin in instance.terminals:
                terminal = instance.terminals[pin]
                fixed_pin_x.append(terminal.x)
                fixed_pin_y.append(terminal.y)
            elif pin in fixed:
                placement = fixed[pin]
                fixed_pin_x.append(placement.cx)
                fixed_pin_y.append(placement.cy)
    xs.extend(fixed_pin_x)
    ys.extend(fixed_pin_y)
    xs.append(median_or_value(fixed_pin_x, target_x))
    ys.append(median_or_value(fixed_pin_y, target_y))
    return xs, ys


def has_no_overlap(candidate: Placement, fixed: dict[str, Placement]) -> bool:
    return all(not overlaps_rect(candidate, other) for other in fixed.values())


def fast_local_refine(
    instance: Instance,
    placements: dict[str, Placement],
    targets: dict[str, tuple[float, float]],
    max_passes: int,
) -> tuple[dict[str, Placement], int, int]:
    current = dict(placements)
    accepted_moves = 0
    completed_passes = 0

    while completed_passes < max_passes:
        completed_passes += 1
        improved_this_pass = False
        order = sorted(
            instance.blocks,
            key=lambda b: (-block_hpwl_contribution(instance, b, current), -b.area, natural_key(b.name)),
        )
        for block in order:
            old = current[block.name]
            fixed = dict(current)
            del fixed[block.name]
            old_contribution = block_hpwl_contribution(instance, block, current)
            centre_x_values, centre_y_values = relevant_centre_values(instance, block, fixed, old, targets)
            best: tuple[tuple[float, ...], Placement] | None = None
            for width, height in orientation_options(block, instance.side):
                xs = integer_positions_from_centres(centre_x_values, 0, instance.side - width, width)
                ys = integer_positions_from_centres(centre_y_values, 0, instance.side - height, height)
                for x in xs:
                    for y in ys:
                        candidate = Placement(block.name, x, y, width, height, block.width, block.height)
                        if not has_no_overlap(candidate, fixed):
                            continue
                        new_contribution = block_hpwl_contribution(instance, block, {**fixed, block.name: candidate})
                        target_x, target_y = targets[block.name]
                        target_distance = abs(candidate.cx - target_x) + abs(candidate.cy - target_y)
                        score = (new_contribution - old_contribution, target_distance, y, x, int(candidate.rotated))
                        if best is None or score < best[0]:
                            best = (score, candidate)
            if best is not None and best[0][0] < -1e-9:
                current[block.name] = best[1]
                accepted_moves += 1
                improved_this_pass = True
        if not improved_this_pass:
            break
    return current, completed_passes, accepted_moves


def order_variants(instance: Instance, targets: dict[str, tuple[float, float]]) -> dict[str, list[Block]]:
    degrees = block_degrees(instance)
    blocks = instance.blocks
    side = instance.side

    def xy_key(block: Block) -> tuple[float, float, int]:
        x, y = targets[block.name]
        return (x, y, block.index)

    def yx_key(block: Block) -> tuple[float, float, int]:
        x, y = targets[block.name]
        return (y, x, block.index)

    def serpentine_x(block: Block) -> tuple[int, float, float, int]:
        x, y = targets[block.name]
        band = int(4 * y / max(side, 1))
        x_key = x if band % 2 == 0 else -x
        return (band, x_key, y, block.index)

    def serpentine_y(block: Block) -> tuple[int, float, float, int]:
        x, y = targets[block.name]
        band = int(4 * x / max(side, 1))
        y_key = y if band % 2 == 0 else -y
        return (band, y_key, x, block.index)

    def centrality(block: Block) -> tuple[float, float, int]:
        x, y = targets[block.name]
        return (abs(x - side / 2) + abs(y - side / 2), -degrees[block.name], block.index)

    def perimeter_first(block: Block) -> tuple[float, float, int]:
        x, y = targets[block.name]
        return (min(x, y, side - x, side - y), -degrees[block.name], block.index)

    raw: dict[str, list[Block]] = {
        "degree_area": sorted(blocks, key=lambda b: (-degrees[b.name], -b.area, natural_key(b.name))),
        "area_degree": sorted(blocks, key=lambda b: (-b.area, -degrees[b.name], natural_key(b.name))),
        "max_side": sorted(blocks, key=lambda b: (-max(b.width, b.height), -b.area, natural_key(b.name))),
        "target_xy": sorted(blocks, key=xy_key),
        "target_yx": sorted(blocks, key=yx_key),
        "serpentine_x": sorted(blocks, key=serpentine_x),
        "serpentine_y": sorted(blocks, key=serpentine_y),
        "centre_first": sorted(blocks, key=centrality),
        "perimeter_first": sorted(blocks, key=perimeter_first),
    }
    raw["degree_area_rev"] = list(reversed(raw["degree_area"]))
    raw["target_xy_rev"] = list(reversed(raw["target_xy"]))
    return raw


def selected_refiner(instance: Instance, refine_method: str):
    if refine_method == "exact" or (refine_method == "mixed" and len(instance.blocks) <= 100):
        return "exact_maxrect_reinsert", local_refine
    return "fast_hpwl_breakpoint", fast_local_refine


def solve_instance(
    instance: Instance,
    refine_passes: int,
    refine_top: int,
    refine_method: str,
) -> tuple[Layout, list[dict[str, object]]]:
    start = time.perf_counter()
    targets = quadratic_targets(instance)
    candidates: list[tuple[str, dict[str, Placement], float, int, int]] = []
    candidate_rows: list[dict[str, object]] = []

    orders = order_variants(instance, targets)
    for policy in ("narrow", "wide", "native"):
        method = f"shelf_bfd:{policy}"
        candidate_start = time.perf_counter()
        placements = construct_best_fit_shelf_layout(instance, targets, policy)
        if placements is None:
            candidate_rows.append(
                {
                    "chip": instance.chip,
                    "method": method,
                    "feasible": False,
                    "initial_hpwl": "",
                    "refined_hpwl": "",
                    "accepted_moves": 0,
                    "refine_method": "",
                    "runtime_sec": f"{time.perf_counter() - candidate_start:.4f}",
                }
            )
            continue
        initial_hpwl = total_hpwl(instance, placements)
        refined_hpwl = initial_hpwl
        candidates.append((method, placements, initial_hpwl, 0, 0))
        candidate_rows.append(
            {
                "chip": instance.chip,
                "method": method,
                "feasible": True,
                "initial_hpwl": f"{initial_hpwl:.4f}",
                "refined_hpwl": f"{refined_hpwl:.4f}",
                "accepted_moves": 0,
                "refine_passes": 0,
                "refine_method": "none",
                "runtime_sec": f"{time.perf_counter() - candidate_start:.4f}",
            }
        )

    for order_name, order in orders.items():
        for policy in ("narrow", "wide", "native"):
            method = f"shelf:{order_name}+{policy}"
            candidate_start = time.perf_counter()
            placements = construct_shelf_layout(instance, order, targets, policy)
            if placements is None:
                candidate_rows.append(
                    {
                        "chip": instance.chip,
                        "method": method,
                        "feasible": False,
                        "initial_hpwl": "",
                        "refined_hpwl": "",
                        "accepted_moves": 0,
                        "refine_method": "",
                        "runtime_sec": f"{time.perf_counter() - candidate_start:.4f}",
                    }
                )
                continue
            initial_hpwl = total_hpwl(instance, placements)
            refined_hpwl = initial_hpwl
            candidates.append((method, placements, initial_hpwl, 0, 0))
            candidate_rows.append(
                {
                    "chip": instance.chip,
                    "method": method,
                    "feasible": True,
                    "initial_hpwl": f"{initial_hpwl:.4f}",
                    "refined_hpwl": f"{refined_hpwl:.4f}",
                    "accepted_moves": 0,
                    "refine_passes": 0,
                    "refine_method": "none",
                    "runtime_sec": f"{time.perf_counter() - candidate_start:.4f}",
                }
            )

    maxrect_order_names = ("degree_area", "area_degree", "target_xy", "target_yx")
    for order_name in maxrect_order_names:
        order = orders[order_name]
        for mode in ("wire", "target", "fit"):
            method = f"maxrects:{order_name}+{mode}"
            candidate_start = time.perf_counter()
            placements = construct_layout(instance, order, targets, mode)
            if placements is None:
                candidate_rows.append(
                    {
                        "chip": instance.chip,
                        "method": method,
                        "feasible": False,
                        "initial_hpwl": "",
                        "refined_hpwl": "",
                        "accepted_moves": 0,
                        "refine_method": "",
                        "runtime_sec": f"{time.perf_counter() - candidate_start:.4f}",
                    }
                )
                continue
            initial_hpwl = total_hpwl(instance, placements)
            refined_hpwl = initial_hpwl
            candidates.append((method, placements, initial_hpwl, 0, 0))
            candidate_rows.append(
                {
                    "chip": instance.chip,
                    "method": method,
                    "feasible": True,
                    "initial_hpwl": f"{initial_hpwl:.4f}",
                    "refined_hpwl": f"{refined_hpwl:.4f}",
                    "accepted_moves": 0,
                    "refine_passes": 0,
                    "refine_method": "none",
                    "runtime_sec": f"{time.perf_counter() - candidate_start:.4f}",
                }
            )

    if not candidates:
        raise RuntimeError(f"No feasible Q2 placement found for {instance.chip}")

    if refine_passes > 0 and refine_top > 0:
        refiner_name, refiner = selected_refiner(instance, refine_method)
        selected = {
            method
            for method, _, _, _, _ in sorted(
                candidates, key=lambda item: total_hpwl(instance, item[1])
            )[:refine_top]
        }
        updated_candidates: list[tuple[str, dict[str, Placement], float, int, int]] = []
        for method, placements, initial_hpwl, passes, accepted in candidates:
            if method not in selected:
                updated_candidates.append((method, placements, initial_hpwl, passes, accepted))
                continue
            refine_start = time.perf_counter()
            refined, passes, accepted = refiner(instance, placements, targets, refine_passes)
            refined_hpwl = total_hpwl(instance, refined)
            updated_candidates.append((method, refined, initial_hpwl, passes, accepted))
            for row in candidate_rows:
                if row["method"] == method:
                    row["refined_hpwl"] = f"{refined_hpwl:.4f}"
                    row["accepted_moves"] = accepted
                    row["refine_passes"] = passes
                    row["refine_method"] = refiner_name
                    row["runtime_sec"] = f"{float(row['runtime_sec']) + time.perf_counter() - refine_start:.4f}"
                    break
        candidates = updated_candidates

    best_method, best_placements, best_initial, best_passes, best_accepted = min(
        candidates, key=lambda item: total_hpwl(instance, item[1])
    )
    best_refinement = "none"
    for row in candidate_rows:
        if row["method"] == best_method:
            best_refinement = str(row.get("refine_method", "none"))
            break
    hpwl = total_hpwl(instance, best_placements)
    layout = Layout(
        chip=instance.chip,
        placements=best_placements,
        hpwl=hpwl,
        side=instance.side,
        total_block_area=instance.total_block_area,
        requested_deadspace=instance.requested_deadspace,
        actual_deadspace_ratio=instance.actual_deadspace_ratio,
        method=best_method,
        refinement_method=best_refinement,
        initial_hpwl=best_initial,
        improvement_passes=best_passes,
        accepted_moves=best_accepted,
        runtime_sec=time.perf_counter() - start,
    )
    return layout, candidate_rows


def validate_layout(instance: Instance, layout: Layout) -> dict[str, object]:
    placements = layout.placements
    names = list(placements)
    duplicate_names = sorted({name for name in names if names.count(name) > 1}, key=natural_key)
    missing_blocks = sorted(set(instance.block_index) - set(placements), key=natural_key)
    extra_blocks = sorted(set(placements) - set(instance.block_index), key=natural_key)
    out_of_bounds: list[str] = []
    overlap_pairs: list[tuple[str, str]] = []
    ordered = [placements[name] for name in sorted(placements, key=natural_key)]
    for i, a in enumerate(ordered):
        if a.x < 0 or a.y < 0 or a.x2 > instance.side or a.y2 > instance.side:
            out_of_bounds.append(a.name)
        for b in ordered[i + 1 :]:
            if overlaps_rect(a, b):
                overlap_pairs.append((a.name, b.name))
    placed_area = sum(p.width * p.height for p in placements.values())
    recomputed_hpwl = total_hpwl(instance, placements)
    return {
        "chip": instance.chip,
        "num_blocks": len(placements),
        "num_terminals": len(instance.terminals),
        "num_nets": len(instance.nets),
        "num_pins": sum(len(net.pins) for net in instance.nets),
        "side": instance.side,
        "outline_area": instance.outline_area,
        "total_block_area": instance.total_block_area,
        "requested_deadspace_ratio": instance.requested_deadspace,
        "actual_deadspace_ratio": instance.actual_deadspace_ratio,
        "terminal_coordinate_side": instance.terminal_coordinate_side,
        "duplicate_names": duplicate_names,
        "missing_blocks": missing_blocks,
        "extra_blocks": extra_blocks,
        "out_of_bounds_count": len(out_of_bounds),
        "out_of_bounds_preview": out_of_bounds[:10],
        "overlap_count": len(overlap_pairs),
        "overlap_pairs_preview": overlap_pairs[:10],
        "placed_area": placed_area,
        "area_conserved": placed_area == instance.total_block_area,
        "hpwl": layout.hpwl,
        "recomputed_hpwl": recomputed_hpwl,
        "hpwl_consistent": abs(layout.hpwl - recomputed_hpwl) < 1e-7,
        "valid": (
            not duplicate_names
            and not missing_blocks
            and not extra_blocks
            and not out_of_bounds
            and not overlap_pairs
            and placed_area == instance.total_block_area
            and abs(layout.hpwl - recomputed_hpwl) < 1e-7
        ),
    }


def color_for_name(name: str) -> tuple[int, int, int]:
    digest = hashlib.sha1(name.encode("utf-8")).digest()
    return (70 + digest[0] % 150, 70 + digest[1] % 150, 70 + digest[2] % 150)


def top_net_boxes(instance: Instance, placements: dict[str, Placement], limit: int = 18) -> list[tuple[float, float, float, float, float]]:
    coords = centers_for_layout(placements, instance.terminals)
    boxes: list[tuple[float, float, float, float, float]] = []
    for net in instance.nets:
        xs = [coords[pin][0] for pin in net.pins]
        ys = [coords[pin][1] for pin in net.pins]
        hpwl = (max(xs) - min(xs)) + (max(ys) - min(ys))
        boxes.append((hpwl, min(xs), min(ys), max(xs), max(ys)))
    return sorted(boxes, reverse=True)[:limit]


def write_layout_csv(layout: Layout, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["block", "x", "y", "width", "height", "rotated", "original_width", "original_height"])
        for name in sorted(layout.placements, key=natural_key):
            p = layout.placements[name]
            writer.writerow([p.name, p.x, p.y, p.width, p.height, int(p.rotated), p.original_width, p.original_height])


def write_candidate_rows(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "chip",
        "method",
        "feasible",
        "initial_hpwl",
        "refined_hpwl",
        "accepted_moves",
        "refine_passes",
        "refine_method",
        "runtime_sec",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary(layouts: list[Layout], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "chip",
                "num_blocks",
                "total_block_area",
                "side",
                "outline_area",
                "requested_deadspace_ratio",
                "actual_deadspace_ratio",
                "hpwl",
                "initial_hpwl_of_selected_method",
                "relative_improvement_after_refine",
                "method",
                "refinement_method",
                "refine_passes_budget",
                "accepted_moves_selected_method",
                "runtime_sec",
            ]
        )
        for layout in layouts:
            improvement = (layout.initial_hpwl - layout.hpwl) / layout.initial_hpwl if layout.initial_hpwl else 0.0
            writer.writerow(
                [
                    layout.chip,
                    len(layout.placements),
                    layout.total_block_area,
                    layout.side,
                    layout.side * layout.side,
                    f"{layout.requested_deadspace:.6f}",
                    f"{layout.actual_deadspace_ratio:.8f}",
                    f"{layout.hpwl:.4f}",
                    f"{layout.initial_hpwl:.4f}",
                    f"{improvement:.8f}",
                    layout.method,
                    layout.refinement_method,
                    layout.improvement_passes,
                    layout.accepted_moves,
                    f"{layout.runtime_sec:.4f}",
                ]
            )


def write_svg(instance: Instance, layout: Layout, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pad = max(24.0, instance.side * 0.035)
    view = f"{-pad} {-pad} {instance.side + 2 * pad} {instance.side + 2 * pad}"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}">',
        f'<rect x="0" y="0" width="{instance.side}" height="{instance.side}" fill="white" stroke="#111" stroke-width="2"/>',
    ]
    for terminal in instance.terminals.values():
        y_svg = instance.side - terminal.y
        parts.append(f'<circle cx="{terminal.x:.2f}" cy="{y_svg:.2f}" r="1.2" fill="#111" opacity="0.75"/>')
    for hpwl, x1, y1, x2, y2 in top_net_boxes(instance, layout.placements):
        parts.append(
            f'<rect x="{x1:.2f}" y="{instance.side - y2:.2f}" width="{x2 - x1:.2f}" height="{y2 - y1:.2f}" '
            f'fill="none" stroke="#d94841" stroke-width="0.6" opacity="0.32"/>'
        )
    for p in sorted(layout.placements.values(), key=lambda item: natural_key(item.name)):
        r, g, b = color_for_name(p.name)
        y_svg = instance.side - p.y - p.height
        parts.append(
            f'<rect x="{p.x}" y="{y_svg}" width="{p.width}" height="{p.height}" '
            f'fill="rgb({r},{g},{b})" fill-opacity="0.72" stroke="#222" stroke-width="0.45"/>'
        )
        if len(layout.placements) <= 130 and min(p.width, p.height) >= 14:
            parts.append(
                f'<text x="{p.x + p.width / 2:.2f}" y="{y_svg + p.height / 2:.2f}" '
                f'font-size="7" text-anchor="middle" dominant-baseline="middle" fill="#111">{p.name}</text>'
            )
    parts.append(
        f'<text x="0" y="{-pad / 2:.2f}" font-size="12" fill="#111">'
        f'{layout.chip}: L={instance.side}, HPWL={layout.hpwl:.2f}, deadspace={layout.actual_deadspace_ratio:.4f}</text>'
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_png(instance: Instance, layout: Layout, path: Path) -> None:
    if Image is None or ImageDraw is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    max_pixels = 1800
    margin = 70
    scale = (max_pixels - 2 * margin) / instance.side
    image_size = int(instance.side * scale + 2 * margin)
    image = Image.new("RGB", (image_size, image_size), "white")
    draw = ImageDraw.Draw(image, "RGBA")
    font = ImageFont.load_default()
    draw.rectangle(
        [margin, margin, margin + instance.side * scale, margin + instance.side * scale],
        outline=(20, 20, 20, 255),
        width=2,
    )
    for hpwl, x1, y1, x2, y2 in top_net_boxes(instance, layout.placements):
        draw.rectangle(
            [
                margin + x1 * scale,
                margin + (instance.side - y2) * scale,
                margin + x2 * scale,
                margin + (instance.side - y1) * scale,
            ],
            outline=(217, 72, 65, 90),
            width=1,
        )
    for p in sorted(layout.placements.values(), key=lambda item: natural_key(item.name)):
        r, g, b = color_for_name(p.name)
        x1 = margin + p.x * scale
        y1 = margin + (instance.side - p.y - p.height) * scale
        x2 = margin + p.x2 * scale
        y2 = margin + (instance.side - p.y) * scale
        draw.rectangle([x1, y1, x2, y2], fill=(r, g, b, 184), outline=(25, 25, 25, 255), width=1)
        if len(layout.placements) <= 130 and min(p.width * scale, p.height * scale) >= 15:
            draw.text(((x1 + x2) / 2, (y1 + y2) / 2), p.name, fill=(0, 0, 0, 255), anchor="mm", font=font)
    for terminal in instance.terminals.values():
        x = margin + terminal.x * scale
        y = margin + (instance.side - terminal.y) * scale
        draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(20, 20, 20, 190))
    title = f"{layout.chip}: L={instance.side}, HPWL={layout.hpwl:.2f}, deadspace={layout.actual_deadspace_ratio:.4f}"
    draw.text((margin, 22), title, fill=(0, 0, 0, 255), font=font)
    image.save(path)


def solve_all(
    data_dir: Path,
    output_dir: Path,
    chips: list[str],
    deadspace_ratio: float,
    refine_passes: int,
    refine_top: int,
    refine_method: str,
) -> list[Layout]:
    output_dir.mkdir(parents=True, exist_ok=True)
    layouts: list[Layout] = []
    all_validation: list[dict[str, object]] = []
    all_candidates: list[dict[str, object]] = []
    for chip in chips:
        print(f"Solving {chip} Q2...", flush=True)
        instance = read_instance(data_dir, chip, deadspace_ratio)
        layout, candidate_rows = solve_instance(
            instance,
            refine_passes=refine_passes,
            refine_top=refine_top,
            refine_method=refine_method,
        )
        validation = validate_layout(instance, layout)
        if not validation["valid"]:
            raise RuntimeError(f"Invalid Q2 layout for {chip}: {validation}")
        layouts.append(layout)
        all_validation.append(validation)
        all_candidates.extend(candidate_rows)
        write_layout_csv(layout, output_dir / "layouts" / f"{chip}_q2_layout.csv")
        write_svg(instance, layout, output_dir / "figures" / f"{chip}_q2_layout.svg")
        write_png(instance, layout, output_dir / "figures" / f"{chip}_q2_layout.png")
        print(
            f"{chip}: L={layout.side}, hpwl={layout.hpwl:.2f}, "
            f"deadspace={layout.actual_deadspace_ratio:.4%}, method={layout.method}, "
            f"time={layout.runtime_sec:.2f}s",
            flush=True,
        )
    write_summary(layouts, output_dir / "q2_summary.csv")
    write_candidate_rows(all_candidates, output_dir / "q2_candidate_runs.csv")
    (output_dir / "q2_validation.json").write_text(json.dumps(all_validation, ensure_ascii=False, indent=2), encoding="utf-8")
    return layouts


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve Q2 fixed-outline HPWL floorplanning.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("2026年第七届华数杯数学建模竞赛赛题") / "B题 VLSI布图规划设计" / "附件",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results") / "q2")
    parser.add_argument("--chips", nargs="+", default=["n100", "n200", "n300"])
    parser.add_argument("--deadspace-ratio", type=float, default=0.15)
    parser.add_argument(
        "--refine-passes",
        type=int,
        default=1,
        help="One-block reinsertion passes. Candidate coordinates are exact; this is only a runtime budget.",
    )
    parser.add_argument(
        "--refine-top",
        type=int,
        default=3,
        help="Refine only the best initial candidates by HPWL; 0 disables the expensive refinement stage.",
    )
    parser.add_argument(
        "--refine-method",
        choices=["fast", "exact", "mixed"],
        default="mixed",
        help="Local refinement. mixed uses exact reinsertion for n<=100 and faster HPWL breakpoints for larger chips.",
    )
    args = parser.parse_args()
    solve_all(
        args.data_dir,
        args.output_dir,
        args.chips,
        args.deadspace_ratio,
        args.refine_passes,
        args.refine_top,
        args.refine_method,
    )


if __name__ == "__main__":
    main()
