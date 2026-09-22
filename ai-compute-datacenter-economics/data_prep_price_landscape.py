"""
Pre-processing for the "Pricing Landscape" redesign of the first two layers
of the Price Change module (release_date vs. output price scatter, and a
same-provider generational comparison table). Reads pricing_history.csv +
models.csv from "LLM API Pricing & Performance Benchmark Tracker/".
"""

import json

import pandas as pd

BASE = "/Users/yixuan/fin-telligent/ai-compute-datacenter-economics/LLM API Pricing & Performance Benchmark Tracker"
OUT_PATH = "/Users/yixuan/fin-telligent/ai-compute-datacenter-economics/dashboard/price_landscape_data.json"

ph = pd.read_csv(f"{BASE}/pricing_history.csv")
m = pd.read_csv(f"{BASE}/models.csv")

latest = ph.sort_values("date_recorded").groupby("model_id").last().reset_index()
merged = latest.merge(m[["model_id", "provider", "release_date"]], on="model_id")

# ---- 1. scatter: release_date vs output_price_per_mtok, colored by provider ----
# keep the top 10 providers by model count distinct; bucket the other 47 into "Other"
top_providers = merged["provider"].value_counts().head(10).index.tolist()
merged["provider_bucket"] = merged["provider"].apply(lambda p: p if p in top_providers else "Other")

scatter = []
for row in merged.itertuples():
    scatter.append({
        "model_id": row.model_id,
        "provider": row.provider,
        "bucket": row.provider_bucket,
        "release_date": row.release_date,
        "output_price": round(float(row.output_price_per_mtok), 4),
    })

# ---- 2. same-provider generational lineages ----
LINEAGES = {
    "OpenAI": ["gpt-4-32k", "gpt-4o", "gpt-4o-mini", "gpt-5"],
    "Anthropic": ["claude-2.0", "claude-3-opus", "claude-3.5-sonnet", "claude-opus-4.5"],
    "Google": ["gemini-1.0-pro", "gemini-1.5-pro", "gemini-2-pro", "gemini-2-flash"],
}

lineage_out = {}
for provider, model_ids in LINEAGES.items():
    rows = []
    prev = None
    for mid in model_ids:
        r = merged[merged.model_id == mid]
        if r.empty:
            continue
        r = r.iloc[0]
        input_p = round(float(r.input_price_per_mtok), 4)
        output_p = round(float(r.output_price_per_mtok), 4)
        input_pct = None if prev is None else round((input_p - prev[0]) / prev[0] * 100, 1)
        output_pct = None if prev is None else round((output_p - prev[1]) / prev[1] * 100, 1)
        rows.append({
            "model_id": mid, "release_date": r.release_date,
            "input_price": input_p, "output_price": output_p,
            "input_pct_change": input_pct, "output_pct_change": output_pct,
        })
        prev = (input_p, output_p)
    lineage_out[provider] = rows

output = {
    "scatter": scatter,
    "top_providers": top_providers,
    "lineages": lineage_out,
}

with open(OUT_PATH, "w") as f:
    json.dump(output, f, separators=(",", ":"))

import os
print("wrote", OUT_PATH, os.path.getsize(OUT_PATH), "bytes")
print("scatter points:", len(scatter))
print("top providers:", top_providers)
print()
for prov, rows in lineage_out.items():
    print(f"=== {prov} ===")
    for r in rows:
        print(f"  {r['model_id']:20s} {r['release_date']}  in=${r['input_price']:<7} ({r['input_pct_change']}%)  out=${r['output_price']:<7} ({r['output_pct_change']}%)")
