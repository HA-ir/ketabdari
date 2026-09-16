# Performance & Architecture Optimization Report — Ketabdari

این سند مستندسازی کامل تحلیل عملکرد، پروفایلینگ کوئری‌ها، بهینه‌سازی مدل همزمانی و نتایج بنچمارک در دو رژیم دیتای مختلف را ارائه می‌دهد:
۱. **مقیاس متوسط (۱۰,۰۰۰ کتاب / ۳,۰۰۰ کاربر / ۲۰,۰۰۰ امانت):** بازنویسی مسیرهای ORM و بهینه‌سازی کوئری‌های جوین سنگین (`/rentals/overdue`).
۲. **مقیاس میلیونی (۴,۰۰۰,۰۰۰ کتاب یکتا):** ارزیابی جستجوی متنی با ایندکس‌های Trigram GIN، مدیریت قفل ردیف برای همزمانی و صفحه‌بندی مقیاس‌پذیر.

---

## 📊 خلاصه نتایج کلی

| Endpoint | قبل (p50) | بعد (p50) | بهبود |
|----------|----------:|----------:|:-----:|
| `GET /rentals/overdue` (۱۰k دیتا) | 267.9ms | **77.0ms** | **3.5×** |
| `GET /books?search=...` (۱۰k دیتا) | 15.8ms | **6.4ms** | **2.5×** |
| `GET /books?search=...` (۴M دیتا - ۱k ریکوئست) | 1,967.2ms | **249.9ms** | **7.9× (p50) / 19.2× (Mean)** |
| `GET /rentals` | 10.1ms | **6.5ms** | 1.6× |
| `GET /users/{id}/rentals` | 5.7ms | **4.1ms** | 1.4× |
| `GET /users` | 3.4ms | **2.9ms** | 1.2× |

---

## 🧪 ابزارها و متدولوژی تست

- **بنچمارک اندپوینت‌های عمومی:** `bench.py` — سنجش میانگین، p50، p95، p99 و max.
- **تولید داده‌های میلیونی:** `scripts/seed_unique_books.py` — تولید ۴,۰۰۰,۰۰۰ عنوان کتاب ۱۰۰٪ یکتا همراه با موجودی تصادفی (`۰` تا `۱۰`) و درج مستقیم با پروتکل باینری COPY در ~۲۸ ثانیه.
- **بنچمارک ارزیابی جستجو:** `scripts/benchmark_search.py` — اجرای ۱,۰۰۰ ریکوئست جستجوی متنوع با توزیع واقع‌گرایانه (۴۵٪ کلمات موجود، ۲۵٪ پیشوندهای ناقص، ۳۰٪ کلمات ناموجود برای ارزیابی رفتارهای hit و miss) تحت همزمانی ۸ کلاینت موازی.
- **تست یکپارچگی همزمانی:** `scripts/verify_live_rental_flow.py` — ارسال ریکوئست‌های مسابقه‌ای همزمان برای بررسی قفل ردیف (`SELECT ... FOR UPDATE`).

---

## 📈 جزئیات مراحل بهینه‌سازی

### Stage 1 — ایندکس‌گذاری پایه
**تغییر:** `scripts/indexes.sql`

۱. **ایندکس پارشیال** برای امانت‌های معوق (فقط رکوردهای باز که `returned_at IS NULL` است و مرتب‌شده بر اساس `due_date`):
```sql
CREATE INDEX idx_rentals_open_due ON rentals (due_date) WHERE returned_at IS NULL;
```

۲. **ایندکس Trigram (GIN)** برای جستجوی زیررشته (`ILIKE '%..%'`):
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_books_title_trgm  ON books USING gin (title gin_trgm_ops);
CREATE INDEX idx_books_author_trgm ON books USING gin (author gin_trgm_ops);
```

**نتیجه در دیتای ۱۰k:**
- جستجوی کتاب: 15.8ms → 5.0ms (۳.۲× سریع‌تر)
- اندپوینت overdue: 267.9ms → 269.0ms (بدون تغییر؛ کوئری سریع بود اما ساخت آبجکت‌های ORM در پایتون گلوگاه بود).

---

### Stage 2 — بازنویسی `/rentals/overdue` (حذف سربار ORM و مسیر سریع Join)

پروفایل مرحله‌به‌مرحله مشخص کرد ساخت ۱۵,۰۰۰ آبجکت ORM در پایتون برای ۵,۰۰۰ رکورد معوق بیش از ۲۰۰ میلی‌ثانیه زمان می‌برد:

| عملیات | زمان |
|--------|-----:|
| کوئری ids-only (۵۰۰۰ سطر) | 51ms |
| ORM کامل (کد قدیم) | **202ms** |
| join tuples مستقیم (بدون ORM) | 63ms |
| ساخت مدلهای pydantic | 32ms |
| serialization پاسخ | 24ms |

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
rows = (await session.exec(stmt)).all()
return [_rental_out(r) for r in rows]   # تبدیل مستقیم تاپل سطر به Pydantic
```

