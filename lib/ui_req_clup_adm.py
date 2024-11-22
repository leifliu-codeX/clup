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
@description: WEB界面的CLup自身管理接口后端服务处理模块
"""

import os
import json
import logging
# agent_log
import math

import agent_logger
import config
import csu_http
import dbapi
import ip_lib
import logger
import rpc_utils
import long_term_task
import general_task_mgr
import task_type_def

from pg_db_lib import is_running
from pg_helpers import get_all_settings
from zqpool_helpers import conf_sort as zqpool_conf_sort

from concurrent.futures import ThreadPoolExecutor, as_completed


def get_clup_host_list(req):
    """
    获取clup主机列表
    """
    params = {}
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # 获取自己的ip地址
    nic_dict = ip_lib.get_nic_ip_dict()
    my_ip, _my_mac = ip_lib.get_ip_in_network(nic_dict, config.get('network'))
    if not my_ip:
        my_ip = '127.0.0.1'
        logging.error(f"In clup.conf network is {config.get('network')}, but this machine not in this network")

    ret = []
    clup = True
    host = my_ip
    rpc_port = config.get('server_rpc_port', 4342)

    # 连接csumdb检查数据库是否正常
    csumdb_is_running = True
    try:
        conn = dbapi.connect_db(host)
        conn.close()
    except Exception as e:
        logging.error(f"({host}) csumdb connect failed: {repr(e)}")
        csumdb_is_running = False

    url = None
    ret.append({
        'host': host,
        'port': rpc_port,
        'csumdb': csumdb_is_running,
        'url': url,
        'clup': clup,
        'primary': True
    })
    return 200, json.dumps(ret)


def get_log_level_list(req):
    params = {
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT,
        'filter': 0,
    }

    # 检查参数的合法性，如果成功，把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    log_level_name_dict = logger.get_log_level_name_dict()

    log_type_list = logger.get_log_type_list()
    rows = []
    for log_type in log_type_list:
        row = {}
        try:
            tmp_logger = logging.getLogger(log_type)
            row['log_type'] = log_type if log_type else 'main'
            row['level'] = tmp_logger.level
            row['level_name'] = log_level_name_dict.get(tmp_logger.level, str(tmp_logger.level))
        except Exception:
            row['level'] = -1
            row['level_name'] = 'unknown'
            row['log_type'] = log_type if log_type else 'main'
        rows.append(row)

    ret_data = {"total": len(rows), "page_size": pdict['page_size'],
                "rows": rows}

    raw_data = json.dumps(ret_data)
    return 200, raw_data


def set_log_level(req):
    params = {
        'log_type': csu_http.MANDATORY,
        'level_name': csu_http.MANDATORY
    }
    # 检查参数的合法性，如果成功，把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    log_type = pdict['log_type']
    if log_type == 'main':
        log_type = ''
    log_type_list = logger.get_log_type_list()
    if log_type not in log_type_list:
        return 400, f"log_type({log_type} not in {log_type_list}"

    log_level_name = pdict['level_name']
    log_level_dict = logger.get_log_level_dict()
    if log_level_name not in log_level_dict:
        return 400, f"level_name({log_level_name} not in {log_level_dict.keys()}"
    log_level = log_level_dict[log_level_name]
    tmp_logger = logging.getLogger(log_type)
    tmp_logger.setLevel(log_level)
    return 200, 'ok'


def get_agent_log_level_list(req):
    params = {
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT,
        'filter': 0,
    }

    # 检查参数的合法性，如果成功，把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    where_cond = ''
    if 'filter' in pdict:
        if pdict["filter"]:
            where_cond = (' WHERE ip like %(filter)s')
    sql = 'SELECT count(*) AS cnt FROM clup_host'
    sql += where_cond
    rows = dbapi.query(sql, pdict)
    row_cnt = rows[0]['cnt']

    log_type_list = agent_logger.get_log_type_list()

    log_level_name_dict = agent_logger.get_log_level_name_dict()
    log_type_cnt = len(log_type_list)
    total_cnt = row_cnt * log_type_cnt

    sql_arg = {}

    sql_arg['offset'] = (pdict['page_num'] - 1) * pdict['page_size'] // log_type_cnt
    # 结束的行号
    end_pos = math.ceil(pdict['page_num'] * pdict['page_size'] / log_type_cnt)
    sql_arg['page_size'] = end_pos - sql_arg['offset'] + 1
    if where_cond:
        sql_arg['filter'] = pdict['filter']
        sql = 'SELECT * FROM clup_host WHERE ip like %(filter)s' \
            ' order by clup_host.hid' \
            ' offset %(offset)s limit %(page_size)s'
    else:
        sql = 'SELECT * FROM clup_host ' \
            ' order by clup_host.hid' \
            ' offset %(offset)s limit %(page_size)s'
    rows = dbapi.query(sql, sql_arg)

    # 应该开始的行位置
    start_pos = (pdict['page_num'] - 1) * pdict['page_size']
    # 循环开始的行位置
    loop_pos = sql_arg['offset'] * log_type_cnt
    # 跳过的行
    skip_cnt = start_pos - loop_pos

    pool = ThreadPoolExecutor(10)
    task_dict = {}
    for row in rows:
        task = pool.submit(agent_logger.query_agent_log_level, row['ip'], log_type_list)
        task_dict[task] = row

    for task in as_completed(task_dict.keys()):
        agent_log_level_dict = task.result()
        row = task_dict[task]
        row['log_level_dict'] = agent_log_level_dict
    pool.shutdown()

    ret_rows = []
    i = 0
    exit_loop = False
    for row in rows:
        for log_type in log_type_list:
            if i >= skip_cnt:
                ret_row = {}
                ret_row['ip'] = row['ip']
                ret_row['log_type'] = log_type if log_type else 'main'
                ret_row['level'] = row['log_level_dict'][log_type]
                ret_row['level_name'] = log_level_name_dict.get(ret_row['level'], str(ret_row['level']))
                ret_rows.append(ret_row)
                if len(ret_rows) == pdict['page_size']:
                    exit_loop = True
                    break
            i += 1
        if exit_loop:
            break

    ret_data = {
        "total": total_cnt,
        "page_size": pdict['page_size'],
        "rows": ret_rows
    }

    raw_data = json.dumps(ret_data)
    return 200, raw_data


def set_agent_log_level(req):
    params = {
        'ip': csu_http.MANDATORY,
        'log_type': csu_http.MANDATORY,
        'level_name': csu_http.MANDATORY
    }
    # 检查参数的合法性，如果成功，把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    log_type = pdict['log_type']
    if log_type == 'main':
        log_type = ''
    log_type_list = logger.get_log_type_list()
    if log_type not in log_type_list:
        return 400, f"log_type({log_type} not in {log_type_list}"
    log_level_name = pdict['level_name']
    log_level_dict = agent_logger.get_log_level_dict()
    if log_level_name not in log_level_dict:
        return 400, f"level_name({log_level_name} not in {log_level_dict.keys()}"
    log_level = log_level_dict[log_level_name]

    err_code, err_msg = rpc_utils.get_rpc_connect(pdict['ip'], 1)
    if err_code != 0:
        return 400, err_msg
    rpc = err_msg
    try:
        err_code, err_msg = rpc.set_log_level(log_type, log_level)
        if err_code != 0:
            return 400, err_msg
        else:
            return 200, 'ok'
    except Exception as e:
        return 400, str(e)
    finally:
        rpc.close()


# 获取clup_settings中的值
def get_clup_settings(req):
    params = {
        'page_num': csu_http.MANDATORY | csu_http.INT,
        'page_size': csu_http.MANDATORY | csu_http.INT,
        'filter': 0,
    }

    # 检查参数的合法性，如果成功，把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    try:
        where_cond = ' WHERE category >=10'
        if 'filter' in pdict:
            if pdict["filter"]:
                where_cond += ' AND key like %(filter)s'
        sql = f'SELECT count(*) AS cnt FROM clup_settings {where_cond}'
        rows = dbapi.query(sql, pdict)
        row_cnt = rows[0]['cnt']

        pdict['offset'] = (pdict['page_num'] - 1) * pdict['page_size']
        sql = f'SELECT * FROM clup_settings {where_cond}' \
            ' order by key' \
            ' offset %(offset)s limit %(page_size)s'
        rows = dbapi.query(sql, pdict)
    except Exception as e:
        return 400, str(e)

    ret_data = {"total": row_cnt, "page_size": pdict['page_size'], "rows": rows}
    row_data = json.dumps(ret_data)
    return 200, row_data


# 更新clup_settings设置
def update_clup_settings(req):
    params = {
        'key': csu_http.MANDATORY,
        'content': csu_http.MANDATORY,
    }
    # 检查参数的合法性，如果成功，把参数放到一个字典中
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict
    try:
        sql = "UPDATE clup_settings SET content=%(content)s WHERE key=%(key)s"
        dbapi.execute(sql, pdict)
    except Exception as e:
        return 400, str(e)
    config.set_key(pdict['key'], pdict['content'])

    return 200, 'Update success'


def get_pg_settings(req):
    """检查各版本的数据库默认参数
    """
    params = {
        'page_num': 0,
        'page_size': 0,
        'pg_version': 0,
        'filter': 0,
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # get all pg version are setted or not
    sql = "SELECT DISTINCT(pg_version), COUNT(*) FROM clup_pg_settings group by pg_version"
    rows = dbapi.query(sql)
    setted_dict = {
        10: False,
        11: False,
        12: False,
        13: False,
        14: False,
        15: False,
        16: False,
        17: False
    }
    for row in rows:
        setted_dict[row["pg_version"]] = True

    ret_dict = {
        "setted_info": setted_dict
    }
    # get follow version db infor
    try:
        if pdict.get("pg_version"):
            search_sql = "SELECT DISTINCT(db_id), host, pgdata, db_detail->>'version' as version FROM clup_db"

            where_cond = " WHERE SUBSTRING(db_detail->>'version', 1, POSITION('.' IN db_detail->>'version') - 1) = %(pg_version)s"
            if pdict.get("filter"):
                where_cond = f" {where_cond} AND cast(db_id AS varchar) like %(filter)s OR host like %(filter)s group by db_id"
            else:
                where_cond = f" {where_cond} group by db_id"

            # search result and pages set
            pdict['offset'] = (pdict['page_num'] - 1) * pdict['page_size']
            page_cond = " ORDER BY db_id OFFSET %(offset)s LIMIT %(page_size)s"
            rows = dbapi.query(f"{search_sql} {where_cond} {page_cond}", pdict)
            if not rows:
                return 400, f"There no database records were found for pg_version={pdict['pg_version']}."

            # just return the database which is running
            ret_dict["db_info_list"] = list()
            for row in rows:
                code, is_run = is_running(row["host"], row['pgdata'])
                if code != 0 or not is_run:
                    continue
                ret_dict["db_info_list"].append({"db_id": row["db_id"], "host": row["host"], "version": row["version"]})
            ret_dict["count"] = len(ret_dict["db_info_list"])
    except Exception as e:
        return 400, str(e)

    return 200, json.dumps(ret_dict)


def update_pg_settings(req):
    """更新数据库默认参数
    """
    params = {
        'db_id': csu_http.MANDATORY,
        'pg_version': csu_http.MANDATORY | csu_http.INT
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check and get the db infor
    sql = "SELECT host, pgdata, port, db_detail->>'version' as version FROM clup_db WHERE db_id = %s"
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if not rows:
        return 400, f"No records were found for this database(db_id={pdict['db_id']})."
    db_dict = rows[0]

    db_version = db_dict['version']
    major_version = int(db_version.split(".")[0])
    if major_version != int(pdict['pg_version']):
        return 400, f"The database(db_id={pdict['db_id']}) version is {db_version},which is not allow to set for {pdict['pg_version']}."

    # Delete the old settings
    delete_sql = "DELETE FROM clup_pg_settings WHERE EXISTS (SELECT * FROM clup_settings WHERE pg_version=%s)"
    dbapi.execute(delete_sql, (int(pdict['pg_version']), ))

    # Insert new settings
    code, result = get_all_settings(pdict['db_id'], {})
    if code != 0:
        return 400, f"Get the database(db_id={pdict['db_id']}) pg_settings failed, {result}."

    try:
        for setting_dict in result:
            need_del_keys = ["setting_type", "conf_setting", "take_effect", "conf_unit"]
            for key in need_del_keys:
                if key in setting_dict:
                    del setting_dict[key]
            setting_dict["pg_version"] = pdict["pg_version"]
            columns = ', '.join([key for key in setting_dict.keys()])
            values = ', '.join(['%s'] * len(setting_dict.keys()))
            inster_sql = f"INSERT INTO clup_pg_settings ({columns}) VALUES({values}) ON CONFLICT DO NOTHING"
            dbapi.execute(inster_sql, tuple(setting_dict.values()))
    except Exception as e:
        return 400, f"Update pg_settings for pg_version({pdict['pg_version']}) with unexpected error, {str(e)}."
    return 200, "Success"


def add_csu_package(req):
    """添加中启乘数提供的安装包

    Args:
        req (_type_): _description_

    Returns:
        _type_: _description_
    """
    params = {
        'package_name': csu_http.MANDATORY,
        'path': csu_http.MANDATORY,
        'file': csu_http.MANDATORY,
        'version': csu_http.MANDATORY,
        'settings': csu_http.MANDATORY,
        'conf_init': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check the packages is exists or not
    sql = "SELECT * FROM csu_packages WHERE package_name = %s and version = %s"
    rows = dbapi.query(sql, (pdict['package_name'], pdict['version']))
    if rows:
        return 400, f"The package (name={pdict['package_name']}, version={pdict['version']}) aready exists."

    # insert into csu_packages table
    pdict['settings'] = json.dumps(pdict['settings'])
    pdict['conf_init'] = json.dumps(pdict['conf_init'])
    sql = """INSERT INTO csu_packages(package_name, version, path, file, settings, conf_init)
        VALUES(%(package_name)s, %(version)s, %(path)s, %(file)s, %(settings)s::jsonb, %(conf_init)s::jsonb) RETURNING package_id
    """
    rows = dbapi.query(sql, pdict)
    if not rows:
        return 400, f"Execute sql({sql}) failed."

    return 200, "Success"


def install_csu_package(req):
    """安装中启乘数提供的一些软件包

    Args:
        req (_type_): _description_

    Returns:
        _type_: _description_
    """
    params = {
        'os_user': csu_http.MANDATORY,
        'package_id': csu_http.INT,
        'root_path': csu_http.MANDATORY,
        'host_list': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # search the package info
    sql = "SELECT * FROM csu_packages WHERE package_id = %s"
    rows = dbapi.query(sql, (pdict['package_id'], ))
    if not rows:
        return 400, f"Cant find any records for the package(id={pdict['package_id']})."
    package_info = dict(rows[0])

    # check the csu_package file is exists
    file_path = os.path.join(package_info['path'], package_info['file'])
    if not os.path.exists(file_path):
        return 400, f"The file({file_path}) is not exists."

    package_info['file_path'] = file_path
    package_info['os_user'] = pdict['os_user']
    package_info['root_path'] = pdict['root_path']

    # install packages
    task_name = f"install package({package_info['package_name'], package_info['version']})"
    task_id = general_task_mgr.create_task(
        task_type_def.INSTALL_PACKAGE, task_name,
        {'package_name': package_info['package_name'], "version": package_info['version']})
    general_task_mgr.run_task(task_id, long_term_task.task_install_csu_package, (package_info, pdict["host_list"]))

    ret_data = {"task_id": task_id, "task_name": task_name}
    raw_data = json.dumps(ret_data)
    return 200, raw_data


def get_csu_package_info(req):
    params = {
        "package_name": csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    where_cond = None
    if pdict['package_name'] != "":
        where_cond = "WHERE package_name like '{0}'".format(pdict['package_name'])
    sql = f"SELECT package_id, package_name, version, conf_init FROM csu_packages {where_cond}"
    rows = dbapi.query(sql)
    if not rows:
        return 400, f"Cant find any records for the package(name={pdict['package_name']})."

    ret_list = list()
    for row in rows:
        row['package'] = "{0}: v{1}".format(row['package_name'], row['version'])
        if 'zqpool' in row['package_name']:
            row['init_conf'] = zqpool_conf_sort(row['conf_init'])
        ret_list.append(dict(row))

    ret_data = {"total": len(ret_list), "rows": ret_list}
    return 200, json.dumps(ret_data)
