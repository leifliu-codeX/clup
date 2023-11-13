CREATE TABLE IF NOT EXISTS clup_settings(
  key text PRIMARY KEY,
  content text
);

CREATE TABLE IF NOT EXISTS clup_cluster
(
    cluster_id   serial PRIMARY KEY,
    cluster_type int,
    cluster_data jsonb,
    state        int,
    lock_time    int
);


CREATE TABLE IF NOT EXISTS clup_db
(
    db_id         serial primary key,
    cluster_id    int,
    state         int,
    pgdata        text,
    is_primary    int,
    repl_app_name text,
    host          text,
    repl_ip       text
);


CREATE TABLE IF NOT EXISTS clup_host
(
    hid  serial primary key,
    ip   text,
    data jsonb
);


CREATE TABLE IF NOT EXISTS task
(
    task_id     serial PRIMARY KEY,
    cluster_id  integer,
    state       integer,
    task_type   varchar(50),
    task_name   varchar(100),
    create_time timestamptz default now(),
    last_msg    text
);

CREATE TABLE IF NOT EXISTS task_log
(
    seq         serial PRIMARY KEY,
    task_id     integer,
    log_level   integer,
    log         text,
    create_time timestamptz default now()
);

create type object_type as enum('unknown', 'host', 'db');


CREATE OR REPLACE FUNCTION f_pivot_time_bucket(a_bucket interval, a_tm timestamptz)
    RETURNS timestamptz
AS
$BODY$
declare
    v_bucket_seconds bigint;
    v_res timestamptz;
begin
    v_bucket_seconds = extract(epoch from a_bucket)::bigint;
    a_tm := a_tm + (a_bucket / 2);
    v_res = to_timestamp( (extract(epoch from a_tm)::bigint / v_bucket_seconds) *  v_bucket_seconds);
    return v_res;
end
$BODY$
    LANGUAGE plpgsql;


INSERT INTO clup_settings(key, content)
with t(key, content) as(
    VALUES('db_version', '1.0')
)
SELECT * FROM t WHERE NOT EXISTS
    (SELECT 1 FROM clup_settings o
      WHERE t.key=o.key)
;


CREATE TABLE IF NOT EXISTS clup_settings(
  key text PRIMARY KEY,
  content text
);
COMMENT ON TABLE clup_settings is '配置表';
COMMENT ON COLUMN clup_settings.key is '配置项';
COMMENT ON COLUMN clup_settings.content is '配置内容';

CREATE TABLE IF NOT EXISTS clup_general_task
(
    task_id     serial PRIMARY KEY,
    state       integer,
    task_type   varchar(50),
    task_name   varchar(100),
    task_data   jsonb,
    create_time timestamptz default now(),
    last_msg    text
);

CREATE TABLE IF NOT EXISTS clup_general_task_log
(
    seq         serial PRIMARY KEY,
    task_id     integer,
    log_level   integer,
    log         text,
    create_time timestamptz default now()
);


ALTER TABLE clup_db ADD COLUMN IF NOT EXISTS instance_name text;
ALTER TABLE clup_db ADD COLUMN IF NOT EXISTS db_detail jsonb;
ALTER TABLE clup_db ADD COLUMN IF NOT EXISTS db_state INT;
ALTER TABLE clup_db ADD COLUMN IF NOT EXISTS port INT;

UPDATE clup_db as d SET port = coalesce((c.cluster_data->>'port')::int, 0),
    db_detail = jsonb_build_object('db_user', cluster_data->>'ha_db_user', 'db_pass',cluster_data->>'ha_db_pass')
FROM clup_cluster as c WHERE d.cluster_id = c.cluster_id;


insert into clup_db (cluster_id, pgdata,port, db_detail, host, db_state, state, is_primary)  select * from
              (select cluster_id, cluster_data->'pgdata' as pgdata, (cluster_data->>'port')::int as port,jsonb_build_object('db_user',cluster_data->'ha_db_user', 'db_pass',cluster_data->'ha_db_pass') as db_detail
              from clup_cluster where cluster_type=2) as t1,
              (select (case (cluster_data->>'primary')::int when 1 then cluster_data->>'host1_ip' else  cluster_data->>'host2_ip' END )  as host, 1,1,1
              from clup_cluster where cluster_type = 2) AS t2;


CREATE OR REPLACE FUNCTION f_pivot_time_bucket(a_bucket interval, a_tm timestamptz)
    RETURNS timestamptz
AS
$BODY$
declare
    v_bucket_seconds bigint;
    v_res timestamptz;
begin
    v_bucket_seconds = extract(epoch from a_bucket)::bigint;
    a_tm := a_tm + (a_bucket / 2);
    v_res = to_timestamp( (extract(epoch from a_tm)::bigint / v_bucket_seconds) *  v_bucket_seconds);
    return v_res;
end
$BODY$
    LANGUAGE plpgsql;


ALTER TABLE clup_db ADD COLUMN IF NOT EXISTS  up_db_id INT;
ALTER TABLE clup_db ADD COLUMN IF NOT EXISTS scores INT;


UPDATE clup_db AS d1 SET up_db_id = d2.db_id FROM
                         (SELECT db_id,cluster_id
                             FROM clup_db INNER JOIN  clup_cluster USING (cluster_id)
                         WHERE is_primary = 1 AND cluster_type=1) AS d2
