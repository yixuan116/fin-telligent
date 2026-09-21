"""
Pre-processing for the "Benchmark Story" section added to the Budget Sandbox
part of ai-compute-datacenter-economics/index.html. Reads
performance_benchmarks.csv and models.csv from
"LLM API Pricing & Performance Benchmark Tracker/" and writes a compact JSON
that gets embedded inline in the HTML (see embed step in the HTML edit).
"""

import json

import pandas as pd

BASE = "/Users/yixuan/fin-telligent/ai-compute-datacenter-economics/LLM API Pricing & Performance Benchmark Tracker"
OUT_PATH = "/Users/yixuan/fin-telligent/ai-compute-datacenter-economics/dashboard/benchmark_story_data.json"

BENCHMARKS = ["MMLU", "GPQA_Diamond", "MT_Bench", "custom_reasoning_v1", "HumanEval", "LiveCodeBench", "GSM8K", "AIME"]
FLAGSHIPS = ["gpt-4o", "claude-3.5-sonnet", "gpt-5", "deepseek-r1"]

pb = pd.read_csv(f"{BASE}/performance_benchmarks.csv")
models = pd.read_csv(f"{BASE}/models.csv")
provider_by_id = models.set_index("model_id")["provider"].to_dict()

max_date = pb["date_tested"].max()

# ---- 1. top-10 per benchmark at the latest date ----
latest = pb[pb["date_tested"] == max_date]
top10 = {}
for b in BENCHMARKS:
    sub = latest[latest["benchmark_name"] == b].sort_values("score", ascending=False).head(10)
    top10[b] = [
        {"model_id": r.model_id, "provider": provider_by_id.get(r.model_id, "Unknown"), "score": round(float(r.score), 2)}
        for r in sub.itertuples()
    ]

# ---- 2. model-count growth over time ----
growth = pb.groupby("date_tested")["model_id"].nunique().sort_index()
model_growth = {"weeks": growth.index.tolist(), "counts": growth.values.tolist()}

# ---- 3. confirm + capture flagship fixed scores ----
variance = pb.groupby(["model_id", "benchmark_name"])["score"].nunique()
assert (variance <= 1).all(), "found a model+benchmark with a score that changes over time"

flagship_scores = {}
for m in FLAGSHIPS:
    row = {}
    sub = pb[pb["model_id"] == m]
    for b in BENCHMARKS:
        vals = sub[sub["benchmark_name"] == b]["score"]
        row[b] = round(float(vals.iloc[0]), 2) if len(vals) else None
    flagship_scores[m] = row

output = {
    "max_date": max_date,
    "min_date": pb["date_tested"].min(),
    "top10": top10,
    "model_count_growth": model_growth,
    "flagship_scores": flagship_scores,
    "scores_are_constant_over_time": True,
}

with open(OUT_PATH, "w") as f:
    json.dump(output, f, separators=(",", ":"))

import os
print("wrote", OUT_PATH, os.path.getsize(OUT_PATH), "bytes")
print("weeks tracked:", len(model_growth["weeks"]), "from", model_growth["counts"][0], "to", model_growth["counts"][-1], "models")
for b in BENCHMARKS:
    print(f"{b}: top model = {top10[b][0]['model_id']} @ {top10[b][0]['score']}")
