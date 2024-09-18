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
@description: WEB界面的高可用集群后端服务处理模块
"""

import copy
import json
import logging
import os
import time
import traceback
from ipaddress import IPv4Address, IPv4Network

import cluster_state
import csu_http
import dao
import database_state
import dbapi
import general_task_mgr
import ha_mgr
import helpers
import ip_lib
import long_term_task
import node_state
import pg_db_lib
import pg_helpers
import polar_lib
import rpc_utils
import task_type_def


def get_cluster_list(req):
    params = {
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT,
        'filter': 0,
        'vip': 0
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    page_num = pdict['page_num']
    page_size = pdict['page_size']

    if 'filter' in pdict:
        filter_cond = pdict['filter']
    else:
        filter_cond = ''

    offset = (page_num - 1) * page_size
    # 可以的条件：cluster_name,vip
    args = copy.copy(pdict)
    where_cond = ""
    if filter_cond:
        where_cond = (
            """WHERE (cluster_data->>'cluster_name' like %(filter)s"""
            """ OR cluster_data->>'vip' LIKE %(filter)s)""")
        args['filter'] = filter_cond

    with dbapi.DBProcess() as dbp:
        sql = "SELECT count(*) as cnt FROM clup_cluster " + where_cond
        rows = dbp.query(sql, args)
        row_cnt = rows[0]['cnt']
        ret_rows = []
        if row_cnt > 0:
            sql = ("SELECT cluster_id, cluster_type, cluster_data->>'cluster_name' as cluster_name, "
                   " cluster_data->>'vip' as vip, state, lock_time "
                   "FROM clup_cluster {where_cond} "
                   " ORDER BY cluster_id LIMIT %(limit)s OFFSET %(offset)s".format(where_cond=where_cond))
            args['limit'] = page_size
            args['offset'] = offset
            ret_rows = dbp.query(sql, args)

    # 前端需要display_state字段
    for row in ret_rows:
        row['display_state'] = cluster_state.to_str(row['state'])

    ret_data = {"total": row_cnt, "page_size": pdict['page_size'], "rows": ret_rows}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def get_cluster_detail(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']

    sql = "SELECT * FROM clup_cluster WHERE cluster_id=%s"
    rows = dbapi.query(sql, (cluster_id,))
    if not rows:
        return 400, f"cluster_id({cluster_id}) not exists"
    row = rows[0]
    cluster_type = row['cluster_type']
    cluster_dict = row['cluster_data']

    # 在返回的数据中需要加下以下两个属性
    cluster_dict['cluster_id'] = cluster_id
    cluster_dict['cluster_type'] = cluster_type

    if 'trigger_db_name' not in cluster_dict:
        cluster_dict['trigger_db_name'] = ''
    if 'trigger_db_func' not in cluster_dict:
        cluster_dict['trigger_db_func'] = ''
    if 'probe_db_name' not in cluster_dict:
        cluster_dict['probe_db_name'] = ''
    if 'probe_interval' not in cluster_dict:
        cluster_dict['probe_interval'] = ''
    if 'probe_timeout' not in cluster_dict:
        cluster_dict['probe_timeout'] = ''
    if 'probe_retry_cnt' not in cluster_dict:
        cluster_dict['probe_retry_cnt'] = ''
    if 'probe_retry_interval' not in cluster_dict:
        cluster_dict['probe_retry_interval'] = ''

    if cluster_type == 1:
        if 'probe_pri_sql' not in cluster_dict:
            cluster_dict['probe_pri_sql'] = ''
        if 'probe_stb_sql' not in cluster_dict:
            cluster_dict['probe_stb_sql'] = ''
    elif cluster_type == 2:
        if 'probe_sql' not in cluster_dict:
            cluster_dict['probe_sql'] = ''
    sql = "SELECT host, db_detail->>'db_user' as db_user, db_detail->>'db_pass' as db_pass, " \
          f"db_detail->>'repl_user' as repl_user, db_detail->>'repl_pass' as repl_pass FROM clup_db WHERE cluster_id={cluster_id}"
    rows = dbapi.query(sql)
    if len(rows) > 0:
        cluster_dict['db_user'] = rows[0]['db_user']
        cluster_dict['db_pass'] = rows[0]['db_pass']
        cluster_dict['repl_user'] = rows[0]['repl_user']
        cluster_dict['repl_pass'] = rows[0]['repl_pass']
    else:
        cluster_dict['db_user'] = ''
        cluster_dict['db_pass'] = ''
        cluster_dict['repl_user'] = ''
        cluster_dict['repl_pass'] = ''
    cluster_dict['host_list'] = [row['host'] for row in rows]
    raw_data = json.dumps(cluster_dict)
    return 200, raw_data


def get_cluster_db_list(req):
    params = {
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT,
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']

    sql = (
        "SELECT db_id,up_db_id,scores, cluster_id, state, pgdata, port, is_primary, repl_app_name, db_type,"
        "host, repl_ip, db_state, db_detail->'instance_type' as instance_type, db_detail-> 'is_rewind' as is_rewind, "
        "db_detail->'is_rebuild' as is_rebuild, db_detail->'rm_pgdata' as rm_pgdata, db_detail->'room_id' as room_id, "
        "db_detail->'reset_cmd' as reset_cmd, db_detail->'polar_type' as polar_type "
        "FROM clup_db WHERE cluster_id=%s ORDER BY db_id"
    )

    rows = dbapi.query(sql, (cluster_id,))
    total = len(rows)

    for db_dict in rows:
        if 'repl_ip' not in db_dict:
            db_dict['repl_ip'] = ''

    # 增加返回hid
    host_data = dbapi.query('select hid, ip from clup_host ', ())
    host_data_dict = {}
    if len(host_data) > 0:
        host_data_dict = {i['ip']: i['hid'] for i in host_data}

    # 获得各个数据库的运行状态
    for db_dict in rows:
        if host_data_dict:
            db_dict['hid'] = host_data_dict[db_dict['host']]
        db_state = db_dict['db_state']
        err_code, ret = pg_helpers.get_db_room(db_dict['db_id'])
        if err_code != 0:
            return 400, ret
        # db_dict['room_name'] = ret['room_name'] if ret else '默认机房'
        if ret:
            db_dict.update(ret)
        else:
            db_dict['room_name'] = '默认机房'
        if db_dict == database_state.CREATING or db_state == database_state.REPAIRING:
            continue
        err_code, err_msg = rpc_utils.get_rpc_connect(db_dict['host'], 2)
        if err_code != 0:
            db_dict['db_state'] = database_state.FAULT
            dao.update_db_state(db_dict['db_id'], database_state.FAULT)
            continue
        rpc = err_msg

        try:
            err_code, is_run = pg_db_lib.is_running(rpc, db_dict['pgdata'])
            if err_code != 0:
                db_state = database_state.FAULT
            else:
                if is_run:
                    db_state = database_state.RUNNING
                else:
                    # 如果状态不是处于创建中或修复中,直接显示数据库状态为停止
                    if db_state not in (database_state.CREATING, database_state.REPAIRING, database_state.CREATE_FAILD):
                        db_state = database_state.STOP

            db_dict['db_state'] = db_state
            dao.update_db_state(db_dict['db_id'], db_dict['db_state'])
        finally:
            rpc.close()
    ret_data = {"total": total, "page_size": pdict['page_size'], "rows": rows}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def get_cluster_db_info_api(req):
    params = {
        "cluster_id": csu_http.MANDATORY,
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']
    try:
        sql = "SELECT db_detail->'room_id' as room_id, db_id, up_db_id," \
              " host, port, instance_name, state, scores, is_primary" \
              " FROM clup_db WHERE cluster_id = %s"
        rows = dbapi.query(sql, (cluster_id, ))
    except Exception as e:
        return 400, repr(e)
    for row in rows:
        err_code, n = pg_helpers.get_db_room(row['db_id'])
        row['state'] = node_state.to_str(row['state'])
        row['up_db_id'] = row["up_db_id"] if row['up_db_id'] else " "
        row['instance_name'] = row["instance_name"] if row['instance_name'] else " "
        row["hp"] = f"{row['host']}:{row['port']}"
        if err_code != 0:
            row['room_name'] = "默认机房"
        else:
            row['room_name'] = n['room_name']
        room_id = row['room_id'] if row['room_id'] else "0"
        row['room'] = f"{row['room_name']}(id: {room_id})"
        if row['is_primary'] == 1:
            row['is_primary'] = "主库"
        elif row['is_primary'] == 0:
            row['is_primary'] = "备库"
        else:
            row['is_primary'] = ""
    rows = helpers.format_rows(rows)
    return 200, json.dumps(rows)


def get_cluster_list_api(req):
    """
    用于工具调用的接口
    @param req:
    @return:
    """
    params = {
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    sql = "SELECT cluster_id, cluster_data->'cluster_name' as cluster_name," \
          "state, cluster_type, cluster_data->'vip' as vip FROM clup_cluster"
    rows = dbapi.query(sql)
    for row in rows:
        row['state'] = cluster_state.to_str(row['state'])
        if row['cluster_type'] == 1:
            row['cluster_type'] = "流复制集群"
        elif row['cluster_type'] == 2:
            row['cluster_type'] = "共享磁盘集群"
        else:
            row['cluster_type'] = "Unknown"
    rows = helpers.format_rows(rows)
    return 200, json.dumps(rows)


def get_cluster_host_list(req):
    params = {
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT,
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']

    sql = "SELECT cluster_data FROM clup_cluster WHERE cluster_id=%s"
    rows = dbapi.query(sql, (cluster_id,))
    if not rows:
        return None
    row = rows[0]
    cluster_dict = row['cluster_data']
    host1_ip = cluster_dict['host1_ip']
    host2_ip = cluster_dict['host2_ip']
    pgdata = cluster_dict['pgdata']
    mount_path = cluster_dict['mount_path']
    primary = cluster_dict['primary']
    vip = cluster_dict['vip']
    # 检查是否为多个挂载目录
    mount_path_list = [k.strip() for k in mount_path.split(',')]

    row1 = {'ip': host1_ip, 'cluster_id': cluster_id}
    row2 = {'ip': host2_ip, 'cluster_id': cluster_id}
    # 这里修改下逻辑,将当前主库总是放在第一个位置
    if primary == 1:
        row1['is_primary'] = '主'
        row2['is_primary'] = '备'

    else:
        row2['is_primary'] = '主'
        row1['is_primary'] = '备'

    rows = [row1, row2]
    for row in rows:
        rpc = ''
        try:
            err_code, err_msg = rpc_utils.get_rpc_connect(row['ip'], 2)
            if err_code != 0:
                row["mount_state"] = "未连接上主机"
                row['db_state'] = '未知'
                row['vip_state'] = '未知'
                continue
            rpc = err_msg
            for _mount_path in mount_path_list:
                check_err_code, check_result = rpc.check_is_mount(_mount_path)
                if check_err_code != 0:
                    row["mount_state"] = "未知"
                else:
                    if check_result:
                        row["mount_state"] = "已挂载"
                    else:
                        row["mount_state"] = "未挂载"
            # 这里修改下逻辑,如果vip未绑定到主库,则将其绑定到主库上
            err_code, ret = rpc.vip_exists(vip)
            if err_code != 0:
                row['vip_state'] = '未知'
            else:
                if ret:
                    row['vip_state'] = '运行'
                else:
                    row['vip_state'] = '无'

            err_code, ret = pg_db_lib.is_running(rpc, pgdata)
            if err_code != 0:
                row['vip_state'] = '未知'
            else:
                if ret:
                    row['db_state'] = '运行'
                else:
                    row['db_state'] = '无'

        finally:
            if rpc:
                rpc.close()
    cluster_db_rows = dao.get_cluster_db_list(cluster_id)
    cluster_db_list = [r['db_id'] for r in cluster_db_rows]
    if len(cluster_db_list) != 0:
        db_id = cluster_db_list[0]
    else:
        db_id = 0
        return 200, 'cluster not have database'
    row1['db_id'] = db_id
    row2['db_id'] = db_id
    ret_data = {"total": 2, "page_size": pdict['page_size'], "rows": [row1, row2]}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def delete_cluster(req):
    params = {
        'vip_delete_flag': csu_http.MANDATORY | csu_http.INT,
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']
    try:
        with dbapi.DBProcess() as dbp:
            # 在删除集群的时候把vip从主库上解绑
            primary_host = dbp.query('select host from clup_db where cluster_id=%s and is_primary = 1', (cluster_id,))

            hotdate = dbp.query("delete from clup_cluster WHERE cluster_id=%s RETURNING *", (cluster_id,))
            dbp.execute("UPDATE clup_db SET cluster_id = null WHERE cluster_id=%s", (cluster_id,))
            vip = hotdate[0]['cluster_data']["vip"]
            if len(primary_host) > 0 and pdict.get('vip_delete_flag') == 1:
                host = primary_host[0]['host']
                rpc_utils.check_and_del_vip(host, vip)

            # delete or update clup_used_vip
            if pdict.get("vip_delete_flag"):
                dbp.execute("DELETE FROM clup_used_vip WHERE cluster_id=%s", (cluster_id, ))
            else:
                # update clup_used_vip
                dbp.execute("UPDATE clup_used_vip SET used_reason=3,cluster_id=null WHERE cluster_id=%s", (cluster_id, ))

    except Exception as e:
        return 400, str(e)
    return 200, 'ok'


def modify_sr_cluster_info(req):
    """
    :param req:
    :return:
    """
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'cluster_name': 0,
        'vip': 0,
        'port': csu_http.INT,
        'db_switch_func': 0,
        'remark': 0,
        'trigger_db_name': 0,
        'trigger_db_func': 0,
        'db_user': 0,
        'db_pass': 0,
        'repl_user': 0,
        'repl_pass': 0,
        'probe_db_name': 0,
        'probe_interval': csu_http.INT,
        'probe_timeout': csu_http.INT,
        'probe_retry_cnt': csu_http.INT,
        'probe_retry_interval': csu_http.INT,
        'probe_pri_sql': 0,
        'auto_failback': 0,
        'auto_failover': 0,
        'failover_keep_cascaded': 0,
        'probe_stb_sql': 0,
        'save_old_room_vip': 0,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']
    attr_dict = copy.copy(pdict)
    # 去除掉不能设置的属性
    forbid_attr_list = ['state', 'cluster_id', 'lock_time', 'cluster_type']
    for attr in forbid_attr_list:
        if attr in attr_dict:
            del attr_dict[attr]

    col_name_list = ['db_user', 'db_pass', 'repl_user', 'repl_pass']
    with dbapi.DBProcess() as dbp:
        set_dict = {}
        for col_name in col_name_list:
            if pdict.get(col_name):
                set_dict[col_name] = pdict.get(col_name)
        if 'db_user' in set_dict and 'repl_user' in set_dict:
            # 两个用户名相同,那么repl_pass的密码应该使用db_pass
            if set_dict['db_user'] == set_dict['repl_user']:
                set_dict['repl_pass'] = set_dict['db_pass']

        if set_dict:
            sql = "UPDATE clup_db set db_detail= db_detail || %s where cluster_id = %s "
            dbp.execute(sql, (json.dumps(set_dict), pdict['cluster_id']))

        dbp.execute("UPDATE clup_db SET port=%s WHERE cluster_id=%s", (pdict['port'], cluster_id))
        # 修改集群的数据库配置时需要修改配置文件配置
        search_sql = 'select host, pgdata from clup_db where cluster_id = %s'
        search_result = dbp.query(search_sql, (cluster_id, ))
        for res in search_result:
            # 修改配置文件中的端口
            try:
                rpc = None
                err_code, err_msg = rpc_utils.get_rpc_connect(res['host'])
                if err_code != 0:
                    return err_code, err_msg
                rpc = err_msg
                postgresql_conf = f"{res['pgdata']}/postgresql.conf"
                rpc.modify_config_type1(postgresql_conf, {"port": pdict['port']}, is_backup=False)
            except Exception as e:
                return 400, str(e)

        rows = dbp.query(
            "SELECT cluster_data FROM clup_cluster WHERE cluster_id=%s",
            (cluster_id,))
        if not rows:
            return 400, f"cluster_id({pdict['cluster_id']}) not exists!"

        cluster_dict = rows[0]['cluster_data']

        rooms = cluster_dict.get('rooms', {})
        cluster_dict.update(attr_dict)
        cur_room_info = pg_helpers.get_current_cluster_room(cluster_id)
        if cur_room_info:
            for k, v in attr_dict.items():
                if k in cur_room_info.keys():
                    cur_room_info[k] = v
            room_id = cur_room_info.pop('room_id', '0')
            rooms[str(room_id)] = {
                'room_name': cur_room_info.get('room_name', '默认机房'),
                'vip': cluster_dict['vip']
            }
            cluster_dict['rooms'] = rooms

        dbp.execute(
            "UPDATE clup_cluster SET cluster_data = %s WHERE cluster_id=%s",
            (json.dumps(cluster_dict), cluster_id))
    return 200, 'ok'


def add_sr_cluster_room_info(req):
    """添加流复制集群的机房信息
    """
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'pool_id': csu_http.INT,
        'room_info': csu_http.MANDATORY
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check the vip is in the vip pool
    pool_id = pdict['pool_id']
    all_room_index = list(pdict["room_info"].keys())
    vip = pdict['room_info'][all_room_index[-1]]['vip']

    code, result = ip_lib.check_vip_in_pool(pool_id, vip, no_used_check=True)
    if code != 0:
        return 400, result

    with dbapi.DBProcess() as dbp:
        insert_sql = "INSERT INTO clup_used_vip(pool_id, vip, cluster_id, used_reason) VALUES(%s, %s, %s, 2) RETURNING vip"
        insert_rows = dbp.query(insert_sql, (pool_id, vip, pdict['cluster_id']))
        if not insert_rows:
            return 400, f"Execute sql({insert_sql}) failed."

        sql = "SELECT cluster_data FROM clup_cluster WHERE cluster_id=%s"
        rows = dbp.query(sql, (pdict['cluster_id'], ))
        if not rows:
            return 400, f"Cluster (cluster_id={pdict['cluster_id']}) information not found"
        cluster_data = rows[0]['cluster_data']
        cluster_data['rooms'] = pdict['room_info']
        try:
            sql = "UPDATE clup_cluster SET cluster_data=%s WHERE cluster_id=%s"
            dbp.execute(sql, (json.dumps(cluster_data), pdict['cluster_id']))
        except Exception as e:
            return 400, f'Failed to update database information: {repr(e)}'

    pg_helpers.update_cluster_room_info(pdict['cluster_id'])
    return 200, 'ok'


def update_sr_cluster_room_info(req):
    """
    修改集群机房信息
    @param req:
    @return:
    """
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'pool_id': csu_http.INT,
        'room_info': csu_http.MANDATORY
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check the vip is in the vip pool
    pool_id = pdict['pool_id']
    all_room_index = list(pdict["room_info"].keys())
    vip = pdict['room_info'][all_room_index[-1]]['vip']

    code, result = ip_lib.check_vip_in_pool(pool_id, vip)
    if code != 0:
        return 400, result

    with dbapi.DBProcess() as dbp:
        sql = "SELECT cluster_data FROM clup_cluster WHERE cluster_id=%s"
        rows = dbp.query(sql, (pdict['cluster_id'], ))
        if not rows:
            return 400, f"Cluster (cluster_id={pdict['cluster_id']}) information not found"
        cluster_data = rows[0]['cluster_data']

        # check the old is used or not, if not used then delete
        old_room_vip = cluster_data["rooms"][all_room_index[-1]]['vip']
        if old_room_vip != vip:
            check_sql = "SELECT db_id, used_reason FROM clup_used_vip WHERE vip = %s"
            used_rows = dbp.query(check_sql, (vip, ))
            if used_rows and used_rows[0]['used_reason'] == 1:
                return 400, f"The vip {old_room_vip} is used by db(db_id={used_rows[0]['db_id']}),can not modify."
            else:
                # delete
                delete_sql = "DELETE FROM clup_used_vip WHERE vip = %s"
                dbp.execute(delete_sql, (old_room_vip, ))

        # check the vip is exists or not
        sql = "SELECT pool_id, cluster_id FROM clup_used_vip WHERE vip = %s"
        rows = dbp.query(sql, (vip, ))
        if rows:
            # check the vip owner is this cluster
            if rows[0]["cluster_id"] != pdict["cluster_id"]:
                return 400, f"The vip is aready used by cluster(cluster_id={rows[0]['cluster_id']})."
        else:
            insert_sql = "INSERT INTO clup_used_vip(pool_id, vip, cluster_id, used_reason) VALUES(%s, %s, %s, 2) RETURNING vip"
            insert_rows = dbp.query(insert_sql, (pool_id, vip, pdict["cluster_id"]))
            if not insert_rows:
                return 400, f"Execute sql({insert_sql}) failed."

        try:
            cluster_data['rooms'] = pdict['room_info']
            sql = "UPDATE clup_cluster SET cluster_data=%s WHERE cluster_id=%s"
            dbp.execute(sql, (json.dumps(cluster_data), pdict['cluster_id']))
        except Exception as e:
            return 400, f'Failed to update database information: {repr(e)}'
    pg_helpers.update_cluster_room_info(pdict['cluster_id'])
    return 200, 'ok'


def get_sr_cluster_room_info(req):
    """
    获取集群机房信息
    @param req:
    @return:
    """
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']
    sql = "SELECT cluster_data FROM clup_cluster WHERE cluster_id=%s"
    rows = dbapi.query(sql, (cluster_id, ))
    if not rows:
        return 400, f'Cluster(cluster_id: {cluster_id}) information not found'
    cluster_data = rows[0]['cluster_data']
    room_info = cluster_data.get('rooms', {})
    default_room = {
        'vip': cluster_data['vip'],
        'room_name': '默认机房',
        'room_use_state': 0
    }
    room_info = {'0': default_room} if not room_info else room_info
    cluster_db_list = dao.get_cluster_db_list(cluster_id)
    room_info_list = []
    for room_id, room_info in room_info.items():
        if not room_info:
            room_info.update(default_room)
        room_info['room_id'] = room_id
        room_info['room_use_state'] = 0
        for item in cluster_db_list:
            if item['room_id'] == room_info['room_id']:
                room_info['room_use_state'] = 1
                break
        # search vip pool info
        sql = "SELECT p.pool_id, start_ip, end_ip FROM clup_vip_pool p,clup_used_vip v "\
            " WHERE v.pool_id = p.pool_id AND v.vip = %s"
        pool_rows = dbapi.query(sql, (room_info['vip'], ))
        if not pool_rows:
            return 400, f"No recard find the vip information for vip {room_info['vip']}."

        room_info['pool_id'] = pool_rows[0]['pool_id']
        room_info['start_ip'] = pool_rows[0]['start_ip']
        room_info['end_ip'] = pool_rows[0]['end_ip']

        room_info_list.append(room_info)
    for row in room_info_list:
        row['room'] = f"{row.get('room_name', '默认机房')}(id: {row.get('room_id', '默认机房')})"
    room_info_list = helpers.format_rows(room_info_list)
    return 200, json.dumps(room_info_list)


def get_switch_log_api(req):
    """
    获取集群机房信息
    @param req:
    @return:
    """
    params = {
        'task_id': csu_http.MANDATORY | csu_http.INT,
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    try:
        sql = "SELECT create_time, log FROM task_log WHERE task_id=%s"
        rows = dbapi.query(sql, (pdict['task_id'], ))
        for row in rows:
            row['create_time'] = row['create_time'].strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        return 400, repr(e)
    return 200, json.dumps(rows)


def delete_sr_cluster_room_info(req):
    """
    删除集群机房信息
    @param req:
    @return:
    """
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'room_id': csu_http.MANDATORY,
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    cluster_id = pdict['cluster_id']
    room_id = pdict['room_id']

    sql = "SELECT db_id FROM clup_db WHERE cluster_id = %s AND db_detail->>'room_id' = %s "
    rows = dbapi.query(sql, (cluster_id, str(room_id)))
    if rows:
        db_id_list = [row['db_id'] for row in rows]
        return 400, f"Delete failed, have some databases ({str(db_id_list)}) in the machine room: (room_id={room_id})"
    sql = "SELECT cluster_data FROM clup_cluster WHERE cluster_id = %s "
    rows = dbapi.query(sql, (cluster_id, ))
    if not rows:
        return 400, f"cluster (cluster_id={cluster_id}) belongs machine room information not found,or can not delete default machine room."
    try:
        cluster_data = rows[0]['cluster_data']
        room_info = cluster_data.get("rooms", {})
        delete_vip = copy.copy(room_info[str(room_id)]['vip'])

        del room_info[str(room_id)]
        cluster_data['rooms'] = room_info
        sql = "UPDATE clup_cluster SET cluster_data = %s WHERE cluster_id = %s"
        dbapi.execute(sql, (json.dumps(cluster_data), cluster_id))

        # delete clup_used_vip
        delete_sql = "DELETE FROM clup_used_vip WHERE vip = %s"
        dbapi.execute(delete_sql, (delete_vip, ))

    except Exception as e:
        return 400, f'delete failure: {repr(e)}'
    return 200, "OK"


def remove_db_from_cluster(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'db_id': csu_http.MANDATORY | csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    sql = "SELECT host, port, cluster_data->'cluster_name' as cluster_name FROM" \
          " clup_db INNER JOIN clup_cluster USING (cluster_id) WHERE db_id=%s"
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if len(rows) == 0:
        return 400, 'No database information found'
    # 集群移除节点修改
    dbapi.execute("UPDATE clup_db SET cluster_id=null WHERE cluster_id=%(cluster_id)s and db_id=%(db_id)s", pdict)

    return 200, 'ok'


def modify_db_in_cluster(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'db_id': csu_http.MANDATORY | csu_http.INT,
        'os_user': 0,
        'pgdata': 0,
        'is_primary': 0,
        'repl_app_name': 0,
        'host': 0,
        'repl_ip': 0,
        'scores': 0,
        'is_rebuild': 0,
        'is_rewind': 0,
        'up_db_id': 0,
        'rm_pgdata': 0,
        'room_id': 0,
        'reset_cmd': 0
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']
    db_id = pdict['db_id']
    db_dict = pdict

    del db_dict['cluster_id']
    del db_dict['db_id']
    db_detail = {
        'is_rewind': db_dict.pop('is_rewind', False),
        'is_rebuild': db_dict.pop('is_rebuild', False),
        'rm_pgdata': db_dict.pop('rm_pgdata', 0),
        'room_id': db_dict.pop('room_id', '0'),
        'reset_cmd': db_dict.get('reset_cmd', '')
    }
    if 'reset_cmd' in db_dict.keys():
        del db_dict['reset_cmd']
    binds = []
    set_list = []
    for attr in db_dict:
        set_list.append("{col_name}=%s".format(col_name=attr))
        binds.append(db_dict[attr])
    if len(binds) == 0 and not db_detail:
        return 400, 'not change data!'

    set_stmt = ', '.join(set_list)
    sql = "UPDATE clup_db SET " + set_stmt + " WHERE cluster_id=%s and db_id = %s"
    binds.append(cluster_id)
    binds.append(db_id)

    with dbapi.DBProcess() as dbp:
        rows = dbp.query("SELECT db_detail FROM clup_db WHERE db_id =%s", (db_id,))
        if not rows:
            return 400, f'No database information found(db_id: {db_id})'
        db = rows[0]['db_detail']
        if 'reset_cmd' in db and db_detail['reset_cmd'] == '':
            del db_detail['reset_cmd']
        db.update(db_detail)
        dbp.execute("UPDATE clup_db SET db_detail=%s WHERE db_id = %s", (json.dumps(db), db_id))
        if set_list:
            dbp.execute(sql, tuple(binds))

    return 200, 'ok'


def get_last_lsn(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']
    err_code, lsn_list_data = ha_mgr.get_last_lsn(cluster_id)
    data = []
    # 1, "192.168.0.61", 1, 10, "0/57262D0"
    for lsn_data in lsn_list_data:
        row = {"id": lsn_data[0],
               "host": lsn_data[1],
               "is_primary": lsn_data[2],
               "timeline": lsn_data[3],
               "lsn": lsn_data[4],
               }
        data.append(row)

    ret_data = {"total": len(lsn_list_data), "page_size": 100, "rows": data}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def get_repl_delay(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    cluster_id = pdict['cluster_id']

    err_code, data = ha_mgr.get_repl_delay(cluster_id)
    if err_code != 0:
        return 400, data

    ret_data = {"total": len(data), "page_size": 100, "rows": data}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def online_cluster(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    cluster_id = pdict['cluster_id']

    err_code, err_list = ha_mgr.online(cluster_id)
    if err_code != 0:
        return 400, json.dumps(err_list)
    pg_helpers.update_cluster_room_info(cluster_id)

    return 200, json.dumps(err_list)


def offline_cluster(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    cluster_id = pdict['cluster_id']

    err_code, err_msg = ha_mgr.offline(cluster_id)
    if err_code != 0:
        return 400, err_msg
    return 200, 'ok'


def repair(req):
    """加回集群

    Args:
        req ([type]): [description]

    Returns:
        [type]: [description]
    """
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'db_id': csu_http.MANDATORY | csu_http.INT,
        'up_db_id': csu_http.MANDATORY | csu_http.INT,
        'rm_pgdata': csu_http.MANDATORY | csu_http.INT,
        'tblspc_dir': 0,
        'is_rewind': 0,
        'is_rebuild': 0
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    cluster_id = pdict['cluster_id']
    db_id = pdict['db_id']
    up_db_id = pdict['up_db_id']

    # 当主库ha状态坏的时候,加回集群检查当前集群中只有一个正常的主库在运行,就把状态改为正常1
    db_dict = dao.get_db_state(db_id)
    if db_dict['state'] == node_state.FAULT and db_dict['is_primary']:
        primary_list = dao.get_cluster_primary(cluster_id)
        normail_primary_list = []
        for primary in primary_list:
            err_code, err_msg = rpc_utils.get_rpc_connect(primary['host'], 2)
            if err_code == 0:
                rpc = err_msg
                rpc.close()
                err_code, is_run = pg_db_lib.is_running(primary['host'], primary['pgdata'])
                if is_run:
                    normail_primary_list.append(primary['db_id'])
        if len(normail_primary_list) == 1 and normail_primary_list[0] == db_id:
            dao.set_cluster_db_state(cluster_id, db_id, 1)
            return 200, ''

    # 先检测是否可以修复,如果不能,直接返回
    ret_code, msg = ha_mgr.can_be_failback(cluster_id, db_id)
    if ret_code != 0:
        return 400, msg

    ret = dao.test_and_set_cluster_state(cluster_id, [cluster_state.NORMAL, cluster_state.OFFLINE, cluster_state.FAILED], cluster_state.REPAIRING)
    if ret is None:
        err_msg = f"cluster({cluster_id}) state is failover or repairing or checking, can not repair now!"
        logging.info(err_msg)
        return -1, (-1, err_msg)

    dao.update_up_db_id(up_db_id, db_id, db_dict['is_primary'])
    restore_cluster_state = ret
    # 因为是一个长时间运行的操作,所以生成一个后台任务,直接返回
    task_name = f"failback {cluster_id}(db={db_id})"
    task_id = general_task_mgr.create_task(task_type_def.FAILBACK, task_name, {'cluster_id': cluster_id})
    general_task_mgr.run_task(task_id, ha_mgr.failback, (pdict, restore_cluster_state))

    ret_data = {"task_id": task_id, "task_name": task_name}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def sr_switch(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'keep_cascaded': 0,
        'db_id': 0,
        'room_id': 0,
        'workwx': 0
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    cluster_id = pdict['cluster_id']
    db_id = pdict.get('db_id')
    room_id = pdict.get('room_id')
    keep_cascaded = pdict.get('keep_cascaded', False)
    if not db_id and room_id is None:
        return 400, 'The room id or database id must be specified'
    if room_id is not None and not db_id:
        sql = "SELECT db_id FROM clup_db " \
              "WHERE db_detail->>'room_id' = %s AND cluster_id = %s AND state = %s AND is_primary=0 ORDER BY scores"
        rows = dbapi.query(sql, (str(room_id), cluster_id, node_state.NORMAL))
        if not rows:
            return 400, f'No standby database in normal state is found in the room.(room_id={room_id})'
        db_id = pg_helpers.get_max_lsn_db(rows)
        if not db_id:
            return 400, f'No standby database in normal state is found in the room.(room_id: {room_id})'
    sql = "SELECT COUNT(*) AS cnt FROM clup_db WHERE db_id = %s AND cluster_id = %s"
    rows = dbapi.query(sql, (db_id, cluster_id))
    if rows[0]['cnt'] == 0:
        return 400, f'The database (db_id={db_id}) is not found in the cluster (cluster_id={cluster_id})'
    # 数据库操作时时检查是否集群信息存在,存在则判断集群是否下线,如果未下线则不允许操作
    if cluster_id:
        return_cluster_state = dao.get_cluster_state(cluster_id)
        if return_cluster_state != cluster_state.OFFLINE and return_cluster_state != cluster_state.FAILED:
            return 400, f"Before performing database operations, please take its cluster(cluster_id={cluster_id}) offline"

    sql = 'select db_id from clup_db where is_primary=1 and cluster_id = %s'
    rows = dbapi.query(sql, (cluster_id, ))
    if not rows:
        return 400, f'The primary database is not found in the cluster ({cluster_id})'
    old_primary_db = rows[0]['db_id']
    sql = f"""SELECT count(*) as cnt from clup_general_task where state=0 and task_data @> '{{"cluster_id": {cluster_id} }}' """
    rows = dbapi.query(sql)
    cnt = rows[0]['cnt']
    if cnt > 0:
        return 400, "The cluster has other operations in progress. Please try again later."

    workwx = pdict.get("workwx")
    # 先检测是否可以切换,如果不能,直接返回
    try:
        ret_code, msg = ha_mgr.test_sr_can_switch(cluster_id, db_id, old_primary_db, keep_cascaded)
        if ret_code != 0:
            if workwx:
                workwx['db_id'] = db_id
                workwx['state'] = "Failed"
                pg_helpers.send_workwx_alarm(workwx)
            return 400, msg
    except Exception as e:
        logging.error(f"Call test_sr_can_switch exception: {traceback.format_exc()}")
        if pdict.get("workwx"):
            workwx['db_id'] = db_id
            workwx['state'] = "Failed"
            pg_helpers.send_workwx_alarm(workwx)
        return 400, str(e)

    # 因为是一个长时间运行的操作,所以生成一个后台任务,直接返回
    task_name = f"sr_switch (cluster_id={cluster_id}, db_id={db_id})"
    task_id = general_task_mgr.create_task(task_type_def.SWITCH, task_name, {'cluster_id': cluster_id})
    general_task_mgr.run_task(task_id, ha_mgr.sr_switch, (cluster_id, db_id, old_primary_db, keep_cascaded))

    ret_data = {"task_id": task_id, "task_name": task_name}
    raw_data = json.dumps(ret_data)
    if workwx:
        try:
            workwx['db_id'] = db_id
            pg_helpers.send_workwx_alarm(workwx)
        except Exception as e:
            logging.error(f'Alarm sending failure: {repr(e)}')
    return 200, raw_data


def get_cluster_list_for_host_login(req):
    params = {'page_num': csu_http.MANDATORY | csu_http.INT,
              'page_size': csu_http.MANDATORY | csu_http.INT,
              'filter': 0,
              'vip': 0
              }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    page_num = pdict['page_num']
    page_size = pdict['page_size']

    sql = """
    with p as (select cluster_id, string_agg(host, ',') ip_list
    from clup_db inner join clup_cluster using (cluster_id) group by cluster_id)
        select c.cluster_id, c.cluster_data->>'cluster_name' as cluster_name,
        case when p.ip_list is null then (c.cluster_data->>'host1_ip') ||','|| (c.cluster_data->>'host2_ip')
        else p.ip_list end as ip_list,
        c.cluster_data->>'remark' as remark
        from clup_cluster c left join p on c.cluster_id= p.cluster_id
    """
    total_sql = "SELECT count(*) as cnt FROM clup_cluster c"

    offset = (page_num - 1) * page_size
    binds = ()
    if 'filter' in pdict:
        where_cond = " WHERE c.cluster_data->>'cluster_name' like %s"
        sql += where_cond
        total_sql += where_cond
        binds = (pdict['filter'],)

    rows = dbapi.query(total_sql, binds)
    row_cnt = rows[0]['cnt']

    sql += f" ORDER BY cluster_id LIMIT {page_size} OFFSET {offset}"
    rows = dbapi.query(sql, binds)

    ret_data = {"total": row_cnt, "page_size": pdict['page_size'], "rows": rows}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def get_cluster_ip_list_for_login(req):
    params = {
        "cluster_id": csu_http.MANDATORY | csu_http.INT
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    with dbapi.DBProcess() as dbp:
        sql = "SELECT cluster_type, cluster_data FROM clup_cluster WHERE cluster_id = %(cluster_id)s"
        rows = dbp.query(sql, pdict)
        if len(rows) <= 0:
            return 400, f"cluster_id({pdict['cluster_id']}) not exists"
        row = rows[0]
        cluster_type = row['cluster_type']
        clu_dict = row['cluster_data']
        if cluster_type == 2:
            ret_data = [{"node_ip": clu_dict['host1_ip']}, {"node_ip": clu_dict['host2_ip']}]
        else:
            sql = "SELECT host as node_ip FROM clup_db WHERE cluster_id = %(cluster_id)s"
            ret_data = dbp.query(sql, pdict)
    return 200, json.dumps({"rows": ret_data})


def get_all_cluster(req):
    """
    查询到所有集群
    :param req:
    :return:
    """
    params = {}
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # sql = "select cluster_id,cluster_data->>'cluster_name' as cluster_name from clup_cluster where state=0;"
    sql = "select cluster_id,cluster_data->>'cluster_name' as cluster_name " \
          "from clup_db inner join clup_cluster using(cluster_id) where clup_cluster.state = 1 " \
          "group by cluster_id,cluster_data->>'cluster_name';"
    rows = dbapi.query(sql)
    return 200, json.dumps(rows)


def get_all_instance(req):
    """
    查询所有实例
    :param req:
    :return:
    """
    params = {
        'cluster_id': csu_http.MANDATORY
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    sql = "select db_id, host,is_primary from clup_db where cluster_id = %(cluster_id)s order by host;"
    rows = dbapi.query(sql, pdict)

    return 200, json.dumps(rows)


def create_sr_cluster(req):
    """创建PostgreSQL流复制集群

    """
    params = {
        'cluster_name': csu_http.MANDATORY,
        'pool_id': csu_http.INT,
        'vip': csu_http.MANDATORY,
        'port': csu_http.MANDATORY,
        'db_user': csu_http.MANDATORY,
        'db_pass': csu_http.MANDATORY,
        'repl_user': csu_http.MANDATORY,
        'repl_pass': csu_http.MANDATORY,
        'db_list': csu_http.MANDATORY,
        'remark': 0,
        'trigger_db_name': 0,
        'trigger_db_func': 0,
        'probe_db_name': csu_http.MANDATORY,
        'probe_interval': csu_http.MANDATORY | csu_http.INT,
        'probe_timeout': csu_http.MANDATORY | csu_http.INT,
        'probe_retry_cnt': csu_http.MANDATORY | csu_http.INT,
        'probe_retry_interval': csu_http.MANDATORY | csu_http.INT,
        'probe_pri_sql': csu_http.MANDATORY,
        'probe_stb_sql': csu_http.MANDATORY,
        'wal_segsize': csu_http.INT,           # wal段文件大小，仅PG11及以上版本支持
        'setting_list': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check vip is used or not
    check_sql = "SELECT * FROM clup_used_vip WHERE vip=%s"
    check_rows = dbapi.query(check_sql, (pdict["vip"], ))
    if check_rows:
        return 400, f"The vip({pdict['vip']}) is aready used by(db_id={check_rows[0]['db_id']},cluster_id={check_rows[0]['cluster_id']}), please check."

    # 检查rpc连接以及数据库插件
    try:
        rpc = None
        err_host_list = []
        not_exist_list = []
        for db in pdict['db_list']:
            err_code, err_msg = rpc_utils.get_rpc_connect(db['host'])
            if err_code != 0:
                err_host_list.append(db['host'])
                continue
            rpc = err_msg

            setting_index = 0
            setting_list = pdict["setting_list"]
            for item in setting_list:
                if item["setting_name"] == "shared_preload_libraries":
                    break
                setting_index += 1
            plug_str = str(setting_list[setting_index]["val"])
            plug_list = plug_str.split(",")
            pg_bin_path = db['pg_bin_path']

            for plug in plug_list:
                plug = plug.strip()
                plug_ctl_file = f"{pg_bin_path}/../share/extension/{plug}.control"
                if not rpc.os_path_exists(plug_ctl_file):
                    plug_ctl_file = f"{pg_bin_path}/../share/postgresql/extension/{plug}.control"
                    if not rpc.os_path_exists(plug_ctl_file):
                        not_exist_list.append(plug)
            rpc.close()
            if not_exist_list:
                return 400, ",".join(not_exist_list) + " not install, you can remove from the plugs shared_preload_libraries!"
        if err_host_list:
            return 400, f'Host connection failure ({str(err_host_list)}),please check service clup-agent is running!'
    except Exception:
        if rpc:
            rpc.close()
        return 400, f"Check the rpc connect and plugs with unexcept error, {traceback.format_exc()}."

    # 定义cluster_data
    cluster_data = pdict.copy()
    del cluster_data['db_list']

    # 操作记录信息
    db_info = {
        "host": [],
        "pgdata": [],
        "port": pdict['port']
    }
    # 检查数据库信息是否已经存在
    for db in pdict['db_list']:
        sql = "SELECT db_id FROM clup_db WHERE host=%s AND port = %s AND pgdata= %s "
        rows = dbapi.query(sql, (db['host'], pdict['port'], db['pgdata']))
        if len(rows) > 0:
            return 400, f"The input database information is({db['host']}:{pdict['port']} " \
                f"pgdata={db['pgdata']}) the same as the existing database.(db_id={rows[0]['db_id']})!"
        db_info['host'].append(db['host'])
        db_info['pgdata'].append(db['pgdata'])

    # 插入集群表
    sql = "INSERT INTO clup_cluster(cluster_type, cluster_data,state,lock_time) " \
        "VALUES (%s, %s, %s, %s) RETURNING cluster_id"
    # 不要把setting_list存入数据库
    cluster_data_in_db = cluster_data.copy()
    del cluster_data_in_db['setting_list']
    rows = dbapi.query(sql, (1, json.dumps(cluster_data_in_db), 0, 0))
    if len(rows) == 0:
        return 400, 'Failed to insert the cluster into the database'
    cluster_id = rows[0]['cluster_id']
    pdict['cluster_id'] = cluster_id

    # insert into clup_used_vip
    insert_sql = "INSERT INTO clup_used_vip(pool_id, vip, cluster_id, used_reason) VALUES(%s, %s, %s, 2) RETURNING vip"
    insert_rows = dbapi.query(insert_sql, (pdict["pool_id"], pdict["vip"], cluster_id))
    if not insert_rows:
        return 400, f"Excute sql({insert_sql}) failed."

    # 开启线程后台创建
    task_name = f"create_sr_cluster(cluster_id={pdict['cluster_id']})"
    task_id = general_task_mgr.create_task(task_type_def.CREATE_SR_CLUSTER, task_name, {'cluster_id': pdict['cluster_id']})
    general_task_mgr.run_task(task_id, long_term_task.task_create_sr_cluster, (cluster_id, pdict))

    ret_data = {"task_id": task_id, "task_name": task_name}
    raw_data = json.dumps(ret_data)

    return 200, raw_data


# 磁盘检查
def check_shared_disk(req):
    params = {
        'shared_disk': csu_http.MANDATORY,
        'mount_path': csu_http.MANDATORY,
        'pgdata': csu_http.MANDATORY,
        'host1_ip': csu_http.MANDATORY,
        'host2_ip': csu_http.MANDATORY,
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 200, json.dumps({"err_code": err_code, "err_msg": pdict})

    shared_disk = pdict['shared_disk']
    shared_disk = shared_disk.strip()
    disk_keys = ['LABEL=', 'UUID=', '/dev/']

    pgdata = pdict['pgdata']
    mount_path = pdict['mount_path']
    if not pgdata.startswith(pdict["mount_path"]):
        return 200, json.dumps({"err_code": -1, "err_msg": f"The data directory{pgdata}does not match the mount path{mount_path}, please check the data directory"})

    host_list = (pdict['host1_ip'], pdict['host2_ip'])
    for host in host_list:
        rpc = None
        try:
            err_code, err_msg = rpc_utils.get_rpc_connect(host)
            if err_code != 0:
                err_msg = f"Unable to connect to the host: {host}"
                return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
            rpc = err_msg

            # 获取'/dev/sdX'这样的设备路径存放在dev_path中
            if shared_disk.startswith('/dev/'):
                err_code, err_msg = rpc.os_real_path(shared_disk)
                if err_code != 0:
                    err_msg = f"Error executing command: os.path.realpath({shared_disk}) on the host{host}, error: {err_msg}"
                    return 200, json.dumps({"err_code": -1, "err_msg": err_msg})

                dev_path = err_msg
            elif shared_disk.startswith('LABEL=') or shared_disk.startswith('UUID='):
                cells = shared_disk.split('=')
                dev_label = cells[1].strip()
                # 可能携带单引号或双引号导致出错
                dev_label = dev_label.strip("'")
                dev_label = dev_label.strip('"')
                if shared_disk.startswith('LABEL='):
                    cmd = f"blkid -L {dev_label}"
                else:
                    cmd = f"blkid -U {dev_label}"
                err_code, err_msg, out_msg = rpc.run_cmd_result(cmd)
                if err_code != 0:
                    if not err_msg:
                        err_msg = f"The shared disk: {shared_disk} does not exist on the host: {host}"
                        return 200, json.dumps({"err_code": -1, "err_msg": err_msg})

                    else:
                        return 400, f"Error executing command: {cmd} on the host:{host}. error:: {err_msg}"
                dev_path = out_msg.strip()
            else:
                err_msg = f"The disk name ({shared_disk}) entered is incorrect and does not start with an item in the list({disk_keys})."
                return 200, json.dumps({"err_code": -1, "err_msg": err_msg})

            if not rpc.os_path_exists(dev_path):
                err_msg = f"The shared disk ({shared_disk}) does not exist on the host: {host}"
                return 200, json.dumps({"err_code": -1, "err_msg": err_msg})

            err_code, err_msg = rpc.os_stat(dev_path)
            if err_code != 0:
                err_msg = f"Failed to get the shared disk({shared_disk}) ID on the host({host}).error: {err_msg}"
                return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
            st_dict = err_msg
            shared_disk_dev_no = st_dict['st_rdev']

            # 检查磁盘或是目录是否已经挂载,如果已经挂载,挂载的路径是否是给定的路径
            # 先读取文件内容
            mount_file = "/proc/mounts"
            err_code, err_msg = rpc.file_read(mount_file)
            if err_code != 0:
                err_msg = f"Error get file(/proc/mounts) content, error: {err_msg}"
                return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
            file_content = err_msg
            lines = file_content.split('\n')

            # 判断设备的挂载情况,如果设备挂载到其他目录下时,直接报错,如果要挂载的目录挂载了其他磁盘,也直接报错
            _is_mounted = False
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line[0] != "/":
                    continue
                cells = line.split()
                tmp_dev_path = cells[0]
                tmp_mount_path = cells[1]
                err_code, err_msg = rpc.os_stat(tmp_dev_path)
                if err_code != 0:
                    err_msg = f"Failed to get the shared disk({tmp_dev_path}) ID on the host({host}), error: {err_msg}"
                    return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
                st_dict = err_msg
                tmp_dev_no = st_dict['st_rdev']
                if tmp_dev_no != shared_disk_dev_no:
                    if tmp_mount_path == mount_path:
                        err_msg = f"Other devices({tmp_dev_path}) are mounted in the directory({pdict['mount_path']}) on the host({host})!"
                        return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
                else:
                    if tmp_mount_path != mount_path:
                        err_msg = f"The shared disk on the host({host}) has been mounted to another directory({tmp_mount_path}), please uninstall and try again!"
                        return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
                    else:
                        err_msg = f"The shared disk on the host({host}) has been mounted to the directory({tmp_mount_path}), please uninstall and try again!"
                        return 200, json.dumps({"err_code": -1, "err_msg": err_msg})

        except Exception:
            err_msg = traceback.format_exc()
            return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
        finally:
            if rpc:
                rpc.close()

    # 做mount和umount测试
    for host in host_list:
        rpc = None
        try:

            err_code, err_msg = rpc_utils.get_rpc_connect(host)
            if err_code != 0:
                err_msg = f"Unable to connect to the host:{host}, err_msg: {err_msg}"
                return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
            rpc = err_msg
            err_code, err_msg = rpc.mount_dev(pdict['shared_disk'], mount_path)
            if err_code != 0:
                err_msg = f"The shared disk cannot be mounted on the host({host}). error: {err_msg}"
                return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
            # 检查数据目录是否存在,如果存在是否为空
            is_exists = rpc.os_path_exists(pgdata)
            if is_exists:
                # 特殊情况：磁盘不为空的情况下,数据目录文件夹的非空判断会报错。
                is_empty = rpc.dir_is_empty(pgdata)
                if not is_empty:
                    # 不检查umount返回码了,失败的概率很低
                    rpc.umount_dev(mount_path)
                    return 200, json.dumps({"err_code": -1, "err_msg": f"The data directory({pgdata}) is not empty, please check the data directory"})
            # ===============
            err_code, err_msg = rpc.umount_dev(mount_path)
            if err_code != 0:
                err_msg = f"The shared disk cannot be umount on the host({host}). error: {err_msg}"
                return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
        except Exception:
            err_msg = traceback.format_exc()
            return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
        finally:
            if rpc:
                rpc.close()

    return 200, json.dumps({"err_code": 0, "err_msg": ""})


def get_cluster_all_db(req):
    params = {
        'cluster_id': csu_http.MANDATORY,
        'db_id': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    sql = "SELECT db_id, up_db_id, host, port, db_state," \
        " db_detail->>'polar_type' as polar_type" \
        " FROM clup_db " \
        " WHERE cluster_id=%s AND db_id != %s "
    rows = dbapi.query(sql, (pdict['cluster_id'], pdict['db_id']))
    return 200, json.dumps(rows)


def set_cluster_failover_state(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'auto_failback': csu_http.MANDATORY | csu_http.INT
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    try:
        sql = f"UPDATE clup_cluster set cluster_data=jsonb_set(cluster_data, '{{auto_failback}}', '{pdict['auto_failback']}')" \
              f" WHERE cluster_id=%s"
        dbapi.execute(sql, (pdict['cluster_id'], ))
    except Exception as e:
        return 400, repr(e)
    return 200, 'OK'


def get_cluster_primary_info_api(req):
    params = {
        "cluster_id": csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    db = dao.get_primary_info(pdict['cluster_id'])
    if not db:
        return 400, "Cluster primary database not found."
    return 200, json.dumps({"host": db['host'], "port": db['port']})


def get_db_relation(req):
    params = {
        "cluster_id": csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    cluster_id = pdict['cluster_id']
    primary_db = dao.get_primary_info(cluster_id)
    primary_db['name'] = primary_db['host']
    err_code, room = pg_helpers.get_db_room(primary_db['db_id'])
    primary_db['room_name'] = room.get('room_name', '') if err_code == 0 else ''
    if not primary_db:
        return 400, f'Failed to obtain cluster primary database information.(cluster_id:{cluster_id})'
    lower_db_rows = dao.get_lower_db(primary_db['db_id'])
    primary_db['children'] = lower_db_rows
    pg_helpers.get_db_relation_info(primary_db)
    return 200, json.dumps(primary_db)


def change_db_ha_state(req):
    """修改数据库的HA状态"""
    params = {
        'db_id': csu_http.MANDATORY,
        'cluster_id': csu_http.MANDATORY,
        'state': csu_http.MANDATORY | csu_http.INT,
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    sql = "UPDATE clup_db SET state=%(state)s WHERE db_id=%(db_id)s"
    dbapi.execute(sql, pdict)
    return 200, 'OK'


def check_ha(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']

    rows = dao.get_cluster_db_list(cluster_id)
    for row in rows:
        db_id = row['db_id']
        up_db_id = row.get('up_db_id')
        state = row['state']
        if state != node_state.FAULT and state != node_state.NORMAL:
            continue
        if row['is_primary']:
            db_dict = dao.get_db_info(db_id)
            if not db_dict:
                return 400, f"Primary database(db_id={db_id}) information not found."
            err_code, is_run = pg_db_lib.is_running(db_dict[0]['host'], db_dict[0]['pgdata'])
            if err_code != 0 or not is_run:
                return 400, f"please check database(db_id={db_id})status is running: {is_run}"
            err_code, err_msg = dao.update_ha_state(db_id, node_state.NORMAL)
            if err_code != 0:
                return 400, err_msg
            continue
        if not up_db_id:
            continue
        err_code, err_msg, data = pg_helpers.check_sr_conn(db_id, up_db_id)
        if err_code != 0:
            return 400, f'check failure: {err_msg} {data}'
        if data['cnt'] == 0 and state == node_state.NORMAL:
            state = node_state.FAULT
        elif data['cnt'] == 1 and state == node_state.FAULT:
            state = node_state.NORMAL
        err_code, err_msg = dao.update_ha_state(db_id, state)
        if err_code != 0:
            return 400, err_msg
    return 200, 'ok'


# 创建polardb共享存储集群
def create_polar_sd_cluster(req):
    params = {
        'cluster_name': csu_http.MANDATORY,
        'pool_id': csu_http.INT,  # vip pool id
        'vip': csu_http.MANDATORY,
        'port': csu_http.MANDATORY,
        'db_user': csu_http.MANDATORY,
        'db_pass': csu_http.MANDATORY,
        'repl_user': csu_http.MANDATORY,
        'repl_pass': csu_http.MANDATORY,
        'db_list': csu_http.MANDATORY,
        'db_type': csu_http.MANDATORY,
        'trigger_db_name': 0,
        'trigger_db_func': 0,
        'probe_db_name': csu_http.MANDATORY,
        'probe_interval': csu_http.MANDATORY | csu_http.INT,
        'probe_timeout': csu_http.MANDATORY | csu_http.INT,
        'probe_retry_cnt': csu_http.MANDATORY | csu_http.INT,
        'probe_retry_interval': csu_http.MANDATORY | csu_http.INT,
        'probe_pri_sql': csu_http.MANDATORY,
        'probe_stb_sql': csu_http.MANDATORY,
        'setting_list': csu_http.MANDATORY,
        'wal_segsize': csu_http.INT,           # wal段文件大小，仅PG11及以上版本支持
        'pfsdaemon_params': csu_http.MANDATORY,
        'pfs_disk_name': csu_http.MANDATORY,
        'polar_datadir': csu_http.MANDATORY,
        'ignore_reset_cmd_return_code': csu_http.INT,
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check vip is useed or not
    check_sql = "SELECT * FROM clup_used_vip WHERE vip=%s"
    check_rows = dbapi.query(check_sql, (pdict["vip"], ))
    if check_rows:
        return 400, f"The vip({pdict['vip']}) is aready used by(db_id={check_rows[0]['db_id']},cluster_id={check_rows[0]['cluster_id']}), please check."

    # 检查数据库信息是否已经存在
    for db in pdict['db_list']:
        sql = "SELECT db_id FROM clup_db WHERE host=%s AND port = %s AND pgdata= %s "
        rows = dbapi.query(sql, (db['host'], pdict['port'], db['pgdata']))
        if len(rows) > 0:
            return 400, f"Input database information({db['host']}:{pdict['port']} pgdata={db['pgdata']}) is the same as the database(db_id={rows[0]['db_id']})!"

    # 检查rpc是否能够连接上
    err_host_list = []
    for db in pdict['db_list']:
        err_code, rpc = rpc_utils.get_rpc_connect(db['host'])
        if err_code != 0:
            err_host_list.append(db['host'])
        rpc.close()
    if err_host_list:
        return 400, f"Host connection failure({str(err_host_list)}), please check service clup-agent is running!"

    # 参数解析
    # pfs 信息
    pfs_info = {
        "pfs_disk_name": pdict["pfs_disk_name"],
        "polar_datadir": pdict["polar_datadir"],
        "pfsdaemon_params": pdict["pfsdaemon_params"]
    }
    # 数据库节点信息
    master_node_info = pdict["db_list"][0]
    reader_node_info_list = pdict["db_list"][1:]

    master_node_info["port"] = pdict["port"]
    master_node_info["db_user"] = pdict["db_user"]
    master_node_info["db_pass"] = pdict["db_pass"]
    master_node_info["repl_user"] = pdict["repl_user"]
    master_node_info["repl_pass"] = pdict["repl_pass"]
    master_node_info["wal_segsize"] = pdict["wal_segsize"]
    master_node_info["setting_list"] = pdict["setting_list"]

    # 定义cluster_data
    cluster_data = pdict.copy()
    del cluster_data['db_list']
    del cluster_data["setting_list"]
    cluster_data['ignore_reset_cmd_return_code'] = pdict.get('ignore_reset_cmd_return_code', 0)
    cluster_data['polar_hostid'] = len(pdict['db_list']) + 1

    # 插入集群表
    sql = "INSERT INTO clup_cluster(cluster_type, cluster_data,state,lock_time) " \
        "VALUES (%s, %s, %s, %s) RETURNING cluster_id"
    rows = dbapi.query(sql, (11, json.dumps(cluster_data), 0, 0))
    if len(rows) == 0:
        return 400, 'Failed to add the database to the cluster.'
    cluster_id = rows[0]['cluster_id']

    # insert into clup_used_vip
    insert_sql = "INSERT INTO clup_used_vip(pool_id, vip, cluster_id, used_reason) VALUES(%s, %s, %s, 2) RETURNING vip"
    insert_rows = dbapi.query(insert_sql, (pdict["pool_id"], pdict["vip"], cluster_id))
    if not insert_rows:
        return 400, f"Excute sql({insert_sql}) failed."

    # 开启线程后台创建数据库
    task_name = f"create_sr_cluster(cluster_id={cluster_id})"
    task_id = general_task_mgr.create_task('create_sr_cluster', task_name, {'cluster_id': cluster_id})
    general_task_mgr.run_task(task_id, long_term_task.task_create_polar_sd_cluster, (cluster_id, master_node_info, reader_node_info_list, pfs_info))

    ret_data = {"task_id": task_id, "task_name": task_name}
    return 200, json.dumps(ret_data)


# 修改polardb共享存储集群信息
def modify_polar_cluster_info(req):
    """
    :param req:
    :return:
    """
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'cluster_name': 0,
        'vip': 0,
        'port': csu_http.INT,
        'db_switch_func': 0,
        'remark': 0,
        'trigger_db_name': 0,
        'trigger_db_func': 0,
        'db_user': 0,
        'db_pass': 0,
        'repl_user': 0,
        'repl_pass': 0,
        'probe_db_name': 0,
        'probe_interval': csu_http.INT,
        'probe_timeout': csu_http.INT,
        'probe_retry_cnt': csu_http.INT,
        'probe_retry_interval': csu_http.INT,
        'probe_pri_sql': 0,
        'auto_failback': 0,
        'probe_stb_sql': 0,
        'save_old_room_vip': 0,
        'polar_hostid': csu_http.MANDATORY,
        'pfs_disk_name': csu_http.MANDATORY,
        'polar_datadir': csu_http.MANDATORY,
        'pfsdaemon_params': csu_http.MANDATORY,
        'ignore_reset_cmd_return_code': csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id = pdict['cluster_id']
    attr_dict = copy.copy(pdict)
    # 去除掉不能设置的属性
    forbid_attr_list = ['state', 'cluster_id', 'lock_time', 'cluster_type']
    for attr in forbid_attr_list:
        if attr in attr_dict:
            del attr_dict[attr]

    # 需要同步修改clup_db中的信息
    col_name_list = ['db_user', 'db_pass', 'repl_user', 'repl_pass', 'pfsdaemon_params']
    with dbapi.DBProcess() as dbp:
        set_dict = {}
        for col_name in col_name_list:
            if pdict.get(col_name):
                set_dict[col_name] = pdict.get(col_name)
        if 'db_user' in set_dict and 'repl_user' in set_dict:
            # 两个用户名相同,那么repl_pass的密码应该使用db_pass
            if set_dict['db_user'] == set_dict['repl_user']:
                set_dict['repl_pass'] = set_dict['db_pass']

        if set_dict:
            sql = "UPDATE clup_db set db_detail= db_detail || %s where cluster_id = %s "
            dbp.execute(sql, (json.dumps(set_dict), pdict['cluster_id']))

        dbp.execute("UPDATE clup_db SET port=%s WHERE cluster_id=%s", (pdict['port'], cluster_id))
        rows = dbp.query(
            "SELECT cluster_data FROM clup_cluster WHERE cluster_id=%s",
            (cluster_id,))
        if not rows:
            return 400, f"cluster_id({pdict['cluster_id']}) not exists!"

        cluster_dict = rows[0]['cluster_data']

        rooms = cluster_dict.get('rooms', {})
        cluster_dict.update(attr_dict)
        cur_room_info = pg_helpers.get_current_cluster_room(cluster_id)
        if cur_room_info:
            for k, v in attr_dict.items():
                if k in cur_room_info.keys():
                    cur_room_info[k] = v
            room_id = cur_room_info.pop('room_id', '0')
            rooms[str(room_id)] = {
                'room_name': cur_room_info.get('room_name', '默认机房'),
                'vip': cluster_dict['vip']
            }
            cluster_dict['rooms'] = rooms

        dbp.execute(
            "UPDATE clup_cluster SET cluster_data = %s WHERE cluster_id=%s",
            (json.dumps(cluster_dict), cluster_id))

    return 200, 'ok'


def polar_switch(req):
    """polardb 共享存储主备切换

    """
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
        'db_id': 0,
        'room_id': 0,
        'workwx': 0
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    cluster_id = pdict['cluster_id']
    db_id = pdict.get('db_id')
    room_id = pdict.get('room_id')
    if not db_id and room_id is None:
        return 400, 'The room id or database id must be specified'
    if room_id is not None and not db_id:
        sql = "SELECT db_id FROM clup_db " \
              "WHERE db_detail->>'room_id' = %s AND cluster_id = %s AND state = %s AND is_primary=0 ORDER BY scores"
        rows = dbapi.query(sql, (str(room_id), cluster_id, node_state.NORMAL))
        if not rows:
            return 400, f'No standby database in normal HA state is found in the room(room_id={room_id})'
        db_id = pg_helpers.get_max_lsn_db(rows)
        if not db_id:
            return 400, f'No standby database in normal HA state is found in the room(room_id={room_id})'
    sql = "SELECT COUNT(*) AS cnt FROM clup_db WHERE db_id = %s AND cluster_id = %s"
    rows = dbapi.query(sql, (db_id, cluster_id))
    if rows[0]['cnt'] == 0:
        return 400, f'No database(db_id={db_id}) information found in the cluste(cluster_id={cluster_id})'

    # 数据库操作时时检查是否集群信息存在,存在则判断集群是否下线,如果未下线则不允许操作
    if cluster_id:
        return_cluster_state = dao.get_cluster_state(cluster_id)
        if return_cluster_state != cluster_state.OFFLINE and return_cluster_state != cluster_state.FAILED:
            return 400, f"Before performing database operations, please take its cluster(cluster_id={cluster_id}) offline"

    sql = 'select db_id from clup_db where is_primary=1 and cluster_id = %s'
    rows = dbapi.query(sql, (cluster_id, ))
    if not rows:
        return 400, f'The primary database is not found in the cluste({cluster_id})'
    old_primary_db = rows[0]['db_id']
    sql = f"""SELECT count(*) as cnt from clup_general_task where state=0 and task_data @> '{{"cluster_id": {cluster_id} }}' """
    rows = dbapi.query(sql)
    cnt = rows[0]['cnt']
    if cnt > 0:
        return 400, "The cluster has other operations in progress. Please try again later"

    # 判断是否是standby节点,如果是则返回
    sql = f"SELECT db_detail->'polar_type' as polar_type from clup_db where db_id = {db_id}"
    rows = dbapi.query(sql)
    if len(rows):
        polar_type = rows[0].get("polar_type")
        if polar_type == "standby":
            return 400, "The switchover must be performed on a reader node. standby nodes do not support switchover"

    workwx = pdict.get("workwx")
    # 先检测是否可以切换,如果不能,直接返回
    try:
        ret_code, msg = ha_mgr.test_polar_can_switch(cluster_id, db_id, old_primary_db)
        if ret_code != 0:
            if workwx:
                workwx['db_id'] = db_id
                workwx['state'] = "Failed"
                pg_helpers.send_workwx_alarm(workwx)
            return 400, msg
    except Exception as e:
        logging.error(f"Call test_sr_can_switch exception: {traceback.format_exc()}")
        if pdict.get("workwx"):
            workwx['db_id'] = db_id
            workwx['state'] = "Failed"
            pg_helpers.send_workwx_alarm(workwx)
        return 400, str(e)

    # 因为是一个长时间运行的操作,所以生成一个后台任务,直接返回
    task_name = f"sr_switch (cluster_id={cluster_id}, db_id={db_id})"
    task_id = general_task_mgr.create_task('switch', task_name, {'cluster_id': cluster_id})
    general_task_mgr.run_task(task_id, ha_mgr.task_polar_switch, (cluster_id, db_id, old_primary_db))
    ret_data = {"task_id": task_id, "task_name": task_name}
    raw_data = json.dumps(ret_data)
    if workwx:
        try:
            workwx['db_id'] = db_id
            pg_helpers.send_workwx_alarm(workwx)
        except Exception as e:
            logging.error(f'alarm send failure: {repr(e)}')
    return 200, raw_data


def check_pfs_disk_name_validity(req):
    """
    在创建polardb共享存储集群时, 检查共享盘的有效性。
    (创建polardb共享存储集群的界面中`pfs_disk_name`框里填写的名字)
    """
    params = {
        'pfs_disk_name': csu_http.MANDATORY,
        'host_list': csu_http.MANDATORY
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    code, result = polar_lib.check_pfs_disk_name_validity(pdict['host_list'], pdict['pfs_disk_name'])
    res_data = {
        "is_valid": True if code == 0 else False,
        "formated": result if code == 0 else 'unknow',
        "err_msg": '' if code == 0 else result
    }
    ret_data = json.dumps(res_data)
    return 200, ret_data


def format_pfs_disk(req):
    """
    创建 PolarDB 时, 格式化磁盘。

    这个函数实际上只使用了主库所在的agent的host信息,
    之所以接收所有的 agent ip,
    是考虑到之后可能会连接所有的agent进行操作。
    """
    params = {
        'host_list': csu_http.MANDATORY,
        'pfs_disk_name': csu_http.MANDATORY,
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    host_list = pdict['host_list']
    pfs_disk_name = pdict['pfs_disk_name']
    if host_list:
        master_host = host_list[0]
    else:
        return 400, 'No agent host informations!'
    return_code, stdout = rpc_utils.get_rpc_connect(master_host, conn_timeout=2)
    if return_code == 0:
        rpc = stdout
    else:
        return 400, f'Failed to connect agent[{master_host}]'

    base_disk_name = os.path.basename(pfs_disk_name)
    cmd = f"pfs -C disk mkfs -f {base_disk_name}"
    return_code, stderr, stdout = rpc.run_cmd_result(cmd)
    if return_code:
        return 400, f'Format pfs disk in host({master_host}) failed: {str(stderr)}'
    else:
        return 200, f'Format pfs disk {pfs_disk_name} sucess.'


def batch_online_cluster(req):
    """批量上线集群

    Args:
        req (_type_): _description_

    Returns:
        _type_: _description_
    """
    params = {
        'cluster_id_list': csu_http.MANDATORY
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id_list = pdict['cluster_id_list']
    wait_online_list = list()
    failed_cluster_list = list()
    allow_alter_cluster_states = [cluster_state.OFFLINE, cluster_state.FAILED]
    while len(cluster_id_list) or len(wait_online_list):
        cluster_id = None
        if len(cluster_id_list):
            cluster_id = cluster_id_list.pop()
        elif len(wait_online_list):
            cluster_id = wait_online_list.pop()
            time.sleep(3)

        if not cluster_id:
            break
        try:
            # get current state
            cluster_dict = dao.get_cluster(cluster_id)
            current_state = cluster_dict['state']
            # only online state to offline
            if current_state in allow_alter_cluster_states:
                err_code, err_list = ha_mgr.online(cluster_id)
                if err_code != 0:
                    failed_cluster_list.append(f"{cluster_id} online failed, {err_list}.")
                else:
                    pg_helpers.update_cluster_room_info(cluster_id)
            elif current_state == cluster_state.CHECKING:
                if cluster_id not in wait_online_list:
                    wait_online_list.append(cluster_id)
            elif current_state == cluster_state.NORMAL:
                continue

            # if current state is others, not care
        except Exception:
            err_msg = traceback.format_exc()
            failed_cluster_list.append(cluster_id)
            logging.error(f"Online cluster({cluster_id}) with unexpected error, {err_msg}.")
            break

    if len(failed_cluster_list):
        return 400, f"There some cluster online failed, {failed_cluster_list}."
    return 200, "Batch online cluster success."


def batch_offline_cluster(req):
    """批量离线集群

    Args:
        req (_type_): _description_
    """

    params = {
        'cluster_id_list': csu_http.MANDATORY
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    cluster_id_list = pdict['cluster_id_list']
    wait_offline_list = list()
    failed_cluster_list = list()
    while len(cluster_id_list) or len(wait_offline_list):
        cluster_id = None
        if len(cluster_id_list):
            cluster_id = cluster_id_list.pop()
        elif len(wait_offline_list):
            cluster_id = wait_offline_list.pop()
            time.sleep(3)

        if not cluster_id:
            break
        try:
            # get current state
            cluster_dict = dao.get_cluster(cluster_id)
            current_state = cluster_dict['state']
            # only online state to offline
            if current_state == cluster_state.NORMAL:
                err_code, err_msg = ha_mgr.offline(cluster_id)
                if err_code != 0:
                    failed_cluster_list.append(f"{cluster_id} offline failed, {err_msg}.")
            elif current_state == cluster_state.CHECKING:
                if cluster_id not in wait_offline_list:
                    wait_offline_list.append(cluster_id)
            elif current_state == cluster_state.OFFLINE:
                continue

            # if current state is others, not care
        except Exception:
            err_msg = traceback.format_exc()
            failed_cluster_list.append(cluster_id)
            logging.error(f"Offline cluster({cluster_id}) with unexpected error, {err_msg}.")
            break

    if len(failed_cluster_list):
        return 400, f"There some cluster offline failed, {failed_cluster_list}."
    return 200, "Batch offline cluster success."


def add_vip_pool(req):
    """添加vip池
    """
    params = {
        'start_ip': csu_http.MANDATORY,
        'end_ip': csu_http.MANDATORY,
        'mask_len': csu_http.INT
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check the start_ip and end_ip in the same network
    start_ip_network = IPv4Network(f"{pdict['start_ip']}/{pdict['mask_len']}", strict=False)
    end_ip_network = IPv4Network(pdict['end_ip'], strict=False)
    if not end_ip_network.subnet_of(start_ip_network):
        return 400, "The end ip and start ip is not in the same network."

    # the end ip must more than the start ip
    if int(IPv4Address(pdict['end_ip'])) < int(IPv4Address(pdict['start_ip'])):
        return 400, "The end ip address cannot be smaller than the start ip address."

    # check the vip pool is aready exists or not
    sql = "SELECT * FROM clup_vip_pool"
    rows = dbapi.query(sql)
    for row in rows:
        row_ip_network = IPv4Network(f"{row['start_ip']}/{row['mask_len']}", strict=False)
        # check the start ip
        if start_ip_network.subnet_of(row_ip_network):
            return 400, f"The start ip is aready in the vip pool(pool_id={row['pool_id']}), please check."
        # check the end ip
        if end_ip_network.subnet_of(row_ip_network):
            return 400, f"The end ip is aready in the vip pool(pool_id={row['pool_id']}), please check."

    # add to clup_vip_pool
    sql = "INSERT INTO clup_vip_pool(start_ip, end_ip, mask_len) VALUES(%(start_ip)s, %(end_ip)s, %(mask_len)s) RETURNING pool_id"
    row = dbapi.query(sql, pdict)
    if not row:
        return 500, f"Excute sql({sql}) failed."

    ret_data = {
        "pool_id": row[0]["pool_id"]
    }
    return 200, json.dumps(ret_data)


def get_vip_pool(req):
    """查询vip池
    """
    params = {
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT,
        'filter': 0
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    offset = (pdict['page_num'] - 1) * pdict['page_size']
    sql = "SELECT * FROM clup_vip_pool ORDER BY pool_id LIMIT %s OFFSET %s"
    rows = dbapi.query(sql, (pdict['page_size'], offset))

    # get the vip pool total vip number and free vip number
    for row in rows:
        total_count = int(IPv4Address(row['end_ip'])) - int(IPv4Address(row['start_ip'])) + 1
        row['total'] = total_count
        # search vips
        sql = "SELECT COUNT(*) FROM clup_used_vip WHERE pool_id = %s"
        used_rows = dbapi.query(sql, (row['pool_id'], ))
        row['free'] = total_count - used_rows[0]['count']

    if not pdict.get('filter'):
        ret_data = {"total": len(rows), "rows": list(rows)}
        return 200, json.dumps(ret_data)

    # if filter
    ret_list = list()
    for row in rows:
        # check ip is in the network or not
        ip_network = IPv4Network(pdict['filter'], strict=False)
        row_ip_network = IPv4Network(f"{row['start_ip']}/{row['mask_len']}", strict=False)

        if ip_network.subnet_of(row_ip_network):
            ret_list.append(dict(row))
            break

    # not find any recard for filter ip
    ret_data = {"total": len(ret_list), "rows": ret_list}
    return 200, json.dumps(ret_data)


def delete_vip_pool(req):
    """删除vip池
    """
    params = {
        'pool_id': csu_http.INT
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check this pool has vip is used or not
    sql = "SELECT COUNT(*) FROM clup_used_vip WHERE pool_id = %s"
    rows = dbapi.query(sql, (pdict['pool_id'], ))
    if rows[0]["count"]:
        return 400, "The vip pool is in used, please check the vip list."

    sql = "DELETE FROM clup_vip_pool WHERE pool_id = %s"
    dbapi.execute(sql, (pdict['pool_id'], ))

    return 200, "Success"


def update_vip_pool(req):
    """更新vip池信息
    """
    params = {
        'pool_id': csu_http.INT,
        'start_ip': 0,
        'end_ip': 0,
        'mask_len': 0
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # get the vip list
    vip_sql = "SELECT vip FROM clup_used_vip WHERE pool_id = %s"
    vip_rows = dbapi.query(vip_sql, (pdict['pool_id'], ))

    # get the vip_pool infor
    pool_sql = "SELECT * FROM clup_vip_pool WHERE pool_id = %s"
    pool_rows = dbapi.query(pool_sql, (pdict['pool_id'], ))
    if not pool_rows:
        return 400, f"The vip pool(pool_id={pdict['pool_id']}) is not exists."

    new_dict = pool_rows[0]
    new_dict.update(pdict)
    new_ip_network = IPv4Network(f"{new_dict['start_ip']}/{new_dict['mask_len']}", strict=False)

    # check the end_ip is more than start_ip
    if int(IPv4Address(new_dict['end_ip'])) < int(IPv4Address(new_dict['start_ip'])):
        return 400, f"The end ip({new_dict['end_ip']}) cannot be smaller than the start ip({new_dict['start_ip']})."

    # check start_ip is in the new network
    if pdict.get("start_ip"):
        start_ip_network = IPv4Network(pdict['start_ip'], strict=False)
        if not start_ip_network.subnet_of(new_ip_network):
            return 400, f"The start ip({pdict['start_ip']}) is not in the vip pool(pool_id={pdict['pool_id']})."

    # check end_ip is in the new network
    if pdict.get("end_ip"):
        end_ip_network = IPv4Network(pdict['end_ip'], strict=False)
        if not end_ip_network.subnet_of(new_ip_network):
            return 400, f"The end ip({pdict['end_ip']}) is not in the vip pool(pool_id={pdict['pool_id']})."

    # check others vip is in the new pool
    for vip_row in vip_rows:
        vip_network = IPv4Network(vip_row['vip'], strict=False)
        if not vip_network.subnet_of(new_ip_network):
            return 400, f"The vip({vip_row['vip']}) is not in this new network."

    sql = "UPDATE clup_vip_pool SET start_ip = %(start_ip)s, end_ip = %(end_ip)s, mask_len = %(mask_len)s" \
        " WHERE pool_id = %(pool_id)s RETURNING pool_id"
    rows = dbapi.query(sql, new_dict)
    if not rows:
        return 400, f"Excute sql({sql}) failed."

    return 200, "Update success."


def get_vip_list(req):
    params = {
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT,
        'filter': 0
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    offset = (pdict['page_num'] - 1) * pdict['page_size']
    ret_list = list()
    sql = "SELECT p.pool_id, p.start_ip, p.mask_len, vip, db_id, cluster_id, used_reason" \
        " FROM clup_used_vip u,clup_vip_pool p" \
        " WHERE u.pool_id=p.pool_id ORDER BY pool_id LIMIT %s OFFSET %s"

    used_info_rows = dbapi.query(sql, (pdict['page_size'], offset))
    if not used_info_rows:
        ret_data = {"total": len(ret_list), "rows": ret_list}
        return 200, json.dumps(ret_data)

    with dbapi.DBProcess() as dbp:
        for row in used_info_rows:
            row["host"] = ""
            row["cluster_name"] = ""
            # get cluster_name
            if row.get("cluster_id"):
                sql = "SELECT cluster_data->'cluster_name' as cluster_name from clup_cluster WHERE cluster_id = %s"
                cluster_rows = dbp.query(sql, (row["cluster_id"], ))
                if cluster_rows:
                    row["cluster_name"] = cluster_rows[0]["cluster_name"]
            # get host
            if row.get("db_id"):
                sql = "SELECT host FROM clup_db WHERE db_id=%s"
                db_rows = dbp.query(sql, (row["db_id"], ))
                if db_rows:
                    row["host"] = db_rows[0]["host"]

            # if used_reason is 1 check vip_exists on host
            if row["used_reason"] == 1 and row["host"] != "":
                try:
                    rpc = None
                    code, result = rpc_utils.get_rpc_connect(row["host"])
                    if code != 0:
                        row["used_reason"] = -1
                    else:
                        rpc = result
                        code, result = rpc.vip_exists(row["vip"])
                        if result == "":
                            row["used_reason"] = 2
                            # update clup_used_vip
                            dbp.execute("UPDATE clup_used_vip SET used_reason=2 WHERE vip=%s", (row["vip"], ))
                except Exception as e:
                    logging.error(f"Check vip exists in host {row['host']} with unexpected error, {str(e)}.")
                finally:
                    if rpc:
                        rpc.close()

            ret_list.append(dict(row))

    if not pdict.get('filter'):
        ret_data = {"total": len(ret_list), "rows": ret_list}
        return 200, json.dumps(ret_data)

    # if filter
    filter_ret_list = list()
    for row in ret_list:
        if row["host"] == pdict["filter"]:
            filter_ret_list.append(row)
        elif row["vip"] == pdict["filter"]:
            filter_ret_list.append(row)
        # else:
        #     # check ip is in the network or not
        #     ip_network = IPv4Network(pdict['filter'], strict=False)
        #     row_ip_network = IPv4Network(f"{row['start_ip']}/{row['mask_len']}", strict=False)

        #     if ip_network.subnet_of(row_ip_network):
        #         filter_ret_list.append(row)

    ret_data = {"total": len(filter_ret_list), "rows": filter_ret_list}
    return 200, json.dumps(ret_data)


def allot_one_vip(req):
    params = {
        'pool_id': csu_http.INT
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # get the vip pool info
    sql = "SELECT start_ip, end_ip, mask_len FROM clup_vip_pool WHERE pool_id = %s"
    pool_rows = dbapi.query(sql, (pdict['pool_id'], ))
    if not pool_rows:
        return 400, f"Cant find any recard for vip pool(pool_id={pdict['pool_id']})."
    start_ip_int = int(IPv4Address(pool_rows[0]['start_ip']))
    end_ip_int = int(IPv4Address(pool_rows[0]['end_ip']))

    used_vip_list = list()
    sql = "SELECT vip FROM clup_used_vip WHERE pool_id = %s"
    used_rows = dbapi.query(sql, (pdict['pool_id'], ))
    if used_rows:
        used_vip_list = [int(IPv4Address(row['vip'])) for row in used_rows]

    # check used count
    count_number = end_ip_int - start_ip_int + 1
    free_numbers = count_number - len(used_rows)
    if not free_numbers:
        return 400, "No vip can be allot from this vip pool."

    ret_vip = None
    for int_vip in range(start_ip_int, end_ip_int + 1):
        if int_vip not in used_vip_list:
            ret_vip = str(IPv4Address(int_vip))
            break

    if not ret_vip:
        return 400, "Cant allot one vip from vip pool"

    return 200, ret_vip


def check_vip_in_pool(req):
    """校验vip是否在vip池中
    """
    params = {
        'pool_id': csu_http.INT,
        'vip': csu_http.MANDATORY
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    code, result = ip_lib.check_vip_in_pool(pdict['pool_id'], pdict['vip'])
    if code != 0:
        return 400, result

    return 200, result
