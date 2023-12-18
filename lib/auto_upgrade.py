#!/usr/bin/env python
# -*- coding:UTF-8

# Copyright (c) 2023 CSUDATA.COM and/or its affiliates.  All rights reserved.
# CLup is licensed under AGPLv3.
# See the GNU AFFERO GENERAL PUBLIC LICENSE v3 for more details.
# You can use this software according to the terms and conditions of the AGPLv3.
#
# THIS SOFTWARE IS PROVIDED BY CSUDATA.COM "AS IS" AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT, ARE
# DISCLAIMED.  IN NO EVENT SHALL CSUDATA.COM BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
@Author: tangcheng
@description: 自动升级
"""

import os

import config
import dbapi
import run_lib
import ip_lib

from ipaddress import IPv4Address, IPv4Network


def get_dbapi_obj():
    upgrade_dbapi = dbapi
    return upgrade_dbapi


def psql_run(sql_fn):
    db_dict = {
        "db_name": config.get('db_name'),
        "db_host": config.get('db_host'),
        "db_port": config.get('db_port'),
        "db_user": config.get('db_user'),
        "db_pass": config.get('db_pass'),
        "psql_cmd": config.get('psql_cmd')
    }

    cmd = f"PGPASSWORD={db_dict['db_pass']} {db_dict['psql_cmd']} -h {db_dict['db_host']} " \
          f"-p {db_dict['db_port']} -U{db_dict['db_user']} -d {db_dict['db_name']} -f {sql_fn}"

    #  当前默认使用的数据库软件是clup机器上的
    err_code, err_msg, out_msg = run_lib.run_cmd_result(cmd)
    if "ERROR:" in err_msg:
        err_code = -1
    return err_code, err_msg, out_msg


def upgrade_common(v1, v2):
    sql_path = config.get_sql_path()
    sql_scripts = os.path.join(sql_path, f'v{v1}_v{v2}.sql')
    try:
        err_code, err_msg, _out_msg = psql_run(sql_scripts)
        if err_code != 0:
            return err_code, err_msg
    except Exception as e:
        return -1, f"run sql file error: \n{sql_scripts}\n{str(e)}\n"
    return 0, ''


def create_default_vip_pool():
    """建立默认的vip池
    """
    # 获取所有已配置的vip
    sql = "SELECT c.cluster_id,c.cluster_data->'rooms' as rooms,c.cluster_data->>'vip' as vip, " \
        " db_id FROM clup_cluster c,clup_db db WHERE c.cluster_id=db.cluster_id AND db.is_primary=1"
    rows = dbapi.query(sql)

    cluster_info_list = list()
    # 默认的vip池的掩码位数都是24
    for cluster_info in rows:
        cluster_info_list.append({
            "vip": cluster_info["vip"],
            "primary_db_id": cluster_info["db_id"],
            "cluster_id": cluster_info["cluster_id"],
            "vip_list": [room_info["vip"] for room_info in cluster_info["rooms"].values()]
        })

    vip_info = dict()
    # get all vip network and vip list
    for cluster_info in cluster_info_list:
        for vip in cluster_info["vip_list"]:
            vip_network = str(IPv4Network(f'{vip}/24', strict=False))
            if vip_network not in vip_info:
                vip_info[vip_network] = list()

            vip_info[vip_network].append(int(IPv4Address(vip)))

    try:
        with dbapi.DBProcess() as dbp:
            # create vip pool
            vip_pool_info = dict()
            for vip_network, vip_list in vip_info.items():
                start_ip = min(vip_list)
                end_ip = max(vip_list)

                # insert into clup_vip_pool
                sql = "INSERT INTO clup_vip_pool(start_ip, end_ip, mask_len) VALUES(%s, %s, 24) RETURNING pool_id"
                pool_rows = dbp.query(sql, (str(IPv4Address(start_ip)), str(IPv4Address(end_ip))))
                if not pool_rows:
                    return -1, f"Excute sql({sql}) failed."

                if vip_network not in vip_pool_info:
                    vip_pool_info[vip_network] = {
                        "pool_id": pool_rows[0]["pool_id"],
                        "start_ip": start_ip,
                        "end_vip": end_ip
                    }

            # add used vip
            for cluster_info in cluster_info_list:
                cluster_id = cluster_info["cluster_id"]
                for vip in cluster_info["vip_list"]:
                    vip_network = str(IPv4Network(f"{vip}/24", strict=False))
                    pool_info = vip_pool_info[vip_network]
                    if vip == cluster_info["vip"]:
                        # insert into clup_used_vip which used_reason = 1
                        sql = "INSERT INTO clup_used_vip(pool_id, vip, db_id, cluster_id, used_reason) VALUES(%s, %s, %s, %s, 1) RETURNING vip"
                        vip_rows = dbp.query(sql, (pool_info["pool_id"], vip, cluster_info["primary_db_id"], cluster_id))
                    else:
                        # insert into clup_used_vip which used_reason = 2
                        sql = "INSERT INTO clup_used_vip(pool_id, vip, cluster_id, used_reason) VALUES(%s, %s, %s, 2) RETURNING vip"
                        vip_rows = dbp.query(sql, (pool_info["pool_id"], vip, cluster_id))
                    if not vip_rows:
                        return -1, f"Excute sql({sql}) failed."

    except Exception as e:
        return -1, f"Create vip pool with unexpected error, {str(e)}."

    return 0, "All clsuter vip create vip pool."


def upgrade_with_vip_pool(v1, v2):
    sql_path = config.get_sql_path()
    sql_scripts = os.path.join(sql_path, f'v{v1}_v{v2}.sql')
    try:
        err_code, err_msg, _out_msg = psql_run(sql_scripts)
        if err_code != 0:
            return err_code, err_msg
        code, result = create_default_vip_pool()
        if code != 0:
            return -1, result
    except Exception as e:
        return -1, f"run sql file error: \n{sql_scripts}\n{str(e)}\n"
    return 0, ''


upgrade_func_list = [
    ["5.0.0", upgrade_common],
    ['5.0.1', upgrade_common],
    ['5.0.2', upgrade_common],
    ['5.0.4', upgrade_common],
    ['5.0.5', upgrade_with_vip_pool],
]


def cmp_version(ver1, ver2):
    items1 = ver1.split('.')
    items2 = ver2.split('.')
    cnt = len(items1)
    for i in range(cnt):
        if i >= len(items2):
            return 1
        if int(items1[i]) > int(items2[i]):
            return 1
        elif int(items1[i]) < int(items2[i]):
            return -1
    if len(items1) == len(items2):
        return 0
    else:
        return -1


def check_and_upgrade():
    try:
        upgrade_dbapi = get_dbapi_obj()

        test_conn = upgrade_dbapi.connect_db()
        if not test_conn:
            return -1, "connect clupcdb faild, check clup.conf and start clupcdb"
        test_conn.close()

        # 找到当前版本，放到db_version
        sql = "select count(*) as cnt from pg_class where relname = 'clup_settings' and relkind = 'r'"
        rows = upgrade_dbapi.query(sql)
        if rows[0]['cnt'] <= 0:
            db_version = '0.0'
        else:
            sql = "SELECT content FROM clup_settings where key='db_version'"
            rows = upgrade_dbapi.query(sql)
            if len(rows) <= 0:
                db_version = '0.0'
            else:
                db_version = rows[0]['content']
        pre_version = '1.0'
        for item in upgrade_func_list:
            version = item[0]
            if cmp_version(item[0], db_version) > 0:
                err_code, err_msg = item[1](pre_version, version)
                if err_code != 0:
                    return err_code, err_msg
                try:
                    sql = """UPDATE clup_settings SET content = %s WHERE key='db_version' """
                    upgrade_dbapi.execute(sql, (version,))
                except Exception as e:
                    return -1, f"run sql error: \n{sql}\n{str(e)}\n"
            pre_version = version
    except Exception as e:
        return -1, str(e)
    return 0, ''
