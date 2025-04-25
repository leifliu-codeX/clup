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
@description: WEB界面的数据库服务处理模块
"""


import copy
import json
import logging
import re
import time
import traceback

import cluster_state
import config
import csu_http
import dao
import database_state
import db_encrypt
import dbapi
import helpers
import pg_db_lib
import pg_helpers
import polar_helpers
import polar_lib
import rpc_utils
from ha_mgr import get_repl_delay as ha_mgr_get_repl_delay


def start_db(req):
    params = {
        "db_id": csu_http.MANDATORY,
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    db_id = pdict['db_id']
    rows = dao.get_db_info(db_id)
    if len(rows) == 0:
        return 400, f"Database information not found(db_id: {db_id})"
    db_dict = rows[0]
    # 检查是否是polardb,如果是且为master或reader节点则需要启动pfs
    polar_type_list = ['master', 'reader']
    polar_type = db_dict.get('polar_type', None)
    if polar_type in polar_type_list:
        # 如果是只读节点,判断其是否有recovery.conf文件,没有的话不能启动,否则会导致主库无法启动
        if polar_type == 'reader':
            polar_version = int(db_dict["version"].split(".")[0])
            err_code, err_msg = polar_lib.is_exists_recovery(db_dict['host'], db_dict['pgdata'], polar_version)
            if err_code != 0:
                return 400, err_msg
        err_code, err_msg = polar_lib.start_pfs(db_dict['host'], db_id)
        if err_code not in {0, 1}:
            return 400, err_msg
    # end start pfs
    err_code, err_msg = pg_db_lib.start(db_dict['host'], db_dict['pgdata'])
    if err_code != 0:
        return 400, err_msg
    dao.update_db_state(db_id, database_state.RUNNING)
    return 200, 'ok'


def stop_db(req):
    params = {
        "db_id": csu_http.MANDATORY,
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    rows = dao.get_db_info(pdict['db_id'])
    if len(rows) == 0:
        return 400, f"Database information not found(db_id: {pdict['db_id']})"
    db_dict = rows[0]
    host = rows[0]['host']
    pgdata = rows[0]['pgdata']

    # 数据库关闭时检查是否集群信息存在,存在则判断集群是否下线,如果未下线则不允许操作
    if db_dict['cluster_id']:
        current_cluster_state = dao.get_cluster_state(db_dict['cluster_id'])
        if current_cluster_state not in {cluster_state.OFFLINE, cluster_state.FAILED}:
            return 400, f"Before performing database operations, please take its cluster(cluster_id={db_dict['cluster_id']}) offline"

    # 检查db是否在polardb集群中,如果是则检查是否是最后一个共享存储中的库,是的话需要先下线集群
    # 这一步操作是防止poalrdb无法正常关闭时,中途产生failover的情况
    polar_type_list = ['master', 'reader']
    polar_type = db_dict.get('polar_type', None)
    if polar_type in polar_type_list:
        err_code, err_msg = polar_lib.check_and_offline_cluster(db_dict['db_id'])
        if err_code != 0:
            return 400, err_msg

    # rows[0]['wait_time'] = 5
    more_msg = ''
    wait_time = 5
    err_code, err_msg = pg_db_lib.stop(host, pgdata, wait_time)
    if err_code != 0:
        # 如果是polardb尝试使用immediate模式停下数据库
        if polar_type:
            err_code, err_msg = polar_lib.stop_immediate(host, pgdata, wait_time)
            if err_code != 0:
                return 400, f"cannot stop the database using immediate mode on the host={host}"
            more_msg += "Normal mode cannot be stopped. Use immediate mode"
        else:
            return 400, err_msg

    # 检查是否是polardb,如果是且为master或reader节点则需要停止pfs
    if polar_type in polar_type_list:
        err_code, err_msg = polar_lib.stop_pfs(db_dict['host'], db_dict['db_id'])
        if err_code != 0:
            more_msg = f",But stop pfs is failed: {err_msg}"
    # end stop pfs

    dao.update_db_state(pdict['db_id'], database_state.STOP)
    return 200, 'Stop db is successed' + more_msg


def get_instance_list(req):
    params = {
        'page_num': csu_http.INT,
        'page_size': csu_http.INT,
        'filter': 0
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    page_num = pdict.setdefault('page_num', 1)
    page_size = pdict.setdefault('page_size', 1000)

    filter_cond = pdict.get("filter", "")
    offset = (page_num - 1) * page_size

    where_cond = ""
    if pdict.get('filter', None):
        filter_cond = filter_cond.replace("'", "")
        filter_cond = filter_cond.replace('"', "")
        where_cond = " (host like %(filter_cond)s or port::text like %(filter_cond)s) "
    pdict['filter_cond'] = "%" + filter_cond + "%"
    where_count = ''
    where_and = ''
    if where_cond:
        where_and = ' and ' + where_cond
        where_count = ' where ' + where_cond
    sql = "SELECT count(*) as cnt FROM clup_db " + where_count
    rows = dbapi.query(sql, pdict)
    row_cnt = rows[0]['cnt']
    if row_cnt == 0:
        ret_data = {"total": row_cnt, "page_size": pdict['page_size'], "rows": []}
        return 200, json.dumps(ret_data)
    pdict['limit'] = page_size
    pdict['offset'] = offset
    sql = "select host, is_primary, data->>'hostname' as host_name,db_id,pgdata,db_state,port,pgdata from clup_db,clup_host " \
          "where clup_db.host::inet=clup_host.ip::inet  {}" \
          "ORDER BY host,port LIMIT %(limit)s OFFSET %(offset)s ".format(where_and)
    rows = dbapi.query(sql, pdict)

    ret_data = {"total": row_cnt, "page_size": pdict['page_size'], "rows": rows}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def create_db(req):
    """
       创建数据库
       :param req:
       :return:
    """
    params = {
        'host': csu_http.MANDATORY,  # 主机
        'port': csu_http.MANDATORY,  # 端口
        'pgdata': csu_http.MANDATORY,  # 数据目录
        'instance_name': 0,  # 名称
        'os_user': csu_http.MANDATORY,  # 操作系统用户名
        'pg_bin_path': csu_http.MANDATORY,  # 数据库软件路径
        'os_uid': csu_http.MANDATORY | csu_http.INT,  # 操作系统用户uid
        'db_user': csu_http.MANDATORY,  # 数据库用户
        'db_pass': csu_http.MANDATORY,  # 数据库密码
        'version': csu_http.MANDATORY,  # 数据库版本
        'db_type': csu_http.MANDATORY,  # 1代表postgresql,11为polardb
        'instance_type': csu_http.MANDATORY,  # 数据库创建的类型
        'wal_segsize': csu_http.INT,       # wal段文件大小，仅PG11及以上版本支持
        'setting_list': csu_http.MANDATORY
    }

    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    if not pdict['pgdata'].startswith('/'):
        return 400, f"The args pgdata({pdict['pgdata']}) is not startswith '/', please check."
    host = pdict['host']

    # 在做其他操作前应先检查相关资源是否已经存在,使用ip+port检查,然后检查数据目录是否为空
    err_code, err_msg = pg_helpers.source_check(host, pdict['port'], pdict['pgdata'])
    if err_code != 0:
        return 400, err_msg

    # 操作日志记录
    sql = "SELECT count(*) FROM clup_db WHERE host = %(host)s AND port= %(port)s "
    rows = dbapi.query(sql, pdict)
    if rows[0]['count'] > 0:
        return 400, f"create fail, Port {pdict['port']} already in used on host:({pdict['host']})"

    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        return 400, f'Host connection failure ({host}),please check service clup-agent is running!'
    rpc = err_msg
    rpc.close()

    err_code, err_msg = pg_helpers.create_db(pdict)
    if err_code != 0:
        return 400, err_msg

    task_id = err_msg
    ret_data = {"task_id": task_id, "db_id": pdict['db_id']}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def create_polardb(req):
    """
       创建PolarDB数据库,支持本地存储或共享存储
       :param req:
       :return:
    """
    params = {
        'host': csu_http.MANDATORY,         # 主机
        'port': csu_http.MANDATORY,         # 端口
        'pgdata': csu_http.MANDATORY,       # 数据目录
        'instance_name': 0,                 # 名称
        'os_user': csu_http.MANDATORY,      # 操作系统用户名
        'pg_bin_path': csu_http.MANDATORY,  # 数据库软件路径
        'os_uid': csu_http.MANDATORY | csu_http.INT,  # 操作系统用户uid
        'db_user': csu_http.MANDATORY,      # 数据库用户
        'db_pass': csu_http.MANDATORY,      # 数据库密码
        'version': csu_http.MANDATORY,      # 数据库版本
        'db_type': csu_http.MANDATORY,      # 1代表postgresql,11为polardb
        'instance_type': csu_http.MANDATORY,  # 数据库创建的类型
        'setting_list': csu_http.MANDATORY,
        'wal_segsize': csu_http.INT,           # wal段文件大小，仅PG11及以上版本支持
        'pfsdaemon_params': 0,              # pfs 参数
        'pfs_disk_name': 0,                 # pfs 磁盘名
        'polar_datadir': 0,                 # polardb 共享盘目录
    }

    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    if not pdict['pgdata'].startswith('/'):
        return 400, f"The args pgdata({pdict['pgdata']}) is not startswith '/', please check."
    host = pdict['host']

    # check ip and port is used or not
    err_code, err_msg = pg_helpers.source_check(host, pdict['port'], pdict['pgdata'])
    if err_code != 0:
        return 400, err_msg

    # test connect the host
    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        return 400, f'Host connection failure ({host}),please check service clup-agent is running!'
    rpc = err_msg
    rpc.close()
    try:
        # if params has pfs_disk_name, build with pfs shared disk
        if pdict.get('pfs_disk_name'):
            # parese params
            pfs_info = {
                "polar_datadir": pdict["polar_datadir"],
                "pfs_disk_name": pdict["pfs_disk_name"],
                'pfsdaemon_params': pdict["pfsdaemon_params"]
            }
            err_code, err_msg = polar_helpers.create_polardb_with_pfs(pdict, pfs_info)
            if err_code != 0:
                return 400, err_msg
        else:
            err_code, err_msg = pg_helpers.create_db(pdict)
            if err_code != 0:
                return 400, err_msg
    except Exception as e:
        return 400, f"create polardb with unexpected error, {str(e)}."

    task_id = err_msg
    ret_data = {"task_id": task_id}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def delete_db(req):
    params = {
        'db_id': csu_http.MANDATORY,  # 数据库id
        'rm_pgdata': csu_http.MANDATORY
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    db_id = pdict['db_id']

    sql = """SELECT cluster_id,clup_cluster.state as state,host,pgdata,instance_name,port,
    db_detail->>'instance_type' as instance_type, db_detail->>'db_user' as db_user,
    db_detail->>'polar_type' as polar_type, db_detail->>'os_user' as os_user
    FROM clup_db left join clup_cluster using (cluster_id) WHERE db_id = %(db_id)s
    """
    rows = dbapi.query(sql, pdict)
    if len(rows) == 0:
        return 400, 'The instance does not exist'
    db_info = rows[0]
    host = db_info['host']
    pgdata = db_info['pgdata']

    if db_info['cluster_id'] and db_info['state'] == 1:
        return 400, f"Database owning cluster (cluster_id:{db_info['cluster_id']})is online,perform this operation offline!"
    sql = "SELECT count(*) FROM clup_db WHERE up_db_id = %(db_id)s "
    count_rows = dbapi.query(sql, pdict)
    if count_rows[0]['count'] > 0:
        return 400, 'The database has standby, please switch standby to other database !'

    # 检查是否为polardb的备库,是则需要删除主库中的复制槽
    more_msg = ''
    polar_type_list = ['reader', 'standby']
    polar_type = db_info.get("polar_type", None)
    if polar_type in polar_type_list:
        code, result = polar_lib.delete_replication_slot(db_id)
        if code != 0:
            more_msg = result

    if pdict.get('rm_pgdata'):
        err_code, err_msg = rpc_utils.get_rpc_connect(host)
        if err_code != 0:
            return 400, f"Failed to connect to the host:{host} when deleting the database: (db_id={db_id}), error message: {err_msg}"
        rpc = err_msg
        try:

            err_code, err_msg = pg_db_lib.delete_db(rpc, pgdata)
            if err_code != 0:
                return 400, f"Failed to delete database: (db_id={db_id}), error message: {err_msg}"

            # polar_test 判断是否为polardb数据库,如果是且为master节点则删除共享文件夹
            if polar_type == "master":
                err_code, err_msg = polar_lib.delete_polar_datadir(rpc, db_id)
                if err_code != 0:
                    more_msg += err_msg
            # polar_test end
        finally:
            rpc.close()

    # 删除的数据库如果是集群最后一个数据库,需要解绑vip
    if db_info['cluster_id']:
        check_sql = "select db_id from clup_db where cluster_id = %s"
        count = dbapi.query(check_sql, (db_info['cluster_id'],))
        if len(count) == 1:
            vip_sql = "select cluster_data->>'vip' as vip from clup_cluster where cluster_id = %s"
            vip_rows = dbapi.query(vip_sql, (db_info['cluster_id'],))
            vip = vip_rows[0]['vip']
            rpc_utils.check_and_del_vip(host, vip)

            # delete from clup_used_vip
            dbapi.execute("DELETE FROM clup_used_vip WHERE vip=%s", (vip, ))

    sql = "DELETE FROM clup_db WHERE db_id=%(db_id)s"
    dbapi.execute(sql, pdict)

    return 200, 'OK'


def restart_db(req):
    params = {
        'db_id': csu_http.MANDATORY,  # 数据库id
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    sql = """ SELECT cluster_id, host,pgdata, instance_name, db_type,
            db_detail->>'instance_type' as instance_type,
            db_detail->>'db_user' as db_user,
            db_detail->>'polar_type' as polar_type,
            db_detail->'is_exclusive' as is_exclusive,
            db_detail->'cpu_list' as cpu_list,
            db_detail->'memory_size' as memory_size
            FROM clup_db WHERE db_id = %s"""
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if len(rows) == 0:
        return 400, 'The instance does not exist'
    host = rows[0]['host']
    pgdata = rows[0]['pgdata']
    cluster_id = rows[0]['cluster_id']
    # 数据库重启时检查是否集群信息存在,存在则判断集群是否下线,如果未下线则不允许操作
    if cluster_id:
        return_cluster_state = dao.get_cluster_state(cluster_id)
        if return_cluster_state not in {cluster_state.OFFLINE, cluster_state.FAILED}:
            return 400, f"Before performing database operations, please take its cluster(cluster_id={cluster_id}) offline"

    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        return 400, f'Host connection failure: ({host}),please check clup-agent is running!'
    rpc = err_msg
    db_id = pdict['db_id']
    pfs_start = False
    try:
        # 检查是否是polardb,如果是且为master或reader节点则需要先启动pfs
        db_dict = rows[0]
        polar_type_list = ['master', 'reader']
        polar_type = db_dict.get('polar_type', None)
        if polar_type in polar_type_list:
            err_code, err_msg = polar_lib.start_pfs(host, db_id)
            if err_code not in {0, 1}:
                return 400, err_msg
            pfs_start = True
        # end start pfs

        err_code, err_msg = pg_db_lib.restart(rpc, pgdata)
        if err_code != 0:
            # 重启失败状态改为1 停止
            dao.update_db_state(pdict['db_id'], 1)
            return 400, f'Restart the database failure: {err_msg}'
    except Exception as e:
        return 400, f'Restart the database failure: {str(e)}'
    finally:
        rpc.close()
        if err_code != 0:
            if pfs_start:
                polar_lib.stop_pfs(host, db_id)

    return 200, 'OK'


def extend_db(req):
    params = {
        'db_id': csu_http.MANDATORY,  # 数据库id
        'mem_size': csu_http.MANDATORY,
        'cpu': 0
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    db_id = pdict['db_id']
    sql = " SELECT cluster_id, host,pgdata,instance_name,clup_cluster.state," \
          " db_detail->>'instance_type' as instance_type, db_detail->>'db_user' as db_user " \
          " FROM clup_db LEFT JOIN clup_cluster USING (cluster_id) WHERE db_id = %s "
    rows = dbapi.query(sql, (db_id, ))
    if len(rows) == 0:
        return 400, 'The instance does not exist'
    host = rows[0]['host']
    pgdata = rows[0]['pgdata']
    mem_size = pdict['mem_size']
    conn_cnt = pdict['conn_cnt']
    if rows[0]['cluster_id'] and rows[0]['state'] == 1:
        return 400, f"Database owning cluster(cluster_id:{rows[0]['cluster_id']}) is online, perform this operation offline"
    db_id = pdict['db_id']
    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        return 400, f'Host connection failure ({host}), please check service clup-agent is running!!'
    rpc = err_msg
    try:
        err_code, err_msg = pg_db_lib.extend_db(rpc, pgdata, conn_cnt, mem_size)
        if err_code != 0:
            return 400, f'modify database failure: {err_msg}'
        # 修改成功重启数据库
        err_code, err_msg = pg_db_lib.restart(rpc, pgdata)
        if err_code != 0:
            # 重启失败状态改为1 停止
            dao.update_db_state(pdict['db_id'], 1)
            return 400, f'restart database failure: {err_msg}'
        if pdict.get('cpu'):
            del pdict['cpu']
    finally:
        rpc.close()

    del pdict['db_id']
    dao.extend_database(db_id, pdict)
    return 200, 'OK'


def pg_reload(req):
    params = {
        'db_id': csu_http.MANDATORY
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    db_id = pdict['db_id']
    sql = "SELECT host, pgdata, db_id, db_detail->> 'db_user' as db_user, " \
          "db_detail->>'instance_type' as instance_type FROM clup_db WHERE db_id = %s"
    rows = dbapi.query(sql, (db_id, ))
    if len(rows) == 0:
        return 400, 'No information about the database is available, please refresh and try again'

    host = rows[0]['host']
    pgdata = rows[0]['pgdata']
    err_code, err_msg = pg_db_lib.reload(host, pgdata)
    if err_code != 0:
        return 400, str(err_msg)
    return 200, 'OK'


def get_all_db_list(req):
    params = {
        'page_num': 0,
        'page_size': 0,
        'filter': 0,
        'upper_level_db': 0
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    # page_num = pdict['page_num']
    page_num = pdict.setdefault('page_num', 1)
    page_size = pdict.setdefault('page_size', 10000)

    filter_cond = pdict.get("filter", "")

    offset = (page_num - 1) * page_size
    # 可以的条件：cluster_name,vip
    args = copy.copy(pdict)
    where_cond = ""
    if filter_cond:
        where_cond = (
            """WHERE (instance_name like %(filter)s"""
            """ OR host LIKE %(filter)s)""")
        args['filter'] = filter_cond
    if 'upper_level_db' in pdict:
        where_cond = (
            "WHERE db_id = %(upper_level_db)s")
        args['upper_level_db'] = pdict['upper_level_db']
    host_data_dict = {}
    with dbapi.DBProcess() as dbp:
        sql = "SELECT count(*) as cnt FROM clup_db " + where_cond
        rows = dbp.query(sql, args)
        row_cnt = rows[0]['cnt']
        ret_rows = []
        if row_cnt > 0:
            sql = (
                "SELECT db_id, instance_name, host, is_primary, port, db_state,"
                " pgdata, db_type, cluster_id, cluster_type, clup_db.state,up_db_id,"
                " db_detail->>'instance_type' as instance_type, db_detail->>'version' as version,"
                " db_detail->>'os_user' as os_user, cluster_data ->> 'cluster_name' as cluster_name,"
                " db_detail->'is_exclusive' as is_exclusive,"
                " db_detail->>'db_user' as db_user, db_detail->>'db_pass' as db_pass,"
                " db_detail->>'repl_user' as repl_user, db_detail->>'repl_pass' as repl_pass,"
                " db_detail->>'polar_type' as polar_type"
                f" FROM clup_db LEFT JOIN clup_cluster USING (cluster_id) {where_cond} "
                " ORDER BY cluster_id,db_id LIMIT %(limit)s OFFSET %(offset)s")
            args['limit'] = page_size
            args['offset'] = offset
            ret_rows = dbp.query(sql, args)
        host_data = dbp.query('select hid, ip from clup_host ', ())
        if len(host_data) > 0:
            host_data_dict = {i['ip']: i['hid'] for i in host_data}
    # 获取数据库对应的集群信息
    err_host_set = set()
    for row in ret_rows:
        # 兼容旧版本,旧版本没有os_user这一列
        if not row['os_user']:
            row['os_user'] = 'postgres'
        row['alarm'] = 1
        err_code, err_msg, ret = pg_helpers.get_db_room(row['db_id'])
        if err_code != 0:
            return 400, err_msg
        row['room_name'] = ret['room_name'] if ret else '默认机房'

        row['switch'] = 1
        if not row['up_db_id']:
            sql = f"SELECT count(*) FROM clup_db WHERE up_db_id = {row['db_id']}"
            count_rows = dbapi.query(sql)
            if count_rows[0]['count'] == 0:
                row['switch'] = 0

        if row['db_state'] == database_state.CREATING:
            continue
        if row['host'] in err_host_set:
            # agent连接超时的数据库状态就不检测了
            row['db_state'] = database_state.FAULT
            continue
        code, is_run = pg_db_lib.is_running(row['host'], row['pgdata'])
        if code == 0:
            if is_run:
                row['db_state'] = database_state.RUNNING
            elif row['db_state'] not in {database_state.CREATING, database_state.REPAIRING, database_state.CREATE_FAILD}:
                # 如果状态不是处于创建中或修复中,直接显示数据库状态为停止
                row['db_state'] = database_state.STOP
        else:
            # agent连接超时加到set集合中,避免重复检查造成接口太慢
            err_host_set.add(row['host'])
            row['db_state'] = database_state.FAULT
        # 20230130增加hid返回
        if host_data_dict:
            row['hid'] = host_data_dict.get(row['host'])

    ret_data = {"total": row_cnt, "page_size": pdict['page_size'], "rows": ret_rows}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def get_create_db_host_list(req):
    params = {
        'db_id': 0
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    with dbapi.DBProcess() as dbp:
        sql = "SELECT count(*) as cnt FROM clup_host "
        rows = dbp.query(sql, )
        row_cnt = rows[0]['cnt']
        if row_cnt == 0:
            return 200, json.dumps([])
        sql = "SELECT * FROM clup_host ORDER BY ip "
        rows = dbp.query(sql, )
        for row in rows:
            data = row['data']
            attr_dict = data
            attr_dict.pop('ip', None)
            row.update(attr_dict)
            row.setdefault('mem_size', 0)

    ip_list = []
    if pdict.get('db_id'):
        db_rows = dao.get_all_cascaded_db(pdict['db_id'])
        if db_rows:
            db_id_list = [row['db_id'] for row in db_rows]
            db_id_list.append(pdict['db_id'])
            str_db_id_list = str(db_id_list)[1:-1]
            sql = f"SELECT host FROM clup_db WHERE db_id in ({str_db_id_list}) "
            host_rows = dbapi.query(sql)
            ip_list = [row['host'] for row in host_rows]

    for row in rows:
        # check the host is aready in the cluster
        row['is_using'] = 0
        if row['ip'] in ip_list:
            row['is_using'] = 1
        sql = "SELECT data->'mem_size' as mem FROM clup_host WHERE hid = %s"

        mem_rows = dbapi.query(sql, (row['hid'], ))
        if mem_rows and mem_rows[0]['mem']:
            row['mem_size'] = mem_rows[0]['mem']
        rpc = None
        err_code, err_msg = rpc_utils.get_rpc_connect(row['ip'], conn_timeout=2)
        if err_code == 0:
            rpc = err_msg
            if rpc:
                rpc.close()
            row['state'] = 1
        else:
            row['state'] = -1

    raw_data = json.dumps(rows)
    return 200, raw_data


def get_db_info(req):
    params = {
        'db_id': csu_http.MANDATORY
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    sql = "SELECT cluster_id, db_state, host, repl_ip, pgdata, port, is_primary,db_id, instance_name, db_type," \
        "db_detail->'os_user' as os_user, db_detail->'os_uid' as os_uid, " \
        "db_detail->'pg_bin_path' as pg_bin_path, " \
        "db_detail->'db_user' as db_user, db_detail->'db_pass' as db_pass , " \
        "db_detail->'repl_user' as repl_user, db_detail->'repl_pass' as repl_pass, " \
        "db_detail->'delay' as delay,db_detail->'version' as version,db_detail->'instance_type' as instance_type " \
        " FROM clup_db WHERE  db_id = %s "
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if len(rows) == 0:
        return 400, f"No data related information :(db_id: {pdict['db_id']})"
    db = rows[0]
    return 200, json.dumps(db)


# 修改pg数据库对应的的配置
def modify_db_conf(req):
    """
    更新数据库postgres.conf/postgres.auto.conf配置文件
    """
    params = {
        'db_id': csu_http.MANDATORY,
        'setting_name': csu_http.MANDATORY,
        'setting_value': csu_http.MANDATORY,
        'setting_unit': csu_http.MANDATORY,
        'is_reload': csu_http.MANDATORY,
        'current_value': 0,
        'need_sync': 0
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # 检查当前要修改的数据库是否是主库
    sql = "SELECT is_primary FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (pdict["db_id"], ))
    if not rows:
        return 400, f"Cant find records for the database(db_id={pdict['db_id']})."
    is_primary = rows[0]["is_primary"]

    # 此参数只能在备库中修改,不能在主库中修改(无效)，也不支持同步修改备库，因为有些项需要设置的值不统一
    if is_primary and pdict["setting_name"] == "primary_conninfo":
        return 400, "primary_conninfo parameter cant modify in primary database."

    # 修改当前实例的参数
    more_msg = None
    err_code, err_msg = pg_helpers.modify_db_conf(pdict)
    if err_code != 0:
        return 400, err_msg

    # 这四个参数备库数值不小于主库
    # FIXME: 此处应该进一步判断备库中的值，而不是直接同步修改
    need_check_settings = ['max_connections',
        'max_prepared_transactions', 'max_worker_processes', 'max_locks_per_transaction']
    if is_primary and not pdict.get("need_sync"):
        if pdict['setting_name'] in need_check_settings:
            if int(pdict["setting_value"]) > int(pdict["current_value"]):
                pdict['need_sync'] = 1

    # 不同步修改直接返回
    if not pdict.get('need_sync'):
        return 200, json.dumps({"msg": "primary database parameter modification completed."})

    # 如果需要同步修改,找到所有相关联的数据库实例
    err_db_list = []
    more_msg = "primary database parameter modification completed"
    db_list = dao.get_all_cascaded_db(pdict["db_id"])
    db_id_list = [db['db_id'] for db in db_list]
    try:
        for db_id in db_id_list:
            if db_id == pdict['db_id']:
                continue
            pdict['db_id'] = db_id
            err_code, err_msg = pg_helpers.modify_db_conf(pdict)
            if err_code != 0:
                err_db_list.append(db_id)

        if err_db_list:
            more_msg += f",Failed to modify parameters synchronously:{err_db_list},please check database is running!"
        else:
            more_msg += ", Synchronizing parameters is complete"
        return 200, json.dumps({"msg": f"{more_msg}"})
    except Exception as e:
        return 400, json.dumps({"msg": f"Failed to modify primary database parameters, error message: {e}"})


def get_db_settings(req):
    """获取pg数据库对应的所有配置
    """
    params = {
        'db_id': csu_http.MANDATORY,
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT,
        'setting_name': 0,
        'setting_category': 0,
        'setting_context': 0,
        'setting_vartype': 0,
        'no_show_params': 0
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # 获取数据库内pg_settings的配置
    db_id = pdict['db_id']
    page_num = pdict['page_num']
    page_size = pdict['page_size']
    condition_dict = {
        "name": pdict.get('setting_name', 0),
        "category": pdict.get('setting_category', 0),
        "context": pdict.get('setting_context', 0),
        "vartype": pdict.get('setting_vartype', 0),
        "no_show": pdict.get("no_show_params", 0)
    }

    # 查询数据库对应的hid
    sql = f"SELECT db_state, hid, d.host, d.pgdata, d.db_detail->'version' as version" \
        f" FROM clup_db as d, clup_host as h WHERE d.host=h.ip AND d.db_id={db_id}"
    rows = dbapi.query(sql)
    if not rows:
        return 400, f"No database db_id={db_id} hid information can be queried!"
    db_dict = rows[0]
    # db_state = db_dict['db_state']

    pg_version = None
    code, is_run = pg_db_lib.is_running(db_dict['host'], db_dict['pgdata'])
    if code == 0:
        if not is_run:
            # the database is not running
            pg_version = int(float(db_dict["version"]))

    # 需要启动数据库后,才能修改配置参数
    # if db_state != 0:
    #     return 400, f"The database: db_id={db_id} not started, modify the parameters after starting the database."

    err_code, err_msg, all_settings_list = pg_helpers.get_all_settings(db_id, condition_dict, pg_version)
    if err_code != 0:
        return 400, err_msg

    # 分页/搜索
    filter_setting_list = all_settings_list

    start_index = (page_num - 1) * page_size if page_num >= 1 else 0
    end_index = page_num * page_size if page_num >= 1 else page_size
    page_setting_list = []
    if filter_setting_list:
        if (len(filter_setting_list) - 1 < end_index):
            end_index = len(filter_setting_list)
        page_setting_list = filter_setting_list[start_index:end_index]
    total_num = len(filter_setting_list)
    page_setting_dict = {'page_size': page_size, 'row': page_setting_list, 'total': total_num}
    return 200, json.dumps(page_setting_dict)


def get_all_setting_category(req):
    """
    获取参数分类专用接口
    """
    params = {
        'db_id': csu_http.MANDATORY
    }
    try:
        # 检查参数的合法性,如果成功,把参数放到一个字典中
        err_code, err_msg, pdict = csu_http.parse_parms(params, req)
        if err_code != 0:
            return 400, err_msg
        db_id = pdict['db_id']

        # get the database information
        sql = f"SELECT db_state, hid, d.host, d.pgdata, d.db_detail->'version' as version" \
            f" FROM clup_db as d, clup_host as h WHERE d.host=h.ip AND d.db_id={db_id}"
        rows = dbapi.query(sql)
        if not rows:
            return 400, f"No database db_id={db_id} hid information can be queried!"
        db_dict = rows[0]
        # db_state = db_dict['db_state']

        pg_version = None
        code, is_run = pg_db_lib.is_running(db_dict['host'], db_dict['pgdata'])
        if code == 0:
            if not is_run:
                # the database is not running
                pg_version = int(float(db_dict["version"]))

        # # 需要启动数据库后,才能修改配置参数
        # if db_state != 0:
        #     return 400, f"The database: db_id={db_id} not started, modify the parameters after starting the database."

        # 获取分类
        err_code, err_msg, all_settings_list = pg_helpers.get_all_settings(db_id, {}, pg_version)
        if err_code != 0:
            return 400, err_msg

        setting_category_set = set([entry['category'] for entry in all_settings_list])
        # 移除None，防止后面的sorted(list(setting_category_set))报错
        setting_category_set.remove(None)
        return 200, json.dumps({'category_list': sorted(list(setting_category_set)), 'msg': 'Successfully obtain the category list!'})
    except Exception as e:
        return 400, json.dumps({'category_list': [], 'msg': f'Description Failed to obtain the category list! error message: {e}'})


def get_pg_family_info(_req):
    """
    获取clup创建pg的种类,例如halo,postgresql
    """
    # 获取clup.conf文件内的配置, 一般配置格式：pg_family_name：PostgreSQL,postgres
    try:
        ret_dict = {
            'pg_family_name': '',
            'pg_family_user': '',
            'clup_replace_content': 'Clup',
            'msg': 'The database not set pg_family_name, that is default!'
        }
        pg_family_name_conf = config.get('pg_family_name', None)
        clup_replace_conf = config.get('clup_replace_content', None)

        if clup_replace_conf:
            ret_dict['clup_replace_content'] = clup_replace_conf.replace(' ', '').split(',')[0]

        if not pg_family_name_conf:
            ret_dict['pg_family_name'] = 'PostgreSQL'
            ret_dict['pg_family_user'] = 'postgres'
            return 200, json.dumps(ret_dict)

        pg_family_name = pg_family_name_conf.replace(' ', '').split(',')[0]
        pg_family_user = pg_family_name_conf.replace(' ', '').split(',')[-1]
        ret_dict['pg_family_name'] = pg_family_name if pg_family_name else ''
        ret_dict['pg_family_user'] = pg_family_user if pg_family_user else ''
        if not pg_family_name or not pg_family_user:
            ret_dict['msg'] = 'Get the pg_family_name failed!'
            return 400, json.dumps(ret_dict)
        return 200, json.dumps(ret_dict)
    except Exception as e:
        ret_dict['msg'] = f"Get the pg_family_name with unexcept error, {str(e)}."
        return 400, json.dumps(ret_dict)


def get_db_session(req):
    params = {
        'db_id': 0,
        'state': 0,
        'backend_type': 0,
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT,
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    db_id = pdict.get('db_id')
    if 'state' not in pdict:
        pdict['state'] = ""
    if 'backend_type' not in pdict:
        pdict['backend_type'] = ""
    if db_id:
        err_code, err_msg, conn = pg_helpers.get_db_conn(db_id)
        if err_code != 0:
            return 400, err_msg
        try:
            sql = "select db_detail->'version' as version from clup_db where db_id=%s"
            rows = dbapi.query(sql, (db_id,))
            if len(rows) <= 0:
                conn.close()
                return 400, "Database does not exist!"
            db_version = rows[0]['version']
            db_main_version = int(db_version.split('.')[0])
        except Exception:
            conn.close()
            return 400, traceback.format_exc()
    else:
        my_ip, _my_mac = helpers.get_my_ip()
        # 查看clup程序数据库的session
        conn = dbapi.connect_db(my_ip)
        # csumdb的db_version是12
        db_version = '12'
        db_main_version = int(db_version.split('.')[0])
    try:
        if db_main_version < 10:
            hide_col_list = ['backend_type']
        else:
            hide_col_list = []

        where_cond = ''
        if db_main_version >= 10:
            cond_name_list = ['state', 'backend_type']
        else:  # PostgreSQL 9.X没有backend_type字段
            cond_name_list = ['state']

        for cond_name in cond_name_list:
            if cond_name in pdict:
                str_ori_cond = pdict[cond_name]
                cond_list = str_ori_cond.split(',')
                # 如果内容中有单引号,则替换为\'
                cond_list = [k.replace("'", r"\'") for k in cond_list]
                # state中有null,需要特殊处理
                has_null = False
                if 'NULL' in cond_list:
                    cond_list.remove('NULL')
                    has_null = True
                cond_list = ["'" + k.strip() + "'" for k in cond_list]
                str_cond = ','.join(cond_list)
                if cond_list:
                    if not where_cond:
                        where_cond = ' WHERE '
                    else:
                        where_cond += ' AND '
                    if has_null:
                        where_cond += f'(({cond_name} in ({str_cond}) OR {cond_name} IS NULL))'
                    else:
                        where_cond += f'{cond_name} in ({str_cond})'
                else:
                    if not has_null:  # 没有任何条件,跳过
                        continue

                    if not where_cond:
                        where_cond = ' WHERE '
                    else:
                        where_cond += ' AND '
                    where_cond += f'{cond_name} IS NULL'

        sql = f"SELECT count(*) FROM pg_stat_activity {where_cond}"
        rows = dao.sql_query(conn, sql)
        total = rows[0]['count']

        page_num = pdict['page_num']
        page_size = pdict['page_size']
        offset = (page_num - 1) * page_size

        # PostgreSQL 9.X 版本没有backend_type字段
        backend_type = "" if db_main_version < 10 else ", backend_type"

        sql = ("SELECT datid,datname,pid,usesysid, usename,application_name,client_addr, client_hostname,"
            "client_port,date_trunc('second', backend_start)::text as backend_start,"
            "date_trunc('second', xact_start)::text as xact_start,"
            "date_trunc('second', query_start)::text as query_start,"
            " date_trunc('second', state_change)::text as state_change, "
            f"wait_event_type, wait_event,state, backend_xid, backend_xmin,query {backend_type} "
            f" FROM pg_stat_activity {where_cond} LIMIT {page_size} OFFSET {offset}")
        rows = dao.sql_query(conn, sql)
    finally:
        conn.close()
    for row in rows:
        backend_start = row['backend_start']
        if backend_start:
            row['backend_start'] = backend_start[0:-3]
        xact_start = row['xact_start']
        if xact_start:
            row['xact_start'] = xact_start[0:-3]
        query_start = row['query_start']
        if query_start:
            row['query_start'] = query_start[0:-3]
        state_change = row['state_change']
        if state_change:
            row['state_change'] = state_change[0:-3]

    ret_data = {
        'total': total,
        'page_size': page_size,
        'hide_col_list': hide_col_list,
        'rows': rows
    }
    return 200, json.dumps(ret_data)


def pg_cancel_backend(req):
    params = {
        'db_id': 0,
        'pid': csu_http.MANDATORY
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    db_id = pdict.get('db_id')

    if db_id:
        err_code, err_msg, conn = pg_helpers.get_db_conn(db_id)
        if err_code != 0:
            return 400, err_msg
    else:
        # 查看clup程序数据库的
        conn = dbapi.connect_db()
    sql = "SELECT pg_cancel_backend(%(pid)s) as t"
    try:
        dao.sql_query(conn, sql, pdict)
    except Exception as e:
        return 400, repr(e)
    finally:
        if conn:
            conn.close()
    return 200, "OK"


def pg_terminate_backend(req):
    params = {
        'db_id': 0,
        'pid': csu_http.MANDATORY
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    db_id = pdict.get('db_id')
    if db_id:
        err_code, err_msg, conn = pg_helpers.get_db_conn(db_id)
        if err_code != 0:
            return 400, err_msg
    else:
        # 查看clup程序数据库的
        conn = dbapi.connect_db()
    sql = "SELECT pg_terminate_backend(%(pid)s) as t"
    try:
        dao.sql_query(conn, sql, pdict)
    except Exception as e:
        return 400, repr(e)
    finally:
        if conn:
            conn.close()
    return 200, "OK"


def modify_db_info(req):
    params = {
        'db_id': csu_http.MANDATORY,
        'instance_name': 0,
        'repl_ip': 0,
        'db_user': 0,
        'db_pass': 0,
        'repl_user': 0,
        'repl_pass': 0,
        'pgdata': 0,
        'port': 0
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    db_id = pdict['db_id']
    try:
        set_sql = ""
        if pdict.get('instance_name') is not None:
            set_sql += f"instance_name='{pdict['instance_name']}', "
        if 'repl_ip' in pdict:
            set_sql += f"repl_ip='{pdict['repl_ip']}', "
        if 'port' in pdict:
            set_sql += f"port={pdict['port']}, "
        if 'pgdata' in pdict:
            set_sql += f"pgdata='{pdict['pgdata']}', "
        if set_sql:
            set_sql = set_sql.strip().strip(',')  # 去掉最后一个逗号
            sql = f"UPDATE clup_db SET {set_sql} WHERE db_id=%s"
            dbapi.execute(sql, (db_id,))

        detail_col_list = ['db_user', 'db_pass', 'repl_user', 'repl_pass']
        detail_set_dict = {}
        for col in detail_col_list:
            if pdict.get(col):
                detail_set_dict[col] = pdict.get(col)

        # 修改db_detail中的db_user、db_pass、repl_user、repl_pass
        if detail_set_dict:
            # 需要把级联的备库存的密码都改一下
            all_db = dao.get_all_cascaded_db(db_id)
            all_db_id = [db['db_id'] for db in all_db]
            str_all_db_id = str(all_db_id)[1:-1]
            sql = f"UPDATE clup_db SET db_detail = db_detail || (%s::jsonb) WHERE db_id in ({str_all_db_id})"
            dbapi.execute(sql, (json.dumps(detail_set_dict),))
    except Exception as e:
        err_msg = f"Modify the database(db_id={db_id}) information in clup_db with unexpected error, {str(e)}."
        return 400, err_msg

    if not pdict.get("port"):
        return 200, "Success"

    # 修改配置文件中的端口
    rpc = None
    try:
        # get the host
        sql = f"SELECT host from clup_db WHERE db_id = {db_id}"
        rows = dbapi.query(sql)
        if not rows:
            return 400, f"Cant find the information from clup_db,which db_id is {db_id}."
        host = rows[0]["host"]

        err_code, err_msg = rpc_utils.get_rpc_connect(host)
        if err_code != 0:
            return 400, err_msg
        rpc = err_msg
        modify_conf_file = f"{pdict['pgdata']}/postgresql.auto.conf"
        if rpc.os_path_exists(modify_conf_file):
            modify_conf_file = f"{pdict['pgdata']}/postgresql.conf"
        if rpc.os_path_exists(modify_conf_file):
            rpc.modify_config_type1(modify_conf_file, {"port": pdict['port']}, is_backup=False)
        else:
            return 400, f"The configuration file({modify_conf_file}) on host({host}) is not exists!"
    except Exception as e:
        err_msg = f"Modify the database(db_id={db_id}) port with unexpected error, {str(e)}."
        return 400, err_msg
    finally:
        if rpc:
            rpc.close()

    return 200, 'Success'


def get_primary_db_info(req):
    params = {
        'db_id': csu_http.MANDATORY,
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    db_id = pdict['db_id']
    sql = "SELECT cluster_id, db_id, repl_ip as primary_repl_ip, cluster_type, clup_cluster.state as cluster_state" \
          " FROM clup_db LEFT JOIN clup_cluster USING (cluster_id) WHERE db_id = %s"
    rows = dbapi.query(sql, (db_id, ))
    if len(rows) == 0:
        return 400, 'The database does not exist, please refresh and try again.'
    cur_db = rows[0]
    # 检查当前集群状态,如果时online,则提示先下线再操作
    cur_cluster_state = cur_db['cluster_state']
    if cur_cluster_state == cluster_state.NORMAL:
        return 403, f"The cluster cluster_id({cur_db['cluster_id']})is online, perform this operation offline"

    primary_id = dao.get_primary_db(db_id)
    if primary_id:
        db_id = primary_id[0]['db_id']
    sql = "SELECT  host, db_type, port, " \
        " db_detail->>'db_user' as db_user, db_detail->>'db_pass' as db_pass, " \
        " db_detail->>'repl_user' as repl_user, db_detail->>'repl_pass' as repl_pass " \
        " FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (db_id, ))
    if len(rows) == 0:
        return 400, 'The database does not exist, please refresh and try again.'
    db_dict = rows[0]
    db_dict.update(cur_db)
    # 获取表空间目录
    table_space = []
    err_code, err_msg, conn = dao.get_db_conn(db_dict)
    if err_code != 0:
        return 400, err_msg
    try:
        sql = "SELECT spcname AS name, pg_catalog.pg_tablespace_location(oid) AS location FROM pg_catalog.pg_tablespace where spcname not in ('pg_default', 'pg_global');"
        table_space = dao.sql_query(conn, sql)
    except Exception as e:
        logging.error(f"get primary db info error: {repr(e)}")
    finally:
        conn.close()
    tblspc_dir = []
    for space in table_space:
        tblspc_dir.append({'old_dir': space['location'], 'new_dir': space['location']})
    db_dict['tblspc_dir'] = tblspc_dir
    # if tabble_space_count[0]['count'] > 1:
    #     db_dict['table_space'] = 1
    return 200, json.dumps(db_dict)


def build_standby(req):
    params = {
        'instance_name': 0,
        'instance_type': csu_http.MANDATORY,  # physical
        'up_db_id': csu_http.MANDATORY,  # 源库的db_id
        'pg_bin_path': csu_http.MANDATORY,
        'version': csu_http.MANDATORY,
        'pgdata': csu_http.MANDATORY,
        'os_user': csu_http.MANDATORY,
        'os_uid': csu_http.MANDATORY | csu_http.INT,
        'repl_ip': csu_http.MANDATORY,
        'repl_user': csu_http.MANDATORY,
        'repl_pass': csu_http.MANDATORY,
        'host': csu_http.MANDATORY,
        'port': csu_http.MANDATORY | csu_http.INT,
        'sync': csu_http.MANDATORY,
        'other_param': csu_http.MANDATORY,
        'delay': 0,
        'cpu': 0,
        'shared_buffers': 0,
        'tblspc_dir': 0,
        # 'is_exclusive': csu_http.MANDATORY | csu_http.INT,  # 是否独享,取值0或1,1为独享,0为共享
        # 'cpu_num': csu_http.MANDATORY,  # cpu核心数量
        # 'memory_size': csu_http.MANDATORY | csu_http.INT,  # 分配的内存大小,单位默认为G
        'is_exclusive': 0,  # 是否独享,取值0或1,1为独享,0为共享
        'cpu_num': 0,  # cpu核心数量
        'memory_size': 0,  # 分配的内存大小,单位默认为G
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    if not pdict['pgdata'].startswith('/'):
        return 400, 'The args "pgdata" is not startswith "/"'

    # 查询上级库端口, 用于测试流复制用户连接
    sql = "SELECT db_id, port FROM clup_db WHERE db_id = %s "
    rows = dbapi.query(sql, (pdict['up_db_id'], ))
    if len(rows) == 0:
        return 400, 'The primary database instance does not exist.'
    if rows[0]['port']:
        up_db_port = rows[0]['port']
    else:
        return 400, 'The superior database port does not exist.'

    # 测试流复制用户连接
    try:
        sql = f"SELECT repl_ip, host FROM clup_db where db_id={pdict['up_db_id']}"
        rows = dbapi.query(sql)
        if len(rows) == 0:
            return -1, f"The up database {pdict['up_db_id']} does not exist, please try again."
        up_db_repl_ip = rows[0]['repl_ip']
        repl_user = pdict['repl_user']
        real_pass = db_encrypt.from_db_text(pdict['repl_pass'])

        rpc = None
        err_code, err_msg = rpc_utils.get_rpc_connect(pdict["host"])
        if err_code != 0:
            err_msg = f"Unable to connect to host: {pdict['host']}"
            return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
        rpc = err_msg

        pg_bin_path = pdict['pg_bin_path']

        # 根据 'pg_bin_path' 的值找到 Postgres 共享库路径, 并据此值 export LD_LIBRARY_PATH
        pg_lib_path = ''
        if pg_bin_path.endswith('/bin'):  # 如果是规范的路径, 则将 /bin 替换成 /lib
            # 替换倒数第一个 /bin 为 /lib
            pattern = '/bin'
            replacement = '/lib'
            reverse_string = pg_bin_path[::-1]
            reverse_pattern = pattern[::-1]
            reverse_replacement = replacement[::-1]
            replaced_string = re.sub(reverse_pattern, reverse_replacement, reverse_string, count=1)
            pg_lib_path = replaced_string[::-1]
        # 生成 export LD_LIBRARY_PATH 的命令
        export_ld_library_path_cmd = ''
        if pg_bin_path:
            export_ld_library_path_cmd = f'export LD_LIBRARY_PATH={pg_lib_path}:$LD_LIBRARY_PATH;'
        cmd = (
            f'{export_ld_library_path_cmd}{pg_bin_path}/psql -h{up_db_repl_ip} -p{up_db_port} '
            f'-U{repl_user} "dbname=template1 password={real_pass} replication=database" -c "IDENTIFY_SYSTEM"')
        err_code, err_msg, _out_msg = rpc.run_cmd_result(cmd)
        if err_code != 0:
            return 400, f"The replication user failed to connect, {err_msg}"
    except Exception as e:
        return 400, str(e)
    finally:
        if rpc:
            rpc.close()
    # ==========================================

    err_code, err_msg = pg_helpers.build_standby(pdict)
    if err_code != 0:
        return 400, err_msg

    task_id = err_msg[0]
    db_id = err_msg[1]

    ret_data = {"task_id": task_id, "db_id": db_id}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def modify_db_repl_info(req):
    """修改复制用户和密码"""
    params = {
        'db_id': csu_http.MANDATORY,
        'repl_user': csu_http.MANDATORY,
        'repl_pass': csu_http.MANDATORY,
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    # 检查该数据库是否在集群中
    db_id = pdict['db_id']
    sql = "SELECT cluster_id, db_detail->> 'db_user' as db_user  FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if len(rows) == 0:
        return 400, 'The database does not exist, please refresh and try again.'
    cluster_id = rows[0]['cluster_id']

    if cluster_id:
        return 400, 'The databasein the cluster,please modify in cluster information!'
    if rows[0]['db_user'] == pdict['repl_user']:
        pdict['db_pass'] = pdict['repl_pass']
    del pdict['db_id']
    all_db = dao.get_all_cascaded_db(db_id)
    all_db_id = [db['db_id'] for db in all_db]
    for k, v in pdict.items():
        k = k.strip()
        v = v.strip()
        str_all_db_id = str(all_db_id)[1:-1]
        sql = "UPDATE clup_db SET db_detail=jsonb_set(db_detail,'{" + k + "}','\"" + v + f"\"') WHERE db_id in ({str_all_db_id})"
        dbapi.execute(sql)
    return 200, 'OK'


def pg_promote(req):
    params = {
        'db_id': csu_http.MANDATORY
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    # 数据库可能在集群中,所以使用left join
    sql = "SELECT pgdata,host,is_primary,cluster_id,db_detail->>'instance_type' AS instance_type," \
          " db_detail->>'db_user' AS db_user,clup_cluster.state, clup_cluster.cluster_type  " \
          "FROM clup_db LEFT JOIN clup_cluster USING(cluster_id) WHERE db_id = %s"
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if len(rows) == 0:
        return 400, 'The database does not exist, please refresh and try again.'

    if rows[0]['state'] == 1:
        return 400, 'Database owning cluster is online, perform this operation offline!'
    if rows[0]['is_primary'] == 1:
        return 400, 'The database is already the primary database'
    pdict.update(rows[0])
    err_code, err_msg = pg_db_lib.promote(pdict['host'], pdict['pgdata'])
    if err_code != 0:
        return 400, err_msg

    cluster_type = rows[0]['cluster_type']
    cluster_id = rows[0]['cluster_id']
    # 激活成功,
    rows = dao.get_all_child_db(pdict['db_id'])
    # 共享磁盘的数据库激活不能让他脱离集群,
    id_list = [row['db_id'] for row in rows]
    if cluster_type == 2:
        # 如果是共享磁盘集群,就吧除了自身和所有子节点的数据库脱离集群
        str_id_list = str(id_list)[1:-1]
        sql = f"SELECT db_id FROM clup_db WHERE cluster_id = {cluster_id} AND db_id not in ({str_id_list})"
        rows = dbapi.query(sql)
        rows.append({'db_id': pdict['db_id']})  # type: ignore

    for row in rows:
        # 需要将当前库包括所有子节点脱离集群,当前库设为主库,上级库为空
        sql = "UPDATE  clup_db SET cluster_id = null WHERE db_id= %s"
        if row['db_id'] == pdict['db_id']:
            sql = "UPDATE  clup_db SET cluster_id = null, up_db_id=null, is_primary=1  WHERE db_id= %s"
            if cluster_type == 2:
                # 共享磁盘的情况不讲当前库脱离集群
                sql = "UPDATE clup_db SET up_db_id = null, is_primary = 1 WHERE db_id = %s"
        dbapi.execute(sql, (row['db_id'],))
    return 200, 'OK'


def get_all_cascaded_db(req):
    params = {
        'db_id': csu_http.MANDATORY
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    db_id = pdict['db_id']
    rows = dao.get_all_cascaded_db(db_id)
    if len(rows) == 0:
        return 400, 'No relevant database found.'
    return 200, json.dumps(rows)


def change_up_primary_db(req):
    """
    切换上级库
    如果要切换到的上级库是当前库的子节点,先把目标库的上级库改成当前库的上级库,然后把当前库的上级库改为目标库；
    当前库是主库的情况,把目标库变成主库,旧主库的所有备库连到新的主库上；
    如果不是子节点的情况,就只需要把当前库的上级库改为目标库；
    :param req:
    :return:
    """
    params = {
        'db_id': csu_http.MANDATORY,
        'up_db_id': csu_http.MANDATORY,
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    db_id = pdict['db_id']
    new_up_db = pdict['up_db_id']
    sql = "SELECT host, port FROM clup_db WHERE db_id= %s"
    new_up_db_info = dbapi.query(sql, (new_up_db, ))
    if not new_up_db_info:
        return 400, f'No database （db_id: {new_up_db}）information.'

    sql = "SELECT up_db_id, is_primary, cluster_id, host, port FROM clup_db WHERE db_id = %s"
    db_rows = dbapi.query(sql, (db_id, ))
    if len(db_rows) == 0:
        return -1, f'No relevant database found.(db_id: {db_id})'
    curr_db = db_rows[0]
    cluster_id = curr_db['cluster_id']

    if cluster_id:
        sql = "SELECT state FROM clup_cluster WHERE cluster_id = %s"
        rows = dbapi.query(sql, (cluster_id, ))
        if len(rows) == 0:
            return 400, 'Failed to switch, because the cluster status not found, please refresh and try again'
        if rows[0]['state'] == cluster_state.NORMAL:
            return 400, f'Database owning cluster(cluster_id:{cluster_id})is online, perform this operation offline!'

    cur_up_db_id = db_rows[0]['up_db_id']
    # 原先的库是主库,则需要实际上是做主备切换的动作
    if curr_db['is_primary']:  # 原先的库是主库,则需要实际上是做主备切换的动作
        old_pri_db = dao.get_db_info(db_id)[0]
        new_pri_db = dao.get_db_info(new_up_db)[0]
        err_code, err_msg = pg_helpers.switch_over_db(old_pri_db, new_pri_db, task_id=None, pre_msg='')
        if err_code != 0:
            return 400, err_msg
        else:
            return 200, 'OK'

    child_rows = dao.get_all_child_db(db_id)
    child_list = [row['db_id'] for row in child_rows]
    if new_up_db in child_list:
        # 新的上级库在原先库的子节点中,先把目标库的上级库改成当前库的上级库,再后面会把当前库的上级库改为目标库；
        if cur_up_db_id:
            err_code, err_msg = pg_helpers.change_up_db_by_db_id(new_up_db, cur_up_db_id)
            if err_code != 0:
                return 400, err_msg

        # 修改数据库配配置：把新上级库的上级库接到当前库的上级库后
        # if curr_db['is_primary']:
        #     is_primary = 1
        # else:
        #     is_primary = 0
        dao.update_up_db_id(cur_up_db_id, new_up_db, 0)

    # 更新集群机房信息
    if cluster_id:
        try:
            pg_helpers.update_cluster_room_info(cluster_id)
        except Exception as e:
            logging.error(f'Failed to update room infomation after the database switchover: {repr(e)}')
    # 最后把当前库接到新的上级库(没有子节点的情况只需要执行这一步)
    err_code, err_msg = pg_helpers.change_up_db_by_db_id(db_id, new_up_db)
    if err_code != 0:
        return 400, err_msg

    return 200, 'OK'


def renew_pg_bin_info(req):
    params = {
        "db_id": csu_http.MANDATORY
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    err_code, err_msg, _ = pg_helpers.renew_pg_bin_info(pdict['db_id'])
    if err_code != 0:
        return 400, err_msg
    return 200, 'OK'


def get_init_db_conf(req):
    params = {
        'version': csu_http.MANDATORY,
        "db_type": 0,
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # 只取两位,如9.3.5,取9.3
    version = pdict['version']
    pdict['version'] = '.'.join(version.split('.')[:2])

    sql = """SELECT setting_name, val, unit, setting_type,
    notes, min_val, max_val, enumvals, order_id, common_level FROM clup_init_db_conf
    WHERE %(version)s::numeric >= min_version AND %(version)s::numeric <= max_version
    """
    rows = dbapi.query(sql, pdict)

    init_conf_dict = {}
    name_common_level_dict = {}
    for row in rows:
        if pdict.get("db_type", 1) == 11 and row["setting_name"] == "log_destination":
            # FIXME: 当前PolarDB15的log_destination的值不能是csvlog，后续修复后改回来
            major_version = int(float(pdict["version"]))
            if major_version >= 15:
                row["val"] = "stderr"

        init_conf_dict[row['setting_name']] = row
        name_common_level_dict[row['setting_name']] = row['common_level']

    for row in rows:
        setting_name = row['setting_name']
        if not (row['min_val'] or row['max_val']):
            continue

        row["common_level"] = name_common_level_dict[setting_name]
        # 给提示添加值的范围
        min_val = row['min_val']
        if ('e+' in min_val or '.' in min_val) or row['setting_type'] not in {3, 4}:
            str_min_val = min_val
        elif row['setting_type'] == 3:
            str_min_val = pg_helpers.pretty_size(int(min_val))
        elif row['setting_type'] == 4:
            str_min_val = pg_helpers.pretty_ms(int(min_val))
        else:
            str_min_val = min_val
        if not str_min_val:
            str_min_val = '-∞'

        max_val = row['max_val']
        if ('e+' in max_val or '.' in max_val) or row['setting_type'] not in {3, 4}:
            str_max_val = max_val
        elif row['setting_type'] == 3:
            str_max_val = pg_helpers.pretty_size(int(max_val))
        elif row['setting_type'] == 4:
            str_max_val = pg_helpers.pretty_ms(int(max_val))
        else:
            str_max_val = max_val
        if not str_max_val:
            str_max_val = '∞'
        str_range = f'[{str_min_val}, {str_max_val}]'
        row['notes'] += f', range is {str_range}'

    return 200, json.dumps({'setting_list': rows})


def get_db_lock_info(req):
    params = {
        'db_id': 0,
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT
    }
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    db_id = pdict.get('db_id')
    if db_id:
        err_code, err_msg, conn = pg_helpers.get_db_conn(db_id)
        if err_code != 0:
            return 400, err_msg
    else:
        # 查看clup程序数据库的
        my_ip, _my_mac = helpers.get_my_ip()
        conn = dbapi.connect_db(my_ip)

    sql = """
    SELECT
        kl.pid as blocking_pid
        ,ka.usename as blocking_user
        ,ka.query as blocking_query
        ,bl.pid as blocked_pid
        ,a.usename as blocked_user
        ,a.query as query
        ,to_char(age(now(), a.query_start),'HH24h:MIm:SSs') as age
    FROM pg_catalog.pg_locks bl
    JOIN pg_catalog.pg_stat_activity a
            ON bl.pid = a.pid
    JOIN pg_catalog.pg_locks kl
        ON bl.locktype = kl.locktype
        and bl.database is not distinct from kl.database
        and bl.relation is not distinct from kl.relation
        and bl.page is not distinct from kl.page
        and bl.tuple is not distinct from kl.tuple
        and bl.transactionid is not distinct from kl.transactionid
        and bl.classid is not distinct from kl.classid
        and bl.objid is not distinct from kl.objid
        and bl.objsubid is not distinct from kl.objsubid
        and bl.pid <> kl.pid
    JOIN pg_catalog.pg_stat_activity ka
        ON kl.pid = ka.pid
    WHERE kl.granted and not bl.granted
    ORDER BY a.query_start
    """
    rows = dao.sql_query(conn, sql)
    total = len(rows)

    page_num = pdict['page_num']
    page_size = pdict['page_size']
    offset = (page_num - 1) * page_size
    sql += f" LIMIT {page_size} OFFSET {offset}"
    rows = dao.sql_query(conn, sql)
    conn.close()

    ret_data = {
        'total': total,
        'page_size': page_size,
        'rows': rows
    }
    return 200, json.dumps(ret_data)


def check_is_pg_bin_path(req):
    param = {
        "host": csu_http.MANDATORY,
        "pg_bin_path": csu_http.MANDATORY,
    }
    err_code, err_msg, pdict = csu_http.parse_parms(param, req)
    if err_code != 0:
        return 400, err_msg

    host = pdict['host']
    pg_bin_path = pdict['pg_bin_path']
    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        err_msg = f"Failed to connect to the host: {host}, Unable to validate directory: {pg_bin_path}"
        return 200, json.dumps({"err_code": -1, "err_msg": err_msg})

    rpc = err_msg
    try:
        fn_list = rpc.os_listdir(pg_bin_path)
    finally:
        rpc.close()
    if fn_list is None:
        return 200, json.dumps({"err_code": -1, "err_msg": f"the directory {pg_bin_path}does not exists!"})
    if ('psql' in fn_list) and ('pg_basebackup' in fn_list) and ('postgres' in fn_list):
        return 200, json.dumps({"err_code": 0, "err_msg": ""})
    else:
        return 200, json.dumps({"err_code": -1, "err_msg": "Not postgreSQL software BIN directory!"})


def get_pg_bin_path_list(req):
    """
    检查主机上PG软件的目录列表
    """
    param = {
        "host": csu_http.MANDATORY,
    }
    err_code, err_msg, pdict = csu_http.parse_parms(param, req)
    if err_code != 0:
        return 400, err_msg
    host = pdict['host']
    try:
        sql = "SELECT content FROM clup_settings WHERE key='pg_bin_path_string' "
        rows = dbapi.query(sql)
    except Exception as e:
        logging.error(repr(e))
        return 400, str(e)
    if len(rows) > 0:
        pg_bin_path_string = rows[0]['content']
    else:
        pg_bin_path_string = '/usr/pgsql-*/bin'
    pg_bin_path_string_list = []
    cells = pg_bin_path_string.split(',')
    for k in cells:
        pg_bin_path_string_list.append(k.strip())

    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        err_msg = f"Failed to connect to the host:{host}, error message: {err_msg}"
        logging.info(err_msg)
        return 400, err_msg
    rpc = err_msg

    try:
        err_code, ret_list = rpc.get_pg_bin_path_list(pg_bin_path_string_list)
        if err_code != 0:
            err_msg = f"call {host} get_pg_bin_path_list failed: {ret_list}"
            logging.error(err_msg)
            return 400, err_msg
        ret_list.sort()
    finally:
        rpc.close()
    return 200, json.dumps(ret_list)


def get_pg_bin_version(req):
    """
    获得PG软件的版本号
    """

    param = {
        "host": csu_http.MANDATORY,
        "pg_bin_path": csu_http.MANDATORY,
    }
    err_code, err_msg, pdict = csu_http.parse_parms(param, req)
    if err_code != 0:
        return 400, err_msg
    host = pdict['host']
    pg_bin_path = pdict['pg_bin_path']
    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        err_msg = f"Failed to connect to the host:{host}"
        return 200, json.dumps({"err_code": -1, "err_msg": err_msg})

    rpc = err_msg
    try:
        err_code, version = pg_db_lib.get_pg_bin_version(rpc, pg_bin_path)
        if err_code != 0:
            err_msg = f"call {host} get_pg_bin_version failed: {version}"
            logging.error(err_msg)
            return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
    finally:
        rpc.close()
    return 200, json.dumps({"err_code": 0, "version": version})


def check_pg_extensions_is_installed(req):
    param = {
        "host": csu_http.MANDATORY,
        "pg_bin_path": csu_http.MANDATORY,
        "pg_extension_list": csu_http.MANDATORY,
    }
    err_code, err_msg, pdict = csu_http.parse_parms(param, req)
    if err_code != 0:
        return 400, err_msg

    host = pdict['host']
    pg_bin_path = pdict['pg_bin_path']
    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        err_msg = f"Failed to connect to the host:{host}, Unable to validate directory {pg_bin_path} is postgreSQL software BIN directory!"
        return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
    rpc = err_msg
    try:
        plug_str = pdict['pg_extension_list']
        plug_list = plug_str.replace("'", '').split(',')

        not_installed_list = []
        for plug in plug_list:
            plug_ctl_file = f"{pg_bin_path}/../share/extension/{plug}.control"
            if not rpc.os_path_exists(plug_ctl_file):
                plug_ctl_file = f"{pg_bin_path}/../share/postgresql/extension/{plug}.control"
                if not rpc.os_path_exists(plug_ctl_file):
                    not_installed_list.append(plug)
    finally:
        rpc.close()

    if not_installed_list:
        err_msg = ', '.join(not_installed_list) + ' not installed!'
        return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
    else:
        return 200, json.dumps({"err_code": 0, "err_msg": ""})


def check_the_dir_is_empty(req):
    """
    判断数据目录是否为空,返回1为空,0为非空,-1为检查出错
    """
    param = {
        "host": csu_http.MANDATORY,
        "pgdata": csu_http.MANDATORY
    }
    err_code, err_msg, pdict = csu_http.parse_parms(param, req)
    if err_code != 0:
        return 400, err_msg
    host = pdict.get('host', '')
    pgdata = pdict.get('pgdata', '')
    try:
        err_code, err_msg = rpc_utils.get_rpc_connect(host)
        if err_code != 0:
            err_msg = f"Unable to connect to the host:{host}, err_msg: {err_msg}"
            return 200, json.dumps({"err_code": -1, "err_msg": err_msg})
        rpc = err_msg
        is_exists = rpc.os_path_exists(pgdata)
        if not is_exists:
            return 200, json.dumps({"is_empty": 1, "err_msg": ''})
        is_dir = rpc.path_is_dir(pgdata)
        if not is_dir:
            return 200, json.dumps({"is_empty": 0, "err_msg": f'{pgdata} is not directory'})
        is_empty = rpc.dir_is_empty(pgdata)
        if not is_empty:
            # 目录不为空
            return 200, json.dumps({"is_empty": 0, "err_msg": f'{pgdata} is not empty!'})
        return 200, json.dumps({"is_empty": 1, "err_msg": ''})
    except Exception as e:
        return 400, json.dumps({"is_empty": 0, "err_msg": f'Check directory with unexcepted error,{str(e)}!'})


def check_pgdata_is_used(req):
    """
    检查数据目录没有被同主机其他数据库使用, 返回0表示未被使用, 返回1表示已被使用
    """
    param = {
        "host": csu_http.MANDATORY,
        "pgdata": csu_http.MANDATORY
    }
    err_code, err_msg, pdict = csu_http.parse_parms(param, req)
    if err_code != 0:
        return 400, err_msg
    host = pdict.get('host', '')
    pgdata = pdict.get('pgdata', '')
    try:
        sql = "select db_id, cluster_id from clup_db where host = %s and pgdata = %s"
        query_result = dbapi.query(sql, (host, pgdata))
        if len(query_result) > 0:
            return 200, json.dumps({"used": 1, "err_msg": f'The pgdata {pgdata}  have been used!'})
        return 200, json.dumps({"used": 0, "err_msg": ''})
    except Exception as e:
        return 400, json.dumps({"used": 1, "err_msg": f'check pgdata {pgdata} with unexcepted error,{str(e)}!'})


def build_polar_reader(req):
    params = {
        'instance_name': 0,
        'instance_type': csu_http.MANDATORY,  # physical
        'up_db_id': csu_http.MANDATORY,  # 源库的db_id
        'pg_bin_path': csu_http.MANDATORY,
        'version': csu_http.MANDATORY,
        'pgdata': csu_http.MANDATORY,
        'os_user': csu_http.MANDATORY,
        'os_uid': csu_http.MANDATORY | csu_http.INT,
        'repl_ip': csu_http.MANDATORY,
        'repl_user': csu_http.MANDATORY,
        'repl_pass': csu_http.MANDATORY,
        'host': csu_http.MANDATORY,
        'port': csu_http.MANDATORY | csu_http.INT,
        'sync': csu_http.MANDATORY,
        'other_param': csu_http.MANDATORY,
        'delay': 0,
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    if not pdict['pgdata'].startswith('/'):
        return 400, 'The args "pgdata" is not startswith "/"'

    err_code, err_msg = polar_helpers.build_polar_standby(pdict, polar_type="reader")
    if err_code != 0:
        return 400, err_msg

    ret_data = json.dumps({"task_id": err_msg})
    return 200, ret_data


def build_polar_standby(req):
    params = {
        'instance_name': 0,
        'instance_type': csu_http.MANDATORY,  # physical
        'up_db_id': csu_http.MANDATORY,  # 源库的db_id
        'pg_bin_path': csu_http.MANDATORY,
        'version': csu_http.MANDATORY,
        'pgdata': csu_http.MANDATORY,
        'os_user': csu_http.MANDATORY,
        'os_uid': csu_http.MANDATORY | csu_http.INT,
        'repl_ip': csu_http.MANDATORY,
        'repl_user': csu_http.MANDATORY,
        'repl_pass': csu_http.MANDATORY,
        'host': csu_http.MANDATORY,
        'port': csu_http.MANDATORY | csu_http.INT,
        'sync': csu_http.MANDATORY,
        'other_param': csu_http.MANDATORY,
        # "polar_datadir": csu_http.MANDATORY,
        'delay': 0,
    }
    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    if not pdict['pgdata'].startswith('/'):
        return 400, 'The args "pgdata" is not startswith "/"'

    err_code, err_msg = polar_helpers.build_polar_standby(pdict, polar_type="standby")
    if err_code != 0:
        return 400, err_msg

    ret_data = json.dumps({"task_id": err_msg})
    return 200, ret_data


def get_pfs_info(req):
    """获取pfs 磁盘信息
    """
    params = {
        'db_id': csu_http.MANDATORY
    }

    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # get the disk info
    result = polar_lib.get_db_pfs_info(pdict['db_id'])
    if not result:
        return 400, f"Cant find any pfs disk information for db(id={pdict['db_id']})."

    pfs_disk_name = result['pfs_disk_name']

    # get the db_info
    sql = "SELECT host FROM clup_db WHERE db_id = %s"
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if not rows:
        return 400, f"No records were found for db(id={pdict['db_id']})."
    host = rows[0]['host']

    # get the pfs infor for the pfs_disk_name
    code, result = polar_lib.get_pfs_info(host, pfs_disk_name)
    if code != 0:
        return 400, result

    ret_dict = {
        "pfs_disk_name": result['pfs_disk_name'],
        "dev_size": result['dev_size'],
        "current_size": result['current_chunks'] * 10,
        "current_chunks": result['current_chunks'],
        "max_chunks": int(result['dev_size'] / 10)
    }

    return 200, json.dumps(ret_dict)


def pfs_growfs(req):
    """pfs disk 扩容
    """
    params = {
        "db_id": csu_http.MANDATORY,
        "pfs_disk_name": csu_http.MANDATORY,
        "current_chunks": csu_http.INT,
        "target_chunks": csu_http.INT
    }

    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # get the db infor by db_id
    rows = dao.get_db_info(pdict['db_id'])
    if not rows:
        return 400, f"No records were found for db(id={pdict['db_id']})."

    db_info = {
        "host": rows[0]['host'],
        "db_user": rows[0]['db_user'],
        "db_pass": db_encrypt.from_db_text(rows[0]['db_pass']),
        "port": rows[0]['port']
    }

    # growfs disk
    code, result = polar_lib.pfs_growfs(db_info, pdict['pfs_disk_name'], pdict['current_chunks'], pdict['target_chunks'])
    if code != 0:
        return 400, f"Growfs the pfs disk failed, {result}."

    return 200, "Success"


def modify_vip_on_host(req):
    """更改vip在主机上的绑定
    """
    params = {
        "host": csu_http.MANDATORY,
        "vip": csu_http.MANDATORY,
        "option": csu_http.INT
    }
    # check request params
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    vip = pdict["vip"]
    host = pdict["host"]

    # bond vip on host
    if pdict["option"] == 1:
        code, result = rpc_utils.check_and_add_vip(host, vip)
        if code != 0:
            return 400, result
        # update clup_used_vip
        sql = "UPDATE clup_used_vip SET used_reason=1 WHERE vip=%s RETURNING vip"
        rows = dbapi.query(sql, (vip, ))
        if not rows:
            return 400, f"Excute sql({sql}) failed."

    # remove vip from host
    else:
        # check the cluster state
        sql = "SELECT c.cluster_id, state, cluster_data->>'cluster_name' as cluster_name " \
            " FROM clup_used_vip v,clup_cluster c WHERE vip=%s AND c.cluster_id=v.cluster_id"
        rows = dbapi.query(sql, (vip, ))
        if rows and rows[0]['state'] not in {cluster_state.FAILED, cluster_state.OFFLINE}:
            cluster_id = rows[0]["cluster_id"]
            cluster_name = rows[0]["cluster_name"]
            return 400, f"The cluster({cluster_id}:{cluster_name}) state is not OFFLINE or FAILED,cant remove vip from host."
        code, result = rpc_utils.check_and_del_vip(host, vip)
        if code != 0:
            return 400, result

        # update clup_used_vip
        sql = "UPDATE clup_used_vip SET used_reason=2 WHERE vip=%s RETURNING vip"
        rows = dbapi.query(sql, (vip, ))
        if not rows:
            return 400, f"Excute sql({sql}) failed."

    return 200, "Success"


def get_db_pg_hba(req):
    """获取数据库的pg_hba设置
    """
    params = {
        "db_id": csu_http.MANDATORY,
        "page_num": csu_http.INT,
        "page_size": csu_http.INT
    }

    # check request params
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    try:
        # get the db info
        db_conn_info = dao.get_db_conn_info(pdict['db_id'])
        if not db_conn_info:
            return 400, f"Cant find any records for db_id={pdict['db_id']}."
        # connect the database
        err_code, err_msg, db_conn = dao.get_db_conn(db_conn_info)
        if err_code != 0:
            return 400, err_msg
    except Exception as e:
        return 400, f"Connect the database with unexpected error, {str(e)}."

    try:
        # search infor from pg_hba_file_rules
        offset = (pdict['page_num'] - 1) * pdict['page_size']
        code, msg, ret_list = pg_helpers.get_pg_hba(pdict['db_id'], db_conn, offset, pdict['page_size'])
        if code != 0:
            return 400, msg

        try:
            # check and get the ident info
            ident_content_list = list()
            for hba_row in ret_list:
                if hba_row["options"] and "map=" in hba_row["options"][0]:  # type: ignore
                    map_user = hba_row["options"][0].split("map=")[-1].strip()  # type: ignore
                    if not ident_content_list:
                        code, result = pg_helpers.get_pg_ident(db_conn, db_conn_info["host"])
                        if code != 0:
                            # if not get the content,no care
                            continue
                        ident_content_list = result

                    for ident_content in ident_content_list:
                        if map_user in ident_content:
                            hba_row["pg_ident"] = ident_content.split()  # type: ignore
        except Exception as e:
            return 400, f"Get the pg_ident information with unexpected error, {str(e)}."

        # query database names and user names from the database
        code, db_names = pg_helpers.get_db_names(db_conn)
        if code != 0:
            return 400, db_names
        code, user_names = pg_helpers.get_user_names(db_conn)
        if code != 0:
            return 400, user_names
    finally:
        db_conn.close()

    ret_dict = {
        "pg_hba_rules": ret_list,
        "db_names": [row['datname'] for row in db_names],  # type: ignore
        "user_names": [row['usename'] for row in user_names],  # type: ignore
        "total": len(ret_list)
    }

    return 200, json.dumps(ret_dict)


def delete_one_pg_hba(req):
    """删除一条数据库pg_hba设置
    """
    params = {
        "db_id": csu_http.INT,
        "line_number": csu_http.INT,
        "is_reload": csu_http.INT
    }

    # check request params
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # get the database infor
    sql = "SELECT host, pgdata FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if not rows:
        return 400, f"Cant find any records for database(db_id={pdict['db_id']})."
    db_info = rows[0]

    # delete from pg_hba
    code, result = pg_helpers.delete_one_pg_hba(
        db_info['host'], db_info['pgdata'], pdict['line_number'], pdict['is_reload'])
    if code != 0:
        return 400, result

    return 200, "Success"


def update_pg_hba(req):
    """更新一条数据库pg_hba设置
    """
    params = {
        "db_id": csu_http.INT,
        "option": csu_http.MANDATORY,
        "conf_dict": csu_http.MANDATORY,
        "is_reload": csu_http.INT,
        "line_number": 0
    }

    # check request params
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # update pg_hba
    code, result = pg_helpers.update_pg_hba(pdict, option=pdict["option"])
    if code != 0:
        return 400, result

    return 200, "Success"


def get_history_hba(req):
    """获取hba的历史文件列表

    Args:
        req (_type_): _description_
    """
    params = {
        "db_id": csu_http.INT
    }

    # check request params
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # get the db info
    sql = "SELECT pgdata, host FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if not rows:
        return 400, f"Cant find any records for the database(db_id={pdict['db_id']})."
    db_info = dict(rows[0])

    # connect the host
    code, result = rpc_utils.get_rpc_connect(db_info['host'])
    if code != 0:
        return 400, f"Connect the host failed, {result}."
    rpc = result

    try:
        # get the file list
        file_list = list()
        dir_path = f"{db_info['pgdata']}/pg_hba_archive"
        if not rpc.os_path_exists(dir_path):
            return 200, json.dumps({"rows": file_list})

        file_list = rpc.os_listdir(dir_path)
        if not file_list:
            file_list = list()
    finally:
        rpc.close()

    file_list.reverse()
    return 200, json.dumps({"rows": file_list})


def get_hba_history_content(req):
    """获取用户认证历史文件的内容

    Args:
        req (_type_): _description_
    """
    params = {
        "db_id": csu_http.INT,
        "file": csu_http.MANDATORY
    }

    # check request params
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # get the database info
    sql = "SELECT pgdata, host FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if not rows:
        return 400, f"Cant find any records for the database(db_id={pdict['db_id']})."
    db_info = dict(rows[0])

    # connect the host
    code, result = rpc_utils.get_rpc_connect(db_info['host'])
    if code != 0:
        return 400, f"Connect the host failed, {result}."
    rpc = result

    file_path = f"{db_info['pgdata']}/pg_hba_archive/{pdict['file']}"
    try:
        # get the file content
        if not rpc.os_path_exists(file_path):
            return 400, f"The file({file_path}) is not exist."

        code, result = rpc.file_read(file_path)
        if code != 0:
            return 400, f"Read the file content failed, {result}."

        return 200, json.dumps({"content": result})
    finally:
        rpc.close()


def get_pg_log_file_list(req):
    """获取pg日志文件列表
    """
    params = {
        "db_id": csu_http.INT,
        "page_num": csu_http.INT,
        "page_size": csu_http.INT
    }

    # check request params
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # get the db_info
    sql = "SELECT host, pgdata FROM clup_db WHERE db_id = %s"
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if not rows:
        return 400, f"Cant find any records for the database(db_id={pdict['db_id']})."
    db_info = dict(rows[0])

    # try to connect the host
    code, result = rpc_utils.get_rpc_connect(db_info["host"])
    if code != 0:
        return 400, f"Connect the host({db_info['host']}) failed, {result}."
    rpc = result

    # get the log_info
    try:
        log_info = None

        # get the database conn info
        db_conn_info = dao.get_db_conn_info(pdict['db_id'])

        # if can connect the database,get log_info from pg_settings,else read from conf files
        if db_conn_info:
            # connect the database
            err_code, err_msg, db_conn = dao.get_db_conn(db_conn_info)
            if err_code != 0:
                return 400, err_msg
            try:
                # get the log_info
                sql = "SELECT name, setting FROM pg_settings WHERE name in ('log_directory', 'log_destination', 'data_directory')"
                rows = dao.sql_query(db_conn, sql)
                if not rows:
                    return 400, f"Execute sql({sql}) failed."
                log_info = {row["name"]: row["setting"] for row in rows}
            finally:
                db_conn.close()

        if not log_info:
            pgdata = db_info['pgdata']
            # read conf files to get the log_info
            log_info = {
                'log_directory': 'log',
                'log_destination': 'stderr',
                'data_directory': pgdata
            }
            setting_list = ['log_directory', 'log_destination']

            postgresql_conf = f"{pgdata}/postgresql.conf"
            postgresql_auto_conf = f"{pgdata}/postgresql.auto.conf"
            # read from postgresql.conf
            code, item_dict = rpc.read_config_file_items(postgresql_conf, setting_list)
            if code != 0:
                return 400, f"Cant read the settings values from {postgresql_conf}, {item_dict}."
            # maybe the setting is not set
            if item_dict["log_directory"]:
                log_info["log_directory"] = item_dict["log_directory"]
            if item_dict["log_destination"]:
                log_info["log_destination"] = item_dict["log_destination"]

            # read from postgresql.auto.conf and update log_info
            code, item_dict = rpc.read_config_file_items(postgresql_auto_conf, setting_list)
            if code == 0:
                log_info.update(item_dict)

    except Exception as e:
        return 400, f"Get the log settings with unexpected error, {str(e)}."

    # get the log file list
    try:
        ret_list = list()
        pgdata = log_info['data_directory']
        log_directory = log_info["log_directory"]
        if not log_info["log_directory"].startswith("/"):
            if "'" in log_info["log_directory"]:
                log_info["log_directory"] = log_info["log_directory"].strip("'")
            log_directory = f"{pgdata}/{log_info['log_directory']}"

        # get the file_list_info
        file_list = rpc.os_listdir(log_directory)
        if not file_list:
            file_list = list()

        # get the file info
        if log_info["log_destination"] == "csvlog":
            filter_str = ".csv"
            file_list = [file for file in file_list if file.endswith(filter_str)]
        for file in file_list:
            file_path = f"{log_directory}/{file}"
            code, file_info = rpc.os_stat(file_path)
            if code != 0:
                ret_list.append(dict())
                continue
            file_ctime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(file_info["st_ctime"]))
            ret_list.append({"file": file, "st_ctime": file_ctime, "st_size": file_info["st_size"]})

    except Exception as e:
        return 400, f"Get the file information with unexpected error, {str(e)}."
    finally:
        if rpc:
            rpc.close()

    page_start = (pdict["page_num"] - 1) * pdict["page_size"]
    page_end = page_start + pdict["page_size"]
    ret_dict = {
        "total": len(ret_list),
        "log_directory": log_directory,
        "log_destination": log_info["log_destination"],
        "file_info_list": ret_list[page_start:page_end]
    }

    return 200, json.dumps(ret_dict)


def get_pg_log_content(req):
    """获取pg日志文件内容
    """
    params = {
        "db_id": csu_http.INT,
        "page_num": csu_http.INT,
        "read_size": csu_http.INT,
        "file_name": csu_http.MANDATORY,
        "log_directory": csu_http.MANDATORY,
        "log_destination": csu_http.MANDATORY
    }

    # check request params
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # get the db_info
    sql = "SELECT host, pgdata FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (pdict["db_id"], ))
    if not rows:
        return 400, f"Cant find any records for db_id={pdict['db_id']}."
    db_info = rows[0]

    # read the log_file content
    log_file_path = f"{pdict['log_directory']}/{pdict['file_name']}"
    rpc = None
    try:
        read_size = pdict['read_size']  # bytes number

        # connect the host
        code, result = rpc_utils.get_rpc_connect(db_info["host"])
        if code != 0:
            return 400, f"Connect the host({db_info['host']}) failed, {result}."
        rpc = result

        # get the file size
        code, result = rpc.os_stat(log_file_path)
        if code != 0:
            return 400, f"Get the file({log_file_path}) stat failed, {result}."
        file_size = result["st_size"]  # unit bytes

        # read the file cotent,one step read 1Kb
        offset = (pdict["page_num"] - 1) * read_size
        code, content = rpc.os_read_file(log_file_path, offset, read_size)
        if code != 0:
            return 400, f"Read the file({log_file_path}) content failed, {content}."

        page_count = file_size // read_size
        if page_count * read_size < file_size:
            page_count += 1

        ret_dict = {
            "total": page_count,
            "content": str(content, encoding="utf-8")
        }

    except Exception as e:
        return 400, f"Get the log file content with unexpected error, {str(e)}."
    finally:
        if rpc:
            rpc.close()

    return 200, json.dumps(ret_dict)


def get_sync_repl_delay(req):
    params = {
        'cluster_id': csu_http.MANDATORY | csu_http.INT,
    }

    # 检查参数的合法性,如果成功,把参数放到一个字典中
    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg
    cluster_id = pdict['cluster_id']

    err_code, data = ha_mgr_get_repl_delay(cluster_id)
    if err_code != 0:
        return 400, data

    # remove the async
    sync_state_list = ['sync', 'potential', 'quorum']
    ret_data_list = list()
    for sync_dict in data:
        if sync_dict['is_sync'] in sync_state_list:
            ret_data_list.append(sync_dict)

    ret_data = {"total": len(data), "rows": ret_data_list}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def get_child_node(req):
    """获取子节点，一级备库节点信息

    Args:
        req (_type_): _description_

    Returns:
        _type_: _description_
    """
    params = {
        'db_id': csu_http.INT
    }

    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    code, msg, result = pg_helpers.get_child_node(pdict['db_id'])
    if code != 0:
        return 400, msg

    return 200, json.dumps({"rows": result})


def enable_standby_sync(req):
    params = {
        'db_id': csu_http.INT,
        'sync_mode': csu_http.MANDATORY,
        'sync_method': csu_http.MANDATORY,
        'standby_id_list': csu_http.MANDATORY,
        'node_number': 0,
    }

    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    code, result = pg_helpers.enable_standby_sync(pdict)
    if code != 0:
        return 400, result

    return 200, "Success"


def disable_standby_sync(req):
    params = {
        'db_id': csu_http.INT
    }

    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    # reset setting
    code, result = pg_helpers.disable_standby_sync(pdict['db_id'])
    if code != 0:
        return 400, result

    return 200, "Success"


def check_port_is_right(req):
    """检查输入的端口是否正确

    Args:
        req (_type_): _description_

    Returns:
        _type_: _description_
    """
    param = {
        "host": csu_http.MANDATORY,
        "pgdata": csu_http.MANDATORY,
        "port": csu_http.MANDATORY | csu_http.INT,
    }
    err_code, err_msg, pdict = csu_http.parse_parms(param, req)
    if err_code != 0:
        return 400, err_msg
    try:
        err_code, err_msg = rpc_utils.get_rpc_connect(pdict["host"])
        if err_code != 0:
            return 200, json.dumps({"err_code": -1, "err_msg": err_msg})

        rpc = err_msg
        postmaster_file = f"{pdict['pgdata']}/postmaster.pid"
        if not rpc.os_path_exists(postmaster_file):
            return 200, json.dumps({"err_code": -1, "err_msg": "Please check whether the database is started."})
        file_size = rpc.get_file_size(postmaster_file)
        if file_size < 0:
            return 200, json.dumps(
                {"err_code": -1, "err_msg": f"Failed to get the file size:(file_name={postmaster_file})"}
            )

        err_code, err_msg = rpc.os_read_file(postmaster_file, 0, file_size)
        if err_code != 0:
            return 200, json.dumps(
                {"err_code": -1, "err_msg": f"Failed to obtain the file content:(file_name={postmaster_file})"}
            )
        lines = err_msg.decode().split("\n")
        if lines[3] != str(pdict["port"]):
            return 200, json.dumps(
                {
                    "err_code": -1,
                    "err_msg": f"The port {pdict['port']} does not match the data directory {pdict['pgdata']}, please check if it is correct."
                }
            )
    except Exception:
        return 200, json.dumps({"err_code": -1, "err_msg": traceback.format_exc()})
    return 200, json.dumps({"err_code": 0, "err_msg": ""})


def add_db(req):
    """导入数据库

    Args:
        req (_type_): _description_
    """
    params = {
        "instance_name": 0,  # 实例名
        "host": csu_http.MANDATORY,  # 主机
        "port": csu_http.MANDATORY,  # 端口
        "pgdata": csu_http.MANDATORY,  # 数据目录
        "db_user": csu_http.MANDATORY,  # 用户名
        "db_pass": csu_http.MANDATORY,  # 密码
        "db_type": 0,  # 数据库类型：1-PG， 11-polardb
    }

    err_code, err_msg, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, err_msg

    if "db_type" not in pdict:
        pdict["db_type"] = 1

    host = pdict["host"]
    port = pdict["port"]
    instance_name = pdict.get("instance_name")
    sql = "SELECT count(*) FROM clup_db wHERE (pgdata = %s AND host=%s) OR (port = %s AND host=%s)"
    rows = dbapi.query(sql, (pdict["pgdata"], host, port, host))
    if rows[0]["count"] > 0:
        return 400, f"Database addition failure, {host}:{port} {pdict['pgdata']} already used"
    sql = f"SELECT count(*) FROM clup_db WHERE host = '{host}' AND port= {port} "
    rows = dbapi.query(sql)
    if rows[0]["count"] > 0:
        return 400, f"create fail, Port {port} already in used on host:({host})"

    # 先尝试连接下数据库
    # 此逻辑在端口检查时已实现，无需再次确认
    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        return 400, err_msg

    rpc = err_msg
    err_code, err_msg = pg_db_lib.is_ready(rpc, pdict["pgdata"], pdict["port"])
    # 测试数据库连接是否正常
    if err_code != 0:
        return 400, err_msg
    err_code, is_primary = pg_db_lib.is_primary(host, pdict["pgdata"])
    if err_code != 0:
        return 400, f"Failed to check whether the database is primary or standby: {is_primary}"

    err_code, err_msg = pg_db_lib.get_db_port(rpc, str(pdict["pgdata"]))
    rpc.close()
    if err_code != 0:
        logging.error(f"Failed to get running database port: {err_msg}")
    else:
        port = err_msg
        if int(pdict["port"]) != int(port):
            return 400, f"The input port is{pdict['port']}, running port is{port}, Please check port and try again!"

    # 尝试连接数据库
    err_code, err_msg, conn = dao.get_db_conn(pdict)
    if err_code == 0:
        conn.close()
    else:
        return 400, f"Failed to connect to the database: {err_msg}"

    db_detail = {
        "db_user": pdict["db_user"],
        "db_pass": pdict["db_pass"],
        "instance_type": "physical",
        "room_id": "0",
    }
    if is_primary:
        pdict["is_primary"] = 1
    else:
        pdict["is_primary"] = 0
    pdict["state"] = 1
    pdict["db_state"] = 0
    # leifliu 当数据库名为空时，为pidct添加'instance_name'字段
    pdict["instance_name"] = instance_name
    pdict["db_detail"] = json.dumps(db_detail)

    sql = (
        "INSERT INTo clup_db(state, pgdata, is_primary, host, instance_name, db_detail, port, db_state, db_type, scores, repl_ip)"
        " VALUES(%(state)s,%(pgdata)s,%(is_primary)s,%(host)s,%(instance_name)s,%(db_detail)s, %(port)s, %(db_state)s, %(db_type)s, 0, %(host)s) RETURNING db_id"
    )
    rows = dbapi.query(sql, pdict)
    db_id = rows[0]["db_id"]
    ret_message = "Add database success"
    err_code, err_msg, _new_dict = pg_helpers.renew_pg_bin_info(db_id)
    if err_code != 0:
        ret_message = f"{ret_message}, renew pg bin info failed, ferr_msgy."

    return 200, ret_message
