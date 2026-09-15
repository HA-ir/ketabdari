<div align="center">

# 📚 Ketabdari (کتابداری)
### High-Performance, Concurrency-Safe Library Management API

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLModel](https://img.shields.io/badge/SQLModel-Async-blue?logo=pydantic&logoColor=white)](https://sqlmodel.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%28pg__trgm%29-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Driver](https://img.shields.io/badge/Driver-asyncpg-informational)](https://github.com/MagicStack/asyncpg)
[![Tests](https://img.shields.io/badge/Tests-37%20Passed-success?logo=pytest&logoColor=white)](tests/test_api.py)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<p align="center">
  A production-ready asynchronous REST API for library operations engineered for scale. Built with FastAPI, SQLModel, asyncpg, and PostgreSQL 16 with pg_trgm trigram acceleration.
</p>

</div>

---

## ⚡ Highlights

- **Million-Scale Search:** Benchmarked on **4,000,000 unique books** — Trigram GIN indexes (`pg_trgm`) deliver a **19.2× throughput increase** and drop p95 tail latency by **24.5×** (from 9.1s to 374ms).
- **Concurrency-Safe Inventory:** Physical stock (`quantity`) secured with PostgreSQL **Row-Level Locking (`SELECT ... FOR UPDATE`)** inside atomic transactions (`async with session.begin():`) to eliminate race conditions under concurrent rental bursts.
- **Zero-ORM Fast-Path Serialization:** Streaming joined row tuples directly into Pydantic models saves >200ms per request on heavy query endpoints (`/rentals/overdue`).
- **Flexible Sorting & Pagination:** Composable multi-field sorting (`created_at`, `title`, `quantity`, `id`) with whitelist validation and composite tie-breaking for deterministic pagination.

---

## 📊 Performance at a Glance (4,000,000 Books)

<div align="center">
  <img src="docs/benchmarks/search_comparison_4m.png" alt="Search 4M Comparison" width="850"/>
  <p><em>PostgreSQL Trigram GIN indexes deliver a <strong>19.2× throughput increase</strong> and <strong>24.5× lower tail latency (p95)</strong> under concurrent load. Full telemetry in <a href="docs/PERFORMANCE.md">docs/PERFORMANCE.md</a>.</em></p>
</div>

---

## 📖 Documentation Guide

For in-depth architectural details, benchmark reports, and implementation records:

| Document | What's Inside |
|---|---|
| ⚡ [**`docs/PERFORMANCE.md`**](docs/PERFORMANCE.md) | **Deep-Dive Performance Report:** Multi-stage query optimizations (Stages 1–5), raw execution plans (`EXPLAIN ANALYZE`), ORM elimination profiling, connection pool tuning, and comparison charts. |
| 📑 [**`docs/TASKS_STATUS.md`**](docs/TASKS_STATUS.md) | **Audit & Implementation Changelog:** Comprehensive record of findings, row-locking design, migration DDL, search benchmark methodology, and test verifications. |
| 🖼️ [**`docs/benchmarks/`**](docs/benchmarks/) | Raw JSON telemetry files and publication-grade chart renders for 1k and 4M book datasets. |
| 🛠️ [**`scripts/`**](scripts/) | Production utility scripts for high-speed bulk seeding (4M in 28s), automated load benchmarking, index application, and live verification. |

---

## 🚀 Quick Start

### 1. Start Database
```bash
docker compose up -d
```
PostgreSQL runs on port `5433` (credentials: `library` / `library`).

### 2. Run API Server
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8888
```
- **Interactive Swagger Docs:** [http://localhost:8888/docs](http://localhost:8888/docs)
- **Health Check:** `curl http://localhost:8888/health`

### 3. Run Test Suite
```bash
pip install -r requirements-dev.txt
PGPASSWORD=library psql -h 127.0.0.1 -p 5433 -U library -d library -c "CREATE DATABASE library_test;"
pytest -v
```
*All 37 test cases validate business rules, validation errors, and concurrent race conditions.*

---

## 🛠️ Key CLI Commands

```bash
# Bulk-seed 4,000,000 unique books via asyncpg COPY (~28 seconds):
python3 scripts/seed_unique_books.py --count 4000000 --truncate

# Build performance indexes (partial index + trigram GIN):
PGPASSWORD=library psql -h 127.0.0.1 -p 5433 -U library -d library -f scripts/indexes.sql

# Run 1,000-request search benchmark:
python3 scripts/benchmark_search.py --count 1000 --concurrency 8 \
    --output-img docs/benchmarks/search_4m_indexed.png \
    --output-json docs/benchmarks/search_4m_indexed.json

# Live race-condition & rental verification against running server:
python3 scripts/verify_live_rental_flow.py
```

---

<div align="center">
  <sub>Built with FastAPI, SQLModel, asyncpg, and PostgreSQL 16. Detailed reports in <a href="docs/">docs/</a>.</sub>
</div>
