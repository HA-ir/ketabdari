-- Performance indexes for Ketabdari
-- Run against the library database:
--   docker exec -i library_db psql -U library -d library < scripts/indexes.sql

SET maintenance_work_mem = '1GB';
SET max_parallel_maintenance_workers = 4;

-- 1) Partial index for /rentals/overdue
CREATE INDEX IF NOT EXISTS idx_rentals_open_due
    ON rentals (due_date)
    WHERE returned_at IS NULL;

-- 2) Trigram indexes for case-insensitive substring search (ILIKE '%..%')
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_books_title_trgm
    ON books USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_books_author_trgm
    ON books USING gin (author gin_trgm_ops);

-- 3) Refresh planner statistics after bulk inserts
ANALYZE rentals;
ANALYZE books;
ANALYZE users;
