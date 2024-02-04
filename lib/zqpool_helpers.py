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
@description: zqpool管理工具
"""

import os
import time
import dbapi
import json
import requests
import traceback
import rpc_utils
import pg_db_lib
import db_encrypt

from copy import deepcopy
from collections import OrderedDict

DB_READONLY  = 1 # 只读节点
DB_READWRITE = 2 # 读写节点

BE_ONLINE      = 1  # 上线使用中
BE_OFFLINE     = 0  # 空闲未被上线使用
BE_REMOVING    = -9 # 表示此portal正在被移除
BE_BAD_NO_FREE = -1 # 表示此portal已经坏了，但可能还有未被释放
BE_BAD_FREEED  = -2 # 表示此portal已经坏了，但所有连接都被释放了
BE_BAD_UNKNOW  = -3 # 表示此portal已经坏了，但所有连接都被释放了


BE_STATE_DICT = {
    "Online": BE_ONLINE,
    "Offline": BE_OFFLINE,
    "Removing": BE_REMOVING,
    "BAD(all connect freed)": BE_BAD_FREEED,
    "BAD(some connect not free)": BE_BAD_NO_FREE
}


def send_request(host, port, api, params_dict):
    # check the host stats is ok
    code, rpc = rpc_utils.get_rpc_connect(host, conn_timeout=2)
    if code != 0:
        return -1, f"Cant connect the host({host}), please check the agent state, {rpc}."
    rpc.close()

    try:
        base_url = 'http://{0}:{1}/api/v1/{2}'.format(host, port, api)

        parmas_list = list()
        for key, value in params_dict.items():
            if key == 'mgr_token':
                value = db_encrypt.from_db_text(value)
            parmas_list.append(f"{key}={value}")
        params = "&".join(parmas_list)
        url = "{0}?{1}".format(base_url, params)
        response = requests.get(url)

        if response.status_code != 200:
            return -1, response.text

        if "{" not in response.text:
            return -1, response.text

        response_data = response.json()
        # maybe option is failed
        if response_data['code'] != 0:
            return -1, response_data['message']

        if "message" in response_data:
            return 0, response_data["message"]

        return 0, response_data['data']

    except Exception:
        return -1, f"Send request to host({host}) with unexpected error, base url is {base_url}."


def conf_sort(conf_dict, check=False):
    key_list = [
        "mgr_addr",
        "mgr_port",
        "listen_addr",
        "listen_port",
        "exporter_port",
        "mgr_token",
        "fe_user",
        "fe_passwd",
        "fe_dbname",
        "be_user",
        "be_passwd",
        "be_dbname",
        "fe_max_conns",
        "be_rw_conns",
        "be_rd_conns",
        "be_ipport",
        "be_conn_life_time",
        "msg_buf_size",
        "be_retry_count",
        "be_retry_interval",
        "retry_cnt_when_full",
        "retry_interval_ms_when_full"
    ]

    new_dict = OrderedDict()

    for key in key_list:
        if key in conf_dict:
            if check and conf_dict[key] == "":
                return key
            else:
                new_dict[key] = conf_dict[key]

    return new_dict


def conf_convert(pool_setting_dict):
    convert_dict = {
        "ID": "id",
        "FeMaxConns": "fe_max_conns",
        "FeUser": "fe_user",
        "FePasswd": "fe_passwd",
        "FeDbName": "fe_dbname",
        "BeRwConnCount": "be_rw_conns",
        "BeRdConnCount": "be_rd_conns",
        "BeUser": "be_user",
        "BePasswd": "be_passwd",
        "BeDbName": "be_dbname",
        "BePortals": "portals",
        "MgrAddr": "mgr_addr",
        "MgrPort": "mgr_port",
        "ListenAddr": "listen_addr",
        "ListenPort": "listen_port",
        "BeConnLifeTime": "be_conn_life_time",
        "MsgBufSize": "msg_buf_size",
        "BeRetryCnt": "be_retry_count",
        "RetryCntWhenFull": "retry_cnt_when_full",
        "RetryIntervalWhenFull": "retry_interval_ms_when_full"
    }

    ret_dict = dict()
    for key, value in pool_setting_dict.items():
        if key in convert_dict:
            ret_dict[convert_dict[key]] = value
        else:
            ret_dict[key] = value

    return ret_dict


def get_zqpool_mgr_info(pool_id, is_zqpool_id=False):
    if is_zqpool_id:
        sql = """SELECT zqpool_id, host, root_path,
            conf_data->'mgr_port' as mgr_port,
            conf_data->'mgr_token' as mgr_token
            FROM csu_zqpool WHERE zqpool_id = %s
        """
    else:
        sql = """SELECT zq.zqpool_id, host, root_path,
            zq.conf_data->'mgr_port' as mgr_port,
            zq.conf_data->'mgr_token' as mgr_token
            FROM csu_zqpool zq, csu_zqpool_pools pool
            WHERE zq.zqpool_id = pool.zqpool_id AND pool_id = %s
        """

    rows = dbapi.query(sql, (pool_id, ))
    if not rows:
        return None

    return dict(rows[0])


def read_zqpool_conf(rpc, conf_file):
    need_close = False
    if isinstance(rpc, str):
        code, result = rpc_utils.get_rpc_connect(rpc)
        if code != 0:
            return -1, f"Connect the host({rpc}) failed, {result}."

        rpc = result
        need_close = True

    # check the path is exists or make it
    if not rpc.os_path_exists(conf_file):
        return -1, f"The configure file({conf_file}) is not exists."

    # check the conf_file is dir or file
    if rpc.path_is_dir(conf_file):
        conf_file = os.path.join(conf_file, 'zqpool.conf')

    # read file
    file_size = rpc.get_file_size(conf_file)
    if file_size < 0:
        return -1, f'Failed to get the file({conf_file}) size.'

    err_code, err_msg = rpc.os_read_file(conf_file, 0, file_size)
    if err_code != 0:
        return -1, f'Failed to obtain the file({conf_file}) content.'
    lines = err_msg.decode().split('\n')

    try:
        setting_dict = {
            "mgr_settings": dict(),
            "pools_settings": dict()
        }
        for line in lines:
            pool_id = None
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue

            if line.startswith("pool"):
                line_split = line.split("=")
                setting_val = line_split[-1].strip()

                line_split = line_split[0].split(".")
                pool_id = line_split[1]
                setting = line_split[-1].strip()
            else:
                line_split = line.split("=")
                setting = line_split[0].strip()
                setting_val = line_split[1].strip()

            if pool_id:
                pool_id = int(pool_id)
                if pool_id not in setting_dict["pools_settings"]:
                    setting_dict["pools_settings"][pool_id] = dict()
                if setting_val.isdigit():
                    setting_val = int(setting_val)
                setting_dict["pools_settings"][pool_id][setting] = setting_val
                continue
            if setting_val.isdigit():
                setting_val = int(setting_val)
            setting_dict["mgr_settings"][setting] = setting_val
    except Exception:
        return -1, f"Get the setting dict with unexpected error, {traceback.format_exc()}."
    finally:
        if need_close:
            rpc.close()

    return 0, setting_dict


def conf_dict_to_content(conf_dict):
    """将字典类型的配置信息转成配置文件需要的文本

    Args:
        conf_dict (_type_): {
            "mgr_settings": {},
            "pools_settings": {
                "ID": {},
                ...
            }
        }
    """
    # conf_dict to string content
    content_lines = list()
    if conf_dict.get("mgr_settings"):
        mgr_settings = conf_convert(conf_dict["mgr_settings"])
        for setting, value in mgr_settings.items():
            content_lines.append("{0} = {1}".format(setting, value))

    if conf_dict.get("pools_settings"):
        for pool_id, setting_dict in conf_dict["pools_settings"].items():
            setting_dict = conf_convert(setting_dict)
            for setting, value in setting_dict.items():
                content_lines.append("pool.{0}.{1} = {2}".format(pool_id, setting, value))
    content = '\n'.join(content_lines)

    return content


def init_zqpool_conf(rpc, root_path, mgr_setting_dict):
    """初始化zqpool.conf文件

    Args:
        rpc (_type_): _description_
        root_path (_type_): _description_

    Returns:
        _type_: _description_
    """
    # check the program is exist
    program_file = os.path.join(root_path, 'zqpool')
    if not rpc.os_path_exists(program_file):
        return -1, f"The program file({program_file}) is not exist, please check."

    conf_file = os.path.join(root_path, 'zqpool.conf')
    # if the file is exist, rename
    if rpc.os_path_exists(conf_file):
        current_time = time.strftime("%Y%m%d%H%M%S", time.localtime())
        new_file_name = "{0}_{1}.conf".format("zqpool", current_time)
        rename_conf = os.path.join(root_path, new_file_name)
        code, result = rpc.os_rename(conf_file, rename_conf)
        if code != 0:
            return -1, f"Rename the file({conf_file}) failed."

    # dict to content
    mgr_setting_dict['mgr_token'] = db_encrypt.from_db_text(mgr_setting_dict['mgr_token'])
    content = conf_dict_to_content({"mgr_settings": mgr_setting_dict})
    # create new file
    code, result = rpc.os_write_file(conf_file, 0, content.encode())
    if code != 0:
        return -1, f"Create the file({conf_file}) error, {result}."

    # get the zqpool file users info
    code, result = rpc.os_stat(program_file)
    if code != 0:
        return -1, f"Get the file({program_file}) os_stat error, {result}."
    st_dict = result

    # change the conf file owner
    code, result = rpc.os_chown(conf_file, st_dict['st_uid'], st_dict['st_gid'])
    if code != 0:
        return -1, f"Cant chmod the file({conf_file}) owner to (uid={st_dict['st_uid']}), {result}."

    return 0, "Init Success"


def get_pool_info(pool_id):
    # get the pool_info
    sql = "SELECT pool_fe FROM csu_zqpool_pools WHERE pool_id = %s"
    rows = dbapi.query(sql, (pool_id, ))
    if not rows:
        return -1, f"Cant find any records for the pool(id={pool_id})."
    pool_fe = rows[0]['pool_fe']

    # get the zqpool info
    zqpool_info = get_zqpool_mgr_info(pool_id)
    if not zqpool_info:
        return -1, f"Cant find the pool manager information."

    pool_info = {
        "pool_id": pool_id,
        "pool_fe": pool_fe,
        "host": zqpool_info['host']
    }

    # send request to get more information
    api = "pool_get_pool_list"
    params_dict = {
        "pool_name": pool_fe,
        "mgr_token": zqpool_info['mgr_token']
    }
    code, result = send_request(zqpool_info['host'], zqpool_info['mgr_port'], api, params_dict)
    if code != 0 or isinstance(result, str):
        pool_info['state'] = -1
        return -1, pool_info
    pool_info = result[0]
    pool_info['ID'] = int(pool_info['ID'])

    pool_info['state'] = 0
    pool_info['pool_fe'] = pool_fe

    # encrypt passswd
    pool_info['FePasswd'] = db_encrypt.to_db_text(pool_info['FePasswd'])
    pool_info['BePasswd'] = db_encrypt.to_db_text(pool_info['BePasswd'])

    # get the cluster_id
    if len(pool_info['BePortals']):
        portal_split = pool_info['BePortals'][0].split(':')
        host = portal_split[0]
        port = portal_split[1]
        sql = """SELECT db.cluster_id, cluster_data->'cluster_name' as cluster_name
            FROM clup_db db, clup_cluster c WHERE c.cluster_id=db.cluster_id AND host=%s AND port=%s
        """
        rows = dbapi.query(sql, (host, port))
        if not rows:
            pool_info['cluster_id'] = None
            pool_info['cluster_name'] = None
        else:
            pool_info['cluster_id'] = rows[0]['cluster_id']
            pool_info['cluster_name'] = rows[0]['cluster_name']

        pool_info['state'] = 1

    # if fe_max_conns is 0, then the pool_state to 0
    if pool_info['FeMaxConns'] == 0:
        pool_info['satte'] = 0

    return 0, pool_info


def get_pool_list(filter=None):
    # get all zqpool info
    if filter != "":
        sql = """SELECT zq.zqpool_id, pool_id, host, pool_fe
            FROM csu_zqpool_pools pool, csu_zqpool zq
            WHERE zq.zqpool_id = pool.zqpool_id AND pool_fe like %s
        """
        rows = dbapi.query(sql, (filter, ))
    else:
        sql = f"""SELECT zq.zqpool_id, pool_id, host, pool_fe
            FROM csu_zqpool_pools pool, csu_zqpool zq
            WHERE zq.zqpool_id = pool.zqpool_id
        """
        rows = dbapi.query(sql)
    if not rows:
        return 0, list()
    pool_list = [dict(row) for row in rows]

    ret_list = list()
    for pool_info in pool_list:
        # get the pool info
        code, result = get_pool_info(pool_info['pool_id'])
        if code != 0:
            pool_info['state'] = -1
        else:
            pool_info.update(result)
        ret_list.append(pool_info)

    return 0, ret_list


def get_portals_list(pool_info_list):
    """获取pool的状态信息

    Args:
        pool_info_list (dict): [
            {
                "host": ,
                "mgr_port": ,
                "mgr_token": ,
                "pool_id": ,
                "zqpool_id": ,
                "pool_fe": ,
            }
        ]

    Returns:
        _type_: _description_
    """
    ret_list = list()
    api = "pool_list_be_db"
    remove_keys = ['Portal', 'State']
    for pool_info in pool_info_list:
        host = pool_info['host']
        mgr_port = pool_info['mgr_port']

        pool_fe = pool_info['pool_fe']
        params_dict = {
            "pool_name": pool_fe,
            "mgr_token": pool_info["mgr_token"],
        }

        try:
            is_get = True
            code, result = send_request(host, mgr_port, api, params_dict)
            if code != 0:
                is_get = False
                continue

            if isinstance(result, str):
                is_get = False
                continue

            if len(result):
                for portal_info in result:
                    # get the portal db_id
                    portal_split = portal_info['Portal'].split(":")
                    be_host = portal_split[0]
                    be_port = portal_split[1]
                    sql = "SELECT cluster_id, db_id FROM clup_db WHERE host = %s and port = %s"
                    rows = dbapi.query(sql, (be_host, be_port))
                    if not rows:
                        continue
                    db_info = rows[0]

                    portal_info['host'] = be_host
                    portal_info['port'] = be_port
                    portal_info['db_id'] = db_info['db_id']
                    portal_info['cluster_id'] = db_info['cluster_id']
                    if portal_info['State'] in BE_STATE_DICT:
                        portal_info['state'] = BE_STATE_DICT[portal_info['State']]
                    else:
                        portal_info['state'] = None
                    # remove keys
                    for key in remove_keys:
                        del portal_info[key]

                    portal_info['pool_fe'] = pool_fe
                    portal_info['pool_id'] = pool_info['pool_id']
                    portal_info['zqpool_id'] = pool_info['zqpool_id']

                    ret_list.append(portal_info)
        except Exception:
            is_get = False
        finally:
            if not is_get:
                portal_info = {
                    'RwState': 'Unknow',
                    'state': BE_BAD_UNKNOW,
                    'pool_fe': pool_fe,
                    'pool_id': pool_info['pool_id'],
                    'zqpool_id': pool_info['zqpool_id']
                }
                ret_list.append(portal_info)

    return 0, ret_list


def modify_pool_info(pool_id, option, setting_dict):
    # get the zqpool mgr info
    zqpool_info = get_zqpool_mgr_info(pool_id)
    if not zqpool_info:
        return -1, "Get the zqpool manager information failed."

    # get the pool_info
    code, result = get_pool_info(pool_id)
    if code != 0:
        return -1, f"Get the pool info failed, {result}."

    pool_info = result
    host = zqpool_info['host']
    pool_fe = pool_info['pool_fe']
    mgr_port = zqpool_info['mgr_port']

    api_dict = {
        "connects": "pool_modify_conns",
        "fe_infor": "pool_modify_fe_info",
        "be_infor": "pool_modify_be_info",
        "add_portals": "pool_add_be_db",
        "remove_portals": "pool_remove_be_db"
    }

    parmas = {
        'pool_name': pool_fe,
        'mgr_token': zqpool_info['mgr_token']
    }

    add_portal_list = list()
    remove_portal_list = list()

    if option == 'connects':
        option_parmas = {
            "be_rw_conns": "",
            "be_rd_conns": "",
            'fe_max_conns': setting_dict['fe_max_conns']
        }
        # need check the BeRwConnCount and BeRdConnCount, must larger than old
        if setting_dict['be_rw_conns'] > pool_info['BeRwConnCount']:
            option_parmas['be_rw_conns'] = setting_dict['be_rw_conns']
        if setting_dict['be_rd_conns'] > pool_info['BeRdConnCount']:
            option_parmas['be_rd_conns'] = setting_dict['be_rd_conns']
    elif option == 'fe_infor':
        option_parmas = deepcopy(setting_dict)
        # update csu_zqpool
        sql = "UPDATE csu_zqpool_pools SET pool_fe = %s WHERE pool_id = %s"
        new_pool_fe = '{0}.{1}'.format(setting_dict['fe_user'], setting_dict['fe_dbname'])
        dbapi.execute(sql, (new_pool_fe, pool_id))

        # decrypt passwd
        option_parmas['fe_passwd'] = db_encrypt.from_db_text(setting_dict['fe_passwd'])

    elif option == 'be_infor':
        option_parmas = deepcopy(setting_dict)
        option_parmas['be_passwd'] = db_encrypt.from_db_text(setting_dict['be_passwd'])

    elif option == 'portals':
        current_portals = pool_info['BePortals']
        # get the add portals
        for portal in setting_dict['portals']:
            if portal not in current_portals:
                add_portal_list.append(portal)

        # get the remove portals
        for portal in current_portals:
            if portal not in setting_dict['portals']:
                remove_portal_list.append(portal)

    # add portals, must befor remove
    if len(add_portal_list):
        option = 'add_portals'
        option_parmas = {'db_portal': ','.join(add_portal_list)}

    # remove portals
    if len(remove_portal_list):
        option = 'remove_portals'
        option_parmas = {'db_portal': ','.join(remove_portal_list)}

    # send request
    parmas.update(option_parmas)
    code, result = send_request(host, mgr_port, api_dict[option], parmas)
    if code != 0:
        return -1, result

    # update csu_zqpool_pools
    update_sql = "UPDATE csu_zqpool_pools SET conf_data = conf_data || %s WHERE pool_id=%s"
    dbapi.execute(update_sql, (json.dumps(setting_dict), pool_id))

    # update the conf file
    if setting_dict.get('portals'):
        portals_list = deepcopy(setting_dict['portals'])
        del setting_dict['portals']
        portals_str = ','.join(portals_list)
        setting_dict['be_ipport'] = portals_str
    new_conf = {
        "pools_settings": {
            pool_info["ID"]: setting_dict
        }
    }
    code, result = update_zqpool_conf(host, zqpool_info['root_path'], new_conf)
    if code != 0:
        return -1, f"Modify the configure file failed, {result}."

    return 0, result


def create_zqpool(pdict, mgr_setting_dict):
    host = pdict['host']
    root_path = pdict['root_path']

    # connect the host
    code, result = rpc_utils.get_rpc_connect(host)
    if code != 0:
        return -1, f"Connect the host({host}) failed, {result}."
    rpc = result

    try:
        # insert into csu_zqpool
        sql = """INSERT INTO csu_zqpool(zqpool_name, package_id,
            state, host, os_user, root_path, conf_data)
            VALUES(%s, %s, 0, %s, %s, %s, %s::jsonb) RETURNING zqpool_id
        """
        rows = dbapi.query(sql, (pdict['zqpool_name'], pdict['package_id'],
                        host, pdict['os_user'], pdict['root_path'], json.dumps(mgr_setting_dict)))
        if not rows:
            return -1, f"Excute sql({sql}) failed."

        # init the conf file
        code, result = init_zqpool_conf(rpc, root_path, mgr_setting_dict)
        if code != 0:
            return -1, result

    except Exception:
        return -1, f"Create zqpool with unexpected error, {traceback.format_exc()}."
    finally:
        rpc.close()

    return 0, "Create Success"


def add_zqpool(pdict):
    # read the conf file
    code, result = read_zqpool_conf(pdict['host'], pdict['root_path'])
    if code != 0:
        return -1, result
    conf_dict = result

    mgr_settings = conf_dict['mgr_settings']
    mgr_settings['mgr_token'] = db_encrypt.to_db_text(mgr_settings['mgr_token'])

    # check the zqpool is exist or not
    sql = "SELECT zqpool_id FROM csu_zqpool WHERE host = %s AND conf_data->>'mgr_port' = %s::text"
    rows = dbapi.query(sql, (pdict['host'], mgr_settings['mgr_port']))
    if rows:
        return -1, f"The zqpool(zqpool_id={rows[0]['zqpool_id']}) is aready exist."

    # insert into csu_zqpool
    settings_json = json.dumps(mgr_settings)
    sql = """INSERT INTO csu_zqpool(zqpool_name,
        package_id, state, host, os_user, root_path, conf_data)
        VALUES(%s, %s, 0, %s, %s, %s, %s::jsonb) RETURNING zqpool_id
    """
    rows = dbapi.query(sql, (pdict['zqpool_name'], pdict['package_id'],
                pdict['host'], pdict['os_user'], pdict['root_path'], settings_json))
    if not rows:
        return -1, f"Excuter sql({sql}) failed."
    zqpool_id = rows[0]["zqpool_id"]

    # insert into csu_zqpool_pools
    if conf_dict.get('pools_settings'):
        for _, setting_dict in conf_dict['pools_settings'].items():
            pool_fe = "{0}.{1}".format(setting_dict['fe_user'], setting_dict['fe_dbname'])
            # check the pool is exist or not
            sql = """SELECT pool_id FROM csu_zqpool zq, csu_zqpool_pools pool
                WHERE zq.zqpool_id = pool.zqpool_id AND pool_fe = %s AND zq.zqpool_id = %s
            """
            rows = dbapi.query(sql, (pool_fe, zqpool_id))
            if rows:
                return -1, f"The pool(pool_id={rows[0]['pool_id']}, pool_fe={pool_fe}) is aready exist."

            insert_sql = """INSERT INTO csu_zqpool_pools(zqpool_id,
                pool_fe, state, conf_data) VALUES(%s, %s, 0, %s::jsonb)
            """
            dbapi.execute(insert_sql, (zqpool_id, pool_fe, json.dumps(setting_dict)))

    return 0, "Success"


def add_pool(pool_info, zqpool_info):
    host = zqpool_info['host']
    root_path = zqpool_info['root_path']
    mgr_port = zqpool_info['conf_data']['mgr_port']
    mgr_token = zqpool_info['conf_data']['mgr_token']

    # connect the host
    code, result = rpc_utils.get_rpc_connect(host)
    if code != 0:
        return -1, f"Connect the host({host}) failed, {result}."
    rpc = result

    conf_dict = dict()
    # check the conf file is exist and read the content to dict
    try:
        conf_file = os.path.join(root_path, "zqpool.conf")
        if not rpc.os_path_exists(conf_file):
            zqpool_info['conf_data']['mgr_token'] = db_encrypt.from_db_text(mgr_token)
            code, result = init_zqpool_conf(rpc, root_path, zqpool_info['conf_data'])
            if code != 0:
                return -1, f"Init zqpool.conf failed, {result}."
        else:
            code, result = read_zqpool_conf(zqpool_info['host'], conf_file)
            if code != 0:
                return -1, f"Read the file({conf_file}) failed, {result}."
            conf_dict = result
    except Exception:
        rpc.close()
        return -1, f"Check or read the file({conf_file}) with unexpected error, {traceback.format_exc()}."

    # if the conf file is exist,read the content
    fe_id_list = [0]
    pool_is_exists = False
    if conf_dict and conf_dict.get('pools_settings'):
        for id, pool_dict in conf_dict['pools_settings'].items():
            fe_id_list.append(id)
            pool_fe = "{0}.{1}".format(pool_dict['fe_user'], pool_dict['fe_dbname'])
            if pool_fe == pool_info['pool_fe']:
                pool_is_exists = True
                pool_dict['fe_passwd'] = db_encrypt.to_db_text(pool_dict['fe_passwd'])
                pool_dict['be_passwd'] = db_encrypt.to_db_text(pool_dict['be_passwd'])
                pool_info['conf_data'] = pool_dict
                break

    # insert into csu_zqpool_pools
    insert_sql = """INSERT INTO csu_zqpool_pools(zqpool_id,
        pool_fe, state, conf_data) VALUES(%s, %s, 0, %s::jsonb) RETURNING pool_id
    """
    rows = dbapi.query(insert_sql, (zqpool_info['zqpool_id'],
                pool_info['pool_fe'], json.dumps(pool_info['conf_data'])))
    if not rows:
        return -1, f"Excute sql({insert_sql}) failed."
    pool_id = rows[0]['pool_id']

    # if pool is not exist in conf file
    if not pool_is_exists:
        pool_fe_id = max(fe_id_list) + 1

        conf_dict = {
            "pools_settings": {
                pool_fe_id: pool_info['conf_data']
            }
        }
        # write to conf file
        code, result = update_zqpool_conf(host, root_path, conf_dict)
        if code != 0:
            return -1, f"Update the zqpool.conf failed, {result}."
    else:
        pool_fe_id = max(fe_id_list)

    # send request
    api = "pool_add_pool"
    params = {
        "pool_id": pool_fe_id,
        "mgr_token": mgr_token
    }
    code, _ = send_request(host, mgr_port, api, params)
    if code != 0:
        return -1, f"Add pool(id={pool_id}) success, but send request failed, maybe zqpool is not start."

    return 0, f"Success add the pool(pool_id={pool_id})."


def update_pool_info(zqpool_id, pool_id):
    # get the zqpool_info
    sql = """SELECT zqpool_id, host, root_path, conf_data
        FROM csu_zqpool zq, csu_zqpool_pools pool
        WHERE zq.zqpool_id = pool.zqpool_id AND zq.zqpool_id = %s AND pool_id = %s
    """
    rows = dbapi.query(sql, (zqpool_id, pool_id))
    if not rows:
        return -1, f"The zqpool(id={zqpool_id}) is not exist."

    sql = """SELECT zq.zqpool_id, host, root_path,
        zq.conf_data as , pool_fe, pool.conf_data
        FROM csu_zqpool zq, csu_zqpool_pools pool
        WHERE zq.zqpool_id = pool.zqpool_id AND zq.zqpool_id = %s AND pool_id = %s
    """
    rows = dbapi.query(sql, (zqpool_id, pool_id))
    if not rows:
        return -1, f"The pool(pool_id={pool_id}, zqpool_id={zqpool_id}) is not exists."
    pool_info = rows[0]

    host = pool_info['host']
    zqpool_info = {
        "host": host,
        "zqpool_id": pool_info['zqpool_id'],
        "mgr_port": pool_info['settings']['mgr_port'],
        "mgr_token": pool_info['settings']['mgr_token']

    }
    code, result = get_pool_list([zqpool_info], filter_pool_fe=pool_info['pool_fe'])
    if code != 0:
        return -1, f"Get the pool list for zqpool(zqpool_id={pool_info['zqpool_id']}) failed, {result}."
    current_conf = conf_convert(result[0])

    # connect the host
    code, result = rpc_utils.get_rpc_connect(host)
    if code != 0:
        return -1, f"Connect the host({host}) failed, {result}."
    rpc = result

    # read the conf file to dict
    conf_file = os.path.join(pool_info['settings']['root_path'], 'zqpool.conf')
    code, result = read_zqpool_conf(rpc, conf_file)
    if code != 0:
        return -1, f"Read the configure file({conf_file}) failed, {result}."
    conf_dict = result

    # check common settings
    for setting in conf_dict['mgr_settings'].keys():
        if setting in current_conf:
            conf_dict['mgr_settings'][setting] = current_conf[setting]

    # check pool settings
    for id, setting_dict in conf_dict['pools_settings']:
        if id != current_conf['id']:
            continue
        for setting in setting_dict.keys():
            if setting in current_conf:
                conf_dict['pools_settings'][id][setting] = current_conf[setting]

    # update conf file


    # update the csu_zqpool and csu_zqpool_pools
    pass


def check_zqpool_state(zqpool_id):
    # get the zqpool info
    sql = """SELECT host,
        conf_data->'mgr_port' as mgr_port,
        conf_data->'mgr_token' as mgr_token
        FROM csu_zqpool WHERE zqpool_id = %s
    """
    rows = dbapi.query(sql, (zqpool_id, ))
    if not rows:
        return -1, f"Cant find any records for the zqpool(id={zqpool_id})."
    zqpool_info = dict(rows[0])

    zqpool_state = 1
    # test send request
    api = "get_log_level"
    params = {
        "mgr_token": zqpool_info['mgr_token']
    }
    code, _ = send_request(zqpool_info['host'], zqpool_info['mgr_port'], api, params)
    if code != 0:
        zqpool_state = 0

    # update csu_zqpool
    update_sql = "UPDATE csu_zqpool SET state = %s WHERE zqpool_id = %s"
    dbapi.execute(update_sql, (zqpool_state, zqpool_id))

    return 0, zqpool_state


def start_zqpool(zqpool_info):
    host = zqpool_info['host']
    os_user = zqpool_info['os_user']
    root_path = zqpool_info['root_path']

    # connect the host
    code, result = rpc_utils.get_rpc_connect(host)
    if code != 0:
        return -1, f"Connect the host({host}) failed, {result}."
    rpc = result

    # run start cmd
    try:
        if os_user:
            cmd = f"su - {os_user} -c 'cd {root_path} & nohup ./zqpool &'"
        else:
            cmd = f"cd {root_path} & nohup ./zqpool &"

        code = rpc.run_cmd(cmd)
        if code != 0:
            return -1, f"Run cmd({cmd}) failed."

        # sleep 3s
        time.sleep(3)
    except Exception:
        result -1, f"Run cmd with unexpected error, {traceback.format_exc()}."
    finally:
        rpc.close()

    # check the zqpool state
    code, result = check_zqpool_state(zqpool_info['zqpool_id'])
    if code != 0:
        return -1, result

    if result != 1:
        return -1, "The zqpool is not start."

    return 0, "Start zqpool success."


def get_pool_init_conf(package_id, strip_mgr=True):
    sql = "SELECT conf_init FROM csu_packages WHERE package_id = %s"
    rows = dbapi.query(sql, (package_id, ))
    if not rows:
        return -1, f"Cant find the init confgiure for the package(id={package_id})."
    conf_dict = dict(rows[0]['conf_init'])

    if strip_mgr:
        mgr_setting_list = ['mgr_port', 'mgr_addr', 'listen_port', 'listen_addr', 'mgr_token', 'exporter_port']
        setting_list = [setting for setting in conf_dict.keys()]
        for setting in setting_list:
            if setting in mgr_setting_list:
                del conf_dict[setting]
    return 0, conf_dict


def update_zqpool_conf(host, conf_file, new_conf):
    """更新zqpool配置文件

    Args:
        rpc (_type_): _description_
        conf_file (_type_): _description_
        new_conf (_type_): {
            "common_settins": {}, # 管理配置信息
            "pools_settings": {
                "1": {},          # 连接池ID对应的配置信息
                ...
            }
        }

    Returns:
        _type_: _description_
    """
    # connect the host
    code, result = rpc_utils.get_rpc_connect(host)
    if code != 0:
        return -1, f"Connect the host failed, {result}."
    rpc = result

    # check the conf_file is dir or file
    if rpc.path_is_dir(conf_file):
        conf_file = os.path.join(conf_file, 'zqpool.conf')

    # read the conf file content to dict
    code, result = read_zqpool_conf(rpc, conf_file)
    if code != 0:
        return -1, f"Read the configure file failed, {result}."
    conf_dict = result

    try:
        # update the conf dict
        if new_conf.get("mgr_settings"):
            conf_dict["mgr_settings"].update(new_conf["mgr_settings"])
            mgr_token = new_conf["mgr_settings"].get("mgr_token")
            if mgr_token:
                conf_dict["mgr_settings"]["mgr_token"] = db_encrypt.from_db_text(mgr_token)

        if new_conf.get("pools_settings"):
            for pool_id, setting_dict in new_conf["pools_settings"].items():
                if pool_id not in conf_dict["pools_settings"]:
                    conf_dict["pools_settings"][pool_id] = dict()

                # decrypt passwd
                if setting_dict.get('fe_passwd'):
                    setting_dict['fe_passwd'] = db_encrypt.from_db_text(setting_dict['fe_passwd'])
                if setting_dict.get('be_passwd'):
                    setting_dict['be_passwd'] = db_encrypt.from_db_text(setting_dict['be_passwd'])

                conf_dict["pools_settings"][pool_id].update(setting_dict)

        # conf_dict to string content
        content = conf_dict_to_content(conf_dict)

        # write the content to the conf file
        code, result = rpc.file_write(conf_file, content)
        if code != 0:
            return -1, f"Write content to the configure file failed, {result}."
    except Exception:
        return -1, f"Update the configure file {conf_file} with unexpected error, {traceback.format_exc()}."
    finally:
        rpc.close()

    return 0, "Success"


def delete_pool(pool_id):
    pool_state = 1
    # check the pool state
    code, result = get_pool_info(pool_id)
    if code != 0:
        pool_state = -1
    else:
        pool_state = result['state']
    pool_info = result

    # get zqpool info
    zqpool_info = get_zqpool_mgr_info(pool_id)
    if not zqpool_info:
        return -1, f"Cant find the pool manager information."

    # if is online, need remove from the zqpool
    if pool_state == 1:
        # send requst
        api = "pool_remove_pool"
        params_dict = {
            "pool_name": pool_info['pool_fe'],
            "mgr_token": zqpool_info['mgr_token']
        }
        code, result = send_request(zqpool_info['host'], zqpool_info['mgr_port'], api, params_dict)
        if code != 0:
            return -1, f"Remove pool({pool_info['pool_fe']}) failed, {result}."

    # connect the host
    code, result = rpc_utils.get_rpc_connect(zqpool_info['host'])
    if code != 0:
        return -1, f"Update the configure file failed: cant connect the host, {result}."
    rpc = result

    try:
        # check the conf file is exist or not
        conf_file = os.path.join(zqpool_info['root_path'], 'zqpool.conf')
        if rpc.os_path_exists(conf_file):
            # read the zqpool.conf content
            code, result = read_zqpool_conf(rpc, zqpool_info['root_path'])
            if code != 0:
                return -1, f"Read the zqpool.conf failed, {result}."
            conf_dict = result

            # del the pool
            if pool_id in conf_dict["pools_settings"]:
                del conf_dict["pools_settings"][pool_id]

            # update zqpool.conf
            content = conf_dict_to_content(conf_dict)

            # write the content to the conf file
            code, result = rpc.file_write(conf_file, content)
            if code != 0:
                return -1, f"Write content to the configure file failed, {result}."
    except Exception:
        return -1, f"Update zqpool.conf with unexpected error, {traceback.format_exc()}."
    finally:
        rpc.close()

    # update csu_zqpool_pools
    update_sql = "DELETE FROM csu_zqpool_pools WHERE pool_id = %s"
    dbapi.execute(update_sql, (pool_id, ))

    return 0, "Success"


def get_zqpool_log_content(pdict):
    zqpool_info = get_zqpool_mgr_info(pdict['zqpool_id'], True)
    if not zqpool_info:
        return -1, zqpool_info

    # read the log_file content
    log_file_path = os.path.join(zqpool_info['root_path'], 'zqpool.log')

    # connect the host
    code, result = rpc_utils.get_rpc_connect(zqpool_info["host"])
    if code != 0:
        return -1, f"Connect the host({zqpool_info['host']}) failed, {result}."
    rpc = result

    try:
        read_size = pdict["read_size"]  # bytes

        # get the file size
        code, result = rpc.os_stat(log_file_path)
        if code != 0:
            return -1, f"Get the file({log_file_path}) stat failed, {result}."
        file_size = result["st_size"]  # unit bytes

        # read the file cotent,one step read 1Kb
        offset = (pdict["page_num"] - 1) * read_size
        code, content = rpc.os_read_file(log_file_path, offset, read_size)
        if code != 0:
            return -1, f"Read the file({log_file_path}) content failed, {content}."
    except Exception:
        return -1, f"Get the log file content with unexpected error, {traceback.format_exc()}."

    # for page
    page_count = file_size // read_size
    if page_count * read_size < file_size:
        page_count += 1

    ret_dict = {
        "page_count": page_count,
        "content": str(content, encoding='utf-8')
    }

    return 0, ret_dict


def get_log_level(zqpool_id):
    zqpool_info = get_zqpool_mgr_info(zqpool_id, True)
    if not zqpool_info:
        return -1, zqpool_info

    # get the log_level
    log_leve = 'info'
    api = "get_log_level"
    params = {
        "mgr_token": zqpool_info['mgr_token']
    }
    code, result = send_request(zqpool_info['host'], zqpool_info['mgr_port'], api, params)
    if code != 0:
        return -1, result

    # result like "Current log level is info."
    log_leve = result.split()[-1].strip(".")
    return 0, log_leve


def set_log_level(zqpool_id, log_level):
    # get the zqpool_info
    zqpool_info = get_zqpool_mgr_info(zqpool_id, True)
    if not zqpool_info:
        return -1, zqpool_info

    # send request
    api = "set_log_level"
    params = {
        "loglevel": log_level,
        "mgr_toekn": zqpool_info['mgr_token']
    }
    code, result = send_request(zqpool_info['host'], zqpool_info['mgr_port'], api, params)
    if code != 0:
        return -1, result

    return 0, "Success"