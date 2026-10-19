"""Matplotlib figures for the app (pure functions: data in, Figure out)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless backend for servers and tests

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from ..calculator import CRSResult, Section

SECTION_COLOURS = {
    Section.CORE: "#1f6f8b",
    Section.SPOUSE: "#99a8b2",
    Section.TRANSFERABILITY: "#e6a400",
    Section.ADDITIONAL: "#b5523b",
    Section.LABOUR_MARKET: "#4a7c59",
}


def _style(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)


def section_bars(result: CRSResult) -> Figure:
    totals = result.section_totals
    fig, ax = plt.subplots(figsize=(7, 3.2))
    labels = [s.value for s in totals]
    values = list(totals.values())
    bars = ax.barh(labels, values, color=[SECTION_COLOURS[s] for s in totals])
    ax.bar_label(bars, padding=3)
    ax.invert_yaxis()
    ax.set_xlabel("CRS points")
    ax.set_title(f"Score by section (total {result.total})", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, max([*values, 1]) * 1.15)
    fig.tight_layout()
    return fig


def french_sweep(df: pd.DataFrame, current_total: int, cutoff: int | None) -> Figure:
    """Stacked section bars per NCLC level, with current score and cut-off lines."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = df["nclc"].to_numpy()
    bottom = np.zeros(len(df))
    for section, colour in SECTION_COLOURS.items():
        if section.value not in df or not df[section.value].any():
            continue
        values = df[section.value].to_numpy()
        ax.bar(x, values, bottom=bottom, color=colour, label=section.value, width=0.7)
        bottom += values
    for xi, total in zip(x, df["total"], strict=True):
        ax.text(xi, total + 6, str(total), ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.axhline(current_total, color="black", linestyle="--", linewidth=1, label=f"Current score ({current_total})")
    if cutoff:
        ax.axhline(cutoff, color="#c0392b", linestyle=":", linewidth=1.5, label=f"Reference cut-off ({cutoff})")
    ax.set_xticks(x, ["< 4" if v == 3 else ("10+" if v == 10 else str(v)) for v in x])
    ax.set_xlabel("French NCLC level (same on all four abilities)")
    ax.set_ylabel("CRS points")
    ax.set_title("Impact of French (NCLC) level on CRS", loc="left")
    ax.set_ylim(0, max(df["total"].max(), cutoff or 0) * 1.12)
    _style(ax)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    fig.tight_layout()
    return fig


def language_heatmap(grid: pd.DataFrame) -> Figure:
    table = grid.pivot(index="french_nclc", columns="english_clb", values="total").sort_index(ascending=False)
    fig, ax = plt.subplots(figsize=(7.5, 5))
    image = ax.imshow(table.to_numpy(), cmap="YlGnBu", aspect="auto")
    ticks = lambda values: ["< 4" if v == 3 else ("10+" if v == 10 else str(v)) for v in values]  # noqa: E731
    ax.set_xticks(range(len(table.columns)), ticks(table.columns))
    ax.set_yticks(range(len(table.index)), ticks(table.index))
    ax.set_xlabel("English CLB (all abilities)")
    ax.set_ylabel("French NCLC (all abilities)")
    ax.set_title("Total CRS by English CLB x French NCLC", loc="left")
    threshold = table.to_numpy().mean()
    for i, row in enumerate(table.to_numpy()):
        for j, value in enumerate(row):
            ax.text(
                j,
                i,
                str(int(value)),
                ha="center",
                va="center",
                fontsize=8,
                color="white" if value > threshold else "black",
            )
    fig.colorbar(image, ax=ax, label="CRS points")
    fig.tight_layout()
    return fig


def factor_line(df: pd.DataFrame, factor: str, current_total: int) -> Figure:
    fig, ax = plt.subplots(figsize=(8, 4))
    labels = [str(v) for v in df["value"]]
    ax.plot(range(len(df)), df["total"], marker="o", color=SECTION_COLOURS[Section.CORE])
    for i, total in enumerate(df["total"]):
        ax.annotate(str(total), (i, total), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    ax.axhline(current_total, color="black", linestyle="--", linewidth=1, label=f"Current score ({current_total})")
    rotate = factor == "Education level"
    ax.set_xticks(
        range(len(df)),
        labels,
        rotation=30 if rotate else 0,
        ha="right" if rotate else "center",
        fontsize=8 if rotate else 9,
    )
    low, high = df["total"].min(), df["total"].max()
    pad = max((high - low) * 0.15, 10)
    ax.set_ylim(low - pad, high + pad)
    ax.set_xlabel(factor)
    ax.set_ylabel("Total CRS points")
    ax.set_title(f"Total CRS as {factor.lower()} changes", loc="left")
    _style(ax)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig
