-- Migration: Add quantity column to books table
ALTER TABLE books ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 1;