WHERE d1.cluster_id = d2.cluster_id AND d1.is_primary = 0;

update clup_db c1 set up_db_id=(select db_id from clup_db c2  where is_primary='1' and c2.cluster_id=c1.cluster_id ) where is_primary='0';




CREATE TABLE IF NOT EXISTS clup_init_db_conf
(
    setting_name  varchar(100) PRIMARY KEY,
    val           varchar(255),
    setting_type     INTEGER DEFAULT 0,  -- 1、常见的值， 2、off/on 3、需要单位的， 4、需要加引号,里面可以填多个值的
    unit          varchar(20),
    is_restart    int,
    notes         text
);
COMMENT ON TABLE clup_init_db_conf is '数据库初始化最佳配置表';
COMMENT ON COLUMN clup_init_db_conf.setting_name is '配置名称';
COMMENT ON COLUMN clup_init_db_conf.val is '配置值';
COMMENT ON COLUMN clup_init_db_conf.setting_type is '配置类型';
COMMENT ON COLUMN clup_init_db_conf.unit is '配置值单位';
COMMENT ON COLUMN clup_init_db_conf.is_restart is '修改是否需要重启数据库 1需要, 0不需要';
COMMENT ON COLUMN clup_init_db_conf.notes is '配置注释说明';

insert into clup_init_db_conf(setting_name, val, setting_type, unit, notes, is_restart)
                values
                  ('logging_collector', 'on', 2, null, 'Start a subprocess to capture stderr output and/or csvlogs into log files.', 1),
                  ('shared_buffers', '20', 5, 'MB', 'Sets the number of shared memory buffers used by the server', 1),  -- 特殊格式，在页面上放到最后, 一定要有这个配置
                  ('max_connections', '2000', 1, null, 'Sets the maximum number of concurrent connections', 1),
                  ('max_prepared_transactions', '2000', 1, null, 'Sets the maximum number of simultaneously prepared transactions', 1),
                  ('work_mem', '4', 3, 'MB', 'Sets the maximum memory to be used for query workspaces', 0),
                  ('maintenance_work_mem', '512', 3, 'MB', 'Sets the maximum memory to be used for maintenance operations.', 0),
                  ('autovacuum_work_mem', '512', 3, 'MB', 'Sets the maximum memory to be used by each autovacuum worker process', 0),
                  ('max_parallel_maintenance_workers', '6', 1, null, 'Sets the maximum number of parallel processes per maintenance operation', 0),
                  ('max_parallel_workers_per_gather', '0', 1, null, 'Sets the maximum number of parallel processes per executor node', 0),
                  ('max_parallel_workers', '32', 1, null, 'Sets the maximum number of parallel workers that can be active at one time', 0),
                  ('max_wal_size', '100', 3, 'GB', 'Sets the WAL size that triggers a checkpoint', 0),
                  ('min_wal_size', '8', 3, 'GB', 'Sets the minimum size to shrink the WAL to.', 0),
                  ('wal_keep_segments', '2048', 1, null, 'Sets the number of WAL files held for standby servers.', 0),
                  ('max_sync_workers_per_subscription', '8', 1, null, 'Maximum number of table synchronization workers per subscription.', 0),
                  ('effective_cache_size', '40', 3, 'GB', 'the planner''s assumption about the total size of the data caches.', 0),
                  ('autovacuum_max_workers', '10', 1, null, 'Sets the maximum number of simultaneously running autovacuum worker processes.', 1),
                  ('temp_file_limit', '20', 3, 'GB', 'Limits the total size of all temporary files used by each process.', 0),
--                   ('track_commit_timestamp', 'off', 2, null, 'track commit timestamp', 0), -- 1
--                   ('vacuum_defer_cleanup_age', '0', 1, null, 'vacuum defer cleanup age', 0), --1
                  ('commit_delay', '10', 1, null, 'Sets the delay in microseconds between transaction commit and flushing WAL to disk', 0),
                  ('log_destination', 'csvlog', 4, null, 'Sets the destination for server log output.', 0),
--                   ('log_directory', 'log', 4, null, '数据库日志收集目录', 0),  -- 1
                  ('log_truncate_on_rotation', 'on', 2, null, 'Truncate existing log files of same name during log rotation.', 0),
--                   ('log_rotation_age', '1', 3, 'd', 'log rotation age', 0),  -- 1
                  ('log_rotation_size', '100', 3, 'MB', 'Automatic log file rotation will occur after N kilobytes', 0),
                  ('log_checkpoints', 'on', 2, null, 'Logs each checkpoint', 0),
--                   ('log_connections', 'off', 2, null, 'log connections', 0),  -- 1
--                   ('log_disconnections', 'off', 2, null, 'log disconnections', 0),  --1
                  ('log_error_verbosity', 'verbose', 1, null, 'Sets the verbosity of logged messages', 0),
                  ('log_lock_waits', 'on', 2, null, 'Logs long lock waits', 0),
                  ('log_temp_files', '256', 3, 'MB', 'Log the use of temporary files larger than this number of kilobytes', 0),
