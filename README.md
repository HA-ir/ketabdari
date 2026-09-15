<div align="center">

# 📚 Ketabdari (کتابداری)
### High-Performance, Concurrency-Safe Library Management API

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLModel](https://img.shields.io/badge/SQLModel-Async-blue?logo=pydantic&logoColor=white)](https://sqlmodel.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%28pg__trgm%29-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Asyncpg](https://img.shields.io/badge/Driver-asyncpg-informational)](https://github.com/MagicStack/asyncpg)
[![Tests](https://img.shields.io/badge/Tests-37%20Passed-success?logo=pytest&logoColor=white)](tests/test_api.py)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<p align="center">
  A production-grade, asynchronous REST API for library operations engineered for scale. Built with FastAPI, SQLModel, asyncpg, and PostgreSQL 16 with pg_trgm trigram acceleration.
</p>

[Key Features](#-key-features) •
[Benchmarks & Performance](#-benchmarks--performance-at-scale) •
[Documentation](#-documentation-index) •
[Quick Start](#-quick-start) •
[API Reference](#-api-reference) •
[Concurrency & Locking](#-concurrency--row-level-locking)

---

</div>

## 🌟 Key Features

- **🚀 Extreme Scale Search:** Substring search benchmarked across **4,000,000 unique books**, achieving **19.2× throughput improvement** and **24.5× lower tail latency (p95)** via PostgreSQL Trigram GIN indexes (`pg_trgm`).
- **🔒 Race-Condition Proof:** Physical inventory tracking (`quantity`) secured by PostgreSQL **Row-Level Locking (`SELECT ... FOR UPDATE`)** inside atomic transactions (`async with session.begin():`), ensuring zero stock over-allocation under concurrent bursts.
- **⚡ Zero-ORM Fast-Path Join Serialization:** Heavy join queries (`/rentals/overdue`, `/rentals`, `/users/{id}/rentals`) utilize direct row tuple streaming into Pydantic models, eliminating thousands of intermediate ORM object allocations and saving over **200ms per request**.
- **🔍 Composable Search, Sorting & Pagination:** Multi-field sorting (`created_at`, `title`, `name`, `quantity`, `id`) with strict whitelist validation, composite ordering for deterministic pagination, and case-insensitive substring filtering.
- **🧪 100% Verified Concurrency:** Comprehensive test suite with **37 passing tests**, including simultaneous multi-client race tests (`asyncio.gather`), validating transactional isolation and stock non-negativity.

---

## 📊 Benchmarks & Performance at Scale

The system has been profiled and benchmarked across two distinct dataset regimes:
1. **Prior Optimization Baseline:** 3,000 users / 10,000 books / 20,000 rentals (overdue join endpoint optimized by **3.5×**).
2. **Million-Scale Benchmark:** **4,000,000 unique books** evaluated with 1,000 varied search requests under concurrent load (`concurrency=8`).

### 4,000,000 Books Search Benchmark: Before vs. After Indexing

The search filter evaluates `WHERE (title ILIKE '%term%') OR (author ILIKE '%term%')`. Standard B-tree indexes cannot index substring matches with leading wildcards. Applying GIN inverted indexes with `gin_trgm_ops` converts full-table sequential scans into high-speed `Bitmap Index Scans`.

<div align="center">
  <img src="docs/benchmarks/search_comparison_4m.png" alt="Search Latency Comparison on 4M Books" width="920"/>
</div>

#### Latency & Throughput Metrics (4,000,000 Books)

| Metric | Before Indexing (Seq Scan) | After Indexing (Trigram GIN) | Improvement Factor |
|---|---|---|:---:|
| **Throughput (RPS)** | 1.95 req/s | **37.40 req/s** | **19.2× faster** |
| **Mean Latency** | 4,100.24 ms | **213.16 ms** | **19.2× faster** |
| **Min Latency** | 1,075.69 ms | **3.31 ms** | **325× faster** |
| **p25 Latency** | 1,709.89 ms | **10.43 ms** | **164× faster** |
| **p50 Latency (Median)** | 1,967.21 ms | **249.92 ms** | **7.9× faster** |
| **p75 Latency** | 6,946.56 ms | **291.24 ms** | **23.9× faster** |
| **p95 Latency (Tail)** | 9,175.42 ms | **374.47 ms** | **24.5× faster** |
| **p99 Latency (Tail)** | 12,034.22 ms | **525.86 ms** | **22.9× faster** |
| **Max Latency** | 12,972.22 ms | **7,133.72 ms** | **1.8× faster** |

<div align="center">
  <img src="docs/benchmarks/search_4m_indexed.png" alt="4M Books Indexed Benchmark Report" width="750"/>
</div>

> 💡 **Architectural Tradeoff (Small vs. Large Scale):**
> At 1,000 books, sequential memory scan (`p50: 11.96 ms`) is marginally faster than GIN index traversal (`p50: 13.18 ms`) due to trigram parsing overhead in tiny in-memory working sets. At 4,000,000 books, however, GIN trigram indexing provides a massive **8× to 25× latency drop**.
> See [`docs/benchmarks/search_comparison_1k.png`](docs/benchmarks/search_comparison_1k.png) for the 1k dataset comparative chart.

---

## 📖 Documentation Index

| Document | Description |
|---|---|
| 📑 [**`docs/TASKS_STATUS.md`**](docs/TASKS_STATUS.md) | Full audit report, broken-vs-fixed analysis, row-locking implementation, and benchmark summaries for Tasks 1–4. |
| ⚡ [**`docs/PERFORMANCE.md`**](docs/PERFORMANCE.md) | In-depth engineering report documenting Stage 1–5 optimizations, ORM profiling, connection pool tuning, and EXPLAIN plans. |
| 🖼️ [**`docs/benchmarks/`**](docs/benchmarks/) | Raw benchmark telemetry (`.json`) and high-resolution chart renders (`.png`). |
| 🛠️ [**`scripts/`**](scripts/) | Production-ready utility scripts for seeding, database migration, and automated load testing. |

---

## 🔒 Concurrency & Row-Level Locking

In high-concurrency environments, naive checks like `SELECT quantity` followed by `UPDATE quantity` suffer from race conditions where multiple requests read the last available copy and decrement it below zero.

Ketabdari enforces pessimistic row-level locking via PostgreSQL `SELECT ... FOR UPDATE`:

```python
# app/routers/rentals.py
async with session.begin():
    # 1. Pessimistic row-lock on target book
    stmt = select(Book).where(Book.id == payload.book_id).with_for_update()
    book = (await session.exec(stmt)).first()

    # 2. Strict inventory guard
    if book.quantity <= 0:
        raise HTTPException(status_code=409, detail="Book is out of stock")

    # 3. Decrement inventory & create rental record atomically
    book.quantity -= 1
    session.add(book)
    session.add(Rental(user_id=payload.user_id, book_id=payload.book_id, due_date=payload.due_date))
```

- When multiple clients race for the last remaining copy, PostgreSQL serializes access at the row level.
- The first transaction decrements `quantity` from 1 to 0 and commits.
- The waiting transactions acquire the lock immediately upon commit, observe `quantity == 0`, and are safely rejected with `HTTP 409 Conflict`.
- Verified live with concurrent test requests in `scripts/verify_live_rental_flow.py` and unit tests in `tests/test_api.py`.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+ / 3.12+
- Docker & Docker Compose

### 1. Launch PostgreSQL Container
```bash
docker compose up -d
```
The database container (`library_db`) runs PostgreSQL 16 on host port `5433` (credentials: `library` / `library`).

### 2. Install Dependencies & Start API
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install application dependencies
pip install -r requirements.txt

# Launch FastAPI server with Uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8888
```
- **Interactive Swagger Docs:** [http://localhost:8888/docs](http://localhost:8888/docs)
- **ReDoc:** [http://localhost:8888/redoc](http://localhost:8888/redoc)
- **Health Check:** `curl http://localhost:8888/health`

### 3. Run Test Suite
```bash
pip install -r requirements-dev.txt

# Create dedicated test database (once):
PGPASSWORD=library psql -h 127.0.0.1 -p 5433 -U library -d library -c "CREATE DATABASE library_test;"

# Execute all 37 test cases:
pytest -v
```

---

## ⚡ Reproducing Benchmarks & Seeding

### High-Speed Seeding (4,000,000 Unique Books)
Uses `asyncpg` native binary `COPY` protocol to stream records directly into PostgreSQL:
```bash
# Seeds 4M unique books with random quantities 0-10 in ~28 seconds:
python3 scripts/seed_unique_books.py --count 4000000 --truncate
```

### Applying Performance Indexes
```bash
# Applies partial index for overdue loans and GIN trigram indexes for search:
PGPASSWORD=library psql -h 127.0.0.1 -p 5433 -U library -d library -f scripts/indexes.sql
```

### Running the Search Benchmark
```bash
# Sends 1,000 varied requests (hits, partial matches, misses) with concurrency=8:
python3 scripts/benchmark_search.py --count 1000 --concurrency 8 \
    --title "Search Benchmark: 4,000,000 Books" \
    --output-img docs/benchmarks/search_4m_indexed.png \
    --output-json docs/benchmarks/search_4m_indexed.json
```

### Live Concurrency & Rental Flow Verification
```bash
# Runs end-to-end race condition & inventory lifecycle test against running server:
python3 scripts/verify_live_rental_flow.py
```

---

## 📡 API Reference

### Books (`/books`)

| Method | Endpoint | Query Parameters | Description | Status Codes |
|---|---|---|---|:---:|
| `POST` | `/books` | — | Create a book (`title`, `author`, `quantity`) | `201`, `422` |
| `GET` | `/books` | `page`, `size`, `search`, `sort_by`, `order`/`sort_dir` | List, search, paginate, and sort books | `200`, `400` |
| `GET` | `/books/{id}` | — | Retrieve book details and current quantity | `200`, `404` |
| `PATCH` | `/books/{id}` | — | Partially update title, author, or quantity | `200`, `404`, `422` |
| `DELETE` | `/books/{id}` | — | Delete book (rejected if rental history exists) | `204`, `404`, `409` |

**Allowed `sort_by` fields:** `id`, `created_at`, `title`, `name` (alias for title), `quantity`, `author`.  
**Allowed `order`/`sort_dir` values:** `asc`, `desc`.

### Users (`/users`)

| Method | Endpoint | Query Parameters | Description | Status Codes |
|---|---|---|---|:---:|
| `POST` | `/users` | — | Register a user (`name`, `email`) | `201`, `422` |
| `GET` | `/users` | `page`, `size` | Paginated user listing | `200` |
| `GET` | `/users/{id}` | — | Retrieve user profile | `200`, `404` |
| `PATCH` | `/users/{id}` | — | Update user details | `200`, `404`, `422` |
| `DELETE` | `/users/{id}` | — | Delete user (rejected if active/past rentals exist) | `204`, `404`, `409` |
| `GET` | `/users/{id}/rentals` | — | List all rentals for a specific user | `200`, `404` |

### Rentals (`/rentals`)

| Method | Endpoint | Query Parameters | Description | Status Codes |
|---|---|---|---|:---:|
| `POST` | `/rentals` | — | Rent a book (`user_id`, `book_id`, `due_date`) with row-level lock | `201`, `400`, `404`, `409` |
| `GET` | `/rentals` | `limit` | High-speed list of all rentals | `200` |
| `GET` | `/rentals/overdue` | `limit` | Filter unreturned rentals past due date (indexed) | `200` |
| `GET` | `/rentals/{id}` | — | Retrieve rental record with user/book brief | `200`, `404` |
| `POST` | `/rentals/{id}/return` | — | Return book and increment inventory under row-level lock | `200`, `404`, `409` |

---

## 🛡️ Business Rules Summary

1. **Future Due Date:** `due_date` must be strictly in the future (`400 Bad Request`).
2. **Physical Stock Requirement:** A book can only be rented if `quantity > 0`. If `quantity == 0`, new requests receive `409 Conflict`.
3. **Pessimistic Concurrency:** Concurrent requests for the same book are serialized using `with_for_update()`.
4. **Single Return Enforced:** A rental that has already been returned cannot be returned again (`409 Conflict`).
5. **Referential Integrity Protection:** Users or books with rental records cannot be deleted (`409 Conflict`).
6. **Strict Sort Validation:** Unrecognized sort fields or invalid directions return clean `400 Bad Request` responses.

---

<div align="center">
  <sub>Built with ❤️ using FastAPI, SQLModel, and PostgreSQL 16.</sub>
</div>
