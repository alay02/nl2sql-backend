"""
Evaluate SQL generation accuracy against golden examples.

For each golden example, generates SQL via the LLM pipeline, executes both
the generated and expected SQL, and compares results. Reports per-category
and overall execution-match accuracy.

Usage:
    python -m scripts.eval_sql_accuracy [--out results.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.nl2sql import eval_one, run_sql
from src.utils.logger import get_logger

logger = get_logger(__name__)

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "dataset" / "golden_sql.jsonl"


def load_golden(path: Path) -> List[Dict[str, Any]]:
    examples = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def normalize_rows(rows: List[List[Any]]) -> List[Tuple]:
    """Round floats and sort rows for comparison."""
    normalized = []
    for row in rows:
        normed = []
        for v in row:
            if isinstance(v, float):
                normed.append(round(v, 4))
            elif isinstance(v, str):
                normed.append(v.strip())
            else:
                normed.append(v)
        normalized.append(tuple(normed))
    return sorted(normalized)


def results_match(gold_data: Dict, gen_data: Dict) -> Tuple[bool, str]:
    """Compare query results, allowing column name differences."""
    if gold_data is None and gen_data is None:
        return True, "both_empty"

    if gold_data is None or gen_data is None:
        return False, "one_side_null"

    gold_rows = gold_data.get("rows", [])
    gen_rows = gen_data.get("rows", [])

    if len(gold_rows) == 0 and len(gen_rows) == 0:
        return True, "both_empty"

    if len(gold_data.get("columns", [])) != len(gen_data.get("columns", [])):
        return False, f"column_count_mismatch ({len(gold_data['columns'])} vs {len(gen_data['columns'])})"

    gold_norm = normalize_rows(gold_rows)
    gen_norm = normalize_rows(gen_rows)

    if gold_norm == gen_norm:
        return True, "exact_match"

    if len(gold_norm) != len(gen_norm):
        return False, f"row_count_mismatch ({len(gold_norm)} vs {len(gen_norm)})"

    return False, "value_mismatch"


def evaluate_one(example: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single golden example through the pipeline and compare."""
    qid = example["id"]
    question = example["question"]
    gold_sql = example["gold_sql"]
    category = example["category"]

    result = {
        "id": qid,
        "category": category,
        "question": question,
        "gold_sql": gold_sql,
        "generated_sql": None,
        "status": None,
        "exec_match": False,
        "match_detail": "",
        "error": None,
    }

    try:
        t0 = time.time()
        pipeline_result = eval_one(question)
        result["latency_s"] = round(time.time() - t0, 2)
        result["status"] = pipeline_result.get("status")
        result["generated_sql"] = pipeline_result.get("sql")

        if pipeline_result.get("status") == "clarify":
            result["match_detail"] = "clarify_skipped"
            return result

        if pipeline_result.get("status") == "error":
            result["error"] = pipeline_result.get("message", "unknown error")
            result["match_detail"] = "pipeline_error"
            return result

        gen_data = pipeline_result.get("data")

        try:
            gold_data = run_sql(gold_sql)
        except Exception as e:
            result["error"] = f"gold_sql_exec_error: {e}"
            result["match_detail"] = "gold_exec_failed"
            return result

        match, detail = results_match(gold_data, gen_data)
        result["exec_match"] = match
        result["match_detail"] = detail

    except Exception as e:
        result["error"] = str(e)
        result["match_detail"] = "exception"

    return result


def print_report(results: List[Dict[str, Any]]) -> None:
    total = len(results)
    matched = sum(1 for r in results if r["exec_match"])
    skipped = sum(1 for r in results if r["match_detail"] == "clarify_skipped")
    errors = sum(1 for r in results if r["error"])
    evaluated = total - skipped

    print("\n" + "=" * 60)
    print("  SQL GENERATION ACCURACY REPORT")
    print("=" * 60)

    print(f"\n  Total examples:    {total}")
    print(f"  Evaluated:         {evaluated}")
    print(f"  Skipped (clarify): {skipped}")
    print(f"  Errors:            {errors}")
    print(f"\n  Execution match:   {matched}/{evaluated}  ({matched/evaluated*100:.1f}%)" if evaluated else "")

    by_cat = defaultdict(lambda: {"total": 0, "match": 0, "skip": 0})
    for r in results:
        cat = r["category"]
        if r["match_detail"] == "clarify_skipped":
            by_cat[cat]["skip"] += 1
        else:
            by_cat[cat]["total"] += 1
            if r["exec_match"]:
                by_cat[cat]["match"] += 1

    print(f"\n  {'Category':<22} {'Match':>5} / {'Total':>5}  {'Accuracy':>8}")
    print("  " + "-" * 48)
    for cat in sorted(by_cat):
        c = by_cat[cat]
        if c["total"] > 0:
            acc = c["match"] / c["total"] * 100
            print(f"  {cat:<22} {c['match']:>5} / {c['total']:>5}  {acc:>7.1f}%")
        else:
            print(f"  {cat:<22}     - /     -        -")

    failures = [r for r in results if not r["exec_match"] and r["match_detail"] != "clarify_skipped"]
    if failures:
        print(f"\n  FAILURES ({len(failures)}):")
        print("  " + "-" * 48)
        for r in failures:
            print(f"  [{r['id']}] {r['question'][:50]}")
            print(f"    Detail: {r['match_detail']}")
            if r["gold_sql"]:
                print(f"    Gold:   {r['gold_sql'][:70]}")
            if r["generated_sql"]:
                print(f"    Gen:    {r['generated_sql'][:70]}")
            if r["error"]:
                print(f"    Error:  {r['error'][:70]}")
            print()

    latencies = [r["latency_s"] for r in results if "latency_s" in r]
    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        print(f"  Avg latency: {avg_lat:.1f}s  (total: {sum(latencies):.0f}s)")

    print("=" * 60)


def save_csv(results: List[Dict[str, Any]], path: str) -> None:
    fields = [
        "id", "category", "question", "gold_sql", "generated_sql",
        "status", "exec_match", "match_detail", "latency_s", "error",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"\n  Results saved to {path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate SQL generation accuracy")
    parser.add_argument("--out", default="eval_results.csv", help="Output CSV path")
    parser.add_argument("--limit", type=int, default=0, help="Max examples to run (0=all)")
    args = parser.parse_args()

    examples = load_golden(GOLDEN_PATH)
    if args.limit > 0:
        examples = examples[:args.limit]

    print(f"Running evaluation on {len(examples)} golden examples...\n")

    results = []
    for i, ex in enumerate(examples, 1):
        print(f"  [{i}/{len(examples)}] {ex['id']}: {ex['question'][:55]}...", end="", flush=True)
        r = evaluate_one(ex)
        mark = "PASS" if r["exec_match"] else ("SKIP" if r["match_detail"] == "clarify_skipped" else "FAIL")
        print(f"  {mark}")
        results.append(r)

    print_report(results)
    save_csv(results, args.out)


if __name__ == "__main__":
    main()