--                   ('log_filename', 'postgresql-%Y-%m-%d_%H%M%S.log', 4, null, 'log filename', 0), -- 1
--                   ('log_min_error_statement', 'error', 4, null, 'log min error statement', 0),  --1
                  ('log_min_duration_statement', '5', 3, 's', 'Sets the minimum execution time above which statements will be logged', 0),
--                   ('log_duration', 'off', 2, null, 'log duration', 0),   --1
                  ('log_statement', 'ddl', 4, null, 'type of statements logged', 0),
                  ('log_autovacuum_min_duration', '0', 1, null, 'minimum execution time above which autovacuum actions will be logged.', 0),
                  ('statement_timeout', '3600000', 1, null, 'maximum allowed duration of any statement', 0),
                  ('archive_timeout', '10', 3, 'min', 'Forces a switch to the next WAL file if a new file has not been started within N seconds.', 0),
                  ('autovacuum_vacuum_cost_delay', '2', 3, 'ms', 'Vacuum cost delay in milliseconds, for autovacuum', 0),
                  ('autovacuum_vacuum_cost_limit', '-1', 1, null, 'Vacuum cost amount available before napping, for autovacuum', 0),
                  ('idle_in_transaction_session_timeout', '6', 3, 'h', 'maximum allowed duration of any idling transaction', 0),
                  ('random_page_cost', '1.1', 1, null, 'planner''s estimate of the cost of a nonsequentially fetched disk page', 0),
                  ('vacuum_cost_delay', '2', 3, 'ms', 'Vacuum cost delay in milliseconds.', 0),
                  ('vacuum_cost_limit', '2000', 1, null, 'Vacuum cost amount available before napping', 0),
                  ('enable_partitionwise_aggregate', 'on', 2, null, 'Vacuum cost amount available before napping', 0),
                  ('enable_partitionwise_join', 'on', 2, null, 'Enables partitionwise join', 0),

                    -- static
                  ('listen_addresses', '*', 4, null, 'Sets the host name or IP address(es) to listen to.', 1),
                  ('superuser_reserved_connections', '10', 1, null, 'superuser_reserved_connectionsSets the number of connection slots reserved for superusers.', 1),
                  ('unix_socket_directories', '/tmp', 4, null, 'Sets the directories where Unix-domain sockets will be created', 1),
                  ('tcp_keepalives_idle', '5', 1, null, 'Time between issuing TCP keepalives', 0),
                  ('tcp_keepalives_interval', '5', 1, null, 'Time between TCP keepalive retransmits', 0),
                  ('tcp_keepalives_count', '3', 1, null, 'Maximum number of TCP keepalive retransmits', 0),
--                   ('huge_pages', 'try', 1, null, 'huge pages', 0),  -- 1
--                   ('dynamic_shared_memory_type', 'posix', 1, null, 'dynamic_shared_memory_type', 0),  --1
                  ('bgwriter_delay', '10', 3, 'ms', 'Background writer sleep time between rounds.', 0),
                  ('bgwriter_lru_maxpages', '1000', 1, null, 'Background writer maximum number of LRU pages to flush per round', 0),
                  ('bgwriter_lru_multiplier', '10.0', 1, null, 'Multiple of the average buffer usage to free per round', 0),
--                   ('bgwriter_flush_after', '512', 3, 'KB', 'bgwriter_flush_after', 0),  --1
                  ('effective_io_concurrency', '0', 1, null, 'Number of simultaneous requests that can be handled efficiently by the disk subsystem', 0),
                  ('max_worker_processes', '256', 1, null, 'Maximum number of concurrent worker processes', 1),
--                   ('parallel_leader_participation', 'on', 2, null, 'parallel_leader_participation', 0),  --1
                  ('old_snapshot_threshold', '6', 3, 'h', 'Time before a snapshot is too old to read pages changed after the snapshot was taken', 1),
--                   ('wal_level', 'replica', 1, null, 'wal_level', 0),  --1
--                   ('synchronous_commit', 'on', 2, null, 'synchronous_commit', 0),  --i
--                   ('full_page_writes', 'on', 2, null, 'full_page_writes', 0),  --1
                  ('wal_compression', 'on', 2, null, 'Compresses full-page writes written in WAL file', 0),
--                   ('wal_buffers', '-1', 1, null, 'wal_buffers', 0),   --1
                  ('wal_writer_delay', '10', 3, 'ms', 'Time between WAL flushes performed in the WAL writer', 0),
--                   ('wal_writer_flush_after', '1', 3, 'MB', 'wal_writer_flush_after', 0),  --1
                  ('checkpoint_timeout', '15', 3, 'min', 'Sets the maximum time between automatic WAL checkpoints', 0),
--                   ('checkpoint_completion_target', '0.5', 1, null, 'checkpoint_completion_target', 0),  --1
                  ('checkpoint_flush_after', '1', 3, 'MB', 'Number of pages after which previously performed writes are flushed to disk', 0),
                  ('archive_mode', 'on', 2, null, 'Allows archiving of WAL files using archive_command', 1),
                  ('archive_command', '/bin/true', 4, null, 'Sets the shell command that will be called to archive a WAL file', 0),
                  ('max_wal_senders', '64', 1, null, 'Sets the maximum number of simultaneously running WAL sender processes', 1),
                  ('max_replication_slots', '64', 1, null, 'Sets the maximum number of simultaneously defined replication slots', 1),
                  ('hot_standby', 'on', 2, null, 'Allows connections and queries during recovery.', 1),
                  ('max_standby_archive_delay', '120', 3, 's', 'Sets the maximum delay before canceling queries when a hot standby server is processing archived WAL data', 0),
                  ('max_standby_streaming_delay', '120', 3, 's', 'Sets the maximum delay before canceling queries when a hot standby server is processing streamed WAL data', 0),
                  ('wal_receiver_status_interval', '1', 3, 's', 'Sets the maximum interval between WAL receiver status reports to the sending server', 0),
