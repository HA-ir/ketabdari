#!/usr/bin/env python3
"""
Search benchmark script for Ketabdari API.
Measures latency percentiles across 1,000 search requests with varied terms (mix of hits and misses).
Generates percentile table, charts, and saves images in docs/benchmarks/.
Supports configurable concurrency.
"""
import argparse
import asyncio
import json
import math
import os
import random
import statistics
import sys
import time
import urllib.parse

import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8888")

# Diverse search pool: hits, partial hits, and misses
HIT_TERMS = [
    "Clean", "Pragmatic", "Design", "Domain", "Refactoring", "Distributed", "Systems",
    "Algorithms", "Patterns", "Architecture", "Python", "Rust", "Go", "Kubernetes",
    "Networks", "Databases", "Compilers", "Crypto", "Graphics", "Operating",
    "Concurrent", "Modern", "Advanced", "Essential", "Foundations", "Practical",
    "Mastering", "Learning", "Building", "Scalable", "High", "Performance",
    "Reliable", "Cloud", "Microservices", "Quantum", "Machine", "Intelligence",
    "Security", "Linux", "Kernel", "Storage", "Memory", "Parallel", "Async"
]

PARTIAL_TERMS = [
    "arch", "dist", "algo", "sys", "comp", "data", "soft", "engin", "learn",
    "build", "scale", "cloud", "intel", "secur", "micro", "quant", "netw", "struc"
]

MISS_TERMS = [
    "xyzzy999", "nonexistent_term", "zzz_missing_query", "impossible404", "randomfoobar",
    "null_result_probe", "nomatch_here", "notfound_search", "unlikelyword88", "miss_probe_1",
    "miss_probe_2", "miss_probe_3", "alpha_omega_void", "quantum_fluff_404", "empty_match_term"
]

def generate_queries(count: int = 1000) -> list[str]:
    random.seed(1337)
    queries = []
    for _ in range(count):
        roll = random.random()
        if roll < 0.45:
            term = random.choice(HIT_TERMS)
        elif roll < 0.70:
            term = random.choice(PARTIAL_TERMS)
        else:
            term = random.choice(MISS_TERMS)
        queries.append(term)
    return queries

async def run_benchmark(count: int = 1000, concurrency: int = 8, warmup: int = 10, page_size: int = 20):
    queries = generate_queries(count)
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency)
    timeout = httpx.Timeout(120.0, connect=10.0)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        print(f"Warming up with {warmup} requests...")
        for _ in range(warmup):
            term = random.choice(HIT_TERMS)
            encoded = urllib.parse.quote(term)
            await client.get(f"{BASE_URL}/books?search={encoded}&page=1&size={page_size}")

        print(f"Running benchmark: {count} requests with concurrency={concurrency} against {BASE_URL}...")
        latencies = []
        status_codes = {}
        t_start = time.perf_counter()

        sem = asyncio.Semaphore(concurrency)
        completed = 0

        async def worker(term: str, idx: int):
            nonlocal completed
            encoded = urllib.parse.quote(term)
            url = f"{BASE_URL}/books?search={encoded}&page=1&size={page_size}"
            async with sem:
                t0 = time.perf_counter()
                try:
                    resp = await client.get(url)
                    lat = (time.perf_counter() - t0) * 1000.0
                    code = resp.status_code
                except Exception as e:
                    lat = (time.perf_counter() - t0) * 1000.0
                    code = 599
                latencies.append(lat)
                status_codes[code] = status_codes.get(code, 0) + 1
                completed += 1
                if completed % 100 == 0 or completed == count:
                    elapsed = time.perf_counter() - t_start
                    rate = completed / elapsed if elapsed > 0 else 0
                    print(f"  Completed {completed}/{count} requests ({rate:.1f} req/s, latest: {lat:.1f}ms, code: {code})")

        tasks = [worker(q, i) for i, q in enumerate(queries)]
        await asyncio.gather(*tasks)

        total_duration = time.perf_counter() - t_start
        sorted_lat = sorted(latencies)

        def pct(p):
            k = max(0, min(len(sorted_lat) - 1, int(math.ceil(p / 100.0 * len(sorted_lat))) - 1))
            return sorted_lat[k]

        results = {
            "n": count,
            "concurrency": concurrency,
            "total_duration_s": round(total_duration, 2),
            "rps": round(count / total_duration, 2),
            "status_codes": status_codes,
            "min": round(sorted_lat[0], 2),
            "p25": round(pct(25), 2),
            "p50": round(pct(50), 2),
            "p75": round(pct(75), 2),
            "p95": round(pct(95), 2),
            "p99": round(pct(99), 2),
            "max": round(sorted_lat[-1], 2),
            "mean": round(statistics.mean(sorted_lat), 2),
            "stdev": round(statistics.stdev(sorted_lat), 2),
            "latencies": [round(x, 2) for x in latencies],
        }
        return results

