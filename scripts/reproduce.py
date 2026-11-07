#!/usr/bin/env python3
"""Rebuild every number in the Helene 1.1 benchmark write-up from the per-item data.

Usage:
    python scripts/reproduce.py            # writes results/ and checks the published numbers

No API keys, no model calls. Everything is computed from the files in data/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)

SEED = 20261107
N_BOOT = 2000
MODELS = ["claude-haiku-4-5", "claude-sonnet-5", "gpt-5.6-luna", "gemini-3.6-flash"]
COMPETITORS = ["bear-2", "kompress-v2"]
LANGS = ["EN", "PL", "LV", "FI", "ET", "LT", "UK", "ZH", "AR", "HI"]


def passage_of(item_id: str) -> str:
    return item_id.rsplit("#", 1)[0]


def load(name: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / name)
    df["passage"] = df["item_id"].map(passage_of)
    return df


def wide(df: pd.DataFrame, value: str) -> pd.DataFrame:
    """Rows: (item_id, lang); columns: (system, model)."""
    return df.pivot_table(index=["item_id", "lang"], columns=["system", "model"], values=value, aggfunc="first")


def band_summary(df: pd.DataFrame, band: str, keep: pd.DataFrame, exclude: set | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if exclude:
        df = df[~df.set_index(["item_id", "lang"]).index.isin(exclude)]
    acc = wide(df, "correct")
    # every language has 300 items, so the band keep rate is the mean of the ten language means
    band_keep = keep[keep.band == band].groupby("system").keep_rate.mean()
    passages = np.array([passage_of(i) for i, _ in acc.index])
    uniq, cluster = np.unique(passages, return_inverse=True)
    rng = np.random.default_rng(SEED)
    boot_clusters = rng.integers(0, len(uniq), size=(N_BOOT, len(uniq)))

    rows, margins = [], []
    helene_unit = acc["helene-1.1"][MODELS].mean(axis=1).to_numpy()
    for system in ["helene-1.1"] + COMPETITORS:
        unit_acc = acc[system][MODELS].mean(axis=1).to_numpy()
        rows.append(dict(band=band, system=system,
                         accuracy=100 * unit_acc.mean(),
                         keep_rate=band_keep[system]))
        if system == "helene-1.1":
            continue
        diff = helene_unit - unit_acc
        # cluster (passage) bootstrap: resample passages, keep all their items and languages
        sums = np.bincount(cluster, weights=diff, minlength=len(uniq))
        counts = np.bincount(cluster, minlength=len(uniq))
        boot = sums[boot_clusters].sum(axis=1) / counts[boot_clusters].sum(axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        margins.append(dict(band=band, competitor=system,
                            helene_keep=band_keep["helene-1.1"],
                            competitor_keep=band_keep[system],
                            margin_points=100 * diff.mean(), ci95_low=100 * lo, ci95_high=100 * hi))
    return pd.DataFrame(rows), pd.DataFrame(margins)


def per_model(b50: pd.DataFrame, b75: pd.DataFrame) -> pd.DataFrame:
    out = []
    for m in MODELS:
        row = {"model": m}
        for system in ["helene-1.1"] + COMPETITORS:
            a50 = b50[(b50.model == m) & (b50.system == system)].correct.mean()
            a75 = b75[(b75.model == m) & (b75.system == system)].correct.mean()
            row[system] = 100 * (a50 + a75) / 2
        for c in COMPETITORS:
            row[f"margin_vs_{c}"] = row["helene-1.1"] - row[c]
        out.append(row)
    df = pd.DataFrame(out)
    mean = {"model": "mean of four", **{c: df[c].mean() for c in df.columns if c != "model"}}
    return pd.concat([df, pd.DataFrame([mean])], ignore_index=True)


def per_language(df: pd.DataFrame, band: str, keep: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["system", "lang"]).agg(accuracy=("correct", "mean")).reset_index()
    g["accuracy"] *= 100
    g = g.merge(keep[keep.band == band][["system", "lang", "keep_rate"]], on=["system", "lang"])
    g.insert(0, "band", band)
    g["lang"] = pd.Categorical(g["lang"], LANGS, ordered=True)
    return g.sort_values(["system", "lang"])


def curve(summary: pd.DataFrame) -> pd.DataFrame:
    """Helene 1 vs Helene 1.1: mean of the four answering models (each model scored 3,000 items)."""
    return summary.groupby(["system", "nominal_rate"]).agg(accuracy=("accuracy", "mean"), keep_rate=("keep_rate", "mean")).reset_index()


def keep_by_language(keep: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Mean share of text kept per language (~0.50 band). Each benchmark item weighs once."""
    by_lang = keep[keep.band == "~0.50"].pivot(index="lang", columns="system", values="keep_rate")
    by_lang = by_lang.reindex(LANGS)
    spread = {s: round(float(by_lang[s].max() / by_lang[s].min()), 2) for s in by_lang.columns}
    return by_lang.round(3).reset_index(), spread


