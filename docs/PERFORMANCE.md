# Performance Optimization Report — Ketabdari

بهینهسازی عملکرد API با دیتای حجیم: **۳,۰۰۰ کاربر / ۱۰,۰۰۰ کتاب / ۲۰,۰۰۰ امانت (۵,۰۰۰ معوق)**

این سند کل فرایند را مستند میکند: متدولوژی، بنچمارک هر مرحله، تحلیل پروفایل، و نتایج نهایی.

---

## 📊 خلاصه نتایج

| Endpoint | قبل (p50) | بعد (p50) | بهبود |
|----------|----------:|----------:|:-----:|
| `GET /rentals/overdue` | 267.9ms | **77.0ms** | **3.5×** |
| `GET /books?search=...` | 15.8ms | **6.4ms** | **2.5×** |
| `GET /rentals` | 10.1ms | **6.5ms** | 1.6× |
| `GET /users/{id}/rentals` | 5.7ms | **4.1ms** | 1.4× |
| `GET /users` | 3.4ms | **2.9ms** | 1.2× |

> اندازهگیری روی p50 (میانه ۳۰ درخواست پس از ۵ warmup) روی همان ماشین. پایداری زیر بار ۲۰ کلاینت موازی هم تأیید شد.

---

## 🧪 متدولوژی

- **ابزار:** `bench.py` (در ریشه ریپو) — Python stdlib، بدون وابستگی
- **روش:** برای هر endpoint، ۵ درخواست warmup + ۳۰ درخواست اندازهگیری؛ گزارش mean/p50/p95/p99/max
- **دیتا:** `scripts/seed_bench.sql` — idempotent (بدون TRUNCATE؛ با re-run داده تکراری نمیسازد)
- **ایندکسها:** `scripts/indexes.sql`

```bash
# بازتولید کامل سناریو:
docker exec -i library_db psql -U library -d library < scripts/seed_bench.sql
docker exec -i library_db psql -U library -d library < scripts/indexes.sql
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8888 &
python3 bench.py http://localhost:8888 /tmp/bench.json
```

---

## 📈 جزئیات مراحل

### Baseline (قبل از هر تغییری)

| Endpoint | mean | p50 | p95 | p99 |
|----------|-----:|----:|----:|----:|
| GET /health | 0.6ms | 0.6ms | 0.6ms | 0.7ms |
| GET /users?page=1&size=100 | 3.3ms | 3.4ms | 4.5ms | 5.0ms |
| GET /users/1500 | 2.8ms | 2.8ms | 3.8ms | 4.3ms |
| GET /users/1500/rentals | 5.7ms | 5.7ms | 8.9ms | 9.6ms |
| GET /books?page=1&size=50 | 3.2ms | 3.1ms | 4.4ms | 5.6ms |
| GET /books?search=clean | **14.8ms** | **15.8ms** | 20.6ms | 21.0ms |
| GET /rentals?page=1&size=50 | 32.8ms | 10.1ms | 86.5ms | **609.1ms** |
| GET /rentals/overdue | **266.5ms** | **267.9ms** | 312.0ms | 312.2ms |

دو گلوگاه مشخص: `/rentals/overdue` (۲۶۸ms) و `/books?search=` (۱۶ms).

---

### Stage 1 — ایندکسهای دیتابیس

**تغییر:** `scripts/indexes.sql`

1. **ایندکس پارشیال** برای overdue — فقط رنتهای باز، مرتب بر اساس `due_date` (با ORDER BY اندپوینت همخوان است):

```sql
CREATE INDEX idx_rentals_open_due ON rentals (due_date) WHERE returned_at IS NULL;
```

2. **Trigram (GIN)** برای جستجوی substring — ایندکس B-tree ساده الگوی `'%term%'` را سرو نمیکند:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_books_title_trgm  ON books USING gin (title gin_trgm_ops);
CREATE INDEX idx_books_author_trgm ON books USING gin (author gin_trgm_ops);
```

**تأیید planner** (هر دو از index scan استفاده میکنند):

```
Limit -> Index Scan using idx_rentals_open_due
          Index Cond: (due_date < now())

Bitmap Heap Scan on books
  -> Bitmap Index Scan on idx_books_title_trgm