--                   ('hot_standby_feedback', 'off', 2, null, 'hot_standby_feedback', 0),   --i
                  ('max_logical_replication_workers', '64', 1, null, 'Maximum number of logical replication worker processes.', 1),
                  ('track_io_timing', 'on', 2, null, 'Collects timing statistics for database I/O activity', 0),
                  ('track_functions', 'all', 1, null, 'Collects function-level statistics on database activity', 0),
--                   ('autovacuum', 'on', 2, null, 'autovacuum', 0),  --1
--                   ('autovacuum_naptime', '1', 3, 'min', 'autovacuum_naptime', 0),  --1
                  ('autovacuum_vacuum_threshold', '500', 1, null, 'Minimum number of tuple updates or deletes prior to vacuum', 0),
                  ('autovacuum_analyze_threshold', '500', 1, null, 'Minimum number of tuple inserts, updates, or deletes prior to analyze', 0),
                  ('autovacuum_vacuum_scale_factor', '0.2', 1, null, 'Number of tuple updates or deletes prior to vacuum as a fraction of reltuples.', 0),
                  ('autovacuum_analyze_scale_factor', '0.1', 1, null, 'Number of tuple inserts, updates, or deletes prior to analyze as a fraction of reltuples', 0),
                  ('autovacuum_freeze_max_age', '1200000000', 1, null, 'Age at which to autovacuum a table to prevent transaction ID wraparound', 1),
                  ('autovacuum_multixact_freeze_max_age', '1250000000', 1, null, 'Multixact age at which to autovacuum a table to prevent multixact wraparound.', 1),
--                   ('default_text_search_config', 'pg_catalog.english', 4, null, 'default_text_search_config', 0),  --i
                  ('track_activity_query_size', '4096', 1, null, 'Sets the size reserved for pg_stat_activity.query, in bytes.', 1),
--                   ('deadlock_timeout', '1', 3, 's', 'deadlock_timeout', 0),  --1
--                   ('lock_timeout', '0', 1, null, 'lock_timeout', 0),  --1

                  ('shared_preload_libraries', 'pg_stat_statements', 4, null, 'Lists shared libraries to preload into server', 1),
--                   ('pg_pathman.insert_into_fdw', 'any_fdw', 1, null, 'pg_pathman.insert_into_fdw', 0),
--                   ('pg_stat_statements.max', '10000', 1, null, 'pg_stat_statements.max', 0),
--                   ('pg_stat_statements.track', 'all', 1, null, 'pg_stat_statements.track', 0),
--                   ('pg_stat_statements.track_utility', 'off', 2, null, 'pg_stat_statements.track_utility', 0),
--                   ('pg_stat_statements.save ', 'on', 2, null, 'pg_stat_statements.save', 0),
                  ('lock_timeout', '0', 1, null, 'Sets the maximum allowed duration of any wait for a lock', 0);



update clup_init_db_conf set val='4' where setting_name = 'work_mem';
update clup_init_db_conf set val='10' where setting_name = 'autovacuum_max_workers';
update clup_init_db_conf set val='320', unit='MB' where setting_name = 'min_wal_size';
update clup_init_db_conf set val='0' where setting_name = 'statement_timeout';
update clup_init_db_conf set val='8192', unit = 'B', setting_type=3 where setting_name = 'track_activity_query_size';
update clup_init_db_conf set val='pg_stat_statements' where setting_name = 'shared_preload_libraries';

-- 原先的第5类是一个有值范围的拖拽的条，现在去掉，把其中唯一的一个参数shared_buffer改成第3类
update clup_init_db_conf set setting_type=3 where setting_name='shared_buffers';
-- 原先第4类是说需要加引号，里面可以填多个值的，现在去掉这个类型，把这个类型改成第1个类型
update clup_init_db_conf set setting_type=1 where setting_type=4;
-- 把原先在第3类中的按时间单位数据库参数改成第4类
update clup_init_db_conf set setting_type=4
 where setting_name in (
 'log_min_duration_statement', 'archive_timeout', 'autovacuum_vacuum_cost_delay',
 'idle_in_transaction_session_timeout', 'vacuum_cost_delay', 'bgwriter_delay', 'wal_writer_delay',
 'checkpoint_timeout', 'max_standby_archive_delay', 'max_standby_streaming_delay', 'wal_receiver_status_interval');

-- 把原先需要加引号的第4类型改成第6类
update clup_init_db_conf as c set setting_type=6 from pg_settings s
    where c.setting_name = s.name and s.vartype='string';


COMMENT ON COLUMN clup_init_db_conf.setting_type is '配置类型: 1-无单位的普通类型 2-布尔类型 3-带字节单位的类型 4-时间类型 5-枚举类型 6-字符串类型';

