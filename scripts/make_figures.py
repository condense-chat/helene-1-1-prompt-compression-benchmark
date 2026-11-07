#!/usr/bin/env python3
"""Draw the README figures from data/ (run scripts/reproduce.py first for results/)."""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
DATA, RES, ASSETS = ROOT / "data", ROOT / "results", ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

MODELS = ["claude-haiku-4-5", "claude-sonnet-5", "gpt-5.6-luna", "gemini-3.6-flash"]
LANGS = ["EN", "PL", "LV", "FI", "ET", "LT", "UK", "ZH", "AR", "HI"]
LANG_NAMES = {"EN": "English", "PL": "Polish", "LV": "Latvian", "FI": "Finnish", "ET": "Estonian",
              "LT": "Lithuanian", "UK": "Ukrainian", "ZH": "Chinese", "AR": "Arabic", "HI": "Hindi"}
COLORS = {"helene-1.1": "#2563EB", "helene-1": "#93B4F5", "bear-2": "#B07A3B", "kompress-v2": "#6E6E68"}
LABELS = {"helene-1.1": "Helene 1.1", "helene-1": "Helene 1", "bear-2": "bear-2", "kompress-v2": "kompress-v2"}
MARKERS = {"helene-1.1": "o", "helene-1": "o", "bear-2": "s", "kompress-v2": "^"}
INK, MUTED, GRID = "#1F2328", "#656D76", "#E6E8EB"

family = "Inter" if any("Inter" in f.name for f in font_manager.fontManager.ttflist) else "DejaVu Sans"
if family != "Inter":
    print("warning: Inter font not found, using DejaVu Sans; figures will differ slightly from the committed ones")
mpl.rcParams.update({
    "font.family": family, "font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
    "axes.titlesize": 14, "axes.titleweight": "semibold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "axes.titlepad": 14, "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.dpi": 200, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.25, "legend.frameon": False, "legend.fontsize": 10.5,
})


def half_up(x, nd=1):
    """Round half away from zero, matching the published figures (72.85 -> 72.9)."""
    from decimal import Decimal, ROUND_HALF_UP
    return str(Decimal(str(round(x, 6))).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP))


def note(fig, text):
    fig.text(0.0, -0.02, text, ha="left", va="top", fontsize=9, color=MUTED, wrap=True)


def fig_accuracy_vs_keep():
    s = pd.read_csv(RES / "summary_by_band.csv")
    cv = pd.read_csv(RES / "helene_curve.csv")
    h = cv[cv.system == "helene-1.1"].sort_values("keep_rate")
    # the ~0.50 and ~0.75 Helene 1.1 points come from the band runs used for the competitor comparisons
    hb = s[s.system == "helene-1.1"].sort_values("keep_rate")
    helene_pts = pd.concat([h[h.nominal_rate == 0.33][["keep_rate", "accuracy"]], hb[["keep_rate", "accuracy"]]])
    v1 = cv[cv.system == "helene-1"].sort_values("keep_rate")

    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.axvspan(0.28, 0.48, color="#F3F4F6", zorder=0)
    ax.text(0.38, 61.2, "no competitor measured\nin this range", ha="center", va="bottom", fontsize=9, color=MUTED)
    ax.plot(v1.keep_rate, v1.accuracy, "--", color=COLORS["helene-1"], lw=2, marker="o", ms=7, label="Helene 1")
    ax.plot(helene_pts.keep_rate, helene_pts.accuracy, "-", color=COLORS["helene-1.1"], lw=2.6, marker="o", ms=8,
            label="Helene 1.1", zorder=5)
    for sysn in ["bear-2", "kompress-v2"]:
        d = s[s.system == sysn].sort_values("keep_rate")
        ax.plot(d.keep_rate, d.accuracy, "-", color=COLORS[sysn], lw=2, marker=MARKERS[sysn], ms=8, label=LABELS[sysn])
    for _, r in helene_pts.iterrows():
        ax.annotate(half_up(r.accuracy), (r.keep_rate, r.accuracy), textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=9.5, color=COLORS["helene-1.1"], fontweight="semibold")
    ax.set_xlim(0.28, 0.84)
    ax.set_ylim(60, 94)
    ax.set_xlabel("Share of text kept after compression (o200k_base tokens)  →  less compression")
    ax.set_ylabel("Answer accuracy (%)")
    ax.set_title("Accuracy at a given amount of kept text")
    ax.legend(loc="lower right", ncol=2)
    note(fig, "Mean of four answering models, 3,000 items per model per point, ten languages. Higher and further left is better.")
    fig.savefig(ASSETS / "fig1_accuracy_vs_keep.png")
    plt.close(fig)


