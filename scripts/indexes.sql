-- Performance indexes for Ketabdari
-- Run once against the library database:
--   docker exec -i library_db psql -U library -d library < scripts/indexes.sql

-- 1) Partial index for /rentals/overdue
--    Only open (not returned) rentals are relevant; ordering by due_date
--    matches the endpoint's ORDER BY, so Postgres can walk the index directly.
CREATE INDEX IF NOT EXISTS idx_rentals_open_due
    ON rentals (due_date)
    WHERE returned_at IS NULL;

-- 2) Trigram indexes for case-insensitive substring search (ILIKE '%..%')
--    A plain B-tree index cannot serve '%term%' patterns.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_books_title_trgm
    ON books USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_books_author_trgm
    ON books USING gin (author gin_trgm_ops);

-- 3) Refresh planner statistics after bulk inserts
ANALYZE rentals;
ANALYZE books;
ANALYZE users;
