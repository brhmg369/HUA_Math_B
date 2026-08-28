"""Generate the Q2-to-Q3 dead-space/HPWL trade-off slope chart."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results" / "q3" / "q3_summary.csv"
OUTPUT_DIR = ROOT / "results" / "q3" / "figures"


def main() -> None:
    data = pd.read_csv(SUMMARY)
    data["q2_deadspace_pct"] = 15.0
    data["q3_deadspace_pct"] = 100.0 * data["min_deadspace_ratio"]
    data["q2_hpwl_index"] = 100.0
    data["q3_hpwl_index"] = 100.0 * (
        data["q3_hpwl_at_min_deadspace"] / data["q2_hpwl_at_0_15"]
    )

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 9,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 8.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    colors = ["#0072B2", "#E69F00", "#009E73"]
    markers = ["o", "s", "^"]
    offsets = [-0.035, 0.0, 0.035]
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.35))

    for idx, row in data.iterrows():
        x = [offsets[idx], 1.0 + offsets[idx]]
        common = dict(
            color=colors[idx],
            marker=markers[idx],
            linewidth=1.8,
            markersize=6.2,
            markeredgecolor="white",
            markeredgewidth=0.7,
            label=row["chip"],
            zorder=3,
        )
        axes[0].plot(
            x,
            [row["q2_deadspace_pct"], row["q3_deadspace_pct"]],
            **common,
        )
        axes[1].plot(
            x,
            [row["q2_hpwl_index"], row["q3_hpwl_index"]],
            **common,
        )

        axes[0].annotate(
            f'{row["q3_deadspace_pct"]:.4f}%',
            (x[1], row["q3_deadspace_pct"]),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            color=colors[idx],
            fontsize=8.2,
        )
        axes[1].annotate(
            f'+{row["hpwl_change_ratio_vs_q2"] * 100:.2f}%',
            (x[1], row["q3_hpwl_index"]),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            color=colors[idx],
            fontsize=8.2,
        )

    axes[0].set_ylabel("死区率 / %")
    axes[0].set_ylim(4.2, 16.2)
    axes[0].set_yticks([5, 7.5, 10, 12.5, 15])
    axes[0].text(
        0.03,
        0.06,
        "轮廓利用率提高",
        transform=axes[0].transAxes,
        color="#4D4D4D",
        fontsize=8.5,
    )

    axes[1].set_ylabel("HPWL 指数（问题二 = 100）")
    axes[1].set_ylim(98.5, 116.2)
    axes[1].set_yticks([100, 105, 110, 115])
    axes[1].text(
        0.03,
        0.91,
        "互连代价上升",
        transform=axes[1].transAxes,
        color="#4D4D4D",
        fontsize=8.5,
    )

    for ax, panel in zip(axes, ["(a) 死区率压缩", "(b) HPWL 代价"]):
        ax.set_xlim(-0.14, 1.24)
        ax.set_xticks([0, 1], ["问题二", "问题三"])
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.6, alpha=0.7)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#777777")
        ax.spines["bottom"].set_color("#777777")
        ax.set_title(panel, fontsize=10, pad=7)

    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=3,
        frameon=False,
        handlelength=2.2,
    )
    fig.subplots_adjust(left=0.09, right=0.94, bottom=0.18, top=0.79, wspace=0.34)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = OUTPUT_DIR / "q3_tradeoff_q2_q3"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), dpi=400, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