def fig_by_model():
    m = pd.read_csv(RES / "accuracy_by_model.csv")
    names = {"claude-haiku-4-5": "Claude Haiku 4.5", "claude-sonnet-5": "Claude Sonnet 5",
             "gpt-5.6-luna": "GPT-5.6 Luna", "gemini-3.6-flash": "Gemini 3.6 Flash", "mean of four": "Mean of four"}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    y = np.arange(len(m))[::-1]
    for yi, (_, r) in zip(y, m.iterrows()):
        lo, hi = min(r["bear-2"], r["kompress-v2"], r["helene-1.1"]), r["helene-1.1"]
        ax.plot([lo, hi], [yi, yi], color=GRID, lw=3, zorder=1, solid_capstyle="round")
        for sysn in ["kompress-v2", "bear-2", "helene-1.1"]:
            ax.scatter(r[sysn], yi, s=90 if sysn == "helene-1.1" else 70, color=COLORS[sysn], marker=MARKERS[sysn],
                       zorder=3, label=LABELS[sysn] if yi == y[0] else None)
        ax.text(r["helene-1.1"] + 0.6, yi, f"{r['helene-1.1']:.1f}", va="center", fontsize=10, color=COLORS["helene-1.1"],
                fontweight="semibold")
        ax.text(97.5, yi, f"+{r['margin_vs_bear-2']:.1f}  /  +{r['margin_vs_kompress-v2']:.1f}", va="center", ha="right",
                fontsize=10, color=INK, fontweight="semibold" if r.model == "mean of four" else "normal")
    ax.axhline(0.5, color=GRID, lw=1)
    ax.set_yticks(y, [names[n] for n in m.model])
    for t in ax.get_yticklabels():
        if t.get_text() == "Mean of four":
            t.set_fontweight("semibold"); t.set_color(INK)
    ax.set_xlim(64, 98)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Answer accuracy (%), mean of the ~0.50 and ~0.75 keep bands")
    ax.set_ylim(-0.6, y[0] + 0.9)
    ax.text(97.5, y[0] + 0.55, "lead vs bear-2 / kompress-v2", ha="right", fontsize=9, color=MUTED)
    ax.set_title("Accuracy by answering model, mean of both bands")
    ax.legend(loc="lower left", ncol=3, bbox_to_anchor=(0, -0.32))
    fig.savefig(ASSETS / "fig2_accuracy_by_model.png")
    plt.close(fig)


def fig_keep_by_language():
    k = pd.read_csv(DATA / "keep_rates_by_language.csv")
    by = k[k.band == "~0.50"].pivot(index="system", columns="lang", values="keep_rate")
    fig, ax = plt.subplots(figsize=(9, 4.4))
    order = ["helene-1.1", "kompress-v2", "bear-2"]
    for i, sysn in enumerate(order):
        yv = len(order) - 1 - i
        vals = by.loc[sysn, LANGS]
        ax.plot([vals.min(), vals.max()], [yv, yv], color=COLORS[sysn], alpha=0.35, lw=6, solid_capstyle="round")
        ax.scatter(vals, [yv] * len(vals), color=COLORS[sysn], marker=MARKERS[sysn], s=60, zorder=3,
                   edgecolor="white", linewidth=0.8)
        lo_l, hi_l = vals.idxmin(), vals.idxmax()
        ax.annotate(f"{lo_l} {vals.min():.2f}", (vals.min(), yv), xytext=(0, -17), textcoords="offset points",
                    ha="center", fontsize=9, color=MUTED, bbox=dict(fc="white", ec="none", pad=1))
        ax.annotate(f"{hi_l} {vals.max():.2f}", (vals.max(), yv), xytext=(0, -17), textcoords="offset points",
                    ha="center", fontsize=9, color=MUTED, bbox=dict(fc="white", ec="none", pad=1))
        ax.text(1.03, yv, f"{vals.max() / vals.min():.1f}×", va="center", fontsize=12, fontweight="semibold",
                color=COLORS[sysn], transform=ax.get_yaxis_transform())
    ax.axvline(0.5, ls="--", color=MUTED, lw=1, zorder=0)
    ax.set_yticks(range(len(order)), [LABELS[s] for s in order[::-1]])
    ax.set_ylim(-0.8, len(order) - 0.4)
    ax.set_xlim(0, 1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share of text kept, one dot per language (~0.50 band)")
    ax.set_title("How much text each compressor keeps, by language")
    note(fig, "Helene 1.1 dots follow per-passage token budgets. "
              "kompress-v2 used one keep threshold and bear-2 one aggressiveness level. Ratio = largest / smallest language mean.")
    fig.savefig(ASSETS / "fig3_keep_by_language.png")
    plt.close(fig)


def fig_accuracy_by_language():
    lg = pd.read_csv(RES / "accuracy_by_language.csv")
    lg = lg[lg.band == "~0.50"]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    x = np.arange(len(LANGS))
    w = 0.26
    for i, sysn in enumerate(["helene-1.1", "bear-2", "kompress-v2"]):
        d = lg[lg.system == sysn].set_index("lang").loc[LANGS]
        ax.bar(x + (i - 1) * w, d.accuracy, width=w, color=COLORS[sysn], label=LABELS[sysn])
        for xi, (acc, kr) in enumerate(zip(d.accuracy, d.keep_rate)):
            ax.text(xi + (i - 1) * w, acc + 0.8, f"{kr:.2f}", ha="center", va="bottom", fontsize=7.5,
                    color=COLORS[sysn], rotation=90)
    ax.set_xticks(x, [LANG_NAMES[l] for l in LANGS], rotation=0)
    ax.tick_params(axis="x", labelsize=9.5)
    ax.set_ylim(0, 115)
    ax.set_yticks(range(0, 101, 20))
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Answer accuracy (%)")
    ax.set_title("Accuracy by language, ~0.50 keep band")
    ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.0))
    note(fig, "Mean of four answering models, 300 items per language per model. Small numbers above bars = share of text kept. "
              "bear-2 is ahead where it keeps far more text (for example 0.96 in Chinese).")
    fig.savefig(ASSETS / "fig4_accuracy_by_language.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_accuracy_vs_keep()
    fig_by_model()
    fig_keep_by_language()
    fig_accuracy_by_language()
    print("Figures written to", ASSETS.relative_to(ROOT))