**نتیجه:** زمان پاسخ از **267.9ms به 77.0ms** کاهش یافت (**۳.۵× بهبود**).

---

### Stage 3 — تعمیم Fast-Path به سایر لیست‌ها

همان الگوی استخراج مستقیم تاپل از جوین برای اندپوینت‌های زیر پیاده‌سازی شد:
- `GET /rentals`
- `GET /users/{id}/rentals`

**نتیجه:** امانت‌ها از 10.1ms به 6.5ms و امانت‌های کاربر از 5.7ms به 4.1ms بهبود یافتند.

---

### Stage 4 — تنظیم Connection Pool

پیکربندی استخر اتصالات دیتابیس در `app/db.py`:
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,        # ۲۰ اتصال دائم
    max_overflow=10,     # تا ۳۰ اتصال در ترافیک بالا
    pool_pre_ping=True,  # بررسی سلامت اتصال پیش از واگذاری
)
```

زیر بار ۲۰ کلاینت همزمان، سیستم کاملاً پایدار و بدون قطعی پاسخ داد.

---

### Stage 5 — بنچمارک مقیاس بزرگ: ۴,۰۰۰,۰۰۰ کتاب (ایندکس Trigram GIN)

در مقیاس ۴ میلیون سطر، اسکن ترتیبی دیتابیس برای الگوهای `ILIKE '%term%'` به شدت کند است. برای بررسی دقیق، ۱,۰۰۰ درخواست متنوع جستجو با ۸ کلاینت موازی اجرا شد.

#### جدول مقایسه نتایج بنچمارک (۴,۰۰۰,۰۰۰ کتاب)

| پارامتر | قبل از ایندکس (Sequential Scan) | بعد از ایندکس (Trigram GIN) | ضریب بهبود |
|---|---|---|:---:|
| **Throughput (RPS)** | 1.95 req/s | **37.40 req/s** | **۱۹.۲ برابر** |
| **میانگین زمان پاسخ (Mean)** | 4,100.24 ms | **213.16 ms** | **۱۹.۲ برابر سریع‌تر** |
| **کمترین زمان (Min)** | 1,075.69 ms | **3.31 ms** | **۳۲۵ برابر سریع‌تر** |
| **صدک ۲۵ (p25)** | 1,709.89 ms | **10.43 ms** | **۱۶۴ برابر سریع‌تر** |
| **میانه (p50)** | 1,967.21 ms | **249.92 ms** | **۷.۹ برابر سریع‌تر** |
| **صدک ۷۵ (p75)** | 6,946.56 ms | **291.24 ms** | **۲۳.۹ برابر سریع‌تر** |
| **صدک ۹۵ (p95)** | 9,175.42 ms | **374.47 ms** | **۲۴.۵ برابر سریع‌تر** |
| **صدک ۹۹ (p99)** | 12,034.22 ms | **525.86 ms** | **۲۲.۹ برابر سریع‌تر** |
| **بیشترین زمان (Max)** | 12,972.22 ms | **7,133.72 ms** | **۱.۸ برابر** |

<div align="center">
  <img src="benchmarks/search_comparison_4m.png" alt="Search 4M Comparison" width="850"/>
  <p><em>مقایسه لگاریتمی تأخیر جستجو در ۴ میلیون کتاب قبل و بعد از ایندکس‌گذاری</em></p>
</div>

<div align="center">
  <img src="benchmarks/search_4m_indexed.png" alt="Search 4M Indexed Report" width="750"/>
  <p><em>گزارش متریک‌ها و توزیع تأخیر پس از اعمال ایندکس Trigram GIN</em></p>
</div>

#### مقایسه در مقیاس کوچک (۱,۰۰۰ کتاب)

| Metric | قبل از ایندکس | بعد از ایندکس | نسبت |
|---|---|---|:---:|
| Throughput | 613.35 req/s | 562.63 req/s | ~0.92× |
| Mean Latency | 12.82 ms | 13.98 ms | ~1.09× |
| p50 Latency | 11.96 ms | 13.18 ms | ~1.10× |
| p95 Latency | 20.10 ms | 20.46 ms | ~1.02× |
| p99 Latency | 26.68 ms | 33.18 ms | ~1.24× |

<div align="center">
  <img src="benchmarks/search_comparison_1k.png" alt="Search 1K Comparison" width="850"/>
</div>

> 💡 **تحلیل رفتار دیتابیس:** در جداول کوچک (۱k رکورد)، کل داده در حافظه RAM قرار دارد و هزینه اسکن ترتیبی زیر یک میلی‌ثانیه است؛ بنابراین سربار پردازش trigram و پیمایش درخت ایندکس در مقیاس‌های بسیار کوچک مزیتی ندارد. اما در مقیاس ۴ میلیون سطر، ایندکس GIN پردازش سنگین دیسک را حذف کرده و زمان پاسخ‌دهی را بیش از **۲۴ برابر** کاهش می‌دهد.

---

### Stage 6 — مدل همزمانی، کنترل موجودی فیزیکی و قفل ردیف دیتابیس

#### ریشه مشکل مسابقه در همزمانی (Race Condition)
پیش از این، امانت دادن کتاب بر اساس یک منطق بولی ساده انجام می‌شد که تنها بررسی می‌کرد آیا امانت بازگردانده‌نشده‌ای برای کتاب وجود دارد یا خیر. با اضافه شدن موجودی فیزیکی (`quantity: int`)، بدون قفل‌گذاری صریح، دو درخواست همزمان برای آخرین نسخه کتاب می‌توانستند همزمان موجودی ۱ را بخوانند، آن را کاهش دهند و موجودی را به عدد منفی برسانند.

#### پیاده‌سازی قفل سطح ردیف (`SELECT ... FOR UPDATE`)
فرآیند امانت و بازگشت با استفاده از `with_for_update()` داخل تراکنش بازنویسی شد:

```python
# app/routers/rentals.py
async with session.begin():
    # دریافت قفل روی ردیف کتاب
    stmt = select(Book).where(Book.id == payload.book_id).with_for_update()
    book = (await session.exec(stmt)).first()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book {payload.book_id} not found")

    if book.quantity <= 0:
        raise HTTPException(status_code=409, detail=f"Book {payload.book_id} is not available (out of stock)")

    # کاهش اتمیک موجودی
    book.quantity -= 1
    session.add(book)
    session.add(Rental(user_id=payload.user_id, book_id=payload.book_id, due_date=payload.due_date))
