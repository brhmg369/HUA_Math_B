"""Redraw Q1 layouts from frozen coordinates without rerunning the solver.

The slender n100/n200 layouts are shown with a true-aspect overview and
equal-height unfolded segments.  The plotting step never changes coordinates
or any numerical result produced by ``q1_floorplanning.py``.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle


PALETTE = ("#4E79A7", "#76B7B2", "#A0A0A0", "#F2CF5B")
CHINESE_FONT = FontProperties(fname=r"C:\Windows\Fonts\msyh.ttc")


def load_layout(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"block", "x", "y", "width", "height"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path} lacks columns: {sorted(missing)}")
    return frame


def dimensions(frame: pd.DataFrame) -> tuple[int, int]:
    width = int((frame["x"] + frame["width"]).max())
    height = int((frame["y"] + frame["height"]).max())
    return width, height


def color_for_index(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def draw_window(
    ax: Axes,
    frame: pd.DataFrame,
    width: int,
    height: int,
    y0: float,
    y1: float,
    *,
    overview: bool = False,
) -> None:
    for index, row in frame.iterrows():
        lower = float(row["y"])
        upper = lower + float(row["height"])
        if upper <= y0 or lower >= y1:
            continue
        ax.add_patch(
            Rectangle(
                (float(row["x"]), lower),
                float(row["width"]),
                float(row["height"]),
                facecolor=color_for_index(int(index)),
                edgecolor="#FFFFFF",
                linewidth=0.35 if overview else 0.55,
            )
        )
    ax.add_patch(
        Rectangle(
            (0, y0),
            width,
            y1 - y0,
            fill=False,
            edgecolor="#303030",
            linewidth=0.9,
        )
    )
    ax.set_xlim(0, width)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def draw_slender_row(
    fig: plt.Figure,
    spec,
    frame: pd.DataFrame,
    chip: str,
    segments: int,
    segment_columns: int = 5,
) -> None:
    width, height = dimensions(frame)
    segment_rows = math.ceil(segments / segment_columns)
    inner = spec.subgridspec(
        segment_rows,
        segment_columns + 1,
        width_ratios=[0.38] + [1.0] * segment_columns,
        wspace=0.16,
        hspace=0.22,
    )

    overview_ax = fig.add_subplot(inner[:, 0])
    draw_window(overview_ax, frame, width, height, 0, height, overview=True)
    overview_ax.set_title(
        f"{chip}  真实比例总览\n{width}×{height}",
        fontsize=9,
        pad=5,
        fontproperties=CHINESE_FONT,
    )

    edges = [height * index / segments for index in range(segments + 1)]
    for index in range(segments):
        row = index // segment_columns
        col = index % segment_columns + 1
        ax = fig.add_subplot(inner[row, col])
        y0, y1 = edges[index], edges[index + 1]
        draw_window(ax, frame, width, height, y0, y1)
        ax.set_title(f"{int(round(y0))}--{int(round(y1))}", fontsize=8, pad=3)

    for index in range(segments, segment_rows * segment_columns):
        row = index // segment_columns
        col = index % segment_columns + 1
        ax = fig.add_subplot(inner[row, col])
        ax.axis("off")


def save_all(fig: plt.Figure, output_stem: Path) -> None:
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(output_stem.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(output_stem.with_suffix(".png"), dpi=450, bbox_inches="tight")


def make_slender_figure(layout_dir: Path, figure_dir: Path) -> None:
    n100 = load_layout(layout_dir / "n100_q1_layout.csv")
    n200 = load_layout(layout_dir / "n200_q1_layout.csv")
    fig = plt.figure(figsize=(7.15, 8.1), constrained_layout=False)
    outer = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.55], hspace=0.24)
    draw_slender_row(fig, outer[0], n100, "n100", segments=5)
    draw_slender_row(fig, outer[1], n200, "n200", segments=10)
    save_all(fig, figure_dir / "q1_slender_overview_segments")
    plt.close(fig)


def make_n300_figure(layout_dir: Path, figure_dir: Path) -> None:
    frame = load_layout(layout_dir / "n300_q1_layout.csv")
    width, height = dimensions(frame)
    fig, ax = plt.subplots(figsize=(6.4, 6.8))
    draw_window(ax, frame, width, height, 0, height)
    ax.set_title(
        f"n300  真实比例总览  {width}×{height}",
        fontsize=10,
        pad=7,
        fontproperties=CHINESE_FONT,
    )
    save_all(fig, figure_dir / "q1_n300_balanced_layout")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Redraw frozen Q1 layout coordinates for the paper.")
    parser.add_argument("--layout-dir", type=Path, default=Path("results/q1/layouts"))
    parser.add_argument("--figure-dir", type=Path, default=Path("results/q1/figures"))
    args = parser.parse_args()
    make_slender_figure(args.layout_dir, args.figure_dir)
    make_n300_figure(args.layout_dir, args.figure_dir)


if __name__ == "__main__":
    main()
