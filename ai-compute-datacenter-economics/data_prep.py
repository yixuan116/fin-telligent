"""
Pre-processing for the Act 2 modules of ai-compute-datacenter-economics/index.html.

Reads the four CSVs in "LLM API Pricing & Performance Benchmark Tracker/",
computes the derived series/tables described in the module specs, and writes
a single compact JSON (act2_data.json) that gets embedded inline into the
HTML at build time (see embed_act2_data.py). No CSV is read in the browser.
"""

import json

import pandas as pd

BASE = "/Users/yixuan/fin-telligent/ai-compute-datacenter-economics/LLM API Pricing & Performance Benchmark Tracker"
OUT_PATH = "/Users/yixuan/fin-telligent/ai-compute-datacenter-economics/dashboard/act2_data.json"

FLAGSHIP_MAP = {
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "claude-3.5-sonnet": "claude-3.5-sonnet",
    "claude-3-haiku": "claude-3-haiku",
    "gemini-1.5-pro": "gemini-1.5-pro",
    "gemini-1.5-flash": "gemini-1.5-flash",
    "llama-3.1-405b": "llama-3.1-405b",
    "mistral-large": "mistral-large-1",  # "mistral-large" has no exact row; -1 covers the full date range
    "deepseek-v3": "deepseek-v3",
    "deepseek-r1": "deepseek-r1",
}

DISPLAY_NAMES = {
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o mini",
    "claude-3.5-sonnet": "Claude 3.5 Sonnet",
    "claude-3-haiku": "Claude 3 Haiku",
    "gemini-1.5-pro": "Gemini 1.5 Pro",
    "gemini-1.5-flash": "Gemini 1.5 Flash",
    "llama-3.1-405b": "Llama 3.1 405B",
    "mistral-large": "Mistral Large",
    "deepseek-v3": "DeepSeek V3",
    "deepseek-r1": "DeepSeek R1",
}

print("Loading CSVs...")
ph = pd.read_csv(f"{BASE}/pricing_history.csv", parse_dates=["date_recorded"])
ce = pd.read_csv(f"{BASE}/cost_efficiency.csv", parse_dates=["date"])
pb = pd.read_csv(f"{BASE}/performance_benchmarks.csv", parse_dates=["date_tested"])
models = pd.read_csv(f"{BASE}/models.csv")

ph["blended_price"] = ph["input_price_per_mtok"] * 0.75 + ph["output_price_per_mtok"] * 0.25

# ============================================================
# MODULE 1: Cost of Frontier Intelligence Over Time
# ============================================================
print("Building Module 1...")
m1 = ph.merge(
    ce[["model_id", "date", "quality_score"]],
    left_on=["model_id", "date_recorded"],
    right_on=["model_id", "date"],
    how="inner",
)

weekly_rows = []
for week, grp in m1.groupby("date_recorded"):
    q80 = grp["quality_score"].quantile(0.80)
    top = grp[grp["quality_score"] >= q80]
    if top.empty:
        continue
    idxmin = top["blended_price"].idxmin()
    weekly_rows.append(
        {
            "week": week.strftime("%Y-%m-%d"),
            "frontier_floor_price": round(float(top.loc[idxmin, "blended_price"]), 4),
            "frontier_model_id": top.loc[idxmin, "model_id"],
            "industry_median": round(float(grp["blended_price"].median()), 4),
        }
    )

weekly_rows.sort(key=lambda r: r["week"])

# annotate the biggest step-downs: weeks where the frontier model changed AND
# the floor price dropped meaningfully (>= 12%) vs. the prior week
annotations = []
for i in range(1, len(weekly_rows)):
    prev, cur = weekly_rows[i - 1], weekly_rows[i]
    if cur["frontier_model_id"] == prev["frontier_model_id"]:
        continue
    if prev["frontier_floor_price"] <= 0:
        continue
    pct_drop = (prev["frontier_floor_price"] - cur["frontier_floor_price"]) / prev["frontier_floor_price"]
    if pct_drop >= 0.12:
        annotations.append(
            {
                "week": cur["week"],
                "model_id": cur["frontier_model_id"],
                "price": cur["frontier_floor_price"],
                "pct_drop": round(pct_drop * 100, 1),
            }
        )

annotations.sort(key=lambda a: a["pct_drop"], reverse=True)
annotations = annotations[:8]
annotations.sort(key=lambda a: a["week"])

module1 = {"weekly": weekly_rows, "annotations": annotations}
print(f"  Module 1: {len(weekly_rows)} weeks, {len(annotations)} annotated drops")

# ============================================================
# MODULE 2: Margin Black Hole Simulator
# ============================================================
print("Building Module 2...")
module2_models = []
for label, model_id in FLAGSHIP_MAP.items():
    price_row = ph[ph["model_id"] == model_id].sort_values("date_recorded").iloc[-1]

    pb_sub = pb[pb["model_id"] == model_id]
    if pb_sub.empty:
        print(f"  WARNING: no performance_benchmarks rows for {model_id}")
        continue
    latest_test_date = pb_sub["date_tested"].max()
    ttft = pb_sub[pb_sub["date_tested"] == latest_test_date]["latency_ttft_ms"].mean()

    module2_models.append(
        {
            "model_id": model_id,
            "label": DISPLAY_NAMES[label],
            "input_price": round(float(price_row["input_price_per_mtok"]), 4),
            "output_price": round(float(price_row["output_price_per_mtok"]), 4),
            "avg_ttft_ms": round(float(ttft), 1),
        }
    )

print(f"  Module 2: {len(module2_models)} models")

# ============================================================
# MODULE 3: Model Selection Router
# ============================================================
print("Building Module 3...")
ce_latest = ce.sort_values("date").groupby("model_id").tail(1).set_index("model_id")

pb_latest_date = pb.groupby("model_id")["date_tested"].transform("max")
pb_latest = pb[pb["date_tested"] == pb_latest_date]
pb_agg = pb_latest.groupby("model_id").agg(
    avg_ttft_ms=("latency_ttft_ms", "mean"),
    avg_tokens_per_sec=("tokens_per_sec", "mean"),
)

models_idx = models.drop_duplicates("model_id").set_index("model_id")

joined = ce_latest[["quality_score", "quality_per_dollar", "price_performance_ratio", "cost_per_1k_queries"]].join(
    pb_agg, how="inner"
).join(models_idx[["provider", "open_weight", "context_window"]], how="inner")

module3 = []
for model_id, row in joined.iterrows():
    module3.append(
        {
            "model_id": model_id,
            "provider": row["provider"],
            "open_weight": bool(row["open_weight"]),
            "context_window": int(row["context_window"]) if pd.notna(row["context_window"]) else None,
            "quality_score": round(float(row["quality_score"]), 2),
            "quality_per_dollar": round(float(row["quality_per_dollar"]), 3),
            "price_performance_ratio": round(float(row["price_performance_ratio"]), 3),
            "cost_per_1k_queries": round(float(row["cost_per_1k_queries"]), 3),
            "avg_ttft_ms": round(float(row["avg_ttft_ms"]), 1),
            "avg_tokens_per_sec": round(float(row["avg_tokens_per_sec"]), 1),
        }
    )

print(f"  Module 3: {len(module3)} models with data in all three tables")

output = {
    "module1": module1,
    "module2": module2_models,
    "module3": module3,
}

with open(OUT_PATH, "w") as f:
    json.dump(output, f, separators=(",", ":"))

import os

size_kb = os.path.getsize(OUT_PATH) / 1024
print(f"\nWrote {OUT_PATH} ({size_kb:.1f} KB)")
