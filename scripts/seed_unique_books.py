#!/usr/bin/env python3
"""
Seed unique books with Faker and random quantity (0-10) directly into PostgreSQL.
Uses asyncpg COPY for high throughput.
"""
import argparse
import asyncio
import os
import random
import sys
import time
from datetime import datetime, timezone
import asyncpg
from faker import Faker

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://library:library@127.0.0.1:5433/library",
)

fake = Faker()
Faker.seed(42)
random.seed(42)

WORDS = [
    "Clean", "Pragmatic", "Design", "Domain", "Refactoring", "Distributed", "Systems",
    "Algorithms", "Patterns", "Architecture", "Python", "Rust", "Go", "Kubernetes",
    "Networks", "Databases", "Compilers", "Crypto", "Graphics", "Operating",
    "Concurrent", "Modern", "Advanced", "Essential", "Foundations", "Practical",
    "Mastering", "Learning", "Building", "Scalable", "High", "Performance",
    "Reliable", "Cloud", "Microservices", "Quantum", "Machine", "Intelligence",
    "Security", "Hacking", "Forensics", "DevOps", "Site", "Reliability", "Linux",
    "Kernel", "Storage", "Memory", "Parallel", "Async", "Event", "Driven"
]

TOPICS = [
    "Software", "Computing", "Engineering", "Development", "Structures", "Analysis",
    "Protocols", "Pipelines", "Automation", "Inference", "Optimization", "Telemetry",
    "Frameworks", "Testing", "Deployment", "Orchestration", "Security", "Networking",
    "Storage", "Virtualization", "Concurrency", "Observability", "Modeling", "Synthesis"
]

# Pre-generate 10,000 realistic author names
AUTHORS = [fake.name() for _ in range(10000)]
# Add some notable authors to the pool
AUTHORS.extend(["Robert C. Martin", "Andrew Hunt", "David Thomas", "Martin Fowler", "Eric Evans"])
random.shuffle(AUTHORS)

def generate_book_batch(start_idx: int, count: int):
    now = datetime.now(timezone.utc)
    records = []
    w_len = len(WORDS)
    t_len = len(TOPICS)
    a_len = len(AUTHORS)
    for i in range(start_idx, start_idx + count):
        w1 = WORDS[i % w_len]
        w2 = WORDS[(i // w_len) % w_len]
        top = TOPICS[(i // (w_len * w_len)) % t_len]
        title = f"{w1} {w2} of {top} Vol. {i + 1}"
        author = AUTHORS[i % a_len]
        quantity = random.randint(0, 10)
        records.append((title, author, quantity, now))
    return records

async def seed(total_count: int, truncate: bool = False, batch_size: int = 100000):
    conn = await asyncpg.connect(DB_URL)
    try:
        if truncate:
            print(f"Truncating books table...")
            await conn.execute("TRUNCATE TABLE rentals, books RESTART IDENTITY CASCADE;")

        print(f"Seeding {total_count:,} books into database...")
        t0 = time.perf_counter()

        inserted = 0
        while inserted < total_count:
            curr_batch = min(batch_size, total_count - inserted)
            batch = generate_book_batch(inserted, curr_batch)
            await conn.copy_records_to_table(
                "books",
                records=batch,
                columns=["title", "author", "quantity", "created_at"],
            )
            inserted += curr_batch
            elapsed = time.perf_counter() - t0
            rate = inserted / elapsed if elapsed > 0 else 0
            print(f"  Inserted {inserted:,} / {total_count:,} books ({rate:,.0f} rows/s)")

        total_time = time.perf_counter() - t0
        print(f"Seeding completed in {total_time:.2f}s.")

        print("Running sanity checks...")
        total_in_db = await conn.fetchval("SELECT COUNT(*) FROM books;")
        print(f"  Total books in DB: {total_in_db:,}")

        dist_row = await conn.fetchrow(
            "SELECT MIN(quantity) as min_q, MAX(quantity) as max_q, AVG(quantity)::numeric(10,2) as avg_q FROM books;"
        )
        print(f"  Quantity distribution: min={dist_row['min_q']}, max={dist_row['max_q']}, avg={dist_row['avg_q']}")

        # Distinct titles check
        print("  Checking distinct titles...")
        distinct_titles = await conn.fetchval("SELECT COUNT(DISTINCT title) FROM books;")
        print(f"  Distinct titles:   {distinct_titles:,}")
        assert total_in_db == distinct_titles, f"Duplicate titles found! Total={total_in_db}, Distinct={distinct_titles}"
        print("Verification PASSED: All book titles are 100% unique!")
    finally:
        await conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000, help="Number of books to seed")
    parser.add_argument("--truncate", action="store_true", help="Truncate table before seeding")
    args = parser.parse_args()
    asyncio.run(seed(args.count, truncate=args.truncate))
