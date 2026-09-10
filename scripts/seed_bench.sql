-- Benchmark seed data for Ketabdari
-- Idempotent (safe to re-run, no TRUNCATE/DELETE).
--   docker exec -i library_db psql -U library -d library < scripts/seed_bench.sql
--
-- Produces: 3,000 users / 10,000 books / 20,000 rentals (5,000 overdue)

-- 3,000 users
INSERT INTO users (name, email, created_at)
SELECT
  'User ' || g,
  'bench_user' || g || '@example.com',
  NOW() - (g || ' hours')::interval
FROM generate_series(1, 3000) g
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'bench_user' || g || '@example.com');

-- 10,000 books (titles composed from word lists)
INSERT INTO books (title, author, created_at)
SELECT
  (ARRAY['Clean','Pragmatic','Design','Domain','Refactoring','Distributed','Systems',
         'Algorithms','Patterns','Architecture','Python','Rust','Go','Kubernetes',
         'Networks','Databases','Compilers','Crypto','Graphics','Operating'])[1 + (g % 20)]
  || ' ' || (ARRAY['Code','Data','Thinking','Engineering','Handbook','Guide',
                   'Primer','Course','Notes','Manual'])[1 + (g % 10)]
  || ' #' || g,
  'Author ' || (1 + (g % 500)),
  NOW() - (g || ' minutes')::interval
FROM generate_series(1, 10000) g;

-- 5,000 OVERDUE rentals (due in the past, not returned)
INSERT INTO rentals (user_id, book_id, due_date, returned_at, created_at)
SELECT
  (SELECT min(id) FROM users) + (g % 3000),
  (SELECT min(id) FROM books) + (g % 10000),
  NOW() - INTERVAL '3 days', NULL, NOW() - INTERVAL '10 days'
FROM generate_series(1, 5000) g;

-- 10,000 returned rentals (history)
INSERT INTO rentals (user_id, book_id, due_date, returned_at, created_at)
SELECT
  (SELECT min(id) FROM users) + (g % 3000),
  (SELECT min(id) FROM books) + (g % 10000),
  NOW() - INTERVAL '20 days', NOW() - INTERVAL '25 days', NOW() - INTERVAL '30 days'
FROM generate_series(5001, 15000) g;

-- 5,000 active rentals (due in the future)
INSERT INTO rentals (user_id, book_id, due_date, returned_at, created_at)
SELECT
  (SELECT min(id) FROM users) + (g % 3000),
  (SELECT min(id) FROM books) + (g % 10000),
  NOW() + INTERVAL '7 days', NULL, NOW() - INTERVAL '2 days'
FROM generate_series(15001, 20000) g;
