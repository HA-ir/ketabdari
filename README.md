# Ketabdari (کتابداری) — Library Management API

API ساده و ماژولار مدیریت کتابخانه — مدیریت کاربران، کتاب‌ها و امانت (Rental) بر پایه FastAPI و PostgreSQL.

## استک
- FastAPI + SQLModel + SQLAlchemy (Async) + asyncpg
- PostgreSQL 16 (docker-compose)
- تست‌ها: pytest + pytest-asyncio + httpx (ASGI Transport)

## راه‌ اندازی سریع
```bash
# ۱) اجرای دیتابیس
docker compose up -d

# ۲) محیط مجازی و نصب وابستگی‌ها
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8888
```
- مستندات خودکار (Swagger): `http://localhost:8888/docs`
- دیتابیس روی پورت `5433` در دسترس است.

## اجرای تست‌ها
```bash
.venv/bin/pip install -r requirements-dev.txt
# ساخت دیتابیس تست (یکبار):
docker exec -i library_db psql -U library -c 'CREATE DATABASE library_test;'
.venv/bin/pytest -v
```

## Endpoints

| Method | Path | توضیح |
|--------|------|-------|
| POST | `/users` | ایجاد کاربر جدید |
| GET | `/users` | لیست کاربران (Pagination) |
| GET | `/users/{id}` | دریافت اطلاعات کاربر |
| PATCH | `/users/{id}` | ویرایش مشخصات کاربر |
| DELETE | `/users/{id}` | حذف کاربر (در صورت داشتن رکورد امانت: `409`) |
| GET | `/users/{id}/rentals` | لیست امانت‌های یک کاربر |
| POST | `/books` | ایجاد کتاب جدید |
| GET | `/books` | جستجو و لیست کتاب‌ها (`page`, `size`, `search`) |
| GET | `/books/{id}` | دریافت اطلاعات کتاب |
| PATCH | `/books/{id}` | ویرایش اطلاعات کتاب |
| DELETE | `/books/{id}` | حذف کتاب (در صورت داشتن رکورد امانت: `409`) |
| POST | `/rentals` | ثبت امانت جدید (`user_id`, `book_id`, `due_date`) |
| GET | `/rentals` | لیست کل امانت‌ها |
| GET | `/rentals/overdue` | لیست امانت‌های معوق (گذشته از `due_date` و بازگردانده‌نشده) |
| GET | `/rentals/{id}` | دریافت اطلاعات امانت |
| POST | `/rentals/{id}/return` | ثبت بازگشت کتاب |

### قوانین بیزینس
- فیلد `due_date` باید در زمان آینده باشد (`400`).
- کتابی که در حال حاضر به امانت رفته، مجدداً قابل امانت دادن نیست (`409`).
- امانتی که قبلاً بازگردانده شده، دوباره قابل بازگشت نیست (`409`).
- کاربر یا کتابی که تاریخچه امانت دارد، حذف فیزیکی نمی‌شود (`409`).
