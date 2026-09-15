# Ketabdari (کتابداری) — Library Management API

API ماژولار و بهینه‌سازی‌شده مدیریت کتابخانه — مدیریت کاربران، کتاب‌ها و امانت (Rental) بر پایه FastAPI، SQLModel و PostgreSQL.

> 📈 **پرفورمنس و مقیاس‌پذیری میلیونی:** سیستم در مقیاس **۴,۰۰۰,۰۰۰ کتاب یکتا** بنچمارک شده است — با ایندکس‌های سه‌حرفی (Trigram GIN)، بازدهی جستجو **۱۹.۲× سریع‌تر** (از ۴,۱۰۰ms به ۲۱۳ms) و در صدک‌های بالا تا **۲۴.۵× سریع‌تر** شده است. جزئیات کامل: [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) و [`docs/TASKS_STATUS.md`](docs/TASKS_STATUS.md).

## استک
- **فریم‌ورک:** FastAPI + SQLModel + SQLAlchemy (Async) + asyncpg
- **دیتابیس:** PostgreSQL 16 (با اکستنشن `pg_trgm`)
- **تست‌ها:** pytest + pytest-asyncio + httpx (ASGI Transport) — ۳۷ تست پوشش کامل
- **ابزارهای بنچمارک:** Faker + Matplotlib + اسکریپت‌های اختصاصی ارزیابی زمان پاسخ‌دهی

## راه‌اندازی سریع
```bash
# ۱) اجرای دیتابیس با داکر
docker compose up -d

# ۲) محیط مجازی و نصب وابستگی‌ها
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8888
```
- مستندات خودکار (Swagger UI): `http://localhost:8888/docs`
- پورت دیتابیس محلی: `5433` (کاربر: `library`، پسورد: `library`، دیتابیس: `library`)

## اجرای تست‌ها
```bash
source .venv/bin/activate
pip install -r requirements-dev.txt

# ساخت دیتابیس تست (یکبار):
PGPASSWORD=library psql -h 127.0.0.1 -p 5433 -U library -d library -c "CREATE DATABASE library_test;"

# اجرای تمامی تست‌ها (۳۷ تست موفق):
pytest -v
```

## مشخصات اندپوینتها (Endpoints)

| Method | Path | توضیح |
|--------|------|-------|
| POST | `/users` | ایجاد کاربر جدید (`name`, `email`) |
| GET | `/users` | لیست کاربران با Pagination (`page`, `size`) |
| GET | `/users/{id}` | دریافت مشخصات کاربر |
| PATCH | `/users/{id}` | ویرایش مشخصات کاربر |
| DELETE | `/users/{id}` | حذف کاربر (در صورت داشتن رکورد امانت: `409`) |
| GET | `/users/{id}/rentals` | لیست امانت‌های یک کاربر (مسیر سریع Joined Tuple) |
| POST | `/books` | ایجاد کتاب جدید (`title`, `author`, `quantity`) |
| GET | `/books` | جستجو، صفحه‌بندی و مرتب‌سازی (`page`, `size`, `search`, `sort_by`, `order`/`sort_dir`) |
| GET | `/books/{id}` | دریافت مشخصات کتاب همراه با موجودی (`quantity`) |
| PATCH | `/books/{id}` | ویرایش عنوان، نویسنده یا موجودی کتاب |
| DELETE | `/books/{id}` | حذف کتاب (در صورت داشتن تاریخچه امانت: `409`) |
| POST | `/rentals` | ثبت امانت با قفل ردیف دیتابیس و کاهش موجودی (`user_id`, `book_id`, `due_date`) |
| GET | `/rentals` | لیست کل امانت‌ها با بازدهی بالا |
| GET | `/rentals/overdue` | لیست امانت‌های معوق (سریع با ایندکس جزئی و تبدیل مستقیم تاپل) |
| GET | `/rentals/{id}` | دریافت اطلاعات امانت |
| POST | `/rentals/{id}/return` | ثبت بازگشت کتاب همراه با افزایش اتمیک موجودی |

