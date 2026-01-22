-- Migration: Add manual_price columns to argentina_positions
-- Run this on your Railway PostgreSQL database

ALTER TABLE argentina_positions 
ADD COLUMN IF NOT EXISTS manual_price FLOAT DEFAULT NULL;

ALTER TABLE argentina_positions 
ADD COLUMN IF NOT EXISTS manual_price_updated_at TIMESTAMP DEFAULT NULL;

-- Verify the changes
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'argentina_positions' 
ORDER BY ordinal_position;
