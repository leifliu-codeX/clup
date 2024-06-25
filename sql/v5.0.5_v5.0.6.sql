CREATE TABLE IF NOT EXISTS csu_packages(
    package_id serial primary key,
    package_name varchar(100),
    version varchar(10),
    path     text,
    file     text,
    settings jsonb,
    conf_init jsonb
);


CREATE TABLE IF NOT EXISTS csu_zqpool(
    zqpool_id  serial primary key,
    zqpool_name text,
    package_id integer,
    state      integer,
    host       text,
    os_user    text,
    root_path  text,
    conf_data  jsonb
);

COMMENT ON COLUMN csu_zqpool.state IS '连接池状态: Online=1, Offline=0, Unknow=-1';
COMMENT ON COLUMN csu_zqpool.package_id IS 'zqpool的版本和默认配置信息,从csu_packages重查看';


CREATE TABLE IF NOT EXISTS csu_zqpool_pools(
    pool_id   serial primary key,  -- 非zqpool配置文件中的poolID
    zqpool_id integer,
    pool_fe   text,                -- fe_user.fe_dbname
    state     integer,
    conf_data jsonb
);

COMMENT ON COLUMN csu_zqpool_pools.conf_data IS '连接池的配置信息';
COMMENT ON COLUMN csu_zqpool_pools.state IS '连接池状态: Online=1, Offline=0, Unknow=-1';
COMMENT ON COLUMN csu_zqpool_pools.pool_fe IS '由连接池fe_user和fe_dbname组成的标识，对应zqpool中的poolName';



/*
INSERT INTO csu_packages(package_name, path, file, version, settings, conf_init)
VALUES('zqpool', '/opt/csu_packages', 'zqpool', '1.0',
    '{
        "os_user": "zqpool",
        "root_path": "/home/zqpool",
        "conf_file": "zqpool.conf"
    }',
    '{
        "fe_user": "",
        "fe_passwd": "",
        "fe_dbname": "",
        "be_user": "",
        "be_passwd": "",
        "be_dbname": "",
        "be_ipport": "",
        "mgr_addr": "*",
        "mgr_port": 9380,
        "listen_addr": "*",
        "listen_port": 5436,
        "exporter_port": 9816,
        "fe_max_conns": 2000,
        "be_rw_conns": 100,
        "be_rd_conns": 100,
        "be_conn_life_time": 60,
        "msg_buf_size": 65536,
        "be_retry_count": 3,
        "be_retry_interval": 10,
        "retry_cnt_when_full": 0,
        "retry_interval_ms_when_full": 100,
        "mgr_token": "KW%X_MDrReadXW$WTA?Nfpy#"
    }'
);
*/