def render_chart(results: dict, title: str, output_image_path: str):
    fig, (ax_table, ax_bar) = plt.subplots(
        2, 1, figsize=(10, 7.5), gridspec_kw={"height_ratios": [1, 1.4]}
    )
    fig.patch.set_facecolor("#1e1e2e")

    # Table section
    ax_table.axis("off")
    table_data = [
        ["Metric", "Value", "Metric", "Value"],
        ["Total Requests (N)", f"{results['n']:,}", "Concurrency", f"{results['concurrency']}"],
        ["Min Latency", f"{results['min']:.2f} ms", "p50 Latency (Median)", f"{results['p50']:.2f} ms"],
        ["p25 Latency", f"{results['p25']:.2f} ms", "p75 Latency", f"{results['p75']:.2f} ms"],
        ["p95 Latency", f"{results['p95']:.2f} ms", "p99 Latency", f"{results['p99']:.2f} ms"],
        ["Mean Latency", f"{results['mean']:.2f} ms", "Throughput (RPS)", f"{results['rps']:.1f} req/s"],
    ]

    table = ax_table.table(
        cellText=table_data,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.6)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#45475a")
        if row == 0:
            cell.set_facecolor("#313244")
            cell.set_text_props(color="#cdd6f4", fontweight="bold")
        elif col in (0, 2):
            cell.set_facecolor("#181825")
            cell.set_text_props(color="#a6adc8", fontweight="semibold")
        else:
            cell.set_facecolor("#1e1e2e")
            cell.set_text_props(color="#89b4fa", fontweight="bold")

    ax_table.set_title(title, fontsize=15, fontweight="bold", color="#f5e0dc", pad=12)

    # Bar chart of percentiles
    metrics = ["Min", "p25", "p50", "p75", "p95", "p99", "Max"]
    values = [
        results["min"],
        results["p25"],
        results["p50"],
        results["p75"],
        results["p95"],
        results["p99"],
        results["max"],
    ]
    colors = ["#a6e3a1", "#94e2d5", "#89dceb", "#74c7ec", "#f9e2af", "#fab387", "#f38ba8"]

    bars = ax_bar.bar(metrics, values, color=colors, edgecolor="#585b70", width=0.55)
    ax_bar.set_facecolor("#181825")
    ax_bar.set_ylabel("Latency (ms)", color="#cdd6f4", fontsize=11, fontweight="bold")
    ax_bar.tick_params(colors="#cdd6f4", labelsize=10)
    for spine in ax_bar.spines.values():
        spine.set_color("#45475a")
    ax_bar.grid(axis="y", linestyle="--", alpha=0.3, color="#585b70")

    # Add data labels
    for bar in bars:
        h = bar.get_height()
        label = f"{h:.1f}ms" if h < 1000 else f"{h/1000:.2f}s"
        ax_bar.annotate(
            label,
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            color="#ffffff",
            fontsize=9,
            fontweight="bold",
        )

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
    plt.savefig(output_image_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"Chart saved to {output_image_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--title", type=str, default="Search Benchmark")
    parser.add_argument("--output-img", type=str, required=True)
    parser.add_argument("--output-json", type=str, required=True)
    args = parser.parse_args()

    res = asyncio.run(run_benchmark(count=args.count, concurrency=args.concurrency))
    print("\nBenchmark Summary:")
    for k in ["n", "concurrency", "rps", "min", "p25", "p50", "p75", "p95", "p99", "max", "mean"]:
        print(f"  {k:<12}: {res[k]}")

    render_chart(res, args.title, args.output_img)
    with open(args.output_json, "w") as f:
        json.dump(res, f, indent=2)
    print(f"Results saved to {args.output_json}")