### قوانین بیزینس و کنترل همزمانی
- **کنترل موجودی کتابخانه:** امانت دادن کتاب منوط به داشتن موجودی فیزیکی (`quantity > 0`) است. در صورتی که تمام نسخه‌های یک کتاب به امانت رفته باشند (`quantity == 0`)، درخواست‌های جدید امانت با خطای `409 Conflict` رد می‌شوند.
- **قفل‌گذاری در سطح ردیف (Row-Level Locking):** هر دو فرآیند ثبت امانت (`POST /rentals`) و بازگشت کتاب (`POST /rentals/{id}/return`) داخل یک تراکنش اختصاصی و با دستور `SELECT ... FOR UPDATE` در سطح ردیف اجرا می‌شوند تا تحت بار همزمان و شدید، امکان امانت گرفتن بیش از موجودی (Race Condition) به صفر برسد و موجودی هرگز منفی نشود.
- **اعتبار سنجی تاریخ امانت:** فیلد `due_date` حتماً باید در زمان آینده باشد (`400`).
- **جلوگیری از بازگشت دوباره:** امانتی که قبلاً ثبت بازگشت شده است، قابل بازگشت مجدد نیست (`409`).
- **یکپارچگی مرجع:** کاربر یا کتابی که رکورد امانت ثبت‌شده دارد، قابل حذف فیزیکی نیست (`409`).
- **مرتب‌سازی منعطف:** در جستجوی کتاب‌ها، فیلتر مرتب‌سازی روی فیلدهای `id`، `created_at`، `title`، `name` و `quantity` با جهت‌های `asc` و `desc` پشتیبانی می‌شود و مقادیر نامعتبر با خطای `400` رد می‌شوند.

## بنچمارک و ارزیابی پرفورمنس

```bash
# اعمال مایگریشن اضافه کردن فیلد quantity (در صورت نیاز):
PGPASSWORD=library psql -h 127.0.0.1 -p 5433 -U library -d library -f scripts/migration_add_quantity.sql

# تولید ۴,۰۰۰,۰۰۰ کتاب یکتا با موجودی تصادفی (۰ تا ۱۰) از طریق COPY باینری در ~۲۸ ثانیه:
python3 scripts/seed_unique_books.py --count 4000000 --truncate

# اجرای بنچمارک جستجو قبل از ایندکس (۱,۰۰۰ ریکوئست با کوئری‌های متنوع):
python3 scripts/benchmark_search.py --count 1000 --concurrency 8 \
    --title "Search Benchmark: 4,000,000 Books (Before Indexing)" \
    --output-img docs/benchmarks/search_4m_unindexed.png \
    --output-json docs/benchmarks/search_4m_unindexed.json

# ساخت ایندکس‌های Trigram GIN در دیتابیس (کمتر از ۲۵ ثانیه):
PGPASSWORD=library psql -h 127.0.0.1 -p 5433 -U library -d library -f scripts/indexes.sql

# اجرای مجدد بنچمارک جستجو پس از ایندکس‌گذاری:
python3 scripts/benchmark_search.py --count 1000 --concurrency 8 \
    --title "Search Benchmark: 4,000,000 Books (After Trigram GIN Indexing)" \
    --output-img docs/benchmarks/search_4m_indexed.png \
    --output-json docs/benchmarks/search_4m_indexed.json

# ترسیم نمودارهای مقایسه‌ای:
python3 scripts/render_comparison_charts.py
```

گزارش کامل تحلیل و تصاویر بنچمارک:
- گزارش جامع مراحل ۱ تا ۴: [`docs/TASKS_STATUS.md`](docs/TASKS_STATUS.md)
- گزارش تحلیل پرفورمنس: [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)
- پوشه تصاویر و داده‌های بنچمارک: [`docs/benchmarks/`](docs/benchmarks/)
