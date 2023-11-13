-- Update pg_bin_path_string
update clup_settings set content = '/usr/csupg-*/bin,/usr/pgsql-*/bin,/usr/polar*/bin',describe = '数据库软件目录'
where key = 'pg_bin_path_string';

-- Delete discard tables
DROP TABLE IF EXISTS csu_right;
DROP TABLE IF EXISTS csu_role_right;

-- Delete discard settings
DELETE FROM clup_settings WHERE key = 'cstlb_token';