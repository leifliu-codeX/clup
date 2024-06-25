-- Add clup_pg_settings table
CREATE TABLE IF NOT EXISTS clup_pg_settings AS SELECT * FROM pg_settings;

-- Add columns for clup_pg_settings
ALTER TABLE clup_pg_settings ADD COLUMN IF NOT EXISTS pg_version integer DEFAULT 12;

-- Add primary key
DO LANGUAGE plpgsql
$BODY$BEGIN
    perform 1 FROM information_schema.table_constraints where constraint_type = 'PRIMARY KEY' AND table_name= 'clup_pg_settings';
    if not found then
        ALTER TABLE clup_pg_settings ADD PRIMARY KEY (name, pg_version);
    end if;
END
$BODY$;
