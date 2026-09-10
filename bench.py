#!/usr/bin/env python3
"""Benchmark tool for Ketabdari API — measures latency percentiles per endpoint."""
import json
import math
import statistics
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8888"

ENDPOINTS = [
    ("GET", "/health", None),
    ("GET", "/users?page=1&size=100", None),
    ("GET", "/users/1500", None),
    ("GET", "/users/1500/rentals", None),
    ("GET", "/books?page=1&size=50", None),
    ("GET", "/books?page=10&size=50", None),
    ("GET", "/books?search=clean&page=1&size=20", None),
    ("GET", "/rentals?page=1&size=50", None),
    ("GET", "/rentals/overdue", None),
]


def req(method, path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            resp.read()
            return (time.perf_counter() - t0) * 1000, resp.status
    except urllib.error.HTTPError as e:
        e.read()
        return (time.perf_counter() - t0) * 1000, e.code


def bench(method, path, body=None, n=30, warmup=5):
    for _ in range(warmup):
        req(method, path, body)
    lat = []
    codes = set()
    for _ in range(n):
        ms, code = req(method, path, body)
        lat.append(ms)
        codes.add(code)
    lat.sort()

    def pct(p):
        k = max(0, min(len(lat) - 1, int(math.ceil(p / 100 * len(lat))) - 1))
        return lat[k]

    return {
        "endpoint": f"{method} {path}",
        "n": n,
        "codes": ",".join(str(c) for c in sorted(codes)),
        "mean": round(statistics.mean(lat), 1),
        "p50": round(pct(50), 1),
        "p95": round(pct(95), 1),
        "p99": round(pct(99), 1),
        "max": round(lat[-1], 1),
    }


if __name__ == "__main__":
    results = []
    for method, path, body in ENDPOINTS:
        results.append(bench(method, path, body))
        r = results[-1]
        print(f"{r['endpoint']:<45} n={r['n']:<3} {r['codes']:<9} "
              f"mean={r['mean']:>7}ms  p50={r['p50']:>7}ms  p95={r['p95']:>8}ms  p99={r['p99']:>8}ms")
    with open(sys.argv[2] if len(sys.argv) > 2 else "/tmp/bench.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nsaved: {sys.argv[2] if len(sys.argv) > 2 else '/tmp/bench.json'}")
