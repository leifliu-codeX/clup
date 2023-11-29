-- Add clup_pg_settings table
CREATE TABLE IF NOT EXISTS clup_pg_settings AS SELECT * FROM pg_settings;

-- Add columns for clup_pg_settings
ALTER TABLE clup_pg_settings ADD COLUMN IF NOT EXISTS pg_version integer;

-- Update info
UPDATE clup_pg_settings SET pg_version = 12;

-- Add primary key
ALTER TABLE clup_pg_settings ADD primary KEY (name, pg_version);