CREATE OR REPLACE FUNCTION f_calc_unit_value(arg_unit text)
    RETURNS bigint
AS
$BODY$
declare
    v_raw_va text;
    v_unit text;
    v_len int;
    v_base bigint;
    v_char text;
    v_pos int;
begin
   if arg_unit is null then
      return 1;
   end if;
   v_len = octet_length(arg_unit);
   if v_len = 0 then
      return 1;
   end if;

   v_unit = '';
   v_pos = v_len;
   LOOP
      v_char = substr(arg_unit, v_pos, 1);
      if ascii(v_char) >= 48 and ascii(v_char) <= 57 then
         exit;
      end if;
      v_unit = v_char || v_unit;
      v_pos = v_pos -1;
      exit when v_pos < 1;
   END LOOP;
   v_raw_va = substr(arg_unit, 1, v_pos);
   --raise notice 'v_unit=%, v_raw_va=%', v_unit, v_raw_va;
   if v_unit = '' then
      v_base = 1;
   elsif v_unit = 'B' then
      v_base = 1;
   elsif v_unit = 'kB' then
      v_base = 1024;
   elsif v_unit = 'MB' then
      v_base = 1024*1024;
   elsif v_unit = 'GB' then
      v_base = 1024*1024*1024;
   elsif v_unit = 'TB' then
      v_base = 1024*1024*1024*1024;
   elsif v_unit = 's' then
      v_base = 1000;
   elsif v_unit = 'ms' then
      v_base = 1;
   elsif v_unit = 'min' then
      v_base = 60*1000;
   elsif v_unit = 'h' then
      v_base = 60*60*1000;
   elsif v_unit = 'd' then
      v_base = 3600*24*1000;
   else
      raise EXCEPTION 'unknown unit: %', v_unit;
   end if;
   if length(v_raw_va) = 0 then
      return v_base;
   else
      return (v_raw_va::bigint)*v_base;
   end if;
end;
$BODY$
    LANGUAGE plpgsql;


DO LANGUAGE plpgsql
$BODY$
BEGIN
    perform attname from pg_attribute where attrelid='clup_init_db_conf'::regclass and attname='min_val';
    if not found then
        alter table clup_init_db_conf add min_val text;
        update clup_init_db_conf as c set min_val = ((s.min_val::float8)*f_calc_unit_value(s.unit))::text from pg_settings s
        where c.setting_name = s.name and s.min_val is not null;
    end if;

    perform attname from pg_attribute where attrelid='clup_init_db_conf'::regclass and attname='max_val';
    if not found then
        alter table clup_init_db_conf add max_val text;
        update clup_init_db_conf as c set max_val = ((s.max_val::float8)*f_calc_unit_value(s.unit))::text from pg_settings s
         where c.setting_name = s.name and s.max_val is not null;
    end if;

    perform attname from pg_attribute where attrelid='clup_init_db_conf'::regclass and attname='enumvals';
    if not found then
        alter table clup_init_db_conf add enumvals text[];
        update clup_init_db_conf as c set enumvals = s.enumvals, setting_type=5 from pg_settings s
        where c.setting_name = s.name and s.enumvals is not null;
    end if;

END
$BODY$;


INSERT INTO clup_init_db_conf(setting_name, val, setting_type, unit, is_restart, notes, min_val, max_val, enumvals)
SELECT name, setting, 1, unit, 0, short_desc, min_val, max_val, enumvals FROM pg_settings where name ='commit_siblings'
 ON CONFLICT DO NOTHING;

INSERT INTO clup_init_db_conf(setting_name, val, setting_type, unit, is_restart, notes, min_val, max_val, enumvals)
SELECT name, setting, 1, unit, 0, short_desc, min_val, max_val, enumvals FROM pg_settings where name ='vacuum_freeze_table_age'
 ON CONFLICT DO NOTHING;

INSERT INTO clup_init_db_conf(setting_name, val, setting_type, unit, is_restart, notes, min_val, max_val, enumvals)
SELECT name, setting, 4, unit, 0, short_desc, ((min_val::float8)*f_calc_unit_value(unit))::text as min_val,
((max_val::float8)*f_calc_unit_value(unit))::text as max_val, enumvals FROM pg_settings
 where name ='statement_timeout'
 ON CONFLICT DO NOTHING;

INSERT INTO clup_init_db_conf(setting_name, val, setting_type, unit, is_restart, notes, min_val, max_val, enumvals)
SELECT name, setting, 5, unit, 0, short_desc, min_val, max_val, enumvals FROM pg_settings where name ='synchronous_commit'
 ON CONFLICT DO NOTHING;

INSERT INTO clup_init_db_conf(setting_name, val, setting_type, unit, is_restart, notes, min_val, max_val, enumvals)
SELECT name, setting, 5, unit, 1, short_desc, min_val, max_val, enumvals FROM pg_settings where name ='wal_level'
 ON CONFLICT DO NOTHING;

INSERT INTO clup_init_db_conf(setting_name, val, setting_type, unit, is_restart, notes, min_val, max_val, enumvals)
SELECT name, setting, 2, unit, 1, short_desc, min_val, max_val, enumvals FROM pg_settings where name ='wal_log_hints'
 ON CONFLICT DO NOTHING;


