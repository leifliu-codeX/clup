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
@description: PostgreSQL数据库操作模块
"""

import copy
import json
import logging
import os
import re
import time
import traceback
from typing import Any, Dict, Tuple, Union, cast

import dao
import database_state
import db_encrypt
import dbapi
import general_task_mgr
import long_term_task
import pg_db_lib
import pg_utils
import probe_db
import rpc_utils
import task_type_def


def log_info(task_id, msg):
    logging.info(msg)
    general_task_mgr.log_info(task_id, msg)


def log_warn(task_id, msg):
    logging.warning(msg)
    general_task_mgr.log_warn(task_id, msg)


def log_error(task_id, msg):
    logging.warning(msg)
    general_task_mgr.log_error(task_id, msg)


def source_check(host, port, pgdata):
    """创建数据库前检查资源是否可用

    Args:
        db_info (_type_): {
            host:
            port:
            pgdata:
        }
    """
    # step1: check ip + port
    check_sql = "SELECT db_id FROM clup_db WHERE host=%s and port=%s"
    rows = dbapi.query(check_sql, (host, port))
    if rows:
        return -1, f"The port {port} in host {host} is aready uesd by db_id={rows[0]['db_id']}."
    # step2: check pgdata
    try:
        rpc = None
        # check is exists or not, if exists must be empty
        err_code, err_msg = rpc_utils.get_rpc_connect(host)
        if err_code != 0:
            return -1, f"Connect the host failed, {err_msg}."
        rpc = err_msg
        is_exists = rpc.os_path_exists(pgdata)
        if is_exists:
            # check is empty or not
            is_empty = rpc.dir_is_empty(pgdata)
            if not is_empty:
                return -1, f"The pgdata {pgdata} is not empty."
    except Exception:
        return -1, f"Check the source in host {host} with unexcept error, {traceback.format_exc()}."
    finally:
        if rpc:
            rpc.close()
    return 0, "Check is OK"


@rpc_utils.rpc_or_host
def check_plugs(rpc, pg_bin_path, plug_str):
    """Check the plugs is installed or not

    Args:
        rpc (_type_): _description_
        pg_bin_path (_type_): _description_
        plug_str (_type_): _description_

    Returns:
        _type_: _description_
    """
    if "'" in plug_str:
        plug_str = plug_str.strip("'")
    plug_list = plug_str.split(",")

    not_exists_list = list()
    for plug_name in plug_list:
        is_exists = False
        plug_name = plug_name.strip()
        # check plug.control file
        plug_ctl_file = f"{pg_bin_path}/../share/extension/{plug_name}.control"
        if rpc.os_path_exists(plug_ctl_file):
            is_exists = True
        else:
            plug_ctl_file = f"{pg_bin_path}/../share/postgresql/extension/{plug_name}.control"
            if rpc.os_path_exists(plug_ctl_file):
                is_exists = True

        # some plug not has control file(such as: auto_explain)
        if not is_exists:
            plug_so_file = f"{pg_bin_path}/../lib/{plug_name}.so"
            if not rpc.os_path_exists(plug_so_file):
                not_exists_list.append(plug_name)

    if not_exists_list:
        ret_msg = f"Some plugs not install: {','.join(not_exists_list)}."
        return -1, ret_msg

    return 0, ""


def create_db(pdict):
    """创建数据库

    Args:
        pdict (dict): 创建数据库的参数,以自带的方式传过来

    Returns:
        int: err_code
        str: err_msg
        int: task_id
    """

    try:
        instance_name = pdict.get('instance_name')
        db_state = database_state.CREATING  # 正在创建中

        setting_dict = pg_setting_list_to_dict(pdict['setting_list'])
        setting_dict['port'] = pdict['port']
        shared_preload_libraries = cast(str, setting_dict.get("shared_preload_libraries"))
        if "pg_stat_statements" not in shared_preload_libraries:
            return -1, 'Database needs pg_stat_statements plug-in, please fill in in shared_preload_libraries'

        host = pdict['host']
        rpc = None
        err_code, err_msg = rpc_utils.get_rpc_connect(host)
        if err_code != 0:
            dao.update_db_state(pdict['db_id'], database_state.FAULT)
            err_msg = f"Host connection failure({host}), please check service clup-agent is running: {err_msg}"
            return -1, err_msg
        rpc = err_msg
    except Exception:
        return -1, traceback.format_exc()

    pre_msg = "Check can create db"
    try:
        # 如果配置中配置了插件,但软件中没有此插件,则报错返回
        plug_str = setting_dict.get('shared_preload_libraries')
        plug_list = plug_str.replace("'", '').split(',')
        err_code = err_msg = ''
        pg_bin_path = pdict['pg_bin_path']
        for plug in plug_list:
            plug_ctl_file = f"{pg_bin_path}/../share/extension/{plug}.control"
            if not rpc.os_path_exists(plug_ctl_file):
                plug_ctl_file = f"{pg_bin_path}/../share/postgresql/extension/{plug}.control"
                if not rpc.os_path_exists(plug_ctl_file):
                    return -1, f"Plug-in({plug}) not installed!"

        pdict['db_detail'] = json.dumps(dict(
            os_user=pdict['os_user'], os_uid=pdict['os_uid'], db_user=pdict['db_user'], db_pass=pdict['db_pass'],
            instance_type=pdict['instance_type'], version=pdict['version'], pg_bin_path=pdict['pg_bin_path'], room_id='0'))
        pdict['is_primary'] = 1
        pdict['instance_name'] = instance_name
        pdict['db_state'] = db_state
        pdict['repl_app_name'] = pdict['host']
        pdict['repl_ip'] = pdict['host']
        # add repl_app_name, repl_ip
        sql = """INSERT INTO clup_db(state, pgdata, is_primary, repl_app_name, host, repl_ip,
        instance_name, db_detail, port, db_state, db_type, scores)
        VALUES(0, %(pgdata)s, %(is_primary)s, %(repl_app_name)s, %(host)s, %(repl_ip)s,
        %(instance_name)s, %(db_detail)s, %(port)s, %(db_state)s, %(db_type)s, 0)
        RETURNING db_id
        """
        rows = dbapi.query(sql, pdict)
        db_id = rows[0]['db_id']

        pre_msg = f"create_db(db_id={db_id})"

        pdict['db_id'] = db_id
        # pdict['instance_name'] = f"pg{db_id:09d}"
        pdict['setting_dict'] = setting_dict
        pdict['db_pass'] = db_encrypt.from_db_text(pdict['db_pass'])

        task_name = f"create_db(db={pdict['db_id']})"

        rpc_dict = {}
        rpc_dict.update(pdict)
        rpc_dict['task_name'] = task_name

        task_id = general_task_mgr.create_task(
            task_type=task_type_def.PG_CREATE_INSTANCE_TASK,
            task_name=task_name,
            task_data=rpc_dict
        )
        rpc_dict['task_id'] = task_id

        general_task_mgr.run_task(task_id, long_term_task.task_create_pg_db, (host, db_id, rpc_dict))
        return 0, task_id

    except Exception as e:
        dao.update_db_state(pdict['db_id'], database_state.CREATE_FAILD)
        err_msg = f"{pre_msg}: Database creation failure: unknown error {str(e)}"
        log_error(task_id, err_msg)
        general_task_mgr.complete_task(task_id, -1, err_msg)
        return -1, err_msg
    finally:
        if rpc:
            rpc.close()


def build_standby(pdict):
    """搭建备库

    Args:
        pdict (dict): 搭建数据库的参数

    Returns:
        int: err_code
        str: err_msg
        int: task_id
        int: db_id
    """
    err_code = 0
    err_msg = ''

    try:
        sql = f""" SELECT count(*) FROM clup_db WHERE host = '{pdict['host']}' AND port= {pdict['port']} """
        rows = dbapi.query(sql)
        if rows[0]['count'] > 0:
            return -1, f"Failed to create the database, The database on the host({pdict['host']}) has used the port({pdict['port']})"

        # 查询上级库的信息
        sql = "SELECT db_id,up_db_id,db_type, cluster_id, host, repl_app_name, repl_ip, port,pgdata,clup_cluster.state as state," \
            "db_detail->>'db_user' as db_user, db_detail->>'db_pass' as db_pass," \
            " db_detail->>'instance_type' as instance_type,"\
            " db_detail->'repl_ip' as repl_ip_in_detail, db_detail " \
            " FROM clup_db left join clup_cluster using (cluster_id) WHERE db_id = %s "
        rows = dbapi.query(sql, (pdict['up_db_id'], ))
        if len(rows) == 0:
            return -1, 'the primary database instance does not exist. Please try again'
        if rows[0]['cluster_id'] and rows[0]['state'] == 1:
            return -1, f"The primary database is in the cluster[cluster_id: {rows[0]['cluster_id']}]. Please take it offline before performing operations."
        # 更新上级库信息,添加repl_user、repl_pass
        update_dict = json.dumps({"repl_user": pdict['repl_user'], "repl_pass": pdict['repl_pass']})
        sql = "UPDATE clup_db SET db_detail = db_detail || (%s::jsonb) WHERE db_id = %s"
        dbapi.execute(sql, (update_dict, pdict['up_db_id']))

        up_db_dict = rows[0]
        err_code, err_msg = get_pg_setting_list(pdict['up_db_id'])
        if err_code != 0:
            return err_code, f"The configuration of the primary database could not be obtained: {err_msg}"
        up_db_dict['setting_list'] = err_msg

        # 检查上级主库中安装的插件,如果要搭建的备库的数据库目录中没有此插件,则报错返回
        setting_dict = pg_setting_list_to_dict(up_db_dict["setting_list"])
        plug_str = setting_dict.get('shared_preload_libraries', '')
        if plug_str:
            plug_str = plug_str.replace("'", '')
        if plug_str != '':
            plug_list = plug_str.split(',')
        else:
            plug_list = []
        pg_bin_path = pdict['pg_bin_path']
        err_code, err_msg = rpc_utils.get_rpc_connect(pdict["host"])
        if err_code != 0:
            err_msg = f"Cannot connect to the host({pdict['host']}), cannot verify whether the directory({pg_bin_path}) is PG BIN directory"
            logging.info(err_msg + f" *** {err_msg}")
            return -1, err_msg
        rpc = err_msg
        try:
            for plug in plug_list:
                plug_ctl_file = f"{pg_bin_path}/../share/extension/{plug}.control"
                if not rpc.os_path_exists(plug_ctl_file):
                    plug_ctl_file = f"{pg_bin_path}/../share/postgresql/extension/{plug}.control"
                    if not rpc.os_path_exists(plug_ctl_file):
                        return -1, f"Plug-in({plug}) not installed!"
        finally:
            rpc.close()

        unix_socket_directories = setting_dict.get('unix_socket_directories', '/tmp')
        cells = unix_socket_directories.split(',')
        unix_socket_dir = cells[0].strip()

        # db_dict存储往表clup_db中插入的数据
        db_dict = copy.copy(pdict)
        # db_detail放clup_db.db_detail字段的数据
        db_detail = {
            'os_user': pdict['os_user'],
            'os_uid': pdict['os_uid'],
            'db_user': up_db_dict['db_user'],
            'db_pass': up_db_dict['db_pass'],
            'instance_type': pdict['instance_type'],
            'repl_user': pdict['repl_user'],
            'repl_pass': pdict['repl_pass'],
            'version': pdict['version'],
            'pg_bin_path': pdict['pg_bin_path']
        }
        if pdict.get('delay'):
            db_detail['delay'] = pdict['delay']
        if pdict.get('tblspc_dir'):
            db_detail['tblspc_dir'] = pdict['tblspc_dir']

        db_dict['db_detail'] = json.dumps(db_detail)
        db_dict['repl_app_name'] = pdict['host']
        db_dict['up_db_host'] = up_db_dict['host']
        db_dict['up_db_repl_ip'] = up_db_dict['repl_ip_in_detail'] if up_db_dict['repl_ip_in_detail'] else up_db_dict['repl_ip']
        db_dict['up_db_port'] = up_db_dict['port']
        db_dict['cluster_id'] = up_db_dict['cluster_id']
        db_dict['db_type'] = up_db_dict["db_type"]
        db_dict['is_primary'] = 0
        db_dict['state'] = 1  # 注意这是HA的状态,不是数据库的状态
        if 'instance_name' not in pdict:
            db_dict['instance_name'] = ''
        db_dict['db_state'] = database_state.CREATING      # 数据库状态默认为创建中

        try:
            # 先插入数据库生成id
            sql = "INSERT INTO clup_db (cluster_id, state, pgdata, is_primary, repl_app_name, host, repl_ip, " \
                "instance_name, db_detail, port, db_state, up_db_id, scores, db_type) values " \
                "(%(cluster_id)s, %(state)s, %(pgdata)s, %(is_primary)s, %(repl_app_name)s, %(host)s, %(repl_ip)s, "\
                "%(instance_name)s, %(db_detail)s, %(port)s, %(db_state)s, %(up_db_id)s, 0, %(db_type)s) RETURNING db_id"
            rows = dbapi.query(sql, db_dict)
        except Exception as e:
            return -1, f'Failed to insert data into the table(clup_db): {str(e)}'
        if len(rows) == 0:
            return -1, 'Failed to insert data into the table(clup_db)'
        db_id = rows[0]['db_id']
        db_dict['db_id'] = db_id

        # rpc_dict 放下创建备库的调用的参数
        # rpc_name_list定义需要从db_dict中复制过来的数据
        rpc_name_list = [
            'up_db_id',       # 上级库id
            'up_db_host',     # 上级库host
            'up_db_port',     # 上级库端口
            'up_db_repl_ip',  # 上级库流复制ip
            'db_id',          # 本备库id
            'os_user',        # 操作系统用户
            'os_uid',         # 操作系统用户uid
            'db_user',        # 数据库超级用户名
            'port',           # 备库的端口
            'pg_bin_path',    # 数据库软件目录
            'repl_user',      # 流复制用于
            'repl_pass',      # 流复制密码
            'pgdata',         # 数据库的数据目录
            'repl_app_name',  # 流复制的application_name
            'delay',          # 延迟时间
            'instance_type',  # 实例类型：独立实例
            'cpu',            # CPU
            'version',        # 版本信息
            'tblspc_dir',     # 表空间的目录信息:  [{'old_dir': '', 'new_dir': ''}, {'old_dir': '', 'new_dir': ''}]
            'other_param',    # pg_basebackup的附加参数
            'is_exclusive',
            'cpu_num',
            'memory_size'
        ]

        rpc_dict = {}
        for k in rpc_name_list:
            rpc_dict[k] = db_dict.get(k)

        rpc_dict['unix_socket_dir'] = unix_socket_dir

        # # 数据库用户,当db_user禹os_user不相同是,需要在pg_hba.conf中加用户映射,否则本地无法误密码的登录数据库
        rpc_dict['db_user'] = up_db_dict['db_user']
        rpc_dict['repl_pass'] = db_encrypt.from_db_text(rpc_dict['repl_pass'])

        # 开始搭建备库
        task_name = f"build_standby(db={db_dict['host']}:{db_dict['port']})"
        rpc_dict['task_name'] = task_name
        # rpc_dict['task_key'] = task_name + str(db_dict['db_id'])

        task_id = general_task_mgr.create_task(
            task_type=task_type_def.PG_BUILD_STANDBY_TASK,
            task_name=task_name,
            task_data=rpc_dict
        )
        try:
            rpc_dict['task_id'] = task_id
            rpc_dict['pre_msg'] = f"Build standby(db_id={db_dict['db_id']})"
            # 开始搭备库
            pdict['repl_pass'] = db_encrypt.from_db_text(pdict['repl_pass'])
            host = db_dict['host']
            general_task_mgr.run_task(task_id, long_term_task.task_build_pg_standby, (host, db_id, rpc_dict))
            return 0, (task_id, db_id)
        except Exception as e:
            err_code = -1
            err_msg = str(e)
            general_task_mgr.complete_task(task_id, -1, err_msg)
            dao.update_db_state(db_dict['db_id'], database_state.CREATE_FAILD)
        return err_code, (task_id, db_id)
    except Exception:
        err_code = -1,
        err_msg = traceback.format_exc()
        dao.update_db_state(db_dict['db_id'], database_state.CREATE_FAILD)
        logging.error(f"Build standby unexpect error: {err_msg}")
        return err_code, err_msg


def change_up_db_by_db_id(db_id, up_db_id):
    """
    将db_id的上级库切换成up_db_id
    :param db_id:
    :param up_db_id:
    :return:
    """
    if up_db_id is None:
        # 这种情况是要切换主库
        # 注释掉set_primary,此函数不需要激活主库
        # return set_primary(db_id)
        return -1, 'up_db_id can not none for call change_up_db_by_db_id'

    # 查到更换上级主库所需参数,并修改recovery文件
    sql = "SELECT host,pgdata,db_detail->>'instance_type' AS instance_type, " \
          " db_detail->>'db_user' as db_user,  db_detail->>'db_pass' as db_pass, " \
          " db_detail->>'repl_user' AS repl_user, db_detail->>'repl_pass' AS repl_pass, " \
          " db_detail->>'version' as version, repl_app_name" \
          " FROM clup_db  WHERE db_id = %s"
    # 当前数据库的信息
    db_rows = dbapi.query(sql, (db_id, ))
    if len(db_rows) == 0:
        return -1, f'Database does not exist(db_id:{db_id})'
    row = db_rows[0]
    host = row['host']
    pgdata = row['pgdata']
    repl_user = row['repl_user']
    repl_pass = db_encrypt.from_db_text(row['repl_pass'])
    repl_app_name = row['repl_app_name']

    sql = "SELECT repl_ip as pri_host, port FROM clup_db WHERE db_id = %s"
    # 上一级主库需要的信息
    up_db_rows = dbapi.query(sql, (up_db_id, ))
    if len(up_db_rows) == 0:
        return -1, f'Database does not exist(db_id:{up_db_id})'

    row = up_db_rows[0]
    up_db_host = row['pri_host']
    up_db_port = row['port']

    err_code, err_msg = rpc_utils.get_rpc_connect(host, 2)
    if err_code != 0:
        return -1, f"Failed to connect to the agent({host})."
    rpc = err_msg
    try:
        err_code, err_msg = pg_db_lib.pg_change_standby_updb(rpc, pgdata, repl_user, repl_pass, repl_app_name, up_db_host, up_db_port)
    finally:
        rpc.close()
    if err_code != 0:
        return -1, f'Failed to modify: {err_msg}'
    # 更新数据库
    dao.update_up_db_id(up_db_id, db_id, 0)
    return 0, ''


def sr_test_can_switch(old_pri_db, new_pri_db):
    """检查备库是否落后主库太多,如果备库需要的WAL已经不再主库上了,则不能切换
    Args:
        old_pri_db ([type]): [description]
        new_pri_db ([type]): [description]

    Returns:
        [type]: [description]
    """

    try:
        repl_pass = db_encrypt.from_db_text(new_pri_db['repl_pass'])
        err_code, err_msg, new_pri_last_wal_file = probe_db.get_last_wal_file(
            new_pri_db['repl_ip'], new_pri_db['port'], new_pri_db['repl_user'], repl_pass)

        if err_code != 0:
            err_msg = f"get new pirmary({new_pri_db['host']}) last wal file failed: {err_msg}"
            return err_code, err_msg

        # err_code, str_ver = rpc_utils.pg_version(old_pri_db['host'], old_pri_db['pgdata'])
        err_code, str_ver = pg_db_lib.pgdata_version(old_pri_db['host'], old_pri_db['pgdata'])
        if err_code != 0:
            err_msg = f"get pg version error: {str_ver}"
            return err_code, err_msg
        pg_major_int_version = int(str(str_ver).split('.')[0])
        if pg_major_int_version >= 10:
            wal_dir = 'pg_wal'
        else:
            wal_dir = 'pg_xlog'
        xlog_file_full_name = os.path.join(old_pri_db['pgdata'], wal_dir, new_pri_last_wal_file)
        err_code, is_exists = rpc_utils.os_path_exists(old_pri_db['host'], xlog_file_full_name)
        if err_code != 0:
            err_msg = f"call rpc os_path_exists({old_pri_db['host']}, {xlog_file_full_name}) failed when find last wal file in " \
                      f"original primary({old_pri_db['host']})," \
                      f"so it can not became primary: {is_exists}"
            return err_code, err_msg

        if not is_exists:
            err_msg = f"new pirmary({new_pri_db['host']}) last wal file({xlog_file_full_name}) not exists in original primary({old_pri_db['host']}), " \
                      "so it can not became primary!"
            return 1, err_msg
        return 0, ''
    except Exception:
        err_msg = f"unexpect error occurred: {traceback.format_exc()}"
        return -1, err_msg


def task_log_info(task_id, msg):
    if task_id is not None:
        general_task_mgr.log_info(task_id, msg)


def task_log_error(task_id, msg):
    if task_id is not None:
        general_task_mgr.log_info(task_id, msg)


def switch_over_db(old_pri_db, new_pri_db, task_id, pre_msg):
    """
    将两个数据库的主备关系互换
    """
    # 步骤1,先把原主库停掉
    try:
        task_log_info(task_id, f"{pre_msg}: begin stopping current primary database({old_pri_db['host']})...")
        err_code, err_msg = pg_db_lib.stop(old_pri_db['host'], old_pri_db['pgdata'], 30)  # 停止数据库等待的时间为
        if err_code != 0:
            err_msg = f"current primary database({old_pri_db['host']}) can not be stopped: {err_msg}"
            task_log_error(task_id, f"{pre_msg}: {err_msg}")
            return -1, err_msg
        task_log_info(task_id, f"{pre_msg}: current primary database({old_pri_db['host']}) stopped.")

        err_code, err_msg = sr_test_can_switch(old_pri_db, new_pri_db)
        if err_code != 0:
            task_log_error(task_id, f"{pre_msg}: {err_msg}")
            # 出现错误,开始回滚前面的操作
            task_log_info(task_id, f"{pre_msg}: switch failed, start the original primary database({old_pri_db['host']}).")
            pg_db_lib.start(old_pri_db['host'], old_pri_db['pgdata'])
            task_log_info(task_id, f"{pre_msg}: the original primary database({old_pri_db['host']}) is started.")
            return err_code, err_msg

        # 先把新主库关掉,然后把旧主库上比较新的xlog文件都拷贝过来：
        task_log_info(task_id, f'{pre_msg}: stop new pirmary database then sync wal from old primary ...')
        # 在rpc.pg_cp_delay_wal_from_pri中 会把新主库给先停掉
        err_code, err_msg = rpc_utils.pg_cp_delay_wal_from_pri(
            new_pri_db['host'],
            old_pri_db['host'],
            old_pri_db['pgdata'],
            new_pri_db['pgdata']
        )

        if err_code != 0:
            err_msg = f"stop new pirmary database then sync wal from old primary failed: {err_msg}"
            task_log_error(task_id, f"{pre_msg}: {err_msg}")
            return err_code, err_msg

        task_log_info(task_id, f'{pre_msg}: stop new pirmary database then sync wal from old primary finished')

        # 再重新启动新主库(目前还处于只读standby模式)
        task_log_info(task_id, f'{pre_msg}: restart new pirmary database and wait it is ready ...')
        err_code, err_msg = pg_db_lib.start(new_pri_db['host'], new_pri_db['pgdata'])
        if err_code != 0:
            err_msg = f"start new primary failed: {err_msg}"
            task_log_error(task_id, f"{pre_msg}: {err_msg}")
            return -1, err_msg

        # 等待新主库滚日志到最新
        task_log_info(task_id, f'{pre_msg}: wait new pirmary to be started and is ready to accept new connection ...')
        while True:
            err_code, err_msg = pg_db_lib.is_ready(new_pri_db['host'], new_pri_db['pgdata'], new_pri_db['port'])
            if err_code == 0:
                break
            elif err_code == 1:
                task_log_info(task_id, f"{pre_msg}: Check is ready, {err_msg}")
                time.sleep(1)
                continue
            else:
                task_log_error(task_id, f"{pre_msg}: Check is ready, {err_msg}")
                return -1, err_msg
        task_log_info(task_id, f'{pre_msg}: new pirmary database started and it is ready.')

        # 需要把其旧主库转换成备库模式,并让其指向新的主库
        log_info(task_id, f"{pre_msg}: change old primary database to standby and change upper level database to new primary...")
        change_up_db_by_db_id(old_pri_db['db_id'], new_pri_db['db_id'])
        # 更新数据库存的上级主库
        # dao.update_up_db_id('null', new_pri_db['db_id'], 1)

        # 修改数据库配配置：把新主库的上级库设置为NULL,is_primary设置为1
        dao.update_up_db_id('NULL', new_pri_db['db_id'], 1)
        # 修改数据库配配置：把旧主库的上级库设置新主库,is_primary设置为0
        dao.update_up_db_id(new_pri_db['db_id'], old_pri_db['db_id'], 0)

        # 把选中的这个新主库（目前处于备库状态）激活成主库
        task_log_info(task_id, f'{pre_msg}: promote new primary ...')
        err_code, err_msg = pg_db_lib.promote(new_pri_db['host'], new_pri_db['pgdata'])
        if err_code != 0:
            err_msg = f"{pre_msg}: promote failed: {str(err_msg)} "
            task_log_error(task_id, f"{pre_msg}: {err_msg}")
            return err_code, err_msg
        task_log_info(task_id, f'{pre_msg}: promote new primary completed.')

        task_log_info(task_id, f"{pre_msg}: start old primary database ...")
        err_code, err_msg = pg_db_lib.start(old_pri_db["host"], old_pri_db["pgdata"])
        if err_code < 0:
            err_msg = f"start the old primary database failed, {err_msg}."
            task_log_error(task_id, err_msg)
            return -1, err_msg
        task_log_info(task_id, f"{pre_msg}: start old primary database completed.")
        return 0, ''
    except Exception:
        err_msg = f"unexpect error occurred: {traceback.format_exc()}"
        return -1, err_msg


def renew_pg_bin_info(db_id) -> Tuple[int, str, dict]:
    """
    更新PG数据库中与PG软件和操作系统相关的信息,如版本、os_user、os_uid、pg_bin_path等信息
    """

    sql = (
        "SELECT db_id, up_db_id, cluster_id, scores, state, pgdata, is_primary, repl_app_name, host, repl_ip, port, "
        " db_detail->>'instance_type' AS instance_type, db_detail->>'db_user' as db_user,"
        " db_detail->>'os_user' as os_user, db_detail->>'os_uid' as os_uid, "
        " db_detail->>'pg_bin_path' as pg_bin_path, db_detail->>'version' as version, "
        " db_detail->>'db_pass' as db_pass, db_detail->'room_id' as room_id  "
        f" FROM clup_db WHERE db_id={db_id}")

    rows = dbapi.query(sql)
    if len(rows) == 0:
        return -10, f'Database(db_id: {db_id}) does not exist, please refresh and try again.', {}
    db = rows[0]

    err_code, err_msg = rpc_utils.get_rpc_connect(db['host'])
    if err_code != 0:
        return err_code, err_msg, {}
    rpc = err_msg
    renew_dict = {}
    try:
        # 读取pgdata目录的属主
        pgdata = db['pgdata']
        err_code, err_msg = rpc.os_stat(pgdata)
        if err_code != 0:
            err_msg = f"get file({pgdata}) stat failed: {err_msg}"
            return err_code, err_msg, {}
        st_dict = err_msg
        os_uid = st_dict['st_uid']
        # 根据os_uid获得用户名称
        err_code, err_msg = rpc.pwd_getpwuid(os_uid)
        if err_code != 0:
            err_msg = f"get username by uid({os_uid}) failed: {err_msg}"
            return err_code, err_msg, {}
        pw_dict = err_msg
        os_user = pw_dict['pw_name']
        renew_dict['os_user'] = os_user
        renew_dict['os_uid'] = os_uid

        # if not db['pg_bin_path']:  # 旧版本没有此字段,其他情况也可能没有这个字段
        # 先看看数据库是否运行,如果数据库正在运行,使用正在运行的程序的pid获得程序路径,否则使用which postgres去获得
        pg_pid_file = f"{pgdata}/postmaster.pid"
        pg_bin_path = None
        err_code, err_msg = rpc.file_read(pg_pid_file)
        if err_code == 0:
            content = err_msg
            cells = content.split('\n')
            pg_master_pid = cells[0].strip()
            proc_pid_exe_file = f'/proc/{pg_master_pid}/exe'
            err_code, err_msg = rpc.os_readlink(proc_pid_exe_file)
            if err_code == 0:
                pg_bin_file = err_msg
                pg_bin_path = os.path.dirname(pg_bin_file)
        if not pg_bin_path:
            cmd = f"su - {os_user} -c 'which postgres'"
            err_code, err_msg, out_msg = rpc.run_cmd_result(cmd)
            if err_code != 0:
                return err_code, err_msg, {}
            out_msg = out_msg.strip()
            pg_bin_path = os.path.dirname(out_msg)
        if pg_bin_path:
            renew_dict['pg_bin_path'] = pg_bin_path
        # else:
        #     pg_bin_path = db['pg_bin_path']
        err_code, err_msg = pg_db_lib.get_pg_bin_version(rpc, pg_bin_path)
        if err_code != 0:
            return err_code, err_msg, {}
        version = err_msg
        renew_dict['version'] = version
    finally:
        rpc.close()
    sql = "UPDATE clup_db set db_detail = db_detail || (%s::jsonb) WHERE db_id=%s"
    dbapi.execute(sql, (json.dumps(renew_dict), db_id))
    db.update(renew_dict)
    return 0, '', db


def get_db_params(up_db_id, standby_id):
    primary = dao.get_db_info(up_db_id)
    standby = dao.get_db_info(standby_id)
    if not primary:
        return -1, f'Failed to obtain database({up_db_id}) information.'
    if not standby:
        return -1, f'Failed to obtain database({standby_id}) information.'
    standby = standby[0]
    primary = primary[0]

    pdict = {
        "host": standby['host'],
        "os_user": standby['os_user'] if standby['os_user'] else 'postgres',
        "os_uid": standby['os_uid'] if standby['os_uid'] else 701,
        "pg_bin_path": standby['pg_bin_path'],
        "db_user": standby['db_user'],
        "up_db_host": primary['host'],
        "up_db_port": primary['port'],
        "up_db_repl_ip": primary['repl_ip'],
        "repl_user": standby['repl_user'],
        "repl_pass": db_encrypt.from_db_text(standby['repl_pass']),
        "pgdata": standby['pgdata'],
        "repl_ip": standby['repl_ip'],
        "repl_app_name": standby['repl_app_name'],
        "instance_type": standby['instance_type'],
        "up_db_id": up_db_id,
        "standby_id": standby_id,
        "tblspc_dir": standby['tblspc_dir'],
        "cpu": standby.get('cpu'),
        "db_name": "template1"
    }
    if not primary['version']:
        err_code, err_msg, renew_dict = renew_pg_bin_info(up_db_id)
        if err_code != 0:
            return err_code, err_msg
        pdict['version'] = renew_dict['version']
    return 0, pdict


def pg_setting_list_to_dict(setting_list) -> Dict[Any, Any]:
    setting_dict = dict()
    for conf in setting_list:
        sql = "SELECT setting_type FROM clup_init_db_conf WHERE setting_name=%s"
        rows = dbapi.query(sql, (conf['setting_name'], ))
        if rows:
            setting_type = rows[0]['setting_type']
        else:
            setting_type = 1

        if setting_type in {3, 4}:
            # 带有单位的配置值
            if 'unit' not in conf:
                if setting_type == 4:
                    conf['unit'] = 'ms'
                else:
                    conf['unit'] = ''
            if setting_type == 3:
                if conf['unit'] == 'B':
                    conf['unit'] = ''
            setting_dict[conf['setting_name']] = str(conf['val']) + str(conf['unit'])
        elif setting_type == 6:
            # 需要加引号的配置
            setting_dict[conf['setting_name']] = f"\'{conf['val']}\'"
        else:
            # 常见类型(1)和布尔类型(2)和enum类型(5)
            setting_dict[conf['setting_name']] = conf['val']

    return setting_dict


def modify_setting_list(setting_list, pdict):
    # setting_list: [{"setting_name": "s", "val": 11}, {}]
    if not setting_list:
        setting_list = []
    for s in setting_list:
        if s['setting_name'] in pdict:
            s['val'] = pdict[s['setting_name']]
            del pdict[s['setting_name']]
    setting_list.extend([{"setting_name": k, "val": v} for k, v in pdict.items()])

    return setting_list


def get_db_conn(db_id) -> Tuple[int, str, Union[Any, None]]:
    """
    通过db_id 获取连接
    """
    sql = "SELECT host as host, port as port, db_detail->'db_user' as db_user," \
          "db_detail->'db_pass' as db_pass  FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (db_id,))
    if len(rows) == 0:
        return -1, f"The instance(db_id={db_id}) does not exist.", None
    db_dict = rows[0]
    db_dict['db_name'] = 'template1'
    try:
        err_code, err_msg, conn = dao.get_db_conn(db_dict)
        if err_code != 0:
            return -1, f"Failed to connect to the database(host={db_dict['host']}, port={db_dict['port']}): {err_msg}", None
    except Exception as e:
        return -1, f'Failed to connect to the database: {str(e)}.', None
    return 0, '', conn


def check_sr_conn(db_id, up_db_id, repl_app_name=None) -> Tuple[int, str, dict]:
    """
    检查流复制连接, 如果传了repl_app_name参数就不需要再去查询了
    @param db_id:
    @param up_db_id:
    @param repl_app_name:
    @return:
    """
    application_name = repl_app_name
    if not repl_app_name:
        db = dao.get_db_info(db_id)
        if not db and not repl_app_name:
            return -1, f'No database(db_id={db_id}) information found', {}
        application_name = db[0]['repl_app_name']
    try:
        err_code, err_msg, conn = get_db_conn(up_db_id)
        if err_code != 0:
            return err_code, f'Failed to obtain the database connection: {err_msg}', {}
        sql = "SELECT count(*) AS cnt  FROM pg_stat_replication WHERE application_name=%s AND state='streaming'"
        rows = dao.sql_query(conn, sql, (application_name, ))

    except Exception as e:
        return -1, repr(e), {}
    return 0, '', rows[0]


def check_auto_conf(host, pgdata, item_list):
    """
    host, pgdata, item_dict
    """
    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        return -1, err_msg

    rpc = err_msg
    try:
        auto_conf = f'{pgdata}/postgresql.auto.conf'
        err_code, item_dict = rpc.read_config_file_items(auto_conf, item_list)
        if err_code != 0:
            return err_code, item_dict
    finally:
        rpc.close()
    return 0, item_dict


def alter_system_conf(db_id, k, v):
    try:
        db_dict = dao.get_db_conn_info(db_id)
    except Exception as e:
        return -1, str(e)
    err_code, err_msg, conn = dao.get_db_conn(db_dict)
    if err_code != 0:
        return err_code, err_msg

    try:
        sql = f"""ALTER SYSTEM SET {k}="{v}" """
        dao.execute(conn, sql)
    except Exception as e:
        return -1, str(e)
    finally:
        conn.close()
    return 0, ""


def psql_test(db_id, sql):
    """
    db_dict: {
    host
    port
    db_user
    db_pass
    sql    }
    """
    db_dict = dao.get_db_conn_info(db_id)
    if not db_dict:
        return -1, f'No information was found for database {db_id}'
    err_code, err_msg, conn = dao.get_db_conn(db_dict)
    if err_code != 0:
        return -1, f"CONN_ERROR: cant connect the database, maybe is not started: {err_msg}"
    try:
        rows = dao.sql_query(conn, sql)
    except Exception as e:
        return -1, "SQL_ERROR: " + str(e)
    finally:
        conn.close()
    return 0, rows


def get_pg_tblspc_dir(db_id):
    db_dict = dao.get_db_conn_info(db_id)
    table_space = []
    err_code, _err_msg, conn = dao.get_db_conn(db_dict)
    if err_code != 0:
        return []
    try:
        sql = "SELECT spcname AS name, pg_catalog.pg_tablespace_location(oid) AS location FROM pg_catalog.pg_tablespace where spcname not in ('pg_default', 'pg_global');"
        table_space = dao.sql_query(conn, sql)
    except Exception as e:
        logging.error(f'get primary db info error: {repr(e)}')
    finally:
        conn.close()
    tblspc_dir = []
    for space in table_space:
        tblspc_dir.append({'old_dir': space['location'], 'new_dir': space['location']})
    return tblspc_dir


def get_pg_setting_name_type_dict():
    name_type_dict = dict()
    sql = "SELECT setting_name,setting_type FROM clup_init_db_conf"
    rows = dbapi.query(sql)
    for row in rows:
        name_type_dict[row['setting_name']] = row['setting_type']
    return name_type_dict


def get_pg_setting_item_val(item):
    val = item['val']
    if isinstance(val, str):
        val = val.strip("'")
    unit = item.get("unit", "")

    if unit == '':
        return val
    elif unit == 'B':
        return int(val)
    elif unit == 'kB':
        return 1024 * int(val)
    elif unit == 'MB':
        return 1024 * 1024 * int(val)
    elif unit == 'GB':
        return 1024 * 1024 * 1024 * int(val)
    elif unit == 'TB':
        return 1024 * 1024 * 1024 * 1024 * int(val)
    elif unit == 's':
        return 1000 * int(val)
    elif unit == 'ms':
        return int(val)
    elif unit == 'min':
        return 60 * 1000 * int(val)
    elif unit == 'h':
        return 60 * 60 * 1000 * int(val)
    elif unit == 'd':
        return 3600 * 24 * 1000 * int(val)


def get_all_settings(db_id, condition_dict=None, pg_version=None) -> Tuple[int, str, list]:
    """
    读取数据库所有的参数,优先级:postgresql.auto.conf > postgresql.conf > pg_settings
    pg_version(int | None): 如果数据库处于停止状态，则查询clup_pg_settings表
    """
    if condition_dict is None:
        condition_dict = {}

    sql = "SELECT host, pgdata FROM clup_db WHERE db_id = %s"
    rows = dbapi.query(sql, (db_id, ))
    if not rows:
        return -1, f'No database(db_id: {db_id}) information found', []
    err_code, err_msg = rpc_utils.get_rpc_connect(rows[0]['host'])
    if err_code != 0:
        return -1, f'agent connection failure: {err_msg}', []
    rpc = err_msg
    try:
        # sql = "select category, name, setting, unit, vartype, context, enumvals, min_val, max_val, short_desc, extra_desc, pending_restart from pg_settings where true "

        # if no show, filter settings which is not change
        where_cond = " sourcefile is not null " if condition_dict.get("no_show", 0) else " true "
        if "no_show" in condition_dict:
            del condition_dict["no_show"]

        args = list()
        filter_cond = ""
        if condition_dict:
            for key, value in condition_dict.items():
                if value:
                    filter_cond += f" and {key} like %s"
                    args.append(value)

        # if db is not running, select from clup_pg_settings
        if pg_version:
            sql = "SELECT category, name, setting, unit, vartype, context, enumvals, min_val, " \
                f"max_val, short_desc, extra_desc, pending_restart FROM clup_pg_settings WHERE pg_version = {pg_version} AND {where_cond}"
            setting_rows = dbapi.query(f"{sql} {filter_cond}", tuple(args))
            if not setting_rows:
                return -1, f"No records were found from clup_pg_settings for pg_version={pg_version}, please update it before use.", []
        else:
            # if db is running, connect db and select from pg_settings
            sql = f"SELECT * FROM pg_settings WHERE {where_cond} "
            db_dict = dao.get_db_conn_info(db_id)
            err_code, err_msg, conn = dao.get_db_conn(db_dict)
            if err_code != 0:
                return err_code, err_msg, []
            try:
                setting_rows = dao.sql_query(conn, f"{sql} {filter_cond}", tuple(args))
            except Exception:
                return -1, traceback.format_exc(), []
            finally:
                conn.close()

        pgdata = rows[0]['pgdata']
        conf_file = pgdata + '/postgresql.conf'
        pg_auto_conf_file = pgdata + '/postgresql.auto.conf'

        # 取出所有配置项,这里的配置值是默认值
        all_conf_list = [dict(row) for row in setting_rows]
        conf_list = [cnf['name'] for cnf in all_conf_list]
        conf_file = pgdata + '/postgresql.conf'
        pg_auto_conf_file = pgdata + '/postgresql.auto.conf'
        # 读取配置文件中的配置
        err_code, data = rpc.read_config_file_items(conf_file, conf_list)
        if err_code != 0:
            return -1, data, []
        is_exists = rpc.os_path_exists(pg_auto_conf_file)
        auto_data = None
        if is_exists:
            err_code, err_msg = rpc.read_config_file_items(pg_auto_conf_file, conf_list)
            if err_code != 0:
                return -1, err_msg, []
            auto_data = err_msg
        # postgresql.auto.conf中的优先级高,用postgresql.auto.conf覆盖postgresql.conf中的相同配置项
        if auto_data:
            data.update(auto_data)
        # 配置格式处理
        for setting_name in data:
            if not isinstance(data[setting_name], str):  # 如果已经不是字符串,就不要处理了。
                continue
            # 去掉前后的单引号
            if len(data[setting_name]) >= 1:
                if data[setting_name][0] == "'":
                    data[setting_name] = data[setting_name][1:]
            if len(data[setting_name]) >= 1:
                if data[setting_name][-1] == "'":
                    data[setting_name] = data[setting_name][:-1]
        # 未做配置或配置为空的取默认值
        for conf in all_conf_list:
            # 判断配置类型setting_type
            if conf['unit']:
                if conf['unit'] in {'s', 'ms', 'min', 'h', 'd'}:
                    conf['setting_type'] = 4
                    conf['setting'] = int(conf['setting']) if conf['setting'].isdigit() else conf['setting']
                elif conf['unit'] in {'B', 'KB', '8kB', 'kB', 'MB', 'GB', 'TB'}:
                    conf['setting_type'] = 3
                    conf['setting'] = int(conf['setting']) if conf['setting'].isdigit() else conf['setting']
                    # if conf['unit'] == '8kB':
                    #     conf['setting'] = int(conf['setting']) * 8 if conf['setting'].isdigit() else conf['setting']
                    #     conf['unit'] = 'kB'
                    #     conf['min_val'] = str(int(conf['min_val']) * 8)
                    #     conf['max_val'] = str(int(conf['max_val']) * 8)
                    # else:
                    #     conf['setting'] = int(conf['setting']) if conf['setting'].isdigit() else conf['setting']
                else:
                    # 有单位但类型未知归为类型6
                    conf['setting_type'] = 6
            elif conf['vartype'] == 'enum':
                conf['setting_type'] = 5
            elif conf['vartype'] == 'bool':
                conf['setting_type'] = 2
            elif conf['vartype'] == 'string':
                conf['setting_type'] = 6
                # real和integer归为类型1
            elif conf['vartype'] == 'integer':
                conf['setting'] = int(conf['setting'])
                conf['setting_type'] = 1
            elif conf['vartype'] == 'real':
                conf['setting'] = float(conf['setting'])
                conf['setting_type'] = 1
            else:
                conf['setting_type'] = 1

            # 获取到的conf文件配置值装入列表
            conf_name = conf['name']
            if conf_name in data:
                conf['conf_setting'] = data[conf_name]
                conf['conf_unit'] = ''
                # -------对配置参数是否生效进行检查,对比配置文件和数据库pg_settings表数值、单位进行判断-------
                # 因为关联性配置导致取值disabled的或者配置文件未配置视为已生效
                if conf['setting'] == '(disabled)' or not data[conf_name]:
                    conf['take_effect'] = 1
                elif conf['unit'] in {'s', 'ms', 'min', 'h', 'd'}:
                    conf_value = pg_utils.get_time_with_unit(conf['setting'], conf['unit'])
                    unit = ''.join([i for i in data[conf_name] if i.isalpha()])
                    val = data[conf_name].replace(unit, '')
                    val = val if val else 0
                    unit = unit if unit else conf['unit']
                    data_value = pg_utils.get_time_with_unit(val, unit)
                    if data_value == conf_value:
                        conf['take_effect'] = 1
                    else:
                        conf['take_effect'] = 0
                    conf['conf_setting'] = val
                    conf['conf_unit'] = unit
                    conf['min_val'] = pg_utils.get_time_with_unit(conf['min_val'], conf['unit'])
                    conf['max_val'] = pg_utils.get_time_with_unit(conf['max_val'], conf['unit'])
                elif conf['unit'] in {'B', 'KB', '8kB', 'kB', 'MB', 'GB', 'TB'}:
                    conf_value = pg_utils.get_val_with_unit(conf['setting'], conf['unit'])
                    unit = ''.join([i for i in data[conf_name] if i.isalpha()])
                    val = data[conf_name].replace(unit, '')
                    val = val if val else 0
                    unit = unit if unit else conf['unit']
                    data_value = pg_utils.get_val_with_unit(val, unit)
                    if conf['setting'] == pg_utils.fomart_by_unit(data_value, conf['unit']):
                        conf['take_effect'] = 1
                    else:
                        conf['take_effect'] = 0
                    conf['conf_setting'] = val
                    conf['conf_unit'] = unit
                    conf['min_val'] = pg_utils.get_val_with_unit(conf['min_val'], conf['unit'])
                    conf['max_val'] = pg_utils.get_val_with_unit(conf['max_val'], conf['unit'])
                elif conf['vartype'] == 'integer':
                    if int(conf['setting']) == int(data[conf_name]):
                        conf['take_effect'] = 1
                    else:
                        conf['take_effect'] = 0
                elif conf['vartype'] == 'real':
                    if float(conf['setting']) == float(data[conf_name]):
                        conf['take_effect'] = 1
                    else:
                        conf['take_effect'] = 0
                elif str(conf['setting']) == str(data[conf_name]):
                    conf['take_effect'] = 1
                else:
                    conf['take_effect'] = 0
            else:
                conf['conf_setting'] = ''
                conf['take_effect'] = 1
            # 需要重启的参数判断生效
            # if conf['pending_restart']:
            #     conf['take_effect'] = 0
        return 0, '', all_conf_list
    except Exception:
        err_msg = traceback.format_exc()
        return -1, err_msg, []
    finally:
        rpc.close()


def modify_db_conf(pdict):
    """
    修改一条pg_settings配置,并同步修改postgresql.auto.conf,postgresql.conf文件
    """
    # 修改的配置信息
    db_id = pdict['db_id']
    setting_name = pdict['setting_name']
    setting_value = pdict['setting_value']
    setting_unit = pdict['setting_unit'] if pdict['setting_unit'] else ''
    is_reload = pdict['is_reload']
    try:
        # pg_settings表部分数据不能直接修改,在配置文件修改后重启自动同步到表内
        sql = "SELECT host, port, pgdata, db_detail->'instance_type' as instance_type  FROM clup_db WHERE db_id = %s"
        rows = dbapi.query(sql, (db_id, ))
        if not rows:
            return -1, f'No database(db_id: {db_id}) information found'
        err_code, err_msg = rpc_utils.get_rpc_connect(rows[0]['host'])
        if err_code != 0:
            return -1, f'agent connection failure: {err_msg}'
        rpc = err_msg
        # 连接目标库查询设置
        db_dict = rows[0]

        # 获取原有配置
        err_code, err_msg = get_pg_setting_list(pdict['db_id'], arg_setting_name=setting_name)
        if err_code != 0:
            return -1, f'The original configuration of the database({pdict["db_id"]}) cannot be obtained.error: {err_msg}'

        pre_setting = err_msg[0]
        if pre_setting.get("is_string"):
            setting_dict = {setting_name: f"'{setting_value}'"}
        else:
            setting_dict = {setting_name: f"{setting_value}{setting_unit}"}

        # 如果是shared_preload_libraries配置项必须包含这个插件
        if setting_name == 'shared_preload_libraries' and "pg_stat_statements" not in setting_value:
            return -1, f'Database({pdict["db_id"]}) needs pg_stat_statements plug, please fill it in the shared_preload_libraries.'

        # 修改配置文件配置数据
        auto_flag = False
        if pre_setting.get("is_in_auto_conf"):
            auto_flag = True
        err_code, err_msg = pg_db_lib.modify_pg_conf(rpc, db_dict['pgdata'], setting_dict, is_pg_auto_conf=auto_flag)
        if err_code != 0:
            return -1, err_msg

        # reload
        if is_reload:
            pg_db_lib.reload(db_dict['host'], db_dict['pgdata'])

        return 0, 'Configuration modification succeeded'
    except Exception as e:
        return -1, str(e)
    finally:
        rpc.close()


def get_pg_setting_list(db_id, fill_up_default=False, arg_setting_name=None):
    """
    读取数据库配置参数,读取postgresql.conf和postgresql.auto.conf中的配置项目
    @param db_id:
    @param fill_up_default: 如果配置文件中无此项,是否填充clup的默认值
    @return:
    """
    try:
        sql = "SELECT host, pgdata FROM clup_db WHERE db_id = %s"
        rows = dbapi.query(sql, (db_id, ))
        if not rows:
            return -1, f'No database(db_id: {db_id}) information found'
        err_code, err_msg = rpc_utils.get_rpc_connect(rows[0]['host'])
        if err_code != 0:
            return -1, f'agent connection failure: {err_msg}'
        rpc = err_msg
        try:
            pgdata = rows[0]['pgdata']
            conf_file = pgdata + '/postgresql.conf'
            pg_auto_conf_file = pgdata + '/postgresql.auto.conf'

            where_cond = ""
            if arg_setting_name:
                where_cond = f" WHERE setting_name='{arg_setting_name}'"
            sql = f"SELECT setting_name, setting_type, val, unit, common_level FROM clup_init_db_conf {where_cond}"
            rows = dbapi.query(sql)
            if not rows and arg_setting_name:
                # 有些参数在clup_init_db_conf中可能没有,那就在pg_settings中查
                sql = f"SELECT name, setting, unit, vartype FROM pg_settings WHERE name = '{arg_setting_name}'"
                # 暂时先按照csumdb(PG12)的版本为准,理论上应该查询指定的数据库
                # result = dbapi.query(sql)

                # 改为查询当前库，连接目标库查询设置
                db_dict = dao.get_db_conn_info(db_id)
                err_code, err_msg, conn = dao.get_db_conn(db_dict)
                if err_code != 0:
                    return err_code, err_msg
                try:
                    result = dao.sql_query(conn, sql)
                except Exception:
                    return -1, traceback.format_exc()
                finally:
                    conn.close()
                setting_type_dict = dict()
                if result:
                    setting_type_dict = {
                        "bool": 2,
                        "enum": 5,
                        "integer": 3,
                        "real": 4,
                        "string": 6
                    }
                    result_dict = dict(result[0])
                    # 如果是integer且没有单位,则为无单位普通数字类型
                    if result_dict["vartype"] == 'integer' and not result_dict.get("unit"):
                        setting_type_dict["integer"] = 1

                    # 如果是字符串, 读取的值是不带单引号的,这里添加上,方便后面处理
                    setting_value = result_dict["setting"]
                    if result_dict["vartype"] == 'string':
                        result_dict["setting"] = f"'{setting_value}'"

                    setting_name_dict = {
                        "setting_name": result_dict["name"],
                        "common_level": 3,
                        "val": result_dict["setting"],
                        "unit": result_dict["unit"],
                        "setting_type": setting_type_dict[result_dict["vartype"]]
                    }
                    rows = [setting_name_dict]

            conf_list = [row['setting_name'] for row in rows]
            conf_unit_list = [row['setting_name'] for row in rows if row['setting_type'] == 3 or row['setting_type'] == 4]

            # 处理下参数类型
            conf_type_dict = dict()
            for setting in rows:
                conf_type_dict[setting["setting_name"]] = setting["setting_type"]

            name_type_dict = {}
            name_clup_default_val_dict = {}
            name_common_level_dict = {}
            for row in rows:
                name_common_level_dict[row['setting_name']] = row['common_level']
                name_type_dict[row['setting_name']] = row['setting_type']
                name_clup_default_val_dict[row['setting_name']] = row

            err_code, data = rpc.read_config_file_items(conf_file, conf_list)
            if err_code != 0:
                return -1, data

            is_exists = rpc.os_path_exists(pg_auto_conf_file)
            auto_data = None
            if is_exists:
                err_code, err_msg = rpc.read_config_file_items(pg_auto_conf_file, conf_list)
                if err_code != 0:
                    return -1, err_msg
                auto_data = err_msg
        finally:
            rpc.close()
        # postgresql.auto.conf中的优先级高,用postgresql.auto.conf覆盖postgresql.conf中的相同配置项
        if auto_data:
            data.update(auto_data)

        setting_list = []
        # 存在参数是默认值,但是在配置文件已经被删除的情况
        if arg_setting_name and not data:
            data = {
                setting_name_dict["setting_name"]: setting_name_dict["val"]
            }
        for setting_name, value in data.items():
            common_level = name_common_level_dict[setting_name]
            conf = {"setting_name": setting_name, "val": value, "common_level": common_level, "is_string": False}

            # 如果已经不是字符串,就不要处理了。
            if isinstance(value, str):
                # 去掉前后的单引号
                if len(value) >= 1:
                    if "'" in value:
                        conf["val"] = value.strip("'")
                if conf_type_dict[setting_name] == 6:
                    conf["is_string"] = True
                #     if data[setting_name][0] == "'":
                #         data[setting_name] = data[setting_name][1:]
                # if len(data[setting_name]) >= 1:
                #     if data[setting_name][-1] == "'":
                #         data[setting_name] = data[setting_name][:-1]

                # 如果值为空,则设置为默认值：
                # if data[setting_name] == '':
                #     if setting_name in setting_default_dict:
                #         data[setting_name] = setting_default_dict[setting_name]
                #     else:
                #         continue

        # for k, v in data.items():
            if fill_up_default:
                # v为空字符串,则表示配置文件中没有配置的项,把这些项的值设置为clup_init_db_conf中的默认值
                if value == '':
                    conf['common_level'] = 0
                    item = name_clup_default_val_dict[setting_name]
                    conf['val'] = item['val']
                    if item['unit']:
                        conf['unit'] = item['unit']

            if setting_name in conf_unit_list:  # setting_type是3和4的情况
                if value.isdigit():  # 这是如参数track_activity_query_size,可以带一个单位B,也可以不带
                    setting_type = name_type_dict[setting_name]
                    if setting_type == 3:
                        conf['unit'] = 'B'
                    elif setting_type == 4:
                        conf['unit'] = 'ms'
                else:
                    res = re.findall(r'(-{0,1}\d+)(\D+)', value)  # 128MB  -> [(128, 'MB')]
                    if not res:
                        setting_list.append(conf)
                        continue
                    conf['unit'] = res[0][1]
                    conf['val'] = res[0][0]

                # 把是数字的值从字符串类型转换成数字类型
                conf['val'] = int(conf['val'])
            else:
                pass
                # if k in name_type_dict:
                #     setting_type = name_type_dict[k]
                #     if setting_type == 1:
                #         if '.' in conf['val']:
                #             conf['val'] = float(conf['val'])
                #         else:
                #             conf['val'] = int(conf['val'])

            if auto_data and setting_name in auto_data:
                conf['is_in_auto_conf'] = 1
            else:
                conf['is_in_auto_conf'] = 0
            setting_list.append(conf)
        if not setting_list:
            return -1, "Get the settings conf failed."
        return 0, setting_list
    except Exception:
        return -1, traceback.format_exc()


def get_db_room(db_id) -> Tuple[int, str, dict]:
    """
    从集群获取对应的机房名字
    @param db_id:
    @return:
    """
    sql = "SELECT db_detail->'room_id' as room_id, cluster_id FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (db_id, ))
    if not rows:
        return -1, f'No database(db_id: {db_id}) information found', {}
    room_id = rows[0]['room_id'] if rows[0]['room_id'] else '0'
    cluster_id = rows[0]['cluster_id']
    if not cluster_id:
        return 0, '', {"room_name": '默认机房', "room_id": '0'}
    sql = "SELECT cluster_data  FROM clup_cluster WHERE cluster_id = %s"
    rows = dbapi.query(sql, (cluster_id, ))
    if not rows:
        return -1, f'No cluster(cluster_id: {cluster_id}) information found', {}
    cluster_data = rows[0]['cluster_data']
    room_info = cluster_data.get('rooms', {})
    if not room_info or (room_id == '0' and not room_info.get(str(room_id))):
        room = {
            "room_name": "默认机房",
            "vip": cluster_data['vip'],
            "room_id": room_id
        }
    else:
        room = room_info.get(str(room_id))
        room['room_id'] = room_id
    return 0, '', room


def get_new_cluster_data(cluster_id, room_id):
    sql = "SELECT cluster_data FROM clup_cluster WHERE cluster_id=%s"
    rows = dbapi.query(sql, (cluster_id, ))
    if not rows:
        return {}
    cluster_data = rows[0]['cluster_data']
    room_info = cluster_data.get('room_info', {})
    cluster_data.update(room_info.get(str(room_id), {}))
    return cluster_data


def update_cluster_room_info(cluster_id, db_id=None):
    """
    更新集群的机房信息
    @param cluster_id:
    @return:
    """
    sql = "SELECT cluster_type, cluster_data FROM clup_cluster WHERE cluster_id=%s"
    rows = dbapi.query(sql, (cluster_id, ))
    if not rows:
        return -1, f'No cluster(cluster_id: {cluster_id}) information found'

    cluster_type = rows[0]['cluster_type']
    if cluster_type == 2:  # 跳过共享存储的集群对机房信息的更新
        return 0, ""

    cluster_data = rows[0]['cluster_data']
    room_info = cluster_data.get('rooms', {})
    if not db_id:
        sql = "SELECT db_detail->'room_id' as room_id FROM clup_db WHERE is_primary = 1 AND cluster_id=%s"
        rows = dbapi.query(sql, (cluster_id, ))
    else:
        sql = "SELECT db_detail->'room_id' as room_id FROM clup_db WHERE db_id = %s"
        rows = dbapi.query(sql, (db_id,))
    if not rows:
        return -1, f'The primary database in the cluster(cluster_id: {cluster_id}) is not found.'

    primary_room_id = rows[0]['room_id']
    primary_room_id = primary_room_id if primary_room_id else '0'

    if not room_info:
        room_info = {
            '0': {
                'vip': cluster_data['vip'],
                'room_name': '默认机房'
            }
        }
    primary_room_info = room_info[str(primary_room_id)]
    cluster_data.update(primary_room_info)
    cluster_data['rooms'] = room_info
    try:
        sql = "UPDATE clup_cluster SET cluster_data= %s WHERE cluster_id=%s"
        dbapi.execute(sql, (json.dumps(cluster_data), cluster_id))
    except Exception as e:
        return -1, f'The cluster(cluster_id: {cluster_id}) room data fails to be updated. error: {repr(e)}'
    return 0, 'ok'


def get_max_lsn_db(db_list):
    """
    db_list :  [{'db_id': 277},{'db_id': 292}]
    @param db_list:
    @return:
    """
    curr_lsn = ''
    new_pri_pg = None
    for db in db_list:
        db_id = db['db_id']
        db = dao.get_db_info(db_id)
        if not db:
            logging.error(f"Failed to obtain database(db_id={db_id}) information.")
            continue
        err_code, err_msg, lsn, _ = probe_db.get_last_lsn(db[0]['host'], db[0]['port'], db[0]['repl_user'], db_encrypt.from_db_text(db[0]['repl_pass']))
        if err_code != 0:
            logging.error(f"Failed to obtain database(db_id={db_id}) lsn information. error: {err_msg}")
            continue
        if lsn > curr_lsn and not new_pri_pg:
            curr_lsn = lsn
            new_pri_pg = db_id
            continue
    return new_pri_pg


def get_current_cluster_room(cluster_id) -> Tuple[int, str, dict]:
    """
    获取集群当前机房信息
    @param cluster_id:
    @return:
    """
    sql = "SELECT cluster_data->'rooms' as rooms FROM clup_cluster WHERE cluster_id = %s"
    room_info_rows = dbapi.query(sql, (cluster_id, ))
    if not room_info_rows:
        return -1, f'No cluster(cluster_id: {cluster_id}) information found', {}
    sql = "SELECT db_detail->'room_id' as room_id FROM clup_db WHERE cluster_id=%s AND is_primary=1"
    room_id_rows = dbapi.query(sql, (cluster_id, ))
    if not room_id_rows:
        return -1, f"Cluster(cluster_id={cluster_id}) primary database information is not found.", {}
    rooms = room_info_rows[0]['rooms'] if room_info_rows[0]['rooms'] else {}
    cur_room_id = room_id_rows[0]['room_id']
    cur_room_id = cur_room_id if cur_room_id else '0'
    cur_room_info = rooms.get(str(cur_room_id), {})
    cur_room_info['room_id'] = cur_room_id
    return 0, '', cur_room_info


def get_db_relation_info(db_dict):
    for db in db_dict['children']:
        err_code, _err_code, room = get_db_room(db['db_id'])
        if err_code != 0:
            return
        db['room_name'] = room.get('room_name', '') if err_code == 0 else ''
        rows = dao.get_lower_db(db['db_id'])
        if rows:
            db['children'] = rows
            get_db_relation_info(db)


def pretty_size(val):
    """传进来的值是以字节为单位,转为 kB MB GB TB的值
    Args:
        val ([type]): [description]

    Returns:
        [type]: [description]
    """
    if val >= 100 * 1024 * 1024 * 1024 * 1024:
        return f'{val / 1024 / 1024 / 1024 / 1024:.0f}TB'
    elif val >= 100 * 1024 * 1024 * 1024:
        return f'{val / 1024 / 1024 / 1024:.0f}GB'
    elif val >= 100 * 1024 * 1024:
        return f'{val / 1024 / 1024:.0f}MB'
    elif val >= 100 * 1024:
        return f'{val / 1024:.0f}kB'
    else:
        return f'{val}'


def pretty_ms(val):
    """传进来的值是以字节为单位,转为单位为 s min h d 的值

    Args:
        val ([type]): [description]

    Returns:
        [type]: [description]
    """
    if val >= 10 * 24 * 3600 * 1000:
        return f'{val / 24 / 3600 / 1000:.0f}d'
    elif val >= 10 * 3600 * 1000:
        return f'{val / 3600 / 1000:.0f}h'
    elif val >= 10 * 60 * 1000:
        return f'{val / 60 / 1000:.0f}MB'
    elif val >= 1000:
        return f'{val / 1000:.0f}s'
    else:
        return f'{val}ms'


def get_pg_ident(db_conn, host):
    # get the ident_file path
    sql = "SELECT setting FROM pg_settings WHERE name=%s"
    rows = dao.sql_query(db_conn, sql, ('ident_file', ))
    if not rows:
        return -1, f"Execute sql({sql}) failed."
    ident_file = rows[0]["setting"]

    # read the file content
    code, result = rpc_utils.read_config_file(host, ident_file)
    if code != 0:
        return -1, f"Read the file({ident_file}) content from host({host}) failed, {result}."
    ident_content = result

    # filter content
    ident_content_list = list()
    for content in ident_content.split("\n"):
        content = content.strip("\n")
        if content.startswith("#") or not len(content):
            continue
        ident_content_list.append(content)

    return 0, ident_content_list


def get_db_names(db_conn):
    sql = "SELECT oid, datname FROM pg_database"
    rows = dao.sql_query(db_conn, sql)
    if not rows:
        return -1, "Get the database names failed."

    filter_datnames = ['cs_sys_ha', 'template1', 'template0']
    ret_list = [dict(row) for row in rows if row['datname'] not in filter_datnames]
    return 0, ret_list


def get_user_names(db_conn):
    sql = "SELECT usename FROM pg_user"
    rows = dao.sql_query(db_conn, sql)
    if not rows:
        return -1, "Get the user names failed."

    ret_list = [dict(row) for row in rows]
    return 0, ret_list


def get_pg_hba(db_id, db_conn=None, offset=None, limit=None) -> Tuple[int, str, list]:
    # check the pg_version,support PG10 and last version
    sql = "SELECT db_detail->'version' as version FROM clup_db WHERE db_id = %s"
    rows = dbapi.query(sql, (db_id, ))
    if not rows:
        return -1, "Check the pg_version failed.", []
    pg_version = rows[0]['version']
    if float(pg_version) < 10:
        return -1, "Only support for pg_version 10 or later.", []

    try:
        need_close = False
        if not db_conn:
            # connect the database
            code, msg, db_conn = get_db_conn(db_id)
            if code != 0:
                return -1, msg, []
            need_close = True

        # query pg_hba info from the database
        sql = "SELECT * FROM pg_hba_file_rules OFFSET %s LIMIT %s"
        rows = dao.sql_query(db_conn, sql, (offset, limit))
        if not rows:
            return -1, f"Execute sql({sql}) on database(db_id={db_id}) failed.", []
        ret_list = [dict(row) for row in rows]

    except Exception as e:
        return -1, f"Search pg_hba rules with unexpected error, {str(e)}.", []
    finally:
        if need_close:
            db_conn.close()

    return 0, '', ret_list


def backup_pg_hba(rpc, pgdata, backup_ident=False):
    code, result = rpc.os_stat(pgdata)
    if code != 0:
        return -1, result
    st_dict = result

    backup_path = os.path.join(pgdata, 'pg_hba_archive')
    if not rpc.os_path_exists(backup_path):
        # 创建目录
        code, result = rpc.os_makedirs(backup_path, 0o700)
        if code != 0:
            return -1, result

        code, result = rpc.os_chown(backup_path, st_dict['st_uid'], st_dict['st_gid'])
        if code != 0:
            err_msg = f"chown directory {backup_path} error: {result}"
            return -1, err_msg

    current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())

    # backup the pg_hba file
    hba_file = os.path.join(pgdata, 'pg_hba.conf')
    new_file = f"{backup_path}/pg_hba.conf-{current_time}"
    cmd = f"cp {hba_file} {new_file}"
    code, err_msg, _out_msg = rpc.run_cmd_result(cmd)
    if code != 0:
        return -1, f"Excute the cmd({cmd}) failed, {err_msg}."
    # chown
    err_code, err_msg = rpc.os_chown(new_file, st_dict['st_uid'], st_dict['st_gid'])
    if err_code != 0:
        return -1, f"Chown the file({new_file}) failed."

    # backup the ident file
    if backup_ident:
        ident_file = os.path.join(pgdata, 'pg_ident.conf')
        new_file = f"{backup_path}/pg_ident.conf-{current_time}"
        cmd = f"cp {ident_file} {new_file}"
        code, err_msg, _out_msg = rpc.run_cmd_result(cmd)
        if code != 0:
            return -1, f"Excute the cmd({cmd}) failed, {err_msg}."
        # chown
        err_code, err_msg = rpc.os_chown(new_file, st_dict['st_uid'], st_dict['st_gid'])
        if err_code != 0:
            return -1, f"Chown the file({new_file}) failed."

    return 0, "Success"


def delete_one_pg_hba(host, pgdata, line_number, is_reload=True):
    rpc = None
    try:
        # connect the host
        code, result = rpc_utils.get_rpc_connect(host)
        if code != 0 or isinstance(result, str):
            return -1, f"Connect the host({host}) failed, {result}."
        rpc = result

        hba_file = f"{pgdata}/pg_hba.conf"
        if not rpc.os_path_exists(hba_file):
            return -1, f"The file({hba_file}) is not exists."

        # read the line contnent
        cmd = f"sed -n '{line_number}p' {hba_file}"
        code, err_msg, out_msg = rpc.run_cmd_result(cmd)
        if code != 0:
            return -1, f"Read the file content line({line_number}) failed, {err_msg}."
        backup_ident = False
        if "map" in out_msg:
            backup_ident = True

        # backup the conf files
        code, result = backup_pg_hba(rpc, pgdata, backup_ident)
        if code != 0:
            return -1, f"Backup the conf file failed, {result}."

        # delete the line
        del_cmd = f"sed -i '{line_number}d' {hba_file}"
        code, err_msg, _out_msg = rpc.run_cmd_result(del_cmd)
        if code != 0:
            return -1, f"Delete line({line_number}) from file({hba_file}) failed, {err_msg}."

        if is_reload:
            code, result = pg_db_lib.reload(host, pgdata)
            if code != 0:
                return -1, f"Reload the database failed, {result}."

    except Exception as e:
        return -1, f"Delete from pg_hba.conf with unexpected error, {str(e)}."
    finally:
        if rpc:
            rpc.close()

    return 0, "Success"


def check_pg_hba(db_id) -> Tuple[int, str, list]:
    """检查pg_hba文件，如果有错误，则删除掉这一行，执行reload，然后返回错误信息
    """
    # get the pg_hba list
    code, msg, result = get_pg_hba(db_id)
    if code != 0:
        return -1, msg, []

    # check error
    error_list = [hba_dict for hba_dict in result if hba_dict["error"]]
    if error_list:
        # get the database infor
        sql = "SELECT host, pgdata FROM clup_db WHERE db_id=%s"
        rows = dbapi.query(sql, (db_id, ))
        if not rows:
            return -1, f"Cant find any records from clup_db, where db_id={db_id}.", []

        host = rows[0]['host']
        pgdata = rows[0]['pgdata']

        for index in range(len(error_list)):
            is_reload = False
            if index == len(error_list) - 1:
                is_reload = True
            # delete from pg_hba
            code, result = delete_one_pg_hba(host, pgdata, error_list[index]['line_number'], is_reload)
            if code != 0:
                return -1, result, []
        # return error_list
        return 1, '', error_list
    return 0, '', []


def update_pg_hba(pdict, option="update"):
    # get the db infor
    sql = "SELECT host, pgdata FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (pdict['db_id'], ))
    if not rows:
        return -1, f"Cant find any records for database(db_id={pdict['db_id']})."
    db_info = rows[0]

    # conf_dict to str
    conf_str = ""
    pg_indet_str = None
    key_sort_list = ['type', 'database', 'user_name', 'address', 'netmask', 'auth_method', 'options', 'pg_ident']
    for key in key_sort_list:
        value = pdict['conf_dict'].get(key, None)
        if not value:
            continue
        if key in {"database", "user_name"}:
            conf_str = f"{conf_str}{','.join(value)}\t"
        elif key == "address":
            address = value
            if pdict['option'] == "update" and "/" in address:
                address = r'\/'.join(address.split("/"))
            conf_str = f"{conf_str}{address}\t"
        elif key == "pg_ident":
            pg_indet_str = value
        else:
            conf_str = f"{conf_str}{value}\t"

    rpc = None
    try:
        # connect the host
        code, result = rpc_utils.get_rpc_connect(db_info["host"])
        if code != 0:
            return -1, f"Connect the host({db_info['host']}) failed, {result}."
        rpc = result

        # check the file is exists or not
        hba_file = f"{db_info['pgdata']}/pg_hba.conf"
        if not rpc.os_path_exists(hba_file):
            return -1, f"The file({hba_file}) is not exists."

        # backup current file
        backup_ident = False
        if "map" in conf_str:
            backup_ident = True
        code, result = backup_pg_hba(rpc, db_info['pgdata'], backup_ident)
        if code != 0:
            return -1, f"Backup the conf file failed, {result}."

        # replace the content for pg_hba.conf
        if option == "update":
            update_cmd = f"sed -i '{pdict['line_number']}s/.*/{conf_str}/' {hba_file}"
            code, err_msg, _out_msg = rpc.run_cmd_result(update_cmd)
            if code != 0:
                return -1, f"Update content for file({hba_file}) failed, {err_msg}."
        # add one record to pg_hba.conf
        elif option == "add":
            add_cmd = f"echo '{conf_str}' >> {hba_file}"
            code, err_msg, _out_msg = rpc.run_cmd_result(add_cmd)
            if code != 0:
                return -1, f"Add content to file({hba_file}) failed, {err_msg}."

        # check pg_hba,is has error,delete the line
        code, msg, result = check_pg_hba(pdict['db_id'])
        if code == 1:
            ret_error = ','.join([hba_dict['error'] for hba_dict in result])
            return -1, ret_error

        # may be need modify pg_ident.conf
        if pg_indet_str:
            need_add = True

            # get the db_conn
            code, msg, db_conn = get_db_conn(pdict['db_id'])
            if code != 0:
                return -1, msg

            # get the ident content,if not get the content,no care
            ident_content_list = list()
            code, result = get_pg_ident(db_conn, db_info["host"])
            if code == 0:
                ident_content_list = result

            # check the map_user is exists in ident content
            for ident_content in ident_content_list:
                if ','.join(pg_indet_str.split()) == ','.join(ident_content.split()):
                    need_add = False
                    break

            if need_add:
                # get the ident_file path
                sql = "SELECT setting FROM pg_settings WHERE name = %s"
                rows = dao.sql_query(db_conn, sql, ('ident_file', ))
                if not rows:
                    return -1, f"Execute sql({sql}) failed."
                ident_file = rows[0]["setting"]

                # add content to pg_ident.conf
                cmd = f"echo '{pg_indet_str}' >> {ident_file}"
                code, err_msg, _out_msg = rpc.run_cmd_result(cmd)
                if code != 0:
                    return -1, f"Add content to file({ident_file}) failed, {err_msg}."
            db_conn.close()
        if pdict["is_reload"]:
            code, result = pg_db_lib.reload(db_info["host"], db_info["pgdata"])
            if code != 0:
                return -1, f"Reload the database failed, {result}."

    except Exception as e:
        return -1, f"Update for pg_hba.conf with unexpected error, {str(e)}."
    finally:
        if rpc:
            rpc.close()

    return 0, "Success"


def get_child_node(db_id) -> Tuple[int, str, list]:
    # get the child standby
    sql = "SELECT db_id, host, pgdata FROM clup_db WHERE up_db_id=%s"
    rows = dbapi.query(sql, (db_id, ))
    if not rows:
        return 400, f"Cant find any child standby information for db_id={db_id}.", []
    child_node_list = [dict(row) for row in rows]

    # check the standby state
    for db_dict in child_node_list:
        code, result = pg_db_lib.is_running(db_dict['host'], db_dict['pgdata'])
        if code != 0:
            db_dict["db_state"] = database_state.STOP

        if result:
            db_dict["db_state"] = database_state.RUNNING
        else:
            db_dict["db_state"] = database_state.STOP

        del db_dict['pgdata']

    return 0, '', child_node_list


def reset_db_conf(db_id, setting_name):
    # get the db_conn
    code, msg, db_conn = get_db_conn(db_id)
    if code != 0:
        return -1, f"Connect the database(db_id={db_id}) failed, {msg}."

    try:
        # reset the setting
        sql = "ALTER SYSTEM RESET %s"
        dao.sql_query(db_conn, sql, (setting_name, ))
    except Exception:
        return -1, f"Excute sql({sql}) with unexpected error, {traceback.format_exc()}."
    finally:
        db_conn.close()

    return 0, "Success reset"


def enable_standby_sync(pdict):
    """开启同步复制

    Args:
        pdict (_type_): _description_

    Returns:
        _type_: _description_
    """
    db_info_list = pdict['standby_id_list'] + [pdict['db_id']]
    # query standby db info
    sql = "SELECT db_id, host FROM clup_db WHERE db_id in %s"
    rows = dbapi.query(sql, (tuple(db_info_list), ))
    if not rows:
        return -1, f"Excute sql({sql}) failed."

    # get the setting_value, primary priority must be lowest
    setting_value = None
    host_list = list()
    primary_host = None
    for row in rows:
        if row['db_id'] == pdict['db_id']:
            primary_host = '"%s"' % row['host']
        else:
            host_list.append('"%s"' % row['host'])
    host_list.append(primary_host)
    host_list_string = ','.join(host_list)
    setting_name = "synchronous_standby_names"

    # check the node_number
    if pdict.get("node_number"):
        if pdict['node_number'] < 1 and pdict['node_number'] > len(pdict['standby_id_list']):
            return -1, f"The number {pdict['node_number']} is not in [1, {len(pdict['standby_id_list'])}]."
        setting_value = f'{pdict["sync_method"]} {pdict["node_number"]} ({host_list_string})'
    else:
        return -1, f"The number({pdict['node_number']}) for {setting_name} is error."

    # 修改数据库参数
    need_reset = False
    success_list = list()
    for row in rows:
        try:
            db_conn = None
            # get db_conn
            code, msg, db_conn = get_db_conn(row['db_id'])
            if code != 0:
                return -1, f"Connect the database(db_id={row['db_id']}) failed, {msg}."

            # try to modify databse conf and reload
            alter_sql = f"ALTER SYSTEM SET {setting_name} = %s"
            dao.execute(db_conn, alter_sql, (setting_value, ))
            success_list.append(row['db_id'])
        except Exception:
            need_reset = True
            break
        finally:
            if db_conn:
                db_conn.close()

    if need_reset:
        # rollback, reset the setting
        failed_reset_list = list()
        for db_id in success_list:
            code, result = reset_db_conf(db_id, setting_name)
            if code != 0:
                failed_reset_list.append(f"db_id={db_id}: {result}")

        if failed_reset_list:
            return -1, f"Reset the setting({setting_name}) failed for {','.join(failed_reset_list)}, please check."

        return -1, "Enable standby sync failed, already rollback."

    # run pg_reload_conf(),just reload primary database
    try:
        db_conn = None
        code, msg, db_conn = get_db_conn(pdict['db_id'])
        if code != 0:
            return -1, f"Connect the database(db_id={pdict['db_id']}) failed, {msg}."
        reload_sql = "SELECT pg_reload_conf()"
        dao.execute(db_conn, reload_sql)
    except Exception:
        return -1, f"Excute sql({reload_sql}) with unexpected error, {traceback.format_exc()}."
    finally:
        if db_conn:
            db_conn.close()

    return 0, "Success"


def disable_standby_sync(db_id):
    # get child node list
    code, msg, result = get_child_node(db_id)
    if code != 0:
        return -1, msg
    standby_info_list = result

    setting_value = None
    reload_sql = "SELECT pg_reload_conf()"
    reset_sql = "ALTER SYSTEM RESET synchronous_standby_names"

    # get the setting value and reset on primary database
    try:
        db_conn = None
        code, msg, db_conn = get_db_conn(db_id)
        if code != 0:
            return -1, f"Connect the databse failed, {msg}."

        # get the setting value
        query_sql = "SELECT setting FROM pg_settings WHERE name='synchronous_standby_names'"
        rows = dao.sql_query(db_conn, query_sql)
        if not rows:
            return -1, f"Excute sql({query_sql}) on db_id({db_id}) failed."

        setting_value = rows[0]['setting']

        # primary reset
        dao.execute(db_conn, reset_sql)

        # run pg_reload_conf() Tip: alter system cant in a transaction block
        dao.execute(db_conn, reload_sql)
    except Exception:
        return -1, f"Excute sql({reset_sql}) on the primary database with unexpected error, {traceback.format_exc()}."
    finally:
        if db_conn:
            db_conn.close()

    # reset on standby database
    failed_list = list()
    for db_info in standby_info_list:
        # if standby host not in setting_value,continue
        if db_info['host'] not in setting_value:
            continue

        if db_info['db_state'] != database_state.RUNNING:
            failed_list.append(f"db_id={db_info['db_id']}: {db_info['host']}")
            continue

        # get the db_conn, alter system cant in a transaction block
        code, msg, db_conn = get_db_conn(db_info['db_id'])
        if code != 0:
            failed_list.append(f"db_id={db_info['db_id']}: {db_info['host']}")
        else:
            try:
                dao.execute(db_conn, reset_sql)
            except Exception:
                failed_list.append(f"db_id={db_info['db_id']}: {db_info['host']}")
            finally:
                if db_conn:
                    db_conn.close()

            # run pg_reload_conf() Tip: alter system cant in a transaction block
            code, msg, db_conn = get_db_conn(db_id)
            if code == 0:
                try:
                    dao.execute(db_conn, reload_sql)
                except Exception:
                    failed_list.append(f"db_id={db_info['db_id']}: {db_info['host']}")
                finally:
                    if db_conn:
                        db_conn.close()
    if failed_list:
        return -1, f"Excute sql({reset_sql}) failed on ({','.join(failed_list)})."

    return 0, "Success"
