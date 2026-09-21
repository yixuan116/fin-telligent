"""
Pre-processing for the "Price Change" module added to the Budget Sandbox
part of ai-compute-datacenter-economics/index.html. Reads pricing_history.csv
from "LLM API Pricing & Performance Benchmark Tracker/" and writes a compact
JSON embedded inline in the HTML.
"""

import json

import pandas as pd

BASE = "/Users/yixuan/fin-telligent/ai-compute-datacenter-economics/LLM API Pricing & Performance Benchmark Tracker"
OUT_PATH = "/Users/yixuan/fin-telligent/ai-compute-datacenter-economics/dashboard/price_story_data.json"

# gemini-2.0-flash has no exact row; gemini-2-flash is the closest (this
# dataset drops the ".0"). The rest are exact matches, incl. the 4 the user
# named by name.
MODELS = ["gpt-4o", "gpt-5", "claude-3.5-sonnet", "deepseek-r1", "gemini-2-flash",
          "gpt-4o-mini", "claude-3-haiku", "gemini-1.5-pro", "llama-3.1-405b", "mistral-large-1"]

ph = pd.read_csv(f"{BASE}/pricing_history.csv")

# ---- sanity check the price-constancy assumption before committing to the UI copy ----
var_in = ph.groupby("model_id")["input_price_per_mtok"].nunique()
var_out = ph.groupby("model_id")["output_price_per_mtok"].nunique()
prices_are_constant = bool((var_in <= 1).all() and (var_out <= 1).all())

# ---- 1. per-model weekly series (for the line chart) ----
series = {}
for m in MODELS:
    sub = ph[ph["model_id"] == m].sort_values("date_recorded")
    series[m] = {
        "dates": sub["date_recorded"].tolist(),
        "input": sub["input_price_per_mtok"].round(4).tolist(),
        "output": sub["output_price_per_mtok"].round(4).tolist(),
    }

# ---- 2. first-vs-latest price drop % per model ----
drops = []
for m in MODELS:
    sub = ph[ph["model_id"] == m].sort_values("date_recorded")
    first_blended = sub.iloc[0]["input_price_per_mtok"] * 0.75 + sub.iloc[0]["output_price_per_mtok"] * 0.25
    latest_blended = sub.iloc[-1]["input_price_per_mtok"] * 0.75 + sub.iloc[-1]["output_price_per_mtok"] * 0.25
    pct_drop = 0.0 if first_blended == 0 else (first_blended - latest_blended) / first_blended * 100
    drops.append({"model_id": m, "first_price": round(float(first_blended), 4),
                   "latest_price": round(float(latest_blended), 4), "pct_drop": round(float(pct_drop), 2)})

# ---- 3. output:input ratio, per selected model + population-wide weekly trend ----
ratios = []
for m in MODELS:
    row = ph[ph["model_id"] == m].iloc[-1]
    ratios.append({"model_id": m, "ratio": round(float(row["output_price_per_mtok"] / row["input_price_per_mtok"]), 3)})

ph_all = ph.copy()
ph_all["ratio"] = ph_all["output_price_per_mtok"] / ph_all["input_price_per_mtok"]
weekly_ratio = ph_all.groupby("date_recorded")["ratio"].mean().round(4)
ratio_trend = {"weeks": weekly_ratio.index.tolist(), "mean_ratio": weekly_ratio.values.tolist()}

# distinct ratio values across the whole 520-model field, for context
all_latest = ph.sort_values("date_recorded").groupby("model_id").last()
all_latest_ratio = (all_latest["output_price_per_mtok"] / all_latest["input_price_per_mtok"]).round(3)
ratio_value_counts = all_latest_ratio.value_counts().sort_index()

# ---- 4. discount scenario simulator inputs (latest pricing row per model) ----
# cached_input_price / batch_discount_pct are genuinely missing for a large
# share of the field (343/520 and 254/520 respectively) -- not every model
# offers caching or batch pricing. Emit null (not NaN, which isn't valid
# JSON) plus explicit availability flags so the UI can say "not offered"
# instead of computing garbage.
scenarios = {}
for m in MODELS:
    row = ph[ph["model_id"] == m].sort_values("date_recorded").iloc[-1]
    has_cache = bool(pd.notna(row["cached_input_price"]))
    has_batch = bool(pd.notna(row["batch_discount_pct"]))
    scenarios[m] = {
        "input_price": round(float(row["input_price_per_mtok"]), 4),
        "output_price": round(float(row["output_price_per_mtok"]), 4),
        "cached_input_price": round(float(row["cached_input_price"]), 4) if has_cache else None,
        "batch_discount_pct": round(float(row["batch_discount_pct"]), 2) if has_batch else None,
        "has_cache": has_cache,
        "has_batch": has_batch,
    }

null_share = {
    "cached_input_price": round(float(ph.sort_values("date_recorded").groupby("model_id").last()["cached_input_price"].isna().mean()) * 100, 1),
    "batch_discount_pct": round(float(ph.sort_values("date_recorded").groupby("model_id").last()["batch_discount_pct"].isna().mean()) * 100, 1),
}

output = {
    "models": MODELS,
    "prices_are_constant_per_model": prices_are_constant,
    "series": series,
    "drops": drops,
    "ratios": ratios,
    "ratio_trend": ratio_trend,
    "ratio_value_counts": {str(k): int(v) for k, v in ratio_value_counts.items()},
    "scenarios": scenarios,
    "cache_batch_null_share_pct": null_share,
    "min_date": ph["date_recorded"].min(),
    "max_date": ph["date_recorded"].max(),
}

with open(OUT_PATH, "w") as f:
    json.dump(output, f, separators=(",", ":"))

import os
print("wrote", OUT_PATH, os.path.getsize(OUT_PATH), "bytes")
print("prices_are_constant_per_model:", prices_are_constant)
print("drops:", [(d["model_id"], d["pct_drop"]) for d in drops])
print("ratios:", ratios)
print("ratio_value_counts:", dict(ratio_value_counts))
print("ratio_trend first/last:", ratio_trend["mean_ratio"][0], "->", ratio_trend["mean_ratio"][-1])