-- 更新排序的序号
DO LANGUAGE plpgsql
$BODY$
BEGIN
    perform attname from pg_attribute where attrelid='clup_init_db_conf'::regclass and attname='order_id';
    if not found then
        alter table clup_init_db_conf add order_id int;
    end if;
    with t(order_id, name) as (
    values
        (1100,'listen_addresses'),
        (1110,'unix_socket_directories'),
        (1120,'max_connections'),
        (1130,'superuser_reserved_connections'),
        (1140,'max_worker_processes'),
        (1150,'max_prepared_transactions'),
        (1200,'shared_preload_libraries'),
        (1210,'archive_mode'),
        (1220,'archive_command'),
        (1230,'archive_timeout'),
        (1300,'shared_buffers'),
        (1310,'work_mem'),
        (1320,'maintenance_work_mem'),
        (1330,'effective_cache_size'),
        (1340,'effective_io_concurrency'),
        (1350,'random_page_cost'),
        (1400,'wal_level'),
        (1410,'max_wal_senders'),
        (1420,'wal_keep_segments'),
        (1430,'wal_compression'),
        (1432,'wal_log_hints'),
        (1440,'max_wal_size'),
        (1450,'min_wal_size'),
        (1500,'synchronous_commit'),
        (1510,'wal_writer_delay'),
        (1520,'idle_in_transaction_session_timeout'),
        (1530,'lock_timeout'),
        (1540,'statement_timeout'),
        (1550,'commit_delay'),
        (1560,'commit_siblings'),
        (1600,'checkpoint_timeout'),
        (1610,'checkpoint_flush_after'),
        (1620,'old_snapshot_threshold'),
        (1630,'vacuum_cost_delay'),
        (1640,'vacuum_cost_limit'),
        (1650,'autovacuum_vacuum_cost_delay'),
        (1660,'autovacuum_vacuum_cost_limit'),
        (1670,'vacuum_freeze_min_age'),
        (1680,'vacuum_freeze_table_age'),
        (1690,'autovacuum_freeze_max_age'),
        (1700,'autovacuum_multixact_freeze_max_age'),
        (1710,'autovacuum_max_workers'),
        (1720,'autovacuum_work_mem'),
        (1730,'autovacuum_analyze_scale_factor'),
        (1740,'autovacuum_analyze_threshold'),
        (1750,'autovacuum_vacuum_scale_factor'),
        (1760,'autovacuum_vacuum_threshold'),
        (1800,'bgwriter_delay'),
        (1810,'bgwriter_lru_maxpages'),
        (1820,'bgwriter_lru_multiplier'),
        (1830,'tcp_keepalives_count'),
        (1840,'tcp_keepalives_idle'),
        (1850,'tcp_keepalives_interval'),
        (1860,'temp_file_limit'),
        (1910,'enable_partitionwise_aggregate'),
        (1920,'enable_partitionwise_join'),
        (1930,'max_parallel_maintenance_workers'),
        (1940,'max_parallel_workers'),
        (1950,'max_parallel_workers_per_gather'),
        (2000,'hot_standby'),
        (2010,'wal_receiver_status_interval'),
        (2020,'max_logical_replication_workers'),
        (2030,'max_replication_slots'),
        (2040,'max_standby_archive_delay'),
        (2050,'max_standby_streaming_delay'),
        (2060,'max_sync_workers_per_subscription'),
        (2070,'track_activity_query_size'),
        (2080,'track_io_timing'),
        (2090,'track_functions'),
        (2100,'logging_collector'),
        (2110,'log_autovacuum_min_duration'),
        (2120,'log_min_duration_statement'),
        (2130,'log_rotation_size'),
        (2140,'log_temp_files'),
        (2150,'log_error_verbosity'),
        (2160,'log_statement'),
        (2170,'log_destination'),
        (2180,'log_truncate_on_rotation'),
        (2190,'log_checkpoints'),
        (2200,'log_lock_waits')
        )
    update clup_init_db_conf as c set order_id = t.order_id from t
    where c.setting_name = t.name;
END
$BODY$;

UPDATE clup_init_db_conf  SET order_id = 100000 WHERE order_id IS NULL;


COMMENT ON TABLE clup_db is '记录数据库信息的表';
COMMENT ON COLUMN clup_db.state is '数据库的HA状态：1:Normal, 2:Fault, 3:Failover, 4:Switching, 5:Repairing';
COMMENT ON COLUMN clup_db.db_state is '数据库状态：0:运行中, 1:停止, 2:创建中, 3:恢复中, -1:agent异常';

COMMENT ON COLUMN clup_cluster.state is 'HA集群状态：0:OFFLINE(离线), 1:ONLINE(在线), 2:REPAIRING(修复中), 3:FAILOVER(故障自动切换中), -1:FAILED(故障自动修复失败，需要手工修复)';

COMMENT ON TABLE clup_general_task is '通用任务表';
COMMENT ON COLUMN clup_general_task.state is '任务状态：0:执行中, 1:成功， -1: 失败';

COMMENT ON TABLE task is '集群HA的任务表';
COMMENT ON COLUMN task.state is '任务状态：0:执行中, 1:成功， -1: 失败';