```

**نتیجه:**

| Endpoint | قبل | بعد | بهبود |
|----------|----:|----:|:-----:|
| GET /books?search=clean | 15.8ms | 5.0ms | 3.2× |
| GET /rentals/overdue | 267.9ms | 269.0ms | — ❗ |

> 💡 **درس مهم:** ایندکس overdue هیچ تغییری نداد! `EXPLAIN` نشان میداد کوئری فقط ۱.۴ms طول میکشد — یعنی گلوگاه اصلاً دیتابیس نبود. مرحله بعد ضروری شد.

---

### Stage 2 — بازنویسی `/rentals/overdue` (join fast-path)

**ریشه مشکل — پروفایل گامبهگام:**

| عملیات | زمان |
|--------|-----:|
| کوئری ids-only (۵۰۰۰ سطر) | 51ms |
| ORM کامل (کد قدیم) | **202ms** |
| join tuples (بدون ORM) | 63ms |
| ساخت مدلهای pydantic | 32ms |
| pydantic dump | 24ms |

کد قدیم برای هر سطر **۳ آبجکت ORM** میساخت (۵۰۰۰ سطر = ۱۵,۰۰۰ آبجکت!) + ۲ کوئری اضافه `selectinload` میزد.

**کد جدید:**

```python
stmt = (
    select(
        Rental.id, Rental.user_id, Rental.book_id,
        Rental.due_date, Rental.returned_at, Rental.created_at,
        User.name.label("user_name"),
        Book.title.label("book_title"),
    )
    .join(User, Rental.user_id == User.id)
    .join(Book, Rental.book_id == Book.id)
    .where(Rental.returned_at.is_(None), Rental.due_date < _utcnow())
    .order_by(Rental.due_date)
)
rows = (await session.execute(stmt)).all()
return [_rental_out(r) for r in rows]   # row tuple -> pydantic مستقیم
```

**تله پرفورمنس که در همین مرحله کشف شد:** ابتدا `response_model_exclude_none=True` گذاشتیم و سرعت باز **۲۶۵ms** ماند! علت: این گزینه FastAPI را از مسیر سریع Rust core (pydantic v2) خارج و به `jsonable_encoder` پایتونی میبرد. حذف شد.

**همچنین اضافه شد:** پارامتر اختیاری `?limit=` (پیشفرض: بدون محدودیت — سازگار با عقب).

**نتیجه: 267.9ms → 77.0ms (3.5×)**

---

### Stage 3 — تعمیم fast-path به بقیه لیستها

همان الگوی join → tuple → pydantic برای:
- `GET /rentals` (+ سقف limit از ۵۰۰ به ۱۰,۰۰۰)
- `GET /users/{id}/rentals`

**نتیجه:** rentals 10.1→6.5ms، user-rentals 5.7→4.1ms

---

### Stage 4 — Connection Pool

**تغییر** (`app/db.py`):

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,        # 5 → 20 اتصال دائم
    max_overflow=10,     # تا ۳۰ اتصال در پیک
    pool_pre_ping=True,  # اتصال مرده قبل از استفاده چک میشود
)
```

**تست همزمانی (۲۰ کلاینت موازی × ۳ دور):**

| Endpoint | 1 کلاینت | ۲۰ کلاینت موازی |
|----------|---------:|----------------:|
| /rentals/overdue | 83ms | 1219ms (پایدار، بدون خطا) |
| /books?search= | 5.7ms | 51.4ms |
| /users | 2.9ms | 29.5ms |

---

## 🧪 صحت عملکرد

- **۲۸/۲۸ تست pytest** پس از هر مرحله پاس شد — هیچ رفتار Business Logic عوض نشد.
- خروجی JSON اندپوینتها byte-to-byte همان ساختار قبلی است (فیلدهای user/book بریبشده).
- `scripts/indexes.sql` و `scripts/seed_bench.sql` هر دو idempotent هستند.

---

## 🔮 گامهای بعدی پیشنهادی (انجامنشده)

1. **Pagination برای `/rentals/overdue`** — با ۵۰۰۰ رکورد و ~۱.۲MB پاس، فیزیک پاسخ حدود ۷۰ms کف دارد (کوئری فقط ۱۰ms است؛ بقیه ساخت/انتقال پاسخ). اگر کلاینتها کل لیست را نمیخواهند، `limit` پیشفرض یا page/size هزینه را به ~۱۰ms میرساند.
2. **کش count** برای `/books` اگر تعداد رکورد خیلی بزرگ شود (count روی subquery).
3. **GZip middleware** — پاسخهای ۱.۲MB متنی، با gzip حدود ۱۰-۱۵ برابر کوچک میشوند.
4. **HTTP/2 + uvloop** — نصب `uvicorn[standard]` (شامل uvloop و httptools) معمولاً ۲۰-۳۰٪ به throughput اضافه میکند.
5. **OpenTelemetry / query counting** — برای رصد N+1های احتمالی آینده.
