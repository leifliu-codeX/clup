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
@description: WEB界面的zqpool管理后端服务处理模块
"""

import os
import json

import dbapi
import csu_http

import zqpool_helpers

from copy import deepcopy


def get_zqpool_list(req):
    params = {
        'page_num': csu_http.INT,
        'page_size': csu_http.INT,
        'filter': csu_http.MANDATORY
    }

    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    offset = (pdict['page_num'] - 1) * pdict['page_size']
    if pdict['filter'] != "":
        sql = """SELECT * FROM csu_zqpool
            WHERE zqpool_name like %s OR host like %s
            ORDER BY zqpool_id OFFSET %s LIMIT %s
        """
        rows = dbapi.query(sql, (pdict['filter'], pdict['filter'], offset, pdict['page_size']))
    else:
        sql = "SELECT * FROM csu_zqpool ORDER BY zqpool_id OFFSET %s LIMIT %s"
        rows = dbapi.query(sql, (offset, pdict['page_size']))

    ret_list = [dict(row) for row in rows]

    for zqpool_info in ret_list:
        # check the zqpool state
        code, result = zqpool_helpers.check_zqpool_state(zqpool_info['zqpool_id'])
        if code != 0:
            zqpool_info['state'] = -1
            continue
        zqpool_info['state'] = result

        # get the init conf
        code, result = zqpool_helpers.get_pool_init_conf(zqpool_info['package_id'])
        if code != 0:
            zqpool_info['conf_dict'] = None
        else:
            zqpool_info['conf_dict'] = result

    ret_data = {"total": len(ret_list), "rows": ret_list}
    return 200, json.dumps(ret_data)


def create_zqpool(req):
    params = {
        'host': csu_http.MANDATORY,
        'package_id': csu_http.INT,
        'zqpool_name': csu_http.MANDATORY,
        'root_path': csu_http.MANDATORY,
        'os_user': csu_http.MANDATORY,
        'mgr_port': csu_http.INT,
        'mgr_addr': csu_http.MANDATORY,
        'listen_port': csu_http.INT,
        'listen_addr': csu_http.MANDATORY,
        'mgr_token': csu_http.MANDATORY,
        'exporter_port': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check the zqpool is exist
    sql = "SELECT zqpool_id FROM csu_zqpool WHERE host = %s AND conf_data->>'mgr_port' = '%s'"
    rows = dbapi.query(sql, (pdict['host'], pdict['mgr_port']))
    if rows:
        return 400, f"The zqpool(id={rows[0]['zqpool_id']}, host={pdict['host']}, mgr_port={pdict['mgr_port']}) is aready exist."

    mgr_setting_dict = deepcopy(pdict)
    del mgr_setting_dict['host']
    del mgr_setting_dict['os_user']
    del mgr_setting_dict['root_path']
    del mgr_setting_dict['package_id']
    del mgr_setting_dict['zqpool_name']

    code, result = zqpool_helpers.create_zqpool(pdict, mgr_setting_dict)
    if code != 0:
        return 400, result

    return 200, "Success"


def add_zqpool(req):
    params = {
        'host': csu_http.MANDATORY,
        'package_id': csu_http.INT,
        'os_user': csu_http.MANDATORY,
        'root_path': csu_http.MANDATORY,
        'zqpool_name': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    code, result = zqpool_helpers.add_zqpool(pdict)
    if code != 0:
        return 400, result

    return 200, "Success"


def online_zqpool(req):
    params = {
        'zqpool_id': csu_http.INT
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    sql = """SELECT zqpool_id,
        host, os_user, root_path,
        conf_data->'mgr_port' as mgr_port,
        conf_data->'mgr_token' as mgr_token
        FROM csu_zqpool WHERE zqpool_id = %s
    """
    rows = dbapi.query(sql, (pdict['zqpool_id'], ))
    if not rows:
        return 400, f"Cant find any records for the zqpool(id={pdict['zqpool_id']})."
    zqpool_info = dict(rows[0])

    code, result = zqpool_helpers.start_zqpool(zqpool_info)
    if code != 0:
        return 400, result

    return 200, "Success"


def update_zqpool_info(req):
    params = {
        'zqpool_id': csu_http.INT,
        'package_id': csu_http.INT,
        'zqpool_name': csu_http.MANDATORY,
        'root_path': csu_http.MANDATORY,
        'mgr_port': csu_http.INT,
        'mgr_addr': csu_http.MANDATORY,
        'listen_port': csu_http.INT,
        'listen_addr': csu_http.MANDATORY,
        'mgr_token': csu_http.MANDATORY,
        'exporter_port': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check the zqpool is exist
    sql = "SELECT zqpool_id, host, root_path, conf_data FROM csu_zqpool WHERE zqpool_id = %s"
    rows = dbapi.query(sql, (pdict['zqpool_id'], ))
    if not rows:
        return 400, f"The zqpool(id={pdict['zqpool_id']}) is not exist."
    zqpool_info = dict(rows[0])

    new_conf_dict = deepcopy(pdict)
    del new_conf_dict['zqpool_id']
    del new_conf_dict['package_id']
    del new_conf_dict['zqpool_name']

    # try to update the conf file
    conf_file = os.path.join(zqpool_info['root_path'], 'zqpool.conf')
    if 'root_path' in new_conf_dict:
        conf_file = os.path.join(new_conf_dict['root_path'], 'zqpool.conf')
        del new_conf_dict['root_path']

    # update csu_zqpool
    zqpool_info['conf_data'].update(new_conf_dict)
    sql = "UPDATE csu_zqpool SET conf_data = %s::jsonb WHERE zqpool_id = %s"
    dbapi.execute(sql, (json.dumps(zqpool_info['conf_data']), pdict['zqpool_id']))

    # update the conf file
    code, result = zqpool_helpers.update_zqpool_conf(zqpool_info['host'],
                                conf_file, {"mgr_settings": new_conf_dict})
    if code != 0:
        return 200, f"Update csu_zqpool success, but modify the configure file({conf_file}) failed, {result}."

    return 200, "Success update zqpool information."


def delete_zqpool(req):
    params = {
        'zqpool_id': csu_http.INT
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check the zqpool has pool or not
    sql = "SELECT pool_id FROM csu_zqpool_pools WHERE zqpool_id = %s"
    rows = dbapi.query(sql, (pdict['zqpool_id'], ))
    if rows:
        pool_id_list = [str(row['pool_id']) for row in rows]
        pools_str = ','.join(pool_id_list)
        return 400, f"The zqpool has pools({pools_str}),delete the pools and try again."

    # delete from csu_zqpool
    sql = "DELETE FROM csu_zqpool WHERE zqpool_id = %s"
    dbapi.execute(sql, (pdict['zqpool_id'], ))

    return 200, "Delete Success"


def add_pool(req):
    params = {
        'zqpool_id': csu_http.INT,
        'conf_dict': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    zqpool_id = pdict['zqpool_id']

    # check the zqpool is exists or not
    sql = "SELECT zqpool_id, host, state, root_path, conf_data FROM csu_zqpool WHERE zqpool_id = %s"
    rows = dbapi.query(sql, (zqpool_id, ))
    if not rows:
        return 400, f"The zqpool(id={zqpool_id}) is not exists."
    zqpool_info = rows[0]

    # check the pool is exist or not
    pool_fe = "{0}.{1}".format(pdict['conf_dict']['fe_user'], pdict['conf_dict']['fe_dbname'])
    sql = "SELECT pool_id FROM csu_zqpool_pools WHERE pool_fe = %s AND zqpool_id = %s"
    rows = dbapi.query(sql, (pool_fe, zqpool_id))
    if rows:
        pool_id = rows[0]['pool_id']
        return 400, f"The pool(zqpool_id={zqpool_id}, pool_id={pool_id}, pool_fe={pool_fe}) is aready exist."

    # check the conf_dict
    result = zqpool_helpers.conf_sort(pdict['conf_dict'], check=True)
    if isinstance(result, str):
        return 400, f"The setting({result}) is invalid, please check."

    pool_info = {
        "pool_fe": pool_fe,
        "conf_data": result
    }

    # add pool
    code, result = zqpool_helpers.add_pool(pool_info, zqpool_info)
    if code != 0:
        return 400, f"Add pool failed, {result}."

    return 200, result


def delete_pool(req):
    params = {
        'pool_id': csu_http.INT
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    code, result = zqpool_helpers.delete_pool(pdict['pool_id'])
    if code != 0:
        return 400, result

    return 200, "Success"


def get_pool_list(req):
    """获取连接池信息

    Args:
        req (_type_): _description_

    Returns:
        _type_: _description_
    """
    params = {
        'page_num': csu_http.INT,
        'page_size': csu_http.INT,
        'filter': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    code, result = zqpool_helpers.get_pool_list(pdict['filter'])
    if code != 0:
        return 400, f"Get the pools information failed, {result}."

    if not len(result):
        return 200, json.dumps({"total": 0, "rows": list()})

    page_num = pdict['page_num']
    page_size = pdict['page_size']
    offset = (page_num - 1) * page_size
    total = len(result)
    if total > offset and total <= (offset + page_size):
        end_index = total
    else:
        end_index = offset + page_size

    ret_data = {"total": total, "rows": result[offset:end_index]}
    return 200, json.dumps(ret_data)


def modify_pool_info(req):
    params = {
        'pool_id': csu_http.INT,
        'option': csu_http.MANDATORY,
        'settings': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    # check the pool is exist or not
    sql = "SELECT pool_id FROM csu_zqpool_pools WHERE pool_id = %s"
    rows = dbapi.query(sql, (pdict['pool_id'], ))
    if not rows:
        return 400, f"The pool(id={pdict['pool_id']}) is not exist."

    # check the option
    option_list = ['connects', 'fe_infor', 'be_infor', 'portals']
    if pdict['option'] not in option_list:
        return 400, f"The option({pdict['option']}) is not in the option_list({option_list})."

    code, result = zqpool_helpers.modify_pool_info(pdict['pool_id'], pdict['option'], pdict['settings'])
    if code != 0:
        return 400, f"Modify zqpool information failed, {result}."

    return 200, result


def get_portals_list(req):
    params = {
        'page_num': csu_http.INT,
        'page_size': csu_http.INT,
        'filter': csu_http.MANDATORY
    }
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    sql = """SELECT zq.zqpool_id, pool_id, host, pool_fe,
        zq.conf_data->'mgr_port' as mgr_port,
        zq.conf_data->'mgr_token' as mgr_token
        FROM csu_zqpool zq, csu_zqpool_pools pool
        WHERE zq.zqpool_id = pool.zqpool_id
        GROUP BY (zq.zqpool_id, pool_id)
    """
    rows = dbapi.query(sql)
    if not rows:
        return 200, json.dumps({"total": 0, "rows": list()})

    pool_info_list = [dict(row) for row in rows]

    # get the zqpool info
    code, result = zqpool_helpers.get_portals_list(pool_info_list)
    if code != 0:
        return 400, f"Get zqpool information failed, {result}."

    ret_list = list()
    if pdict['filter'] != "":
        filter = pdict['filter']
        for portal_info in result:
            if "%" in filter:
                filter = filter.strip("%")
            if filter in portal_info['pool_fe'] or filter in portal_info['host']:
                ret_list.append(portal_info)
    else:
        ret_list = result

    # make page
    page_num = pdict['page_num']
    page_size = pdict['page_size']
    offset = (page_num - 1) * page_size
    total = len(result)
    if total > offset and total <= (offset + page_size):
        end_index = total
    else:
        end_index = offset + page_size

    ret_data = {"total": len(ret_list), "rows": ret_list[offset:end_index]}
    return 200, json.dumps(ret_data)


def get_zqpool_log_content(req):
    """获取zqpool日志文件内容
    """
    params = {
        "zqpool_id": csu_http.INT,
        "page_num": csu_http.INT,
        "read_size": csu_http.INT
    }
    # check request params
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    code, result = zqpool_helpers.get_zqpool_log_content(pdict)
    if code != 0:
        return 400, result

    return 200, json.dumps(result)


def get_zqpool_log_level(req):
    params = {
        "zqpool_id": csu_http.INT
    }
    # check request params
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    code, result = zqpool_helpers.get_log_level(pdict['zqpool_id'])
    if code != 0:
        return 400, result

    return 200, json.dumps({"log_level": result})


def set_zqpool_log_level(req):
    params = {
        "zqpool_id": csu_http.INT,
        "log_level": csu_http.MANDATORY
    }
    # check request params
    err_code, pdict = csu_http.parse_parms(params, req)
    if err_code != 0:
        return 400, pdict

    code, result = zqpool_helpers.set_log_level(pdict['zqpool_id'], pdict['log_level'])
    if code != 0:
        return 400, f"Set log level failed, {result}."

    return 200, f"Success set log level to {pdict['log_level']}."