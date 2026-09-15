#!/usr/bin/env python3
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def generate_comparison_chart(before_path, after_path, title, output_path, is_4m=True):
    with open(before_path) as f:
        before = json.load(f)
    with open(after_path) as f:
        after = json.load(f)

    metrics = ["Min", "p25", "p50", "p75", "p95", "p99", "Mean"]
    keys = ["min", "p25", "p50", "p75", "p95", "p99", "mean"]

    before_vals = [before[k] for k in keys]
    after_vals = [after[k] for k in keys]

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#1e1e2e")
    ax.set_facecolor("#181825")

    x = np.arange(len(metrics))
    width = 0.35

    rects1 = ax.bar(x - width/2, before_vals, width, label="Before Indexing (Seq Scan)", color="#f38ba8", edgecolor="#585b70")
    rects2 = ax.bar(x + width/2, after_vals, width, label="After Indexing (Trigram GIN)", color="#a6e3a1", edgecolor="#585b70")

    ax.set_ylabel("Latency (ms)" + (" [Log Scale]" if is_4m else ""), color="#cdd6f4", fontsize=12, fontweight="bold")
    ax.set_title(title, color="#f5e0dc", fontsize=15, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, color="#cdd6f4", fontsize=11, fontweight="bold")
    ax.tick_params(colors="#cdd6f4")
    ax.legend(facecolor="#313244", edgecolor="#45475a", labelcolor="#cdd6f4", fontsize=11)
    ax.grid(axis="y", linestyle="--", alpha=0.3, color="#585b70")

    if is_4m:
        ax.set_yscale("log")
        for rect in rects1:
            h = rect.get_height()
            lbl = f"{h:.0f}ms" if h < 1000 else f"{h/1000:.1f}s"
            ax.annotate(lbl, xy=(rect.get_x() + rect.get_width()/2, h),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                        color="#f38ba8", fontsize=8.5, fontweight="bold")
        for rect in rects2:
            h = rect.get_height()
            lbl = f"{h:.0f}ms" if h < 1000 else f"{h/1000:.1f}s"
            ax.annotate(lbl, xy=(rect.get_x() + rect.get_width()/2, h),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                        color="#a6e3a1", fontsize=8.5, fontweight="bold")
    else:
        for rect in rects1 + rects2:
            h = rect.get_height()
            ax.annotate(f"{h:.1f}ms", xy=(rect.get_x() + rect.get_width()/2, h),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                        color="#ffffff", fontsize=8.5, fontweight="bold")

    for spine in ax.spines.values():
        spine.set_color("#45475a")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved {output_path}")

if __name__ == "__main__":
    generate_comparison_chart(
        "docs/benchmarks/search_4m_unindexed.json",
        "docs/benchmarks/search_4m_indexed.json",
        "Search Latency Comparison: 4,000,000 Books (Before vs After GIN Indexing)",
        "docs/benchmarks/search_comparison_4m.png",
        is_4m=True
    )
    generate_comparison_chart(
        "docs/benchmarks/search_1k_unindexed.json",
        "docs/benchmarks/search_1k_indexed.json",
        "Search Latency Comparison: 1,000 Books (Before vs After GIN Indexing)",
        "docs/benchmarks/search_comparison_1k.png",
        is_4m=False
    )