DO LANGUAGE plpgsql
$BODY$
BEGIN
    perform attname from pg_attribute where attrelid='clup_init_db_conf'::regclass and attname='min_version';
    if not found then
        ALTER TABLE clup_init_db_conf ADD min_version numeric(4,1);
    end if;

    perform attname from pg_attribute where attrelid='clup_init_db_conf'::regclass and attname='max_version';
    if not found then
        ALTER TABLE clup_init_db_conf ADD max_version numeric(4,1);
    end if;
END
$BODY$;


UPDATE  clup_init_db_conf SET min_version=9.6, max_version=99;
UPDATE clup_init_db_conf SET min_version=10 WHERE setting_name in (
    'max_logical_replication_workers',
    'max_parallel_workers',
    'max_sync_workers_per_subscription'
    );

UPDATE clup_init_db_conf SET min_version=11.0 WHERE setting_name in (
    'enable_partitionwise_join',
    'max_parallel_maintenance_workers',
    'enable_partitionwise_aggregate');

UPDATE clup_init_db_conf SET max_version=12.99 WHERE setting_name ='wal_keep_segments';

UPDATE clup_init_db_conf SET setting_type=6 WHERE setting_name  in ('unix_socket_directories', 'shared_preload_libraries');

UPDATE clup_init_db_conf SET val=150000000, setting_type=1, unit=null, is_restart=0,
notes='Age at which VACUUM should scan whole table to freeze tuples.' WHERE setting_name='vacuum_freeze_table_age';


INSERT INTO clup_init_db_conf(setting_name, val, setting_type, unit, is_restart, notes, min_val, max_val, enumvals, order_id, min_version, max_version)
 VALUES('wal_keep_size', '4096', 3, 'MB', 0, 'Sets the size of WAL files held for standby servers.', 0, 2251799812636672, null,  1420, 13.0, 99.0) ON CONFLICT DO NOTHING;

UPDATE clup_init_db_conf SET min_version=13.0 WHERE setting_name ='wal_keep_size';


DO LANGUAGE plpgsql
$BODY$
BEGIN
    perform attname from pg_attribute where attrelid='clup_init_db_conf'::regclass and attname='common_level';
    if not found then
        ALTER TABLE clup_init_db_conf ADD common_level int default 3;
    end if;
END
$BODY$;


COMMENT ON COLUMN clup_init_db_conf.common_level is '1-最常用参数 2-常用参数 3-一般参数';

UPDATE clup_init_db_conf SET common_level =1 WHERE setting_name in (
	'listen_addresses',
	'unix_socket_directories',
	'shared_buffers',
	'work_mem',
	'wal_keep_segments',
	'archive_mode',
	'max_wal_size',
	'min_wal_size',
	'shared_preload_libraries',
	'archive_command',
	'max_wal_senders',
	'max_connections',
	'superuser_reserved_connections',
	'max_worker_processes',
	'max_prepared_transactions',
	'maintenance_work_mem',
	'checkpoint_timeout',
	'random_page_cost'
);

UPDATE clup_init_db_conf SET common_level =2 WHERE setting_name in (
	'wal_compression',
	'wal_log_hints',
	'statement_timeout',
	'autovacuum_analyze_scale_factor',
	'autovacuum_analyze_threshold',
	'autovacuum_vacuum_scale_factor',
	'autovacuum_vacuum_threshold',
	'enable_partitionwise_join',
	'track_io_timing',
	'track_functions',
	'log_lock_waits',
	'autovacuum_freeze_max_age',
	'autovacuum_multixact_freeze_max_age',
	'autovacuum_max_workers',
	'autovacuum_work_mem',
	'track_activity_query_size',
	'vacuum_cost_delay',
	'vacuum_cost_limit',
	'effective_io_concurrency',
	'idle_in_transaction_session_timeout',
	'vacuum_freeze_table_age',
	'log_min_duration_statement',
	'archive_timeout',
	'lock_timeout',
	'old_snapshot_threshold',
	'autovacuum_vacuum_cost_delay',
	'autovacuum_vacuum_cost_limit'
);

UPDATE clup_init_db_conf SET common_level=3 WHERE setting_name in (
	'logging_collector',
	'bgwriter_delay',
	'bgwriter_lru_maxpages',
	'bgwriter_lru_multiplier',
	'log_rotation_size',
	'log_temp_files',
	'tcp_keepalives_idle',
	'tcp_keepalives_interval',
	'tcp_keepalives_count',
	'temp_file_limit',
	'wal_receiver_status_interval',
	'effective_cache_size',
	'log_autovacuum_min_duration',
	'commit_siblings',
	'log_error_verbosity',
	'log_statement',
	'log_destination',
	'log_truncate_on_rotation',
	'log_checkpoints',
	'hot_standby',
	'wal_writer_delay',
	'commit_delay',
	'checkpoint_flush_after',
	'max_parallel_workers',
	'max_logical_replication_workers',
	'max_sync_workers_per_subscription',
	'enable_partitionwise_aggregate',
	'max_parallel_maintenance_workers',
	'max_parallel_workers_per_gather',
	'max_replication_slots',
	'max_standby_archive_delay',
	'max_standby_streaming_delay'
);


UPDATE clup_init_db_conf SET unit='min',val='-1' WHERE setting_name = 'old_snapshot_threshold';
UPDATE clup_init_db_conf SET unit='ms', val='0' WHERE setting_name = 'idle_in_transaction_session_timeout';


