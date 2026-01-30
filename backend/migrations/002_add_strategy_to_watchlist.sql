-- Migration to add strategy column to watchlist
ALTER TABLE watchlist ADD COLUMN strategy TEXT;
