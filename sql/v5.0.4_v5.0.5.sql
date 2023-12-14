CREATE TABLE IF NOT EXISTS clup_vip_pool(
	pool_id serial primary key,
	start_ip text,
	end_ip text,
	mask_len int
);

CREATE TABLE IF NOT EXISTS clup_used_vip(
	vip text primary key,
	pool_id int,
	db_id int,
	used_reason int
);
COMMENT ON COLUMN clup_used_vip.used_reason is '1-表示当前正在被使用, 2-表示当前被分配但未启用, 99-表示被手工占用(从集群中移除或集群已不存在，在主机上应用)。'
