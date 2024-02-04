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
@Author: leifliu
@description: PolarDB的数据库操作模块
"""

import copy
import json
import logging
import traceback

import dao
import db_type_def
import database_state
import cluster_state
import db_encrypt
import dbapi
import general_task_mgr
import long_term_task
import pg_db_lib
import pg_helpers
import polar_lib
import rpc_utils
import task_type_def


def build_polar_standby(pdict, polar_type):
    """搭建polardb 备库
    Args:
        pdict (dict): 搭建数据库的参数
        polar_type (str): 要搭建的polardb类型，standby为本地存储类型，reader为共享存储只读节点
    Returns:
    """

    step = "Data preparation for build polardb database"
    try:
        # get the up db info and check cluster state is online or not
        up_db_dict = polar_lib.get_up_db_info(pdict['up_db_id'])
        if not up_db_dict:
            return -1, f'{step}: The superior database instance does not exist. Please check.'
        current_cluster_state = dao.get_cluster_state(up_db_dict["cluster_id"])
        if current_cluster_state not in [cluster_state.OFFLINE, cluster_state.FAILED]:
            err_msg = f"The superior database is in the cluster(cluster_id={up_db_dict['cluster_id']})," \
                f"which cluster state is not OFFLINE or FAILED, cant create standby or reader database."
            return -1, err_msg

        # if polar_type is standby,superior database must be RW node
        if polar_type == "standby":
            up_db_polar_type = polar_lib.get_polar_type(up_db_dict["db_id"])
            if not up_db_polar_type:
                return -1, f"Cant get the polar_type of superior database({up_db_dict['db_id']})."
            elif up_db_polar_type != "master":
                return -1, f"The superior database({up_db_dict['db_id']}) is not an RW node and cannot be used to build a standby database."

        # check the host and port is aready used
        sql = f"""SELECT db_id FROM clup_db WHERE host = '{pdict['host']}' AND port= {pdict['port']}"""
        rows = dbapi.query(sql)
        if rows:
            return -1, f"{step} failed: Port({pdict['port']}) is already used on the host({pdict['host']}) which db_id is {rows[0]['db_id']}."

        # if not repl user,update repl_user、repl_pass for up db
        if not up_db_dict.get("repl_user"):
            update_dict = json.dumps({"repl_user": pdict['repl_user'], "repl_pass": pdict['repl_pass']})
            sql = "UPDATE clup_db SET db_detail = db_detail || (%s::jsonb) WHERE db_id = %s"
            dbapi.execute(sql, (update_dict, pdict['up_db_id']))

        # get db settings from up db
        err_code, err_msg = pg_helpers.get_pg_setting_list(pdict['up_db_id'])
        if err_code != 0:
            return -1, f"{step}: Cant get the configurations from the superior database, {err_msg}."
        up_db_dict['setting_list'] = err_msg
    except Exception:
        return -1, f"{step} with unexpected error, {traceback.format_exc()}."

    step = "Insert database information into clup_db"
    try:
        # new database infor
        db_dict = copy.copy(pdict)
        del pdict

        # db_detail放clup_db.db_detail字段的数据
        db_detail = {
            'os_user': db_dict['os_user'],
            'os_uid': db_dict['os_uid'],
            'db_user': up_db_dict['db_user'],
            'db_pass': up_db_dict['db_pass'],
            'instance_type': db_dict['instance_type'],
            'repl_user': db_dict['repl_user'],
            'repl_pass': db_dict['repl_pass'],
            'version': db_dict['version'],
            'polar_type': polar_type,
            'pg_bin_path': db_dict['pg_bin_path'],
            'pfs_disk_name': up_db_dict["pfs_disk_name"],
            'pfsdaemon_params': up_db_dict['pfsdaemon_params'],
            'polar_datadir': up_db_dict['polar_datadir']
        }
        if db_dict.get('delay'):
            db_detail['delay'] = db_dict['delay']

        # 获取集群的polar_hostid
        err_code, err_msg = polar_lib.get_cluster_polar_hostid(up_db_dict['cluster_id'])
        if err_code != 0:
            return -1, f"{step}: Get the polardb hostid failed, {err_msg}."
        polar_hostid = err_msg
        db_detail['polar_hostid'] = polar_hostid

        insert_data_dict = dict()
        insert_data_dict["is_primary"] = 0
        insert_data_dict["host"] = db_dict["host"]
        insert_data_dict["pgdata"] = db_dict["pgdata"]
        insert_data_dict["port"] = up_db_dict["port"]
        insert_data_dict["up_db_id"] = up_db_dict["db_id"]
        insert_data_dict["db_type"] = up_db_dict["db_type"]
        insert_data_dict["repl_ip"] = db_dict["repl_ip"]
        insert_data_dict['repl_app_name'] = db_dict['repl_ip']
        insert_data_dict['cluster_id'] = up_db_dict['cluster_id']
        insert_data_dict["db_detail"] = json.dumps(db_detail)
        insert_data_dict['state'] = up_db_dict["state"]  # 注意这是HA的状态，不是数据库的状态
        insert_data_dict['up_db_repl_ip'] = up_db_dict['repl_ip_in_detail'] if up_db_dict['repl_ip_in_detail'] else up_db_dict['repl_ip']
        if 'instance_name' not in db_dict:
            insert_data_dict['instance_name'] = ''
        insert_data_dict['db_state'] = database_state.CREATING      # 数据库状态默认为创建中

        try:
            # 先插入数据库生成id
            sql = "INSERT INTO clup_db (cluster_id, state, pgdata, is_primary, repl_app_name, host, repl_ip, " \
                "instance_name, db_detail, port, db_state, up_db_id, db_type) values " \
                "(%(cluster_id)s, %(state)s, %(pgdata)s, %(is_primary)s, %(repl_app_name)s, %(host)s, %(repl_ip)s, "\
                "%(instance_name)s, %(db_detail)s, %(port)s, %(db_state)s, %(up_db_id)s, %(db_type)s) RETURNING db_id"
            rows = dbapi.query(sql, insert_data_dict)
        except Exception:
            return -1, f'{step}: Failed to insert data into clup_db,{traceback.format_exc()}.'
        if not rows:
            return -1, f'{step}: Failed to insert data into clup_db.'
        del insert_data_dict
        del db_detail
        db_dict['db_id'] = rows[0]["db_id"]

        # 更新集群的polar_hostid
        polar_lib.update_cluster_polar_hostid(up_db_dict['cluster_id'], polar_hostid + 1)

    except Exception:
        err_msg = f"{step} with unexpected error, {traceback.format_exc()}."
        logging.error(f"Build reader unexpect error: {err_msg}")
        return -1, err_msg

    step = "Create build database task"
    try:
        # rpc_dict 放下创建备库的调用的参数
        rpc_dict = db_dict
        # 数据库用户，当db_user禹os_user不相同是，需要在pg_hba.conf中加用户映射，否则本地无法误密码的登录数据库
        rpc_dict['db_user'] = up_db_dict['db_user']
        rpc_dict['db_pass'] = up_db_dict['db_pass']
        rpc_dict['up_db_id'] = up_db_dict['db_id']
        rpc_dict['up_db_host'] = up_db_dict['host']
        rpc_dict['up_db_port'] = up_db_dict['port']
        rpc_dict["up_db_os_user"] = up_db_dict["os_user"]
        rpc_dict['up_db_pgdata'] = up_db_dict['pgdata']
        rpc_dict['repl_pass'] = up_db_dict['repl_pass']
        rpc_dict["up_db_repl_ip"] = up_db_dict["repl_ip"]
        rpc_dict["other_param"] = db_dict["other_param"]

        rpc_dict["polar_hostid"] = polar_hostid
        rpc_dict['primary_slot_name'] = f"replica{polar_hostid}"
        rpc_dict['pfs_disk_name'] = up_db_dict["pfs_disk_name"]
        rpc_dict["polar_datadir"] = up_db_dict["polar_datadir"]
        rpc_dict['pfsdaemon_params'] = up_db_dict["pfsdaemon_params"]

        # 开始搭建只读节点
        task_name = f"build polardb(db={db_dict['host']}:{db_dict['port']})"
        rpc_dict['task_name'] = task_name
        # rpc_dict['task_key'] = task_name + str(db_dict['db_id'])

        task_id = general_task_mgr.create_task(
            task_type=task_type_def.PG_BUILD_STANDBY_TASK,
            task_name=task_name,
            task_data=rpc_dict
        )
        rpc_dict['task_id'] = task_id
        # rpc_dict['pre_msg'] = f"Build reader(db_id={db_dict['db_id']})"
        if polar_type == "reader":
            general_task_mgr.run_task(task_id, long_term_task.task_build_polar_reader, (rpc_dict, ))
        elif polar_type == "standby":
            general_task_mgr.run_task(task_id, long_term_task.task_build_polar_standby, (rpc_dict, ))

        return 0, task_id
    except Exception:
        err_msg = f"{step} with unexpected error, {traceback.format_exc()}."
        general_task_mgr.complete_task(task_id, -1, err_msg)
        dao.update_db_state(db_dict['db_id'], database_state.FAULT)
        return -1, err_msg


def repair_polar_standby(task_id, pdict, polar_type):
    """polardb 备库重搭加回集群
    Args:
        pdict (dict): 搭建数据库的参数

    Returns:
        int: err_code
        str: err_msg
        int: task_id
        int: db_id
    """
    try:
        step = "Get superior database information"
        general_task_mgr.log_info(task_id, f"{step} ...")
        up_db_dict = polar_lib.get_up_db_info(pdict['up_db_id'])
        if not up_db_dict:
            return -1, f"{step} faild, superior database instance(db_id={pdict['up_db_id']}) does not exist, please check."

        err_code, err_msg = pg_helpers.get_pg_setting_list(pdict['up_db_id'])
        if err_code != 0:
            return -1, f"Failed to get the configuration of the superior database(up_db_id={pdict['up_db_id']})：{err_msg}"
        up_db_dict['setting_list'] = err_msg

        # 获取集群的polar_hostid
        err_code, err_msg = polar_lib.get_db_polar_hostid(pdict['db_id'])
        if err_code != 0:
            return -1, err_msg
        if not err_msg.get('polar_hostid'):
            return -1, f"{step} failed, cant get polardb hostid for database(db_id={pdict['db_id']})."
        polar_hostid = int(err_msg['polar_hostid'])

        # db_dict存储往表clup_db中插入的数据

        db_dict = copy.copy(pdict)
        db_dict["delay"] = up_db_dict["delay"]
        if not db_dict.get('instance_name'):
            db_dict['instance_name'] = ''
        # db_detail = up_db_dict['db_detail']
        # db_detail['delay'] = pdict.get('delay', None)
        # db_detail['tblspc_dir'] = pdict.get('tblspc_dir', [])

        # 数据库用户，当db_user禹os_user不相同是，需要在pg_hba.conf中加用户映射，否则本地无法误密码的登录数据库
        db_dict['db_user'] = up_db_dict['db_user']
        db_dict['db_pass'] = up_db_dict['db_pass']
        db_dict['up_db_host'] = up_db_dict['host']
        db_dict['up_db_pgdata'] = up_db_dict['pgdata']
        db_dict["up_db_os_user"] = up_db_dict["os_user"]
        db_dict['repl_pass'] = db_encrypt.to_db_text(db_dict['repl_pass'])
        db_dict["other_param"] = '-X stream --progress --write-recovery-conf -v'

        db_dict['polar_hostid'] = polar_hostid
        db_dict['pfs_disk_name'] = up_db_dict['pfs_disk_name']
        db_dict["polar_datadir"] = up_db_dict["polar_datadir"]
        db_dict['pfsdaemon_params'] = up_db_dict['pfsdaemon_params']
        general_task_mgr.log_info(task_id, f"{step} success.")

        if polar_type == "reader":
            err_code, err_msg = long_term_task.build_polar_reader(task_id, db_dict)
        elif polar_type == "standby":
            err_code, err_msg = long_term_task.build_polar_standby(task_id, db_dict)
        return err_code, err_msg

    except Exception:
        err_msg = f"Build polardb database with unexpected error, {traceback.format_exc()}."
        logging.error(err_msg)
        dao.update_db_state(db_dict['db_id'], database_state.FAULT)
        general_task_mgr.complete_task(task_id, -1, err_msg)
        return -1, err_msg


def change_recovery_up_db(db_id, up_db_id, polar_type):
    """修改备库的流复制连接

    """
    rows = dao.get_db_info(up_db_id)
    if not len(rows):
        return -1, f"Failed to obtain database(db_id={up_db_id}) information."
    up_db_host = rows[0]['host']
    up_db_port = rows[0]['port']

    # 先检查是否存在recovery.conf文件，没有的话直接新建一个
    err_code, err_msg = polar_lib.check_or_create_recovery_conf(db_id, rows[0])
    if err_code != 0 and err_code != 1:
        return -1, err_msg

    # 返回值为0说明存在recovery.conf,为1时已新建不需要再修改
    if err_code == 0:
        err_code, err_msg = polar_lib.update_recovery(db_id, up_db_host, up_db_port)
        if err_code != 0:
            return -1, err_msg

    rows = dao.get_db_info(db_id)
    if not len(rows):
        return -1, f"Failed to obtain database(db_id={db_id}) information."
    host = rows[0]['host']
    pgdata = rows[0]['pgdata']

    if polar_type in ['reader', 'master']:
        # 启动pfs
        err_code, err_msg = polar_lib.start_pfs(host, db_id)
        if err_code != 0 and err_code != 1:
            return -1, err_msg

    err_code, err_msg = pg_db_lib.restart(host, pgdata)
    return err_code, err_msg


def recovery_standby(task_id, msg_prefix, recovery_host, pgdata):
    """recovery polardb standby in local storage

    Args:
        recovery_host (_type_): _description_
        pgdata (_type_): _description_
    """
    try:
        # move polar_shared_data to local
        err_code, err_msg = polar_lib.polar_share_to_local(task_id, msg_prefix, recovery_host, pgdata)
        if err_code != 0:
            general_task_mgr.log_error(task_id, err_msg)
            return -1, err_msg

        # create rpc connect
        rpc = None
        err_code, err_msg = rpc_utils.get_rpc_connect(recovery_host)
        if err_code != 0:
            err_msg = f"Connect to host({recovery_host}) failed, {err_msg}."
            return -1, err_msg
        rpc = err_msg

        # disable some settings
        postgresql_conf = f"{pgdata}/postgresql.conf"
        remove_conf_list = [
            'polar_datadir',
            'polar_disk_name',
            'polar_vfs.localfs_mode',
            'polar_storage_cluster_name',
            'polar_enable_shared_storage_mode'
        ]
        # edit the postgres.conf file
        err_code, err_msg = polar_lib.disable_settings(rpc, postgresql_conf, remove_conf_list)
        if err_code != 0:
            err_msg = f"""Restore file is ok, but edit the {postgresql_conf} failed,{err_msg},
            need disable the {remove_conf_list} by yourself.
            """
            general_task_mgr.log_error(task_id, err_msg)
            return -1, err_msg
        # need add polar_vfs.localfs_mode to on
        rpc.modify_config_type1(postgresql_conf, {"polar_vfs.localfs_mode": "on"}, is_backup=False)
        # check postgres.auto.conf
        postgresql_auto_conf = f"{pgdata}/postgresql.auto.conf"
        err_code, err_msg = polar_lib.disable_settings(rpc, postgresql_auto_conf, remove_conf_list)
        if err_code != 0:
            err_msg = f"""Restore file is ok, but edit the {postgresql_auto_conf} failed,{err_msg},
            need disable the {remove_conf_list} by yourself.
            """
            general_task_mgr.log_error(task_id, err_msg)
            return -1, err_msg

        return 0, "recovery for polrdb success"
    except Exception:
        err_msg = f"recovery polardb to local storage with unexcept error, {traceback.format_exc()}"
        general_task_mgr.log_error(task_id, err_msg)
        return -1, err_msg
    finally:
        if rpc:
            rpc.close()


def create_polardb_with_pfs(pdict):
    # insert db info into clup_db
    try:
        # db_detail cloumn data
        db_detail = {
            "polar_hostid": 1,
            'polar_type': 'master',
            'os_user': pdict['os_user'],
            'os_uid': pdict['os_uid'],
            'db_user': pdict['db_user'],
            'db_pass': pdict['db_pass'],
            'version': pdict['version'],
            'pg_bin_path': pdict['pg_bin_path'],
            'wal_segsize': pdict['wal_segsize'],
            'pfs_disk_name': pdict['pfs_disk_name'],
            'polar_datadir': pdict["polar_datadir"],
            'pfsdaemon_params': pdict['pfsdaemon_params']
        }

        # db info
        db_info = {
            "polar_hostid": 1,
            "is_primary": 1,
            "scores": pdict.get("scores", 0),
            "host": pdict["host"],
            "port": pdict["port"],
            "pgdata": pdict["pgdata"],
            "state": cluster_state.NORMAL,
            "db_state": database_state.CREATING,
            "db_detail": json.dumps(db_detail),
            "repl_ip": pdict.get("repl_ip", pdict["host"]),
            "repl_app_name": pdict['host'],
            "db_type": db_type_def.POLARDB
        }

        sql = "INSERT INTO clup_db (state, pgdata, is_primary, repl_app_name, host," \
              " repl_ip, db_detail, port, db_state, scores, db_type) VALUES " \
              "(%(state)s, %(pgdata)s, %(is_primary)s, %(repl_app_name)s, %(host)s, " \
              " %(repl_ip)s, %(db_detail)s, %(port)s, %(db_state)s, %(scores)s, %(db_type)s) RETURNING db_id"
        rows = dbapi.query(sql, db_info)
        if len(rows) == 0:
            err_msg = 'Cant insert database information into clup_db.'
            return -1, err_msg
        db_id = rows[0]['db_id']
    except Exception:
        return -1, f"Insert database information into clup_db with unexpected error, {traceback.format_exc()}."

    # create task for create database instance
    try:
        task_name = "create polardb with shared disk"

        rpc_dict = dict()
        rpc_dict.update(db_info)
        del rpc_dict['db_detail']
        rpc_dict['db_id'] = db_id
        rpc_dict['task_name'] = task_name
        rpc_dict['instance_name'] = rpc_dict['host']
        rpc_dict["os_uid"] = pdict["os_uid"]
        rpc_dict["os_user"] = pdict["os_user"]
        rpc_dict["db_user"] = pdict["db_user"]
        rpc_dict["version"] = pdict["version"]
        rpc_dict["pg_bin_path"] = pdict["pg_bin_path"]
        rpc_dict["wal_segsize"] = pdict["wal_segsize"]
        rpc_dict['db_pass'] = db_encrypt.from_db_text(pdict['db_pass'])

        rpc_dict["polar_hostid"] = 1
        rpc_dict['pfsdaemon_params'] = pdict['pfsdaemon_params']
        rpc_dict['pfs_disk_name'] = pdict['pfs_disk_name']
        rpc_dict['polar_datadir'] = pdict['polar_datadir']

        setting_dict = long_term_task.pg_setting_list_to_dict(pdict['setting_list'])
        setting_dict['port'] = pdict['port']
        rpc_dict['setting_dict'] = setting_dict

        task_id = general_task_mgr.create_task(
            task_type=task_type_def.PG_CREATE_INSTANCE_TASK,
            task_name=task_name,
            task_data=rpc_dict
        )
        general_task_mgr.run_task(task_id, long_term_task.task_create_polardb, (rpc_dict, ))
    except Exception:
        err_msg = f"Create task for create polardb with unexpected error, {traceback.format_exc()}."
        if task_id:
            general_task_mgr.complete_task(task_id, -1, err_msg)
        dao.update_db_state(rpc_dict['db_id'], database_state.FAULT)
        return -1, err_msg
    return 0, task_id


if __name__ == '__main__':
    pass