def md_table(df: pd.DataFrame, floatfmt: str = "{:.2f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = [floatfmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in r]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> int:
    b50, b75 = load("accuracy_band50.csv"), load("accuracy_band75.csv")
    cur = pd.read_csv(DATA / "helene_curve_summary.csv")
    keep = pd.read_csv(DATA / "keep_rates_by_language.csv")
    contam = json.loads((DATA / "contamination_flagged_items.json").read_text())
    fidelity_reported = json.loads((DATA / "helene_budget_fidelity_reported.json").read_text())
    flagged = {(i, "EN") for i in contam["flagged_items"]}

    s50, m50 = band_summary(b50, "~0.50", keep)
    s75, m75 = band_summary(b75, "~0.75", keep)
    _, m50x = band_summary(b50, "~0.50", keep, exclude=flagged)
    _, m75x = band_summary(b75, "~0.75", keep, exclude=flagged)
    summary = pd.concat([s50, s75], ignore_index=True)
    margins = pd.concat([m50, m75], ignore_index=True)
    margins_clean = pd.concat([m50x, m75x], ignore_index=True)
    models = per_model(b50, b75)
    langs = pd.concat([per_language(b50, "~0.50", keep), per_language(b75, "~0.75", keep)], ignore_index=True)
    cv = curve(cur)
    keep_table, spread = keep_by_language(keep)
    unparsed = pd.concat([b50.assign(band="~0.50"), b75.assign(band="~0.75")]).assign(unparsed=lambda d: 1 - d.parsed) \
        .groupby(["band", "system"]).unparsed.sum().reset_index()

    summary.to_csv(OUT / "summary_by_band.csv", index=False)
    margins.to_csv(OUT / "margins_with_ci.csv", index=False)
    margins_clean.to_csv(OUT / "margins_excluding_flagged_items.csv", index=False)
    models.to_csv(OUT / "accuracy_by_model.csv", index=False)
    langs.to_csv(OUT / "accuracy_by_language.csv", index=False)
    cv.to_csv(OUT / "helene_curve.csv", index=False)
    keep_table.to_csv(OUT / "keep_rate_by_language.csv", index=False)
    unparsed.to_csv(OUT / "unparsed_answers.csv", index=False)
    (OUT / "keep_spread_by_language.json").write_text(json.dumps(spread, indent=2) + "\n")
    for f in ["summary_by_band", "margins_with_ci", "margins_excluding_flagged_items", "accuracy_by_model",
              "accuracy_by_language", "helene_curve"]:
        df = pd.read_csv(OUT / f"{f}.csv")
        df.round(3).to_csv(OUT / f"{f}.csv", index=False)

    # ------------------------------------------------------------------ checks
    def acc(df, system):  # mean accuracy across models
        return float(df.loc[df.system == system, "accuracy"].iloc[0])

    def mg(df, band, comp):
        return float(df[(df.band == band) & (df.competitor == comp)].margin_points.iloc[0])

    def gap(df, band, comp):
        r = df[(df.band == band) & (df.competitor == comp)].iloc[0]
        return 100 * abs(r.competitor_keep - r.helene_keep)

    mrow = models.set_index("model")
    published = [
        ("Helene 1.1 accuracy, ~0.50 band", acc(s50, "helene-1.1"), "82.12"),
        ("Margin vs bear-2, ~0.50 band", mg(margins, "~0.50", "bear-2"), "7.08"),
        ("Margin vs kompress-v2, ~0.50 band", mg(margins, "~0.50", "kompress-v2"), "12.54"),
        ("Keep-rate gap vs kompress-v2, ~0.50 band (points)", gap(margins, "~0.50", "kompress-v2"), "13.40"),
        ("Keep-rate gap vs bear-2, ~0.50 band (points)", gap(margins, "~0.50", "bear-2"), "1.02"),
        ("Helene 1.1 accuracy, ~0.75 band", acc(s75, "helene-1.1"), "90.56"),
        ("Margin vs bear-2, ~0.75 band", mg(margins, "~0.75", "bear-2"), "3.72"),
        ("Margin vs kompress-v2, ~0.75 band", mg(margins, "~0.75", "kompress-v2"), "12.01"),
        ("Keep-rate gap vs kompress-v2, ~0.75 band (points)", gap(margins, "~0.75", "kompress-v2"), "5.46"),
        ("Keep-rate gap vs bear-2, ~0.75 band (points)", gap(margins, "~0.75", "bear-2"), "3.28"),
        ("Helene 1.1 accuracy at nominal 0.33", float(cv[(cv.system == "helene-1.1") & (cv.nominal_rate == 0.33)].accuracy.iloc[0]), "72.85"),
        ("Mean margin vs bear-2 across models", mrow.loc["mean of four", "margin_vs_bear-2"], "5.40"),
        ("Mean margin vs kompress-v2 across models", mrow.loc["mean of four", "margin_vs_kompress-v2"], "12.27"),
        ("Smallest per-model margin vs bear-2", models.iloc[:4]["margin_vs_bear-2"].min(), "3.88"),
        ("Largest per-model margin vs bear-2", models.iloc[:4]["margin_vs_bear-2"].max(), "7.08"),
        ("Smallest per-model margin vs kompress-v2", models.iloc[:4]["margin_vs_kompress-v2"].min(), "9.43"),
        ("Largest per-model margin vs kompress-v2", models.iloc[:4]["margin_vs_kompress-v2"].max(), "17.67"),
        ("kompress-v2 keep spread across languages (x)", spread["kompress-v2"], "1.68"),
        ("bear-2 keep spread across languages (x)", spread["bear-2"], "23.6"),
    ]
    # A published figure passes only if the data rounds to exactly the digits shown.
    check_rows, failed = [], 0
    for name, got, want in published:
        decimals = len(want.split(".")[1]) if "." in want else 0
        ok = f"{got:.{decimals}f}" == want
        failed += not ok
        check_rows.append(dict(check=name, published=want, reproduced=f"{got:.{decimals}f}", status="OK" if ok else "MISMATCH"))
    checks = pd.DataFrame(check_rows)
    checks.to_csv(OUT / "checks.csv", index=False)

    # ------------------------------------------------------------------ report
    report = [
        "# Reproduced results",
        "",
        "Generated by `scripts/reproduce.py` from the per-item data in `data/`. Accuracy is in percent;",
        "keep rate is the share of o200k_base tokens left after compression. Confidence intervals are",
        f"95% passage-cluster bootstrap intervals ({N_BOOT:,} resamples, seed {SEED}).",
        "",
        "## Accuracy by band (mean of four answering models)",
        "",
        md_table(summary[["band", "system", "accuracy", "keep_rate"]], "{:.3f}"),
        "",
        "## Helene 1.1 margins",
        "",
        md_table(margins[["band", "competitor", "helene_keep", "competitor_keep", "margin_points", "ci95_low", "ci95_high"]], "{:.2f}"),
        "",
        "## Margins without the items flagged by the contamination screen",
        "",
        md_table(margins_clean[["band", "competitor", "margin_points", "ci95_low", "ci95_high"]], "{:.2f}"),
        "",
        "## Accuracy by answering model (mean of the two bands)",
        "",
        md_table(models, "{:.2f}"),
        "",
        "## Helene 1 vs Helene 1.1",
        "",
        md_table(cv, "{:.3f}"),
        "",
        "## Share of text kept by language (~0.50 band)",
        "",
        md_table(keep_table, "{:.3f}"),
        "",
        "Largest / smallest language mean: " + ", ".join(f"{k} {v:.2f}x" for k, v in spread.items()) + ".",
        "",
        "## Unparsed answers (scored as wrong)",
        "",
        md_table(unparsed, "{:.0f}"),
        "",
        "## Helene 1.1 budget fidelity (reported, not rebuildable from this repository)",
        "",
        f"Mean absolute error {fidelity_reported['mean_abs_error_points']:.2f} points over {fidelity_reported['passages']:,} passages; "
        f"{fidelity_reported['share_exact_percent']:.0f}% exactly on budget; "
        f"{fidelity_reported['share_within_one_token_percent']:.1f}% within one token; "
        f"no language above {fidelity_reported['max_language_mean_abs_error_points']:.2f} points.",
        "",
        "## Checks against the published write-up",
        "",
        md_table(checks, "{:.2f}"),
        "",
    ]
    (OUT / "RESULTS.md").write_text("\n".join(report))

    print(checks.to_string(index=False))
    print(f"\n{len(checks) - failed}/{len(checks)} published numbers reproduced. Results written to {OUT.relative_to(ROOT)}/")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