-- 不再使用clup_cluster.cluster_data中的ha_db_user,ha_db_pass,db_repl_user,db_repl_pass，而是统一使用clup_db.db_detail中的内容
update clup_db d set db_detail = db_detail || ('{"db_user":"' || (c.cluster_data->>'ha_db_user') || '"}')::jsonb
 from clup_cluster c where d.cluster_id=c.cluster_id and c.cluster_data->'ha_db_user' is not null and d.db_detail->'db_user' is null;

update clup_db d set db_detail = db_detail || ('{"db_pass":"' || (c.cluster_data->>'ha_db_pass') || '"}')::jsonb
 from clup_cluster c where d.cluster_id=c.cluster_id and c.cluster_data->'ha_db_pass' is not null and d.db_detail->'db_pass' is null;

update clup_db d set db_detail = db_detail || ('{"repl_user":"' || (c.cluster_data->>'db_repl_user') || '"}')::jsonb
 from clup_cluster c where d.cluster_id=c.cluster_id and c.cluster_data->'db_repl_user' is not null and d.db_detail->'repl_user' is null;

update clup_db d set db_detail = db_detail || ('{"repl_pass":"' || (c.cluster_data->>'db_repl_pass') || '"}')::jsonb
 from clup_cluster c where d.cluster_id=c.cluster_id and c.cluster_data->'db_repl_pass' is not null and d.db_detail->'repl_pass' is null;



DO LANGUAGE plpgsql
$BODY$
BEGIN
    perform attname from pg_attribute where attrelid='clup_settings'::regclass and attname='category';
    if not found then
        ALTER TABLE clup_settings ADD category int default 0;
    end if;

    perform attname from pg_attribute where attrelid='clup_settings'::regclass and attname='val_type';
    if not found then
        ALTER TABLE clup_settings ADD val_type text default 'str';
    end if;

    perform attname from pg_attribute where attrelid='clup_settings'::regclass and attname='describe';
    if not found then
        ALTER TABLE clup_settings ADD describe text default null;
    end if;
END
$BODY$;

COMMENT ON COLUMN clup_settings.val_type is 'str: 字符串, int(min, max): 整数';
COMMENT ON COLUMN clup_settings.category is '0: 内部使用的配置项不在界面中显示(category的值小于10都不显示), 10:  clup自身配置, 20: HA高可用的配置, 30-监控告警, 99-其它参数';
COMMENT ON COLUMN clup_settings.describe is '描述';

update clup_settings set category=10 where key='pg_bin_path_string';

INSERT INTO clup_settings (key, content, category, val_type, describe) VALUES ('pg_bin_path_string', '/usr/csupg-*/bin,/usr/pgsql-*/bin', 10, 'str', 'PostgreSQL软件的目录') ON CONFLICT DO NOTHING;
INSERT INTO clup_settings (key, content, category, val_type, describe) VALUES ('agent_packages_path', '/opt/agent_packages', 10, 'str', 'agent的升级包存放的目录') ON CONFLICT DO NOTHING;
INSERT INTO clup_settings (key, content, category, val_type, describe) VALUES ('debug_sql', 0, 10, 'int(0,1)', '日志中是否输出执行的SQL') ON CONFLICT DO NOTHING;

INSERT INTO clup_settings (key, content, category, val_type, describe) VALUES ('probe_island_ip', null, 20, 'str', '检测是否是自己变成了孤岛的检测IP') ON CONFLICT DO NOTHING;
INSERT INTO clup_settings (key, content, category, val_type, describe) VALUES ('lock_ttl', 120, 20, 'int(30, 3600)', '参数指定HA锁的存活的最长时间') ON CONFLICT DO NOTHING;
INSERT INTO clup_settings (key, content, category, val_type, describe) VALUES ('db_cluster_change_check_interval', 10, 20, 'int(1, 3600)', '检查集群的变动的周期') ON CONFLICT DO NOTHING;
INSERT INTO clup_settings (key, content, category, val_type, describe) VALUES ('sr_ha_check_interval', 10, 20, 'int(1, 3600)',  '流复制集群是否健康的检查周期') ON CONFLICT DO NOTHING;
INSERT INTO clup_settings (key, content, category, val_type, describe) VALUES ('sd_ha_check_interval', 10, 20, 'int(1, 3600)', '共享盘集群是否健康的检查周期') ON CONFLICT DO NOTHING;


DO LANGUAGE plpgsql
$BODY$
BEGIN
    perform attname from pg_attribute where attrelid='clup_db'::regclass and attname='db_type';
    if not found then
        ALTER TABLE clup_db ADD db_type int default 1;
    end if;
END
$BODY$;

COMMENT ON COLUMN clup_db.db_type is '数据库类型: 1-pg, 11-polardb';


DELETE FROM  clup_settings where key='lock_ttl';


UPDATE clup_init_db_conf SET setting_type=4 WHERE setting_name='old_snapshot_threshold';
UPDATE clup_init_db_conf SET setting_type=4, unit='ms' WHERE setting_name='lock_timeout';

CREATE TABLE IF NOT EXISTS check_task_info(
    task_id SERIAL primary key,
    task_name       varchar(100),
    doc_path        varchar(100),
    create_time     varchar(100),
    docx_content    bytea,
    html_content    bytea
);