```

- در سناریوی همزمانی، اولین درخواست قفل را تصاحب کرده و موجودی را کاهش می‌دهد.
- درخواست‌های رقیب در صف قفل منتظر می‌مانند تا تراکنش اول `COMMIT` شود؛ سپس با خواندن `quantity == 0` با خطای معتبر `HTTP 409 Conflict` رد می‌شوند.
- در مسیر بازگشت (`POST /rentals/{id}/return`)، ردیف امانت و کتاب با قفل قفل‌گذاری شده و موجودی به صورت اتمیک افزایش می‌یابد.

---

### Stage 7 — صفحه‌بندی و مرتب‌سازی در جستجو

- **مرتب‌سازی منعطف:** افزودن پارامترهای `sort_by` و `order` / `sort_dir` روی فیلدهای `id`, `created_at`, `title`, `name`, `quantity`, `author`.
- **اعتبارسنجی ورودی:** درخواست‌های حاوی فیلد یا جهت نامعتبر با خطای صریح `400 Bad Request` رد می‌شوند.
- **ترتیب ترکیبی (Deterministic Ordering):** برای جلوگیری از جابجایی تکراری آیتم‌ها بین صفحات در فیلدهای غیریکتا (مثل موجودی یا تاریخ یکسان)، کوئری همیشه با کلید اولیه ترکیب می‌شود: `ORDER BY sort_column DESC, Book.id DESC`.
- **نکته در مورد صفحات عمیق در مقیاس ۴M:** در پجینیشن مبتنی بر آفست (`OFFSET n LIMIT m`)، برای صفحات بسیار دور (مثل صفحه ۱۰۰,۰۰۰)، دیتابیس باید تمام ردیف‌های ماقبل را شمارش کند. برای مقیاس‌های بسیار عمیق، استفاده از Keyset/Cursor Pagination گام منطقی بعدی است.

---

## 🧪 صحت عملکرد و تست‌ها

- **۳۷ تست خودکار:** تمامی تست‌ها در فایل `tests/test_api.py` شامل تست‌های همزمانی با `asyncio.gather`، تست‌های اعتبارسنجی مرتب‌سازی، تست‌های کاهش/افزایش موجودی و بیزینس لاجیک‌ها با موفقیت پاس شدند.
- **اسکریپت تست لایو:** فایل `scripts/verify_live_rental_flow.py` صحت قفل ردیف و مدل تراکنش را در محیط واقعی تایید می‌کند.
