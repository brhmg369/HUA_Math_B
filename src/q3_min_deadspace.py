"""Q3 minimum-deadspace fixed-outline floorplanning.

Q3 wraps the Q2 solver with an outer integer side-length feasibility search.
Because the outline is a square and all module dimensions are integer, the
dead-space ratio changes only when the square side length changes:

    Gamma(L) = (L^2 - total_block_area) / total_block_area.

The script first proves a lower bound from area, block dimensions and fixed
terminal coordinates, then tries to construct a feasible packing at increasing
integer side lengths. If the lower bound itself is feasible, the minimum side
length is certified under these modelling assumptions.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

from rectpack import (
    MaxRectsBaf,
    MaxRectsBlsf,
    MaxRectsBssf,
    SORT_AREA,
    SORT_LSIDE,
    SORT_RATIO,
    SORT_SSIDE,
    newPacker,
)

from q2_fixed_outline_hpwl import (
    Instance,
    Layout,
    Placement,
    fast_local_refine,
    natural_key,
    quadratic_targets,
    read_instance,
    solve_instance,
    total_hpwl,
    validate_layout,
    write_layout_csv,
    write_png,
    write_svg,
)


@dataclass
class FeasibilityResult:
    chip: str
    side: int
    lower_bound_side: int
    lower_bound_attained: bool
    placements: dict[str, Placement]
    method: str
    search_log: list[dict[str, object]]


def deadspace_ratio(total_area: int, side: int) -> float:
    return (side * side - total_area) / total_area


def set_instance_side(instance: Instance, side: int) -> None:
    instance.side = side
    instance.requested_deadspace = deadspace_ratio(instance.total_block_area, side)


def theoretical_side_lower_bound(instance: Instance) -> tuple[int, dict[str, int]]:
    area_lb = math.ceil(math.sqrt(instance.total_block_area))
    block_lb = max(max(block.width, block.height) for block in instance.blocks)
    terminal_lb = instance.terminal_coordinate_side
    lower = max(area_lb, block_lb, terminal_lb)
    return lower, {
        "area_lower_bound": area_lb,
        "block_side_lower_bound": block_lb,
        "terminal_coordinate_lower_bound": terminal_lb,
    }


def rectpack_variants() -> list[tuple[object, object, str]]:
    algos = [
        (MaxRectsBssf, "MaxRectsBssf"),
        (MaxRectsBaf, "MaxRectsBaf"),
        (MaxRectsBlsf, "MaxRectsBlsf"),
    ]
    sorts = [
        (SORT_AREA, "SORT_AREA"),
        (SORT_LSIDE, "SORT_LSIDE"),
        (SORT_SSIDE, "SORT_SSIDE"),
        (SORT_RATIO, "SORT_RATIO"),
    ]
    return [(algo, sort, f"rectpack:{algo_name}:{sort_name}") for algo, algo_name in algos for sort, sort_name in sorts]


def rectpack_fixed_square(instance: Instance, side: int) -> tuple[dict[str, Placement], str] | None:
    block_by_name = {block.name: block for block in instance.blocks}
    for pack_algo, sort_algo, method in rectpack_variants():
        packer = newPacker(pack_algo=pack_algo, sort_algo=sort_algo, rotation=True)
        for block in instance.blocks:
            packer.add_rect(block.width, block.height, block.name)
        packer.add_bin(side, side)
        packer.pack()
        if len(packer.rect_list()) != len(instance.blocks):
            continue
        placements: dict[str, Placement] = {}
        for _, x, y, width, height, rid in packer.rect_list():
            name = str(rid)
            block = block_by_name[name]
            placements[name] = Placement(
                name=name,
                x=int(x),
                y=int(y),
                width=int(width),
                height=int(height),
                original_width=block.width,
                original_height=block.height,
            )
        return placements, method
    return None


def terminal_bounds_report(instance: Instance) -> dict[str, object]:
    outside = [
        terminal.name
        for terminal in instance.terminals.values()
        if terminal.x < 0 or terminal.y < 0 or terminal.x > instance.side or terminal.y > instance.side
    ]
    return {
        "terminal_out_of_bounds_count": len(outside),
        "terminal_out_of_bounds_preview": sorted(outside, key=natural_key)[:10],
    }


def find_minimum_feasible_side(instance: Instance, upper_side: int) -> FeasibilityResult:
    lower_side, lower_terms = theoretical_side_lower_bound(instance)
    search_log: list[dict[str, object]] = []
    if lower_side > upper_side:
        raise ValueError(f"Lower bound {lower_side} exceeds upper side {upper_side} for {instance.chip}")

    for side in range(lower_side, upper_side + 1):
        start = time.perf_counter()
        set_instance_side(instance, side)
        packed = rectpack_fixed_square(instance, side)
        runtime = time.perf_counter() - start
        row = {
            "chip": instance.chip,
            "side": side,
            **lower_terms,
            "deadspace_ratio": deadspace_ratio(instance.total_block_area, side),
            "feasible": packed is not None,
            "method": packed[1] if packed else "",
            "runtime_sec": f"{runtime:.4f}",
        }
        search_log.append(row)
        if packed is None:
            continue
        placements, method = packed
        return FeasibilityResult(
            chip=instance.chip,
            side=side,
            lower_bound_side=lower_side,
            lower_bound_attained=side == lower_side,
            placements=placements,
            method=method,
            search_log=search_log,
        )
    raise RuntimeError(f"No feasible packing found for {instance.chip} up to side={upper_side}")


def rectpack_layout_as_q2_layout(instance: Instance, placements: dict[str, Placement], method: str, start: float) -> Layout:
    targets = quadratic_targets(instance)
    refined, passes, accepted = fast_local_refine(instance, placements, targets, max_passes=2)
    hpwl = total_hpwl(instance, refined)
    initial_hpwl = total_hpwl(instance, placements)
    return Layout(
        chip=instance.chip,
        placements=refined,
        hpwl=hpwl,
        side=instance.side,
        total_block_area=instance.total_block_area,
        requested_deadspace=instance.requested_deadspace,
        actual_deadspace_ratio=instance.actual_deadspace_ratio,
        method=method,
        refinement_method="fast_hpwl_breakpoint",
        initial_hpwl=initial_hpwl,
        improvement_passes=passes,
        accepted_moves=accepted,
        runtime_sec=time.perf_counter() - start,
    )


def solve_hpwl_at_min_side(
    instance: Instance,
    feasibility: FeasibilityResult,
    refine_passes: int,
    refine_top: int,
    refine_method: str,
) -> tuple[Layout, list[dict[str, object]]]:
    start = time.perf_counter()
    try:
        layout, candidate_rows = solve_instance(
            instance,
            refine_passes=refine_passes,
            refine_top=refine_top,
            refine_method=refine_method,
        )
    except Exception as exc:
        layout = rectpack_layout_as_q2_layout(
            instance,
            feasibility.placements,
            f"{feasibility.method}:fallback",
            start,
        )
        candidate_rows = [
            {
                "chip": instance.chip,
                "method": layout.method,
                "feasible": True,
                "initial_hpwl": f"{layout.initial_hpwl:.4f}",
                "refined_hpwl": f"{layout.hpwl:.4f}",
                "accepted_moves": layout.accepted_moves,
                "refine_passes": layout.improvement_passes,
                "refine_method": layout.refinement_method,
                "runtime_sec": f"{layout.runtime_sec:.4f}",
                "fallback_reason": str(exc),
            }
        ]
    return layout, candidate_rows


def read_q2_summary(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", newline="", encoding="utf-8") as f:
        return {row["chip"]: row for row in csv.DictReader(f)}


def write_summary(
    layouts: list[Layout],
    feasibility_results: list[FeasibilityResult],
    q2_rows: dict[str, dict[str, str]],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "chip",
        "total_block_area",
        "area_lower_bound",
        "block_side_lower_bound",
        "terminal_coordinate_lower_bound",
        "lower_bound_side",
        "min_feasible_side",
        "lower_bound_attained",
        "min_deadspace_ratio",
        "q2_side_at_0_15",
        "q2_hpwl_at_0_15",
        "q3_hpwl_at_min_deadspace",
        "hpwl_change_vs_q2",
        "hpwl_change_ratio_vs_q2",
        "method",
        "refinement_method",
        "refine_passes",
        "accepted_moves",
        "runtime_sec",
    ]
    feasibility_by_chip = {item.chip: item for item in feasibility_results}
    first_log_by_chip = {item.chip: item.search_log[0] for item in feasibility_results}
    with (output_dir / "q3_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for layout in layouts:
            feasibility = feasibility_by_chip[layout.chip]
            lower_terms = first_log_by_chip[layout.chip]
            q2 = q2_rows.get(layout.chip, {})
            q2_hpwl = float(q2["hpwl"]) if q2.get("hpwl") else float("nan")
            q2_side = q2.get("side", "")
            delta = layout.hpwl - q2_hpwl if q2.get("hpwl") else float("nan")
            ratio = delta / q2_hpwl if q2.get("hpwl") and q2_hpwl else float("nan")
            writer.writerow(
                {
                    "chip": layout.chip,
                    "total_block_area": layout.total_block_area,
                    "area_lower_bound": lower_terms["area_lower_bound"],
                    "block_side_lower_bound": lower_terms["block_side_lower_bound"],
                    "terminal_coordinate_lower_bound": lower_terms["terminal_coordinate_lower_bound"],
                    "lower_bound_side": feasibility.lower_bound_side,
                    "min_feasible_side": layout.side,
                    "lower_bound_attained": feasibility.lower_bound_attained,
                    "min_deadspace_ratio": f"{layout.actual_deadspace_ratio:.8f}",
                    "q2_side_at_0_15": q2_side,
                    "q2_hpwl_at_0_15": q2.get("hpwl", ""),
                    "q3_hpwl_at_min_deadspace": f"{layout.hpwl:.4f}",
                    "hpwl_change_vs_q2": "" if math.isnan(delta) else f"{delta:.4f}",
                    "hpwl_change_ratio_vs_q2": "" if math.isnan(ratio) else f"{ratio:.8f}",
                    "method": layout.method,
                    "refinement_method": layout.refinement_method,
                    "refine_passes": layout.improvement_passes,
                    "accepted_moves": layout.accepted_moves,
                    "runtime_sec": f"{layout.runtime_sec:.4f}",
                }
            )


def write_search_log(feasibility_results: list[FeasibilityResult], output_dir: Path) -> None:
    rows: list[dict[str, object]] = []
    for result in feasibility_results:
        rows.extend(result.search_log)
    fields = [
        "chip",
        "side",
        "area_lower_bound",
        "block_side_lower_bound",
        "terminal_coordinate_lower_bound",
        "deadspace_ratio",
        "feasible",
        "method",
        "runtime_sec",
    ]
    with (output_dir / "q3_feasibility_log.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_candidate_rows(rows: list[dict[str, object]], output_dir: Path) -> None:
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
        "fallback_reason",
    ]
    with (output_dir / "q3_candidate_runs.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def solve_all(
    data_dir: Path,
    output_dir: Path,
    chips: list[str],
    q2_summary_path: Path,
    refine_passes: int,
    refine_top: int,
    refine_method: str,
) -> list[Layout]:
    output_dir.mkdir(parents=True, exist_ok=True)
    q2_rows = read_q2_summary(q2_summary_path)
    layouts: list[Layout] = []
    feasibility_results: list[FeasibilityResult] = []
    validations: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []

    for chip in chips:
        print(f"Solving {chip} Q3...", flush=True)
        q2_instance = read_instance(data_dir, chip, 0.15)
        upper_side = q2_instance.side
        feasibility_instance = read_instance(data_dir, chip, 0.15)
        feasibility = find_minimum_feasible_side(feasibility_instance, upper_side)
        hpwl_instance = read_instance(data_dir, chip, 0.15)
        set_instance_side(hpwl_instance, feasibility.side)
        layout, rows = solve_hpwl_at_min_side(
            hpwl_instance,
            feasibility,
            refine_passes=refine_passes,
            refine_top=refine_top,
            refine_method=refine_method,
        )
        validation = validate_layout(hpwl_instance, layout)
        validation.update(terminal_bounds_report(hpwl_instance))
        validation["lower_bound_side"] = feasibility.lower_bound_side
        validation["lower_bound_attained"] = feasibility.lower_bound_attained
        validation["valid"] = validation["valid"] and validation["terminal_out_of_bounds_count"] == 0
        if not validation["valid"]:
            raise RuntimeError(f"Invalid Q3 layout for {chip}: {validation}")

        layouts.append(layout)
        feasibility_results.append(feasibility)
        validations.append(validation)
        candidate_rows.extend(rows)

        write_layout_csv(layout, output_dir / "layouts" / f"{chip}_q3_layout.csv")
        write_svg(hpwl_instance, layout, output_dir / "figures" / f"{chip}_q3_layout.svg")
        write_png(hpwl_instance, layout, output_dir / "figures" / f"{chip}_q3_layout.png")
        print(
            f"{chip}: L_min={layout.side}, gamma={layout.actual_deadspace_ratio:.6%}, "
            f"HPWL={layout.hpwl:.2f}, method={layout.method}, time={layout.runtime_sec:.2f}s",
            flush=True,
        )

    write_summary(layouts, feasibility_results, q2_rows, output_dir)
    write_search_log(feasibility_results, output_dir)
    write_candidate_rows(candidate_rows, output_dir)
    (output_dir / "q3_validation.json").write_text(json.dumps(validations, ensure_ascii=False, indent=2), encoding="utf-8")
    return layouts


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve Q3 minimum-deadspace fixed-outline floorplanning.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("2026年第七届华数杯数学建模竞赛赛题") / "B题 VLSI布图规划设计" / "附件",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results") / "q3")
    parser.add_argument("--chips", nargs="+", default=["n100", "n200", "n300"])
    parser.add_argument("--q2-summary", type=Path, default=Path("results") / "q2" / "q2_summary.csv")
    parser.add_argument("--refine-passes", type=int, default=2)
    parser.add_argument("--refine-top", type=int, default=3)
    parser.add_argument("--refine-method", choices=["fast", "exact", "mixed"], default="fast")
    args = parser.parse_args()
    solve_all(
        args.data_dir,
        args.output_dir,
        args.chips,
        args.q2_summary,
        args.refine_passes,
        args.refine_top,
        args.refine_method,
    )


if __name__ == "__main__":
    main()
