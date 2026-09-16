# Ketabdari (کتابداری) — Library Management API

سرویس مدیریت کتابخانه بر پایه FastAPI، SQLModel و PostgreSQL 16. شامل مدیریت کاربران، کاتالوگ کتاب‌ها، کنترل موجودی فیزیکی و امانت با تراکنش‌های همزمان امن.

## ویژگی‌ها
- **مدیریت کاربران و کتاب‌ها:** عملیات کامل CRUD، کنترل فیلتر و اعتبارسنجی داده‌ ها.
- **کنترل همزمانی موجودی:** ثبت امانت و بازگشت کتاب با قفل سطح ردیف (`SELECT ... FOR UPDATE`) داخل تراکنش اتمیک برای جلوگیری از Race Condition.
- **جستجو و صفحه‌ بندی:** جستجوی فازی روی عنوان و نویسنده با Trigram GIN ایندکس، صفحه‌بندی و مرتب‌سازی قطعی روی فیلدهای مختلف (`created_at`، `title`، `quantity`، `id`).
- **بهینه‌سازی کارایی:** حذف سربار ORM روی کوئری‌های جوین سنگین و سنجش عملکرد روی ۴,۰۰۰,۰۰۰ رکورد. گزارش کامل در [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md).

## پیش‌نیازها و راه‌ اندازی

```bash
# اجرای دیتابیس با داکر
docker compose up -d

# محیط مجازی و نصب وابستگی‌ها
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8888
```

- Swagger UI: `http://localhost:8888/docs`
- دیتابیس PostgreSQL: پورت `5433` (`library` / `library`)

## اجرای تست‌ ها

```bash
pip install -r requirements-dev.txt

# ساخت دیتابیس تست (یک‌بار)
docker exec -i library_db psql -U library -d library -c "CREATE DATABASE library_test;"

# اجرای تست‌ها
pytest
```

## مشخصات اندپوینت‌ ها

| متد | مسیر | شرح |
|---|---|---|
| POST | `/users` | ایجاد کاربر جدید |
| GET | `/users` | لیست کاربران (صفحه‌بندی) |
| GET / PATCH / DELETE | `/users/{id}` | دریافت، ویرایش و حذف کاربر (رد حذف در صورت وجود سابقه امانت: ۴۰۹) |
| GET | `/users/{id}/rentals` | لیست امانت‌های یک کاربر |
| POST | `/books` | ایجاد کتاب (`title`, `author`, `quantity`) |
| GET | `/books` | جستجو، صفحه‌بندی و مرتب‌سازی (`search`, `sort_by`, `order`, `page`, `size`) |
| GET / PATCH / DELETE | `/books/{id}` | دریافت، ویرایش موجودی و حذف کتاب |
| POST | `/rentals` | ثبت امانت با کنترل موجودی و قفل ردیف (`due_date` در آینده، موجودی > ۰) |
| GET | `/rentals` | لیست امانت‌ها |
| GET | `/rentals/overdue` | لیست امانت‌های معوق (بهینه‌شده بدون سربار ORM) |
| GET | `/rentals/{id}` | جزئیات امانت |
| POST | `/rentals/{id}/return` | ثبت بازگشت کتاب و افزایش موجودی |

## مستندات و بنچمارک‌ ها

تحلیل کامل عملکرد، مقایسه تأخیر قبل و بعد از ایندکس‌گذاری روی ۴ میلیون رکورد، نمودارها و جزئیات مدل همزمانی در مستند زیر در دسترس است:
- [گزارش عملکرد و معماری همزمانی (`docs/PERFORMANCE.md`)](docs/PERFORMANCE.md)
