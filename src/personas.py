"""Behavioural personas: K-Means on log-scaled RFM-style features at a cutoff.

Segments describe BEHAVIOUR only. The dataset has no demographics, so none are invented.
k is chosen by silhouette over 2..8 (or forced with --k) and every silhouette is printed.
Silhouette tends to favour few clusters; force a larger k if the business needs finer segments.
Writes reports/personas.csv and reports/personas_prompt.txt (paste the prompt into Claude to get persona cards).

Usage: python -m src.personas --cutoff 2011-12-01 [--k 4]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.features import build_features, load_orders


def _matrix(f: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "log_monetary": np.log1p(f["monetary"]),
        "log_frequency": np.log1p(f["frequency"]),
        "recency_days": f["recency_days"],
        "log_aov": np.log1p(f["avg_order_value"]),
        "tenure_days": f["tenure_days"],
    }, index=f.index)


def build_personas(orders, cutoff, k_range=range(2, 9), seed=42, force_k=None):
    f = build_features(orders, cutoff)
    Z = StandardScaler().fit_transform(_matrix(f))
    sil = {}
    for kk in k_range:
        lab = KMeans(kk, n_init=10, random_state=seed).fit_predict(Z)
        sil[kk] = float(silhouette_score(Z, lab, sample_size=min(len(Z), 5000), random_state=seed))
    k_best = force_k if force_k else max(sil, key=sil.get)
    f = f.assign(persona=KMeans(k_best, n_init=10, random_state=seed).fit_predict(Z))

    prof = f.groupby("persona").agg(
        customers=("monetary", "size"), recency_days=("recency_days", "median"),
        orders=("frequency", "median"), total_spend=("monetary", "median"),
        avg_order_value=("avg_order_value", "median"), tenure_days=("tenure_days", "median"),
        revenue=("monetary", "sum"))
    prof["share_customers"] = prof["customers"] / prof["customers"].sum()
    prof["share_revenue"] = prof["revenue"] / prof["revenue"].sum()
    med = f[["recency_days", "monetary"]].median()
    prof["placeholder_label"] = [
        f"{'High' if r.total_spend > med['monetary'] else 'Low'} spend, "
        f"{'recent' if r.recency_days < med['recency_days'] else 'lapsing'}"
        for r in prof.itertuples()]
    return f, prof.drop(columns="revenue"), sil, k_best


def prompt_for_claude(prof: pd.DataFrame) -> str:
    return (
        "Below are behavioural segments of retail customers (medians per segment).\n"
        "Write one persona card per segment: a short name, who they are, how they behave, what they need, "
        "and one recommended action for a CRM manager. Use ONLY these numbers. Do not invent demographics, "
        "ages or motives; the data has none. Flag any segment too small to act on.\n\n"
        + prof.round(2).to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", required=True)
    ap.add_argument("--k", type=int, default=None, help="force the number of personas")
    a = ap.parse_args()
    f, prof, sil, k = build_personas(load_orders(), a.cutoff, force_k=a.k)
    Path("reports").mkdir(exist_ok=True)
    prof.to_csv("reports/personas.csv")
    Path("reports/personas_prompt.txt").write_text(prompt_for_claude(prof))
    print("Silhouette by k:", {k_: round(v, 3) for k_, v in sil.items()}, "-> using k =", k)
    print(prof.round(2).to_string())
    print("\nPaste reports/personas_prompt.txt into Claude to write the persona cards.")
