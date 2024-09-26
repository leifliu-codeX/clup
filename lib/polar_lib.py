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

import json
import os
import time
import traceback

import cluster_state
import dao
import dbapi
import general_task_mgr
import pg_db_lib
import pg_utils
import rpc_utils


class PolarCommon:
    def __init__(self, rpc, node_info, pfs_info=None):
        self.rpc = rpc
        if pfs_info:
            self.pfs_info = pfs_info
        self.node_info = node_info
        self.port = node_info["port"]
        self.pgdata = node_info["pgdata"]
        self.os_user = node_info["os_user"]
        self.db_user = node_info["db_user"]
        self.pg_bin_path = node_info["pg_bin_path"]

    # 创建os_user
    def create_os_user(self):
        if 'os_uid' not in self.node_info:
            if self.os_user == 'halo':
                os_uid = 1000
            else:
                os_uid = 701
        else:
            os_uid = self.node_info['os_uid']
        err_code, err_msg = pg_db_lib.pg_init_os_user(self.rpc, self.node_info["os_user"], os_uid)
        return err_code, err_msg

    # 设置环境变量
    def edit_bashrc(self):
        """[summary]
        args:
            - rpc
            - kwargs dict
        Returns:
            [type]: [description]
        """
        err_code, err_msg = self.rpc.pwd_getpwnam(self.os_user)
        if err_code != 0:
            return err_code, err_msg
        pwd_dict = err_msg
        os_user_home = pwd_dict['pw_dir']
        err_code, err_msg = pg_db_lib.pg_init_bashrc(self.rpc, os_user_home, self.pg_bin_path, self.pgdata, self.port)
        return err_code, err_msg

    # 初始化数据库
    def init_db(self, db_pass, wal_segsize=16):
        param = f'{self.pg_bin_path}/initdb --wal-segsize={wal_segsize} --auth-local=peer --auth-host=md5 ' \
            f'--username="{self.db_user}" --pwfile=<(echo "{db_pass}") -D {self.pgdata}'
        cmd_initdb = f""" su - {self.os_user} -c '{param}' """
        err_code, err_msg, _out_msg = self.rpc.run_cmd_result(cmd_initdb)
        return err_code, err_msg

    # 执行polar-initdb
    def polar_initdb(self, polar_version=11):
        """执行polar-initdb
        """
        pfs_disk_name = self.pfs_info["pfs_disk_name"]
        polar_datadir = self.pfs_info["polar_datadir"]
        cmd = f"{self.pg_bin_path}/polar-initdb.sh {self.pgdata}/ /{pfs_disk_name}/{polar_datadir}/"
        # polardb15 的polar-initdb.sh要求携带primary|replica
        if polar_version > 11:
            cmd = f"{cmd} primary"
        err_code, err_msg, _out_msg = self.rpc.run_cmd_result(cmd)
        return err_code, err_msg

    # 修改postgresql.conf配置文件
    def edit_postgresql_conf(self, setting_dict):
        pfs_disk_name = self.pfs_info["pfs_disk_name"]
        polar_datadir = self.pfs_info["polar_datadir"]
        # 当打开归档后,wal_level不能是minimal
        if 'archive_mode' in setting_dict:
            if setting_dict.get('archive_mode') == 'on':
                if 'wal_level' in setting_dict:
                    if setting_dict['wal_level'] == 'minimal':
                        setting_dict['wal_level'] = 'replica'

        try:
            setting_dict["polar_hostid"] = self.node_info["polar_hostid"]
            setting_dict['polar_vfs.localfs_mode'] = "off"
            setting_dict['polar_enable_shared_storage_mode'] = "on"
            setting_dict["polar_disk_name"] = pfs_disk_name
            setting_dict["polar_datadir"] = f"/{pfs_disk_name}/{polar_datadir}/"
            setting_dict['polar_storage_cluster_name'] = setting_dict.get("polar_storage_cluster_name", "disk")

            postgresql_conf = f'{self.pgdata}/postgresql.conf'
            content = ''
            key_words = ['on', 'off']
            for key, value in setting_dict.items():
                value = str(value)
                if value[0] == "'":
                    args = f"{key} = {value}\n"
                    content = content + args
                    continue
                # 如果值是数字类型的话就转为整形
                if value.isdigit():
                    value = int(value)
                    args = f"{key} = {value}\n"
                elif value in key_words:
                    args = f"{key} = {value}\n"
                else:
                    args = f"{key} = '{value}'\n"
                content = content + args
            # 在配置文件尾部追加参数
            # offset = self.rpc.get_file_size(postgresql_conf)
            self.rpc.append_file(postgresql_conf, content)
        except Exception as e:
            err_code = -1
            err_msg = str(e)
            return err_code, err_msg
        return 0, 'Successfully modified the postgresql.conf file.'

    # 修改pg_hba.conf身份认证
    def edit_hba_conf(self, polar_type):
        hba_file = f'{self.pgdata}/pg_hba.conf'
        # reader节点的话这里无需添加下面这行，在copy_conf_to_reader这步已经从主库上获取并写入过了
        if polar_type == "master":
            content = """\nhost replication all all md5\nhost all all all md5"""
            err_code, err_msg = self.rpc.append_file(hba_file, content)
            if err_code != 0:
                return err_code, err_msg

        # # 如果数据库用户名不等于操作系统用户名,需要在pg_hba.conf加本地的用户映射以便于本地不需要密码旧可以登录
        if self.os_user != self.db_user:
            ci_dict = {
                r"^local\s+all\s+all\s+peer$": f"local\tall\tall\t\tpeer map={self.db_user}",
                r"^local\s+replication\s+all\s+peer$": f"local\treplication\tall\t\tpeer map={self.db_user}"
            }
            self.rpc.modify_config_type2(hba_file, ci_dict, is_backup=False)
            pg_ident_conf_file = f'{self.pgdata}/pg_ident.conf'
            content = f"{self.db_user}\t{self.os_user}\t{self.db_user}"
            tag_line = '# ====== Add by clup map os user'
            self.rpc.config_file_set_tag_content(pg_ident_conf_file, tag_line, content)

        return 0, 'Successfully configured pg_hba.conf.'

    # 添加插件
    def create_extension(self, setting_dict):
        plug_str = setting_dict.get('shared_preload_libraries', "'pg_stat_statements'")
        plug_list = plug_str.replace("'", '').split(',')
        err_code = err_msg = ''
        for plug in plug_list:
            db_name = 'template1'
            sql = f"CREATE EXTENSION {plug}"
            cmd = f"""su - {self.os_user} -c "psql -U {self.db_user} -p {self.port} -d {db_name}  -c '{sql}' " """
            err_code, err_msg, _out_msg = self.rpc.run_cmd_result(cmd)
            if err_code != 0:
                err_msg = f"run cmd: {cmd} failed: {err_msg}"
                return err_code, err_msg
        return 0, f'Plugin({plug_str}) added successfully.'

    # 启动pfsdaemon
    def start_pfsdaemon(self):
        pfs_disk_name = self.pfs_info["pfs_disk_name"]
        pfsdaemon_params = self.pfs_info["pfsdaemon_params"]
        cmd_start_pfsdaemon = f'/usr/local/polarstore/pfsd/bin/start_pfsd.sh -p {pfs_disk_name} {pfsdaemon_params}'
        err_code = self.rpc.run_cmd(cmd_start_pfsdaemon)
        return err_code, ''

    # 创建pfs共享文件夹
    def mk_share_dir(self):
        pfs_disk_name = self.pfs_info["pfs_disk_name"]
        polar_datadir = self.pfs_info["polar_datadir"]
        cmd_mkdir = f'pfs -C disk mkdir /{pfs_disk_name}/{polar_datadir}'
        err_code, err_msg, _out_msg = self.rpc.run_cmd_result(cmd_mkdir)
        if err_code != 0:
            if err_code == 255:
                return err_code, f"The folder(/{pfs_disk_name}/{polar_datadir}) already exists, please check before proceeding!"
            return err_code, err_msg
        return err_code, err_msg

    # 执行pg_basebackup
    def polar_basebackup(self, task_id, msg_prefix, up_db_info):
        up_db_port = up_db_info["port"]
        repl_user = up_db_info['repl_user']
        up_db_repl_ip = up_db_info["repl_ip"]

        other_param = self.node_info.get('other_param')
        other_param = ' -P -Xs ' if not other_param else other_param

        param = f'polar_basebackup -h{up_db_repl_ip} -p{up_db_port} -U{repl_user} -D {self.pgdata} {other_param}'
        cmd = f"""su  - {self.os_user} -c "{param}" """
        cmd_id = self.rpc.run_long_term_cmd(cmd, output_qsize=10, output_timeout=600)
        state = 0
        while state == 0:
            state, err_code, err_msg, stdout_lines, stderr_lines = self.rpc.get_long_term_cmd_state(cmd_id)
            has_output = False
            if stdout_lines:
                has_output = True
                for line in stdout_lines:
                    general_task_mgr.log_info(task_id, f"{msg_prefix}: {line}")
            if stderr_lines:
                has_output = True
                for line in stderr_lines:
                    if "Password" in line:
                        general_task_mgr.log_info(task_id, f"{msg_prefix}: Streaming replication password configuration error, please check before proceeding.")
                        state = -1
                        break
                    else:
                        general_task_mgr.log_info(task_id, f"{msg_prefix}: {line}")
            if not has_output:
                time.sleep(1)
            if state < 0:
                err_code = -1
                return err_code, err_msg
        self.rpc.remove_long_term_cmd(cmd_id)
        return 0, 'polar_basebackup executed successfully'


def get_polar_type(db_id):
    """获取polardb数据库的类型: master共享存储主库、reader节点共享存储只读库、standby共享存储的本地存储备库
    :param db_id:
    :return: 根据db_id返回polar数据库类型; master主节点,共享存储reader只读,standby本地存储节点;
    """
    sql = "SELECT db_detail->'polar_type' as polar_type FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (db_id,))
    if not rows:
        return None
    return rows[0]["polar_type"]


def update_polar_type(db_id, polar_type):
    """更新polar_type
    """
    try:
        update_dict = json.dumps({"polar_type": polar_type})
        sql = "UPDATE clup_db SET db_detail = db_detail || (%s::jsonb) WHERE db_id = %s"
        dbapi.execute(sql, (update_dict, db_id))
    except Exception as e:
        return -1, f"Failed to update 'polar_type': {repr(e)}"
    return 0, ""


def get_db_pfs_info(db_id):
    """获取polardb pfs的相关信息
    :param db_id:
    :return 根据db_id返回pfs相关信息
    """
    # 根据db_id返回pfs相关信息
    sql = "select db_detail->'pfs_disk_name' as pfs_disk_name, \
        db_detail->'pfsdaemon_params' as pfsdaemon_params, \
        db_detail->'polar_datadir' as polar_datadir" \
        "  from clup_db where db_id=%s"
    rows = dbapi.query(sql, (db_id,))
    if not len(rows):
        return None
    return rows[0]


def start_pfs(host, db_id=None, pfs_dict=None):
    """启动pfs
    """
    if db_id:
        pfs_dict = get_db_pfs_info(db_id)
    if not pfs_dict:
        return -1, "No information related to pfs was found for this database."
    try:
        rpc = None
        pfsdaemon_params = pfs_dict["pfsdaemon_params"]
        pfs_disk_name = pfs_dict["pfs_disk_name"]
        cmd_start_pfsdaemon = f'/usr/local/polarstore/pfsd/bin/start_pfsd.sh -p {pfs_disk_name} {pfsdaemon_params} '
        # 连接主机执行命令
        err_code, err_msg = rpc_utils.get_rpc_connect(host)
        if err_code != 0:
            err_msg = f"Connect to host({host}) failed"
            return err_code, err_msg
        rpc = err_msg
        err_code = rpc.run_cmd(cmd_start_pfsdaemon)
        if err_code != 0 and err_code != 1:
            return err_code, "Start of pfsdaemon failed"
    except Exception:
        return -1, traceback.format_exc()
    finally:
        if rpc:
            rpc.close()
    return 0, f"start host={host} pfs success"


def stop_pfs(host, db_id=None, pfs_dict=None):
    """停止pfs
    """
    if db_id:
        pfs_dict = get_db_pfs_info(db_id)
    if not pfs_dict:
        return -1, "There is no information related to pfs in the database, Please stop pfsdaemon manually."
    try:
        rpc = None
        pfs_disk_name = pfs_dict["pfs_disk_name"]
        if pfs_disk_name:
            cmd_stop_pfsdaemon = f'/usr/local/polarstore/pfsd/bin/stop_pfsd.sh {pfs_disk_name}'
            # 连接主机执行命令
            err_code, err_msg = rpc_utils.get_rpc_connect(host)
            if err_code != 0:
                err_msg = f"Connect to host({host}) failed"
                return err_code, err_msg
            rpc = err_msg
            err_code, err_msg, _out_msg = rpc.run_cmd_result(cmd_stop_pfsdaemon)
            if err_code != 0:
                return err_code, err_msg
            return 0, f'stop host={host} pfs success'
    except Exception:
        return -1, traceback.format_exc()
    finally:
        if rpc:
            rpc.close()
    return 0, "no pfs running"


def get_up_db_info(up_db_id):
    sql = "SELECT db_id, up_db_id, state, host, cluster_id, port, pgdata, db_type, repl_app_name, repl_ip," \
        " db_detail->'wal_segsize' as wal_segsize, db_detail->>'delay' as delay," \
        " db_detail->>'db_user' as db_user, db_detail->>'db_pass' as db_pass," \
        " db_detail->>'os_user' as os_user, db_detail->>'instance_type' as instance_type,"\
        " db_detail->'repl_ip' as repl_ip_in_detail, db_detail->'repl_user' as repl_user, "\
        " db_detail->'repl_pass' as repl_pass, db_detail->>'pfs_disk_name' as pfs_disk_name," \
        " db_detail->>'polar_datadir' as polar_datadir, db_detail->>'pfsdaemon_params' as pfsdaemon_params" \
        " FROM clup_db WHERE db_id = %s "
    rows = dbapi.query(sql, (up_db_id, ))
    if not rows:
        return None
    return rows[0]


def init_polar_reader_old(rpc, pgdata, up_db_host, up_db_pgdata, polar_version=11):
    """简化版搭建RO节点
    """
    try:
        master_rpc = None
        dirs_list = [
            'base', 'global', 'pg_csnlog', 'pg_dynshmem',
            'pg_log', 'pg_logindex', 'pg_logical', 'pg_logical/snapshots',
            'pg_logical/mappings', 'pg_multixact', 'pg_notify', 'pg_replslot',
            'pg_serial', 'pg_snapshots', 'pg_stat', 'pg_stat_tmp', 'pg_subtrans',
            'pg_tblspc', 'pg_twophase', 'polar_cache_trash', 'polar_fullpage', 'polar_rel_size_cache'
        ]
        # 创建目录
        dirs = " ".join(dirs_list)
        cmd = f"cd {pgdata} && mkdir {dirs}"
        err_code, err_msg, out_msg = rpc.run_cmd_result(cmd)
        if err_code != 0:
            return -1, f"Create directory failed: {err_msg},{out_msg}"

        # 获取pgdata的属性
        err_code, err_msg = rpc.os_stat(pgdata)
        if err_code != 0:
            return -1, f"Get directory({pgdata}) properties error:{err_msg}"
        st_dict = err_msg

        # 把创建的文件夹属主改成与pgdata相同,修改权限为700
        chown_cmd = f"cd {pgdata} && chown -R {st_dict['st_uid']}:{st_dict['st_gid']} {dirs}"
        err_code, err_msg, out_msg = rpc.run_cmd_result(chown_cmd)
        if err_code != 0:
            return -1, f"chown dirs error: {err_msg}, {out_msg}"
        chmod_cmd = f"cd {pgdata} && chmod 700 {dirs}"
        err_code, err_msg, out_msg = rpc.run_cmd_result(chmod_cmd)
        if err_code != 0:
            return -1, f"chmod dirs error: {err_msg}, {out_msg}"

        # 获取主库的postgresql.conf文件内容
        err_code, err_msg = rpc_utils.get_rpc_connect(up_db_host)
        if err_code != 0:
            return -1, f"Failed to get the configuration file of the master node:{err_msg}"
        master_rpc = err_msg

        # 获取上级库的postgresql.conf文件内容
        postgresql_conf = f"{up_db_pgdata}/postgresql.conf"
        err_code, err_msg = master_rpc.read_config_file_items(postgresql_conf, [], read_all=True)
        if err_code != 0:
            return -1, f"Failed to get the file({up_db_pgdata}) contents from the superior database({up_db_host}):{err_msg}"
        setting_dict = err_msg
        # 创建一个postgresql.conf空文件
        reader_postgresql_conf = f"{pgdata}/postgresql.conf"
        err_code, err_msg = rpc.os_write_file(reader_postgresql_conf, 0, b"")
        if err_code != 0:
            return -1, err_msg
        # 写入新的参数
        rpc.modify_config_type1(reader_postgresql_conf, setting_dict, is_backup=False)

        # 配置pg_hba.conf文件内容
        reader_pg_hba_conf = f"{pgdata}/pg_hba.conf"
        hba_content = """
                # TYPE  DATABASE        USER            ADDRESS                 METHOD

                # "local" is for Unix domain socket connections only
                local   all             all                                     trust
                # IPv4 local connections:
                host    all             all             127.0.0.1/32            trust
                # IPv6 local connections:
                host    all             all             ::1/128                 trust
                # Allow replication connections from localhost, by a user with the
                # replication privilege.
                local   replication     all                                     trust
                host    replication     all             127.0.0.1/32            trust
                host    replication     all             ::1/128                 trust
            """
        err_code, err_msg = rpc.file_write(reader_pg_hba_conf, hba_content)
        if err_code != 0:
            return -1, err_msg

        # 创建一个PG_VERSION
        pg_version_file = f"{pgdata}/PG_VERSION"
        err_code, err_msg = rpc.os_write_file(pg_version_file, 0, str(polar_version).encode())
        if err_code != 0:
            return -1, err_msg

        # 创建一个pg_ident.conf空文件
        reader_pg_ident_conf = f"{pgdata}/pg_ident.conf"
        err_code, err_msg = rpc.os_write_file(reader_pg_ident_conf, 0, b"")
        if err_code != 0:
            return -1, err_msg

        # 创建一个postgresql.auto.conf空文件
        reader_pg_auto_conf = f"{pgdata}/postgresql.auto.conf"
        err_code, err_msg = rpc.os_write_file(reader_pg_auto_conf, 0, b"")
        if err_code != 0:
            return -1, err_msg

        # 创建一个polar_dma.conf空文件
        reader_polar_dma_conf = f"{pgdata}/polar_dma.conf"
        err_code, err_msg = rpc.os_write_file(reader_polar_dma_conf, 0, b"")
        if err_code != 0:
            return -1, err_msg

        # 修改文件属主及权限
        files = f"{reader_postgresql_conf} {reader_pg_hba_conf} {pg_version_file} " \
                f"{reader_pg_ident_conf} {reader_pg_auto_conf} {reader_polar_dma_conf}"
        chown_cmd = f"cd {pgdata} && chown -R {st_dict['st_uid']}:{st_dict['st_gid']} {files}"
        err_code, err_msg, out_msg = rpc.run_cmd_result(chown_cmd)
        if err_code != 0:
            return -1, f"chown {files} error: {err_msg}, {out_msg}"
        chmod_cmd = f"cd {pgdata} && chmod 600 {files}"
        err_code, err_msg, out_msg = rpc.run_cmd_result(chmod_cmd)
        if err_code != 0:
            return -1, f"chmod {files} error: {err_msg}, {out_msg}"

        return 0, ''
    except Exception as e:
        return -1, f"Configuration of 'reader' node directory and configuration file failed:{str(e)}"
    finally:
        if master_rpc:
            master_rpc.close()


def copy_conf_to_reader(rpc, pgdata, up_db_host, up_db_pgdata):
    """配置reader节点
    """
    try:
        master_rpc = None
        # connect the updb host
        code, result = rpc_utils.get_rpc_connect(up_db_host)
        if code != 0:
            return -1, f"Failed to get the configuration file of the master node: {result}."
        master_rpc = result

        # 获取上级库的文件内容
        file_list = ["postgresql.auto.conf", "postgresql.conf", "pg_hba.conf", "pg_ident.conf"]
        for file in file_list:
            source_file = f"{up_db_pgdata}/{file}"
            if not master_rpc.os_path_exists(source_file):
                continue

            code, result = master_rpc.file_read(source_file)
            if code != 0:
                return -1, f"Failed to get the file({up_db_pgdata}) contents from the superior database({up_db_host}): {result}."
            file_content = result

            # 创建一个空文件
            # err_code, err_msg = rpc.os_write_file(target_file, 0, b"")
            # if err_code != 0:
            #     return -1, err_msg

            # 写入配置信息
            target_file = f"{pgdata}/{file}"
            code, result = rpc.file_write(target_file, file_content, mode='w')
            if code != 0:
                return -1, f"Write the content to file({target_file}) failed, {result}."

        return 0, ''
    except Exception as e:
        return -1, f"Configuration of 'reader' node directory and configuration file failed:{str(e)}"
    finally:
        if master_rpc:
            master_rpc.close()


def edit_reader_postgresql_conf(rpc, node_info):
    """配置只读节点的postgresql.conf
    """
    postgresql_conf = f"{node_info['pgdata']}/postgresql.conf"

    try:
        reader_setting_dict = {}
        reader_setting_dict['port'] = node_info["port"]
        reader_setting_dict['polar_hostid'] = node_info["polar_hostid"]
        reader_setting_dict['synchronous_standby_names'] = f"""'csu_replica{node_info["db_id"]}'"""

        setting_list = [setting for setting in reader_setting_dict.keys()]
        err_code, err_msg = rpc.read_config_file_items(postgresql_conf, setting_list)
        if err_code != 0:
            return -1, err_msg

        setting_dict = err_msg
        for key, value in reader_setting_dict.items():
            setting_dict[key] = value
        # 写入新的参数
        rpc.modify_config_type1(postgresql_conf, setting_dict, is_backup=False)

    except Exception:
        return -1, traceback.format_exc()
    return 0, "Successfully modified 'postgresql.conf' file"


def edit_standby_postgresql_conf(rpc, node_info):
    """配置备库的postgresql.conf
    """
    pgdata = node_info["pgdata"]

    try:
        polar_datadir = f"{pgdata}/polar_shared_data"
        standby_setting_dict = {
            "port": node_info["port"],
            "polar_hostid": node_info["polar_hostid"],
            "polar_vfs.localfs_mode": 'true',
            "polar_datadir": f"'file-dio://{polar_datadir}'",
            "synchronous_standby_names": f"""'csu_standby{ node_info["db_id"] }'"""
        }
        postgresql_conf = f'{pgdata}/postgresql.conf'
        setting_list = [setting for setting in standby_setting_dict.keys()]
        err_code, err_msg = rpc.read_config_file_items(postgresql_conf, setting_list)
        if err_code != 0:
            return -1, err_msg

        setting_dict = err_msg
        for key, value in standby_setting_dict.items():
            setting_dict[key] = value
        # 写入新的参数
        rpc.modify_config_type1(postgresql_conf, setting_dict, is_backup=False)
    except Exception:
        return -1, traceback.format_exc()
    return 0, "Successfully modified postgresql.conf file."


def edit_standby_conf(rpc, db_id, pgdata, repl_app_name, repl_user, up_db_repl_ip, up_db_port, polar_version=11):
    """创建standby节点recovery.conf
    """
    primary_slot_name = f"csu_standby{db_id}"
    primary_conninfo = (f"user={repl_user} host={up_db_repl_ip} port={up_db_port} sslmode=prefer "
        f"sslcompression=0 application_name={repl_app_name}"
    )
    content = f"recovery_target_timeline='latest'\nprimary_slot_name='{primary_slot_name}'\nprimary_conninfo='{primary_conninfo}'"
    if polar_version == 11:
        content = f"standby_mode='on'\n{content}"
        target_file = f'{pgdata}/recovery.conf'
    elif polar_version > 11:
        target_file = f"{pgdata}/postgresql.conf"
    else:
        return -1, f"Invalid polardb version({polar_version})."

    try:
        err_code, err_msg = rpc.file_write(target_file, content, mode='a+')
        if err_code != 0:
            err_msg = f"write file {target_file} error: {err_msg}"
            return err_code, err_msg

        # 如果是15及以上的版本，则需要创建standby.signal文件
        if polar_version > 11:
            cmd = f"touch {pgdata}/standby.signal"
            code = rpc.run_cmd(cmd)
            if code != 0:
                return -1, f"Run cmd({cmd}) failed."
            target_file = f"{pgdata}/standby.signal"

        # 获取postgresql.conf文件属主
        example_file = f"{pgdata}/postgresql.auto.conf"
        err_code, err_msg = rpc.os_stat(example_file)
        if err_code != 0:
            return err_code, err_msg
        st_dict = err_msg

        # 修改文件属主
        err_code, err_msg = rpc.os_chown(target_file, st_dict['st_uid'], st_dict['st_gid'])
        if err_code != 0:
            err_msg = f"chown file {target_file} error: {err_msg}"
            return err_code, err_msg

        err_code, err_msg = rpc.os_chmod(target_file, 0o600)
        if err_code != 0:
            err_msg = f"chmod file {target_file} error: {err_msg}"
            return err_code, err_msg
    except Exception as e:
        return -1, f"Write the standby information to file({target_file}) with unexpected error, {str(e)}."

    return 0, err_msg


def edit_reader_conf(rpc, db_id, pgdata, repl_app_name, repl_user, up_db_repl_ip, up_db_port, polar_version=11):
    """创建reader节点recovery.conf
    """
    primary_slot_name = f"csu_replica{db_id}"
    primary_conninfo = (f"user={repl_user} host={up_db_repl_ip} port={up_db_port} sslmode=prefer "
        f"sslcompression=0 application_name={repl_app_name}"
    )
    content = f"polar_replica='on'\nrecovery_target_timeline='latest'\nprimary_slot_name='{primary_slot_name}'\nprimary_conninfo='{primary_conninfo}'"

    try:
        target_file = f'{pgdata}/recovery.conf'
        if polar_version > 11:
            target_file = f"{pgdata}/postgresql.conf"

        err_code, err_msg = rpc.file_write(target_file, content, mode='a+')
        if err_code != 0:
            err_msg = f"write file {target_file} error: {err_msg}"
            return err_code, err_msg

        # 如果是15及以上的版本，则需要创建standby.signal文件
        if polar_version > 11:
            cmd = f"touch {pgdata}/standby.signal"
            code = rpc.run_cmd(cmd)
            if code != 0:
                return -1, f"Run cmd({cmd}) failed."
            target_file = f"{pgdata}/standby.signal"

        # 获取postgresql.conf文件属主
        example_file = f"{pgdata}/postgresql.auto.conf"
        err_code, err_msg = rpc.os_stat(example_file)
        if err_code != 0:
            return err_code, err_msg
        st_dict = err_msg

        # 修改文件属主
        err_code, err_msg = rpc.os_chown(target_file, st_dict['st_uid'], st_dict['st_gid'])
        if err_code != 0:
            err_msg = f"chown file {target_file} error: {err_msg}"
            return err_code, err_msg

        err_code, err_msg = rpc.os_chmod(target_file, 0o600)
        if err_code != 0:
            err_msg = f"chmod file {target_file} error: {err_msg}"
            return err_code, err_msg
    except Exception:
        return -1, traceback.format_exc()
    return err_code, err_msg


def set_recovery_conf(db_id, up_db_id=None):
    """配置备库的复制信息

    Args:
        rpc (_type_): _description_
        db_id (_type_): _description_
    """
    # 获取当前库的信息
    db_info_list = dao.get_db_info(db_id)
    db_info = db_info_list[0]

    # 获取上级库的流复制信息
    sql = "SELECT repl_ip, port, pgdata, repl_app_name, db_detail->'repl_user' as repl_user FROM clup_db WHERE db_id=%s"
    if not up_db_id:
        up_db_id = db_info["up_db_id"]
    rows = dbapi.query(sql, (up_db_id, ))
    if not rows:
        return -1, f"Cant get the superior instance information for the cluster(cluster_id={db_info['cluster_id']})."
    up_db_repl_info = rows[0]

    # setting_dict 存放要配置的参数信息
    setting_dict = {"recovery_target_timeline": "'latest'"}

    # 生成primary_conninfo字符串
    up_db_port = up_db_repl_info["port"]
    up_db_repl_ip = up_db_repl_info["repl_ip"]
    up_db_repl_user = up_db_repl_info["repl_user"]
    repl_app_name = db_info.get("repl_app_name", db_info["repl_ip"])
    setting_dict["primary_conninfo"] = f"'user={up_db_repl_user} host={up_db_repl_ip} port={up_db_port} sslmode=prefer sslcompression=0 application_name={repl_app_name}'"

    # reader节点和standby节点写入的信息不一样
    polar_type = db_info["polar_type"]
    if polar_type == "reader":
        setting_dict["polar_replica"] = "'on'"
        setting_dict["primary_slot_name"] = f"'csu_replica{db_id}'"
        # primary_slot_name = f"csu_replica{db_id}"
        # content = f"polar_replica='on'\nrecovery_target_timeline='latest'\nprimary_slot_name='{primary_slot_name}'\nprimary_conninfo='{primary_conninfo}'"
    elif polar_type == "standby":
        setting_dict["standby_mode"] = "'on'"
        setting_dict["primary_slot_name"] = f"'csu_standby{db_id}'"
        # primary_slot_name = f"csu_standby{db_id}"
        # content = f"recovery_target_timeline='latest'\nprimary_slot_name='{primary_slot_name}'\nprimary_conninfo='{primary_conninfo}'"

    # 获取rpc连接
    code, result = rpc_utils.get_rpc_connect(db_info["host"])
    if code != 0:
        return -1, f"Connect the host({db_info['host']}) failed, {result}."
    rpc = result

    # polardb11之后的版本，写入的文件不一样
    pgdata = db_info["pgdata"]
    recovery_file = f"{pgdata}/recovery.conf"
    polar_version = int(db_info["version"].split(".")[0])
    if polar_version == 11:
        target_file = f"{pgdata}/recovery.conf"
    else:
        # 先读取postgresql.auto.conf,如果其中有配置项primary_conninfo,则使用postgresql.auto.conf
        target_file = f"{pgdata}/postgresql.auto.conf"
        code, item_dict = rpc.read_config_file_items(target_file, ['primary_conninfo'])
        if code != 0 or not item_dict.get('primary_conninfo'):
            target_file = f"{pgdata}/postgresql.conf"
        # 如果是15及以上的版本，则需要创建standby.signal文件
        recovery_file = f"{pgdata}/standby.signal"
    try:
        if not rpc.os_path_exists(recovery_file):
            # 新建一个空文件
            code, result = rpc.os_write_file(recovery_file, 0, b"")
            if code != 0:
                return -1, f"Create the file({recovery_file}) failed, {result}."

        # 将配置信息写入文件
        rpc.modify_config_type1(target_file, setting_dict, deli_type=1, is_backup=False)

        # 获取postgresql.conf文件属主
        example_file = f"{pgdata}/postgresql.conf"
        code, result = rpc.os_stat(example_file)
        if code != 0:
            return -1, result
        st_dict = result

        # 修改文件属主
        code, result = rpc.os_chown(recovery_file, st_dict['st_uid'], st_dict['st_gid'])
        if code != 0:
            return -1, f"Chown file {recovery_file} error: {result}."
        # 修改文件权限
        code, result = rpc.os_chmod(recovery_file, 0o600)
        if code != 0:
            return -1, f"Chmod file {recovery_file} error: {result}."

    except Exception:
        return -1, f"Modify the reocvery information with unexpected error, {traceback.format_exc()}."
    finally:
        if rpc:
            rpc.close()

    return 0, "Success"


def create_replication_slot(db_id):
    """在上级库中创建复制槽
    """

    # get the instance info
    sql = "SELECT cluster_id, up_db_id, db_detail->'polar_type' as polar_type FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (db_id, ))
    if not rows:
        return -1, f"Cant find any records for the instance(db_id={db_id})."
    node_info = dict(rows[0])

    # 查询slot_name是否存在，存在则删除
    polar_type = node_info["polar_type"]
    if polar_type == "standby":
        slot_name = f"csu_standby{db_id}"
    else:
        slot_name = f"csu_replica{db_id}"

    try:
        # 获取上级库的信息
        up_db_info = dao.get_db_conn_info(node_info['up_db_id'])
        if not up_db_info:
            return -1, f"Get the instance database({node_info['up_db_id']}) connect information failed."

        # get the database connect
        db_conn = dao.get_db_conn(up_db_info)
        if not db_conn:
            return -1, f"Connect the database instance(host={up_db_info['host']},port={up_db_info['port']}) failed."

        # 查询当前的slot_name是否已经存在,已经存在的话就不需要创建了
        sql = "SELECT slot_name FROM pg_replication_slots WHERE slot_name=%s"
        rows = dbapi.conn_query(db_conn, sql, (slot_name, ))
        if not rows:
            sql = f"SELECT pg_create_physical_replication_slot('{slot_name}');"
            dbapi.conn_execute(db_conn, sql)

    except Exception:
        return -1, f"Create the replication slot with unexpected error, {traceback.format_exc()}."

    return 0, "Success"


def delete_replication_slot(db_id, is_self=False):
    """删除db_id对应的复制槽, is_self为False时连接上级库删除
    """
    # get the instance info
    sql = "SELECT cluster_id, up_db_id, db_detail->'polar_type' as polar_type FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (db_id, ))
    if not rows:
        return -1, f"Cant find any records for the instance(db_id={db_id})."
    node_info = dict(rows[0])

    polar_type = node_info["polar_type"]
    if polar_type == "standby":
        slot_name = f"csu_standby{db_id}"
    else:
        slot_name = f"csu_replica{db_id}"

    try:
        conn_db_id = db_id
        if not is_self:
            conn_db_id = node_info["up_db_id"]

        db_info = dao.get_db_conn_info(conn_db_id)
        if not db_info:
            return -1, f"Get the instance database({conn_db_id}) connect information failed."

        # get the database connect
        db_conn = dao.get_db_conn(db_info)
        if not db_conn:
            return -1, f"Connect the database instance(host={db_info['host']},port={db_info['port']}) failed."

        sql = "SELECT slot_name FROM pg_replication_slots WHERE slot_name=%s"
        rows = dbapi.conn_query(db_conn, sql, (slot_name, ))
        if rows:
            db_conn = dao.get_db_conn(db_info)
            sql = f"SELECT pg_drop_replication_slot('{slot_name}');"
            dbapi.conn_execute(db_conn, sql)

    except Exception:
        return -1, f"Delete the replication slot with unexpected error, {traceback.format_exc()}."

    return 0, "The replication slot in the primary database has been deleted."


def mv_recovery(db_id):
    """将新主库的recovery.conf 改名为recovery.done
    """
    query = f"SELECT db_id,host,pgdata FROM clup_db WHERE db_id={db_id}"
    rows = dbapi.query(query)
    if not len(rows):
        return -1, f"No information related to the database(db_id={db_id}) was found."
    try:
        pgdata = rows[0]['pgdata']
        host = rows[0]['host']
        rpc = None
        err_code, err_msg = rpc_utils.get_rpc_connect(host)
        if err_code != 0:
            err_msg = f"Connect to host({host}) failed"
            return err_code, err_msg

        rpc = err_msg
        is_exists = rpc.os_path_exists(f'{pgdata}/recovery.conf')
        if is_exists:
            err_code, err_msg = rpc.change_file_name(f'{pgdata}/recovery.conf', f"{pgdata}/recovery.done")
            if err_code != 0:
                return err_code, err_msg
        else:
            return 0, f"The file {pgdata}/recovery.conf no longer exists."
    except Exception:
        return -1, traceback.format_exc()
    finally:
        if rpc:
            rpc.close()
    return 0, "change file name success"


def remove_recovery_conf(db_id):
    """移除复制配置信息

    Args:
        db_id (_type_): _description_
    """
    # 获取当前库的信息
    db_info_list = dao.get_db_info(db_id)
    db_info = db_info_list[0]
    pgdata = db_info["pgdata"]
    polar_version = int(db_info["version"].split(".")[0])

    code, result = rpc_utils.get_rpc_connect(db_info["host"])
    if code != 0:
        return -1, f"Connect to host({db_info['host']}) failed."
    rpc = result

    try:
        # 如果是PolarDB11，将recovery.conf文件改名即可
        if polar_version == 11:
            target_file = f'{pgdata}/recovery.conf'
            is_exists = rpc.os_path_exists(target_file)
            if is_exists:
                code, result = rpc.change_file_name(target_file, f"{pgdata}/recovery.done")
                if code != 0:
                    return -1, f"Rename the file({target_file}) failed, {result}."

            return 0, "Success"

        # 后面是处理PolarDB15及之后的版本
        remove_setting_list = [
            "standby_mode",
            "polar_replica",
            "primary_slot_name",
            "primary_conninfo",
            "recovery_target_timeline"
        ]

        # 读取postgresql.auto.conf配置，剔除相关配置后，重新写入
        target_file_list = [f"{pgdata}/postgresql.auto.conf", f"{pgdata}/postgresql.conf"]
        for target_file in target_file_list:
            if not rpc.os_path_exists(target_file):
                continue

            code, content = rpc.file_read(target_file)
            if code != 0:
                return -1, f"Read the content from the file({target_file}) failed, {content}."
            # 移除相关配置
            new_content = ""
            for line in content.split("\n"):
                if line.startswith("#"):
                    new_content += f"{line}\n"
                    continue
                setting_name = line.split("=")[0].strip()
                if setting_name in remove_setting_list:
                    line = f"#{line}"
                new_content += f"{line}\n"
            # 重新写入内容
            code, result = rpc.file_write(target_file, new_content)
            if code != 0:
                return -1, f"Write the content into the file({target_file}) failed, {result}."

        # 移除standby.signal文件
        rpc.delete_file(f"{pgdata}/standby.signal")
    except Exception:
        return -1, f"Remove the recovery configuration with unexpected error, {traceback.format_exc()}."
    finally:
        if rpc:
            rpc.close()

    return 0, "Success"


def update_primary_conninfo(db_id, up_db_id):
    """主备切换更新备库复制信息
    """
    # 获取当前库的信息
    db_info_list = dao.get_db_info(db_id)
    db_info = db_info_list[0]
    pgdata = db_info["pgdata"]
    polar_version = int(db_info["version"].split(".")[0])

    # 获取上级库的流复制信息
    sql = """SELECT repl_ip, port, repl_app_name,
    db_detail->'repl_user' as repl_user FROM clup_db WHERE db_id=%s
    """
    rows = dbapi.query(sql, (up_db_id, ))
    if not len(rows):
        return -1, f"No information related to the database(db_id={db_id}) was found."
    up_db_info = rows[0]

    try:
        rpc = None
        code, result = rpc_utils.get_rpc_connect(db_info["host"])
        if code != 0:
            return -1, f"Connect to host({db_info['host']}) failed, {result}."
        rpc = result

        up_db_port = up_db_info["port"]
        up_db_repl_ip = up_db_info["repl_ip"]
        up_db_repl_user = up_db_info["repl_user"]
        repl_app_name = db_info.get("repl_app_name", db_info["repl_ip"])

        primary_conninfo = f"application_name={repl_app_name} user={up_db_repl_user}" \
            f" host={up_db_repl_ip} port={up_db_port} sslmode=disable sslcompression=1"
        recovery_conf = {'primary_conninfo': f"'{primary_conninfo}'"}

        # 读取recovery.conf文件内容
        target_file = f"{pgdata}/recovery.conf"
        if polar_version > 11:
            target_file = f"{pgdata}/postgresql.auto.conf"

        # 更新recovery.conf文件
        rpc.modify_config_type1(target_file, recovery_conf, is_backup=False)
        dao.update_up_db_id(db_id, up_db_id, is_primary=0)

        # 把文件recovery.conf属主改成于postgresql.conf相同
        example_file = f"{pgdata}/postgresql.conf"
        err_code, err_msg = rpc.os_stat(example_file)
        if err_code != 0:
            return err_code, err_msg
        st_dict = err_msg
        err_code, err_msg = rpc.os_chown(target_file, st_dict['st_uid'], st_dict['st_gid'])
        if err_code != 0:
            err_msg = f"chown file {target_file} error: {err_msg}"
            return err_code, err_msg
        err_code, err_msg = rpc.os_chmod(target_file, 0o600)
        if err_code != 0:
            err_msg = f"chmod file {target_file} error: {err_msg}"
            return err_code, err_msg
    except Exception:
        return -1, traceback.format_exc()
    finally:
        if rpc:
            rpc.close()

    return 0, "Configuration of recovery.conf completed."


def delete_polar_datadir(rpc, db_id):
    """删除共享文件夹

    Returns: 如果不能成功删除返回提示消息,让用户手动删除
    """
    sql = """SELECT is_primary,
    db_detail->'polar_type' as polar_type,
    db_detail->'pfs_disk_name' as pfs_disk_name,
    db_detail->'polar_datadir'as polar_datadir FROM clup_db WHERE db_id=%s
    """
    rows = dbapi.query(sql, (db_id, ))
    if not rows:
        err_msg = f"The information related to the database(db_id={db_id}) is not found, so it cannot be determined whether to delete the pfs shared folder."
        return -1, err_msg
    primary_db_info = rows[0]

    try:
        is_primary = primary_db_info["is_primary"]
        polar_type = primary_db_info.get("polar_type", None)
        if polar_type == 'master' and is_primary:
            polar_datadir = primary_db_info["polar_datadir"]
            pfs_disk_name = primary_db_info.get("pfs_disk_name")
            if not polar_datadir:
                err_msg = f"The 'polar_datadir' information was not found in the 'db_detail' of the database(db_id={db_id}). Please manually delete the pfs shared folder."
                return -1, err_msg
            cmd_deletedir = f'pfs -C disk rm -r /{pfs_disk_name}/{polar_datadir}/'
            code = rpc.run_cmd(cmd_deletedir)
            if code != 0:
                if code == 255:
                    err_msg = f"The '/{pfs_disk_name}/{polar_datadir}' folder has been deleted!"
                    return 0, err_msg
                return -1, f"An unknown error occurred while executing the '{cmd_deletedir}' command. Please manually delete the pfs shared folder!"
    except Exception:
        return -1, f"Delete the polar shared directory with unexpected error, {traceback.format_exc()}."

    return 0, "Success"


def set_sr_config_file(rpc, pg_major_int_version, repl_user, repl_pass, up_db_repl_ip, up_db_port, repl_app_name, pgdata, primary_slot_name, recovery_min_apply_delay=None):
    """
    设置备库配置文件以满足流复制的需要
    """

    new_primary_conninfo_str = f"'application_name={repl_app_name} user={repl_user} password={repl_pass} host={up_db_repl_ip} port={up_db_port} sslmode=disable sslcompression=1'"

    primary_conninfo_dict = {
        "application_name": repl_app_name,
        "user": repl_user,
        "host": up_db_repl_ip,
        "port": up_db_port,
        "password": repl_pass,
    }

    # 记录需要把文件的属主改成与数据目录相同的文件列表
    need_set_owner_file_list = []

    if not rpc.os_path_exists(pgdata):
        return -1, f"directory {pgdata} not exists!"

    if pg_major_int_version < 12:
        recovery_file = f'{pgdata}/recovery.conf'
        recovery_done_file = f"{pgdata}/recovery.done"
        if not rpc.os_path_exists(recovery_file):
            need_set_owner_file_list.append(recovery_file)
            if rpc.os_path_exists(recovery_done_file):
                cmd = """/bin/cp %s %s""" % (recovery_done_file, recovery_file)
                err_code, err_msg, _out_msg = rpc.run_cmd_result(cmd)
                if err_code != 0:
                    return err_code, err_msg
            else:
                # 如果recovery.conf不存在,则写一个空文件
                err_code, err_msg = rpc.os_write_file(recovery_file, 0, b"")
                if err_code != 0:
                    return err_code, err_msg
        # 通过前面的操作,recovery.conf文件必定存在
        config_file = recovery_file
        err_code, item_dict = rpc.read_config_file_items(config_file, ['primary_conninfo'])
    else:
        # PostgreSQL 12及之上的版本,需要有standby.signal表示其是备库
        standby_signal_file = f"{pgdata}/standby.signal"
        err_code, err_msg = rpc.os_write_file(standby_signal_file, 0, b"")
        if err_code != 0:
            return err_code, err_msg
        need_set_owner_file_list.append(standby_signal_file)

        # 先读取postgresql.auto.conf,如果其中有配置项primary_conninfo,则使用postgresql.auto.conf
        auto_conf_file = '%s/postgresql.auto.conf' % pgdata
        err_code, item_dict = rpc.read_config_file_items(auto_conf_file, ['primary_conninfo'])
        if err_code == 0 and item_dict.get('primary_conninfo'):
            config_file = auto_conf_file
        else:
            config_file = '%s/postgresql.conf' % pgdata
            err_code, item_dict = rpc.read_config_file_items(config_file, ['primary_conninfo'])
            if err_code != 0:
                return err_code, item_dict

    old_primary_conninfo_str = item_dict.get('primary_conninfo', '')[1:-1]
    if old_primary_conninfo_str:
        err_code, err_msg = pg_db_lib.merge_primary_conninfo_str(old_primary_conninfo_str, primary_conninfo_dict)
        if err_code != 0:
            return err_code, err_msg
        # 如果没有出错,err_msg中是merge后的primary_conninfo
        new_primary_conninfo_str = err_msg if err_msg else new_primary_conninfo_str

    modify_item_dict = {
        "recovery_target_timeline": "'latest'",
        "polar_replica": "'on'",
        "primary_slot_name": f"'{primary_slot_name}'",
        "primary_conninfo": new_primary_conninfo_str
    }

    if recovery_min_apply_delay:
        modify_item_dict['recovery_min_apply_delay'] = recovery_min_apply_delay

    # if pg_major_int_version < 12:
    #    modify_item_dict['standby_mode'] = "'on'"

    rpc.modify_config_type1(config_file, modify_item_dict, deli_type=1, is_backup=False)

    try:
        err_code, err_msg = rpc.os_stat(pgdata)
        if err_code != 0:
            return err_code, err_msg
        fs = err_msg

        err_code, err_msg = rpc.pwd_getpwuid(fs['st_uid'])
        if err_code != 0:
            return err_code, err_msg
        upw_dict = err_msg
    except Exception as e:
        return -1, str(e)

    for var_file in need_set_owner_file_list:
        err_code, err_msg = rpc.os_chown(var_file, upw_dict['pw_uid'], upw_dict['pw_gid'])
        if err_code != 0:
            err_msg = f"can not set {var_file} owner to {upw_dict['pw_uid']}: {err_msg}"
            return err_code, err_msg
    return 0, ''


def check_and_offline_cluster(db_id):
    """检查是否是集群中最后一台数据库,如果是且集群为online则将集群下线
    """
    sql = "SELECT cluster_id, c.state FROM clup_cluster c left join clup_db d USING(cluster_id) WHERE d.db_id=%s"
    rows = dbapi.query(sql, (db_id, ))
    if not len(rows):
        return 0, ""
    clu_state = rows[0]['state']
    cluster_id = rows[0]['cluster_id']
    if clu_state != cluster_state.NORMAL:
        return 0, ""

    sql = "SELECT count(*) FROM clup_db WHERE cluster_id = %s AND db_state = 0"
    rows = dbapi.query(sql, (cluster_id, ))
    count = rows[0]['count']
    if count > 1:
        return 0, ""

    res = dao.test_and_set_cluster_state(cluster_id, [cluster_state.NORMAL], cluster_state.OFFLINE)
    if res is None:
        return -1, f"The status of the cluster(cluster_id={cluster_id}) has changed, and it's not possible to bring it offline."
    return 0, f"Offline cluster_id={cluster_id} is successed"


def is_exists_recovery(host, pgdata, polar_version):
    """检查poalrdb节点是否有recovery.conf文件
    """
    try:
        rpc = None
        # 连接主机执行命令
        err_code, err_msg = rpc_utils.get_rpc_connect(host)
        if err_code != 0:
            err_msg = f"Connect to host({host}) failed"
            return err_code, err_msg
        rpc = err_msg

        check_file = f'{pgdata}/recovery.conf'
        if polar_version > 11:
            check_file = f"{pgdata}/standby.signal"

        is_exists = rpc.os_path_exists(check_file)
        if not is_exists:
            return -1, f"The file({check_file}) does not exist in the '{pgdata}' directory on the host(host={host})."

    except Exception:
        return -1, traceback.format_exc()
    finally:
        if rpc:
            rpc.close()
    return 0, ""


def check_or_create_recovery_conf(db_id, up_db_dict):
    """检查和配置recovery.conf
    """
    rows = dao.get_db_info(db_id)
    if not len(rows):
        return -1, f"No database(db_id={db_id}) information was obtained"
    db_dict = rows[0]

    host = db_dict['host']
    pgdata = db_dict['pgdata']
    try:
        rpc = None
        # 连接主机执行命令
        err_code, err_msg = rpc_utils.get_rpc_connect(host)
        if err_code != 0:
            err_msg = f"Connect to host({host}) failed"
            return err_code, err_msg
        rpc = err_msg
        is_exists = rpc.os_path_exists(f'{pgdata}/recovery.conf')
        if not is_exists:
            repl_app_name = db_dict['repl_app_name']
            repl_user = db_dict['repl_user']
            up_db_repl_ip = up_db_dict['repl_ip']
            up_db_port = up_db_dict['port']

            polar_type = db_dict['polar_type']
            if polar_type == 'reader':
                err_code, err_msg = edit_reader_conf(rpc, db_id, pgdata, repl_app_name, repl_user, up_db_repl_ip, up_db_port)
                if err_code != 0:
                    return -1, err_msg
            elif polar_type == 'standby':
                err_code, err_msg = edit_standby_conf(rpc, db_id, pgdata, repl_app_name, repl_user, up_db_repl_ip, up_db_port)
                if err_code != 0:
                    return -1, err_msg
            return 1, 'create new recovery.conf'
        return 0, 'recovery.conf is exists'
    except Exception as e:
        return -1, str(e)
    finally:
        if rpc:
            rpc.close()


def stop_immediate(host, pgdata, _wait_time=0):
    """使用immediate参数停止数据库
    :return: 如果成功,则返回True,如果失败则返回False
    """
    rpc = None
    err_code, err_msg = rpc_utils.get_rpc_connect(host)
    if err_code != 0:
        return -1, err_msg

    rpc = err_msg
    if not rpc.os_path_exists(pgdata):
        return -1, f"directory {pgdata} not exists"

    try:
        err_code, err_msg = rpc.os_stat(pgdata)
        if err_code != 0:
            return err_code, err_msg
        fs = err_msg
        err_code, err_msg = rpc.pwd_getpwuid(fs['st_uid'])
        if err_code != 0:
            return err_code, err_msg
        upw_dict = err_msg

        # 把数据库停下来
        cmd = f'''su - {upw_dict["pw_name"]} -c 'pg_ctl stop -m immediate -w -D {pgdata} > /dev/null' '''
        err_code, err_msg, _out_msg = rpc.run_cmd_result(cmd)
        if err_code != 0:
            return -1, err_msg
        return 0, "Success"
    except Exception as e:
        return -1, str(e)
    finally:
        if rpc:
            rpc.close()


def get_cluster_polar_hostid(cluster_id):
    """获取集群的polar_hostid
    """
    sql = f"SELECT cluster_data->'polar_hostid' as polar_hostid FROM clup_cluster WHERE cluster_id = {cluster_id} "
    rows = dbapi.query(sql)
    if not len(rows):
        return -1, f"Failed to get the 'polar_hostid' of the cluster(cluster_id={cluster_id})."
    polar_hostid = rows[0].get("polar_hostid")
    if not polar_hostid:
        return -1, f"Failed to get polar_hostid, please modify the polar_hostid for the cluster(cluster_id={cluster_id}) information first."
    return 0, int(polar_hostid)


def update_cluster_polar_hostid(cluster_id, polar_hostid):
    """更新集群的polar_hostid
    """
    update_dict = json.dumps({"polar_hostid": polar_hostid})
    sql = "UPDATE clup_cluster SET cluster_data = cluster_data || (%s::jsonb) WHERE cluster_id = %s"
    dbapi.execute(sql, (update_dict, cluster_id))


def get_db_polar_hostid(db_id):
    """获取数据库的polar_hostid
    """
    sql = f"SELECT db_detail->'polar_hostid' as polar_hostid FROM clup_db WHERE db_id = {db_id} "
    rows = dbapi.query(sql)
    if not len(rows):
        return -1, f"Failed to get the 'polar_hostid' of the database(db_id={db_id})."
    return 0, rows[0]


def search_polar_hostid(rpc, pgdata):
    """通过配置文件获取polar_hostid
    """
    postgresql_conf = f"{pgdata}/postgresql.conf"
    postgresql_auto_conf = f"{pgdata}/postgresql.auto.conf"
    err_code, err_msg = rpc.read_config_file_items(postgresql_auto_conf, ['polar_hostid'])
    if err_code != 0 or not err_msg.get('polar_hostid'):
        err_code, err_msg = rpc.read_config_file_items(postgresql_conf, ['polar_hostid'])
        if err_code != 0 or not err_msg.get('polar_hostid'):
            return -1, ""
        return 0, int(err_msg['polar_hostid'])
    return 0, int(err_msg['polar_hostid'])


def polar_share_to_local(task_id, msg_prefix, recovery_host, pgdata):
    """move polar_shared_data to local
    """
    step = f"{msg_prefix} init polardb"
    try:
        rpc = None
        # create rpc connect
        err_code, err_msg = rpc_utils.get_rpc_connect(recovery_host)
        if err_code != 0:
            err_msg = f"Connect to host({recovery_host}) failed, {err_msg}."
            return -1, err_msg
        rpc = err_msg
        # check pgdata is exixts
        result = rpc.os_path_exists(pgdata)
        if not result:
            err_msg = f"{step}: the directory {pgdata} is not exists."
            general_task_mgr.log_error(task_id, err_msg)
            return -1, err_msg
        shared_data = f"{pgdata}/polar_shared_data"
        if not rpc.os_path_exists(shared_data):
            return 0, ""
    finally:
        if rpc:
            rpc.close()

    try:
        rpc = None
        # create rpc connect
        err_code, err_msg = rpc_utils.get_rpc_connect(recovery_host)
        if err_code != 0:
            err_msg = f"Connect to host({recovery_host}) failed, {err_msg}."
            return -1, err_msg
        rpc = err_msg
        # delete files which in pgdata except polar_shared_data
        general_task_mgr.log_info(task_id, f"{step}: Start delete extra files...")
        delete_base_files = f"cd {pgdata} && ls polar_shared_data|xargs rm -rf"
        _cmd_id = rpc.run_long_term_cmd(delete_base_files, output_qsize=100, output_timeout=600)
        rpc.close()
        rpc = None

        if err_code != 0:
            err_msg = f"{step}: run long term cmd {delete_base_files} failed, {err_msg}."
            general_task_mgr.log_error(task_id, err_msg)
            return -1, err_msg
        general_task_mgr.log_info(task_id, f"{step}: Delete extra files success.")

        # create rpc connect
        err_code, err_msg = rpc_utils.get_rpc_connect(recovery_host)
        if err_code != 0:
            err_msg = f"Connect to host({recovery_host}) failed, {err_msg}."
            return -1, err_msg
        rpc = err_msg
        # mv polar_shared_data files to pgdata
        general_task_mgr.log_info(task_id, f"{step}: Start move polar_shared_data...")
        mv_shared_data = f"cd {pgdata} && mv polar_shared_data/* ./"
        # run long cmd for pg_basebasckup
        _cmd_id = rpc.run_long_term_cmd(mv_shared_data, output_qsize=100, output_timeout=600)
        rpc.close()
        rpc = None

        if err_code != 0:
            err_msg = f"{step}: run long term cmd {mv_shared_data} failed, {err_msg}."
            general_task_mgr.log_error(task_id, err_msg)
            return -1, err_msg
        general_task_mgr.log_info(task_id, f"{step}: Move polar_shared_data success.")

        # create rpc connect
        err_code, err_msg = rpc_utils.get_rpc_connect(recovery_host)
        if err_code != 0:
            err_msg = f"Connect to host({recovery_host}) failed, {err_msg}."
            return -1, err_msg
        rpc = err_msg
        # delete polar_shared_data directory
        delete_shared_dir = f"cd {pgdata} && rm -rf polar_shared_data"
        rpc.run_cmd(delete_shared_dir)
    except Exception:
        err_msg = f"{step}: failed with unexcept error, {traceback.format_exc()}"
        general_task_mgr.log_error(task_id, err_msg)
        return -1, err_msg
    finally:
        if rpc:
            rpc.close()

    return 0, "success"


def check_disk_on_host(host, pfs_disk_name):
    """在主机上检查磁盘的mount情况
    如果发现pfs选中的磁盘或此盘的分区已经做为文件系统被mount上了,则不能作为为pfs的磁盘使用
    :resturn
        返回一个元组, 第一个元素代表是否有效, 第二个元素代表 host 的 IP。
    """

    # 先获得此机器上已经挂载的文件系统,如果发现磁盘或
    return_code, stdout = rpc_utils.get_rpc_connect(host, conn_timeout=2)
    if return_code == 0:
        rpc = stdout
    else:
        return -1, f'Failed to connect agent[{host}]'

    code, stdout = rpc.file_read('/proc/mounts')
    if code != 0:
        return -1, f"Failed to open /proc/mouts in agent[{host}]"

    mounted_dev = []
    lines = stdout.splitlines()
    for line in lines:
        path = line.split()[0]
        if path.startswith("/dev"):
            return_code, stdout = rpc.os_stat(path)
            if return_code == 0:
                st_rdev = stdout['st_rdev']
            else:
                return -1, f"Failed to get st_rdev {path} in agent[{host}]"
            dev = major(st_rdev), minor(st_rdev)
            mounted_dev.append(dev)

    # If pfs_disk_name is relative path then generate absolute path.
    if '/' not in pfs_disk_name:
        dev_path = os.path.join("/dev", pfs_disk_name)
    else:
        dev_path = pfs_disk_name
    exist = rpc.os_path_exists(dev_path)
    if not exist:
        return -1, f'{dev_path} is not exist in host({host})'

    code, stdout = rpc.os_stat(dev_path)
    if code != 0:
        return -1, f"Failed to get st_rdev `{dev_path}` in agent[{host}]"
    st_rdev = stdout['st_rdev']
    dev = major(st_rdev), minor(st_rdev)
    if dev in mounted_dev:
        return -1, f"{dev_path} is mounted in host({host})"

    # 查找此盘的分区信息
    # 先从/sys/block中找出所有的块设备
    fn_list = rpc.os_listdir('/sys/block')
    # 找出此设备
    curr_sys_block_fn = ''
    for fn in fn_list:
        devno_file = f"/sys/block/{fn}/dev"
        err_code, err_msg = rpc.file_read(devno_file)
        if err_code != 0:
            return -1, f"read {devno_file} failed: {err_msg}"
        str_dev = err_msg.strip()
        cells = str_dev.split(':')
        curr_dev_no = int(cells[0]), int(cells[1])
        if curr_dev_no == dev:
            curr_sys_block_fn = fn
            break
    if not curr_sys_block_fn:
        return -1, f"{dev_path} is not in /sys/block, maybe it not block device!"
    # 再遍历 /sys/block/XXXX/下的文件,如/sys/block/sda/目录下,有文件sda1或sda2
    fn_list = rpc.os_listdir(f'/sys/block/{curr_sys_block_fn}')
    for fn in fn_list:
        # 分区的名字一般是此设备的名字开头
        if not fn.startswith(curr_sys_block_fn):
            continue

        devno_file = f"/sys/block/{curr_sys_block_fn}/{fn}/dev"
        err_code, err_msg = rpc.file_read(devno_file)
        if err_code != 0:
            return -1, f"read {devno_file} failed: {err_msg}"
        str_dev = err_msg.strip()
        cells = str_dev.split(':')
        curr_dev_no = int(cells[0]), int(cells[1])
        if curr_dev_no in mounted_dev:
            return -1, f"Partition {fn} is mounted in host({host})"

    # check pfs disk aready format or not
    pfs_disk_name = dev_path.split("/dev/")[-1]
    cmd = f"echo `pfs info {pfs_disk_name}`"
    err_code, err_msg, _out_msg = rpc.run_cmd_result(cmd)
    if err_code != 0:
        return -1, f"run cmd({cmd}) failed, {err_msg}."
    if _out_msg == "\n":
        return 1, "Is not formated."

    return 0, 'Is Ok'


def check_pfs_disk_name_validity(host_list, pfs_disk_name):
    """
    检查所有的 host 是否符合要求,
    如果都符合, 返回 (True, ''),
    否则返回 (False, msg) # msg 为 结果/报错 信息。
    """
    failed_host_msg = []
    pfs_disk_formated = False
    for host in host_list:
        code, result = check_disk_on_host(host, pfs_disk_name)
        if code != 0 and code != 1:
            failed_host_msg.append(result)
        elif code == 0:
            pfs_disk_formated = True

    if failed_host_msg:
        return -1, ''.join(failed_host_msg)

    return 0, pfs_disk_formated


def major(devno):
    """
    从dev_t类型的设备号中获取主设备号
    :param devno:
    :return:
    """

    ma = ((devno >> 8) & 0xfff) | ((devno >> 32) & 0xfffff000)
    return ma


def minor(devno):
    """
    从dev_t类型的设备号中获取次设备号
    :param devno:
    :return:
    """
    mi = (devno & 0xff) | ((devno >> 12) & 0xffffff00)
    return mi


def get_pfs_info(host, pfs_disk_name, directory_name=None):
    """get the pfs information

    returns:
        {
            'pfs_disk_name': 'nvmecsu01',
            'dev_name': 'sda',
            'dev_size': 30.0,
            'current_chunks': 2,
            'free_size': 13.47,
            'blk_numbers': 5120,
            'blk_free_numbers': 3449,
            'blk_usage': 32.64,
            'dir_numbers': 4096,
            'dir_free_numbers': 2520,
            'dir_usage': 38.48
        }
    """

    step = "Get the dev info"
    try:
        # connect the host
        err_code, err_msg = rpc_utils.get_rpc_connect(host, 2)
        if err_code != 0:
            return -1, f"{step} failed, {err_msg}."
        rpc = err_msg

        pfs_disk_info = {"pfs_disk_name": pfs_disk_name}
        # get the disk DEVNAME
        cmd = f"udevadm info --query=property --name={pfs_disk_name} | grep DEVNAME"
        err_code, err_msg, out_msg = rpc.run_cmd_result(cmd)
        if err_code != 0:
            return -1, f"{step}: run cmd({cmd}) failed, {err_msg}."
        dev_name = out_msg.split("=")[-1]
        if dev_name.startswith("/dev"):
            # strip '/dev/
            dev_name = dev_name.strip("\n").split("/dev/")[-1]
            pfs_disk_info['dev_name'] = dev_name

        # get the disk size
        cmd = f"lsblk -b -o name,size |grep {dev_name}"
        err_code, err_msg, out_msg = rpc.run_cmd_result(cmd)
        if err_code != 0:
            return -1, f"{step}: run cmd({cmd}) failed, {err_msg}."
        dev_size_bytes = int(out_msg. split(" ")[-1])

        # exchange unit to GB
        dev_size = round(dev_size_bytes / 1024 / 1024 / 1024, 2)
        pfs_disk_info['dev_size'] = dev_size

    except Exception:
        return -1, f"{step} with unexpected error, {traceback.format_exc()}."
    finally:
        if rpc:
            rpc.close()

    step = "Get the pfs info"
    try:
        # connect the host
        err_code, err_msg = rpc_utils.get_rpc_connect(host, 2)
        if err_code != 0:
            return -1, f"{step} failed, {err_msg}."
        rpc = err_msg

        # get pfs disk info, pfs is not stdout, use echo
        cmd = f"echo `pfs -C disk info {pfs_disk_name}`"
        err_code, err_msg, out_msg = rpc.run_cmd_result(cmd)
        if err_code != 0:
            return -1, f"{step}: run cmd({cmd}) failed, {err_msg}."
        elif out_msg == "\n":
            return -1, f"{step} failed, cant the disk info, maybe the pfs disk is not formated."

        """
        Blktag Info: (0)allocnode: id 0, shift 0, nchild=2, nall 5120, nfree 3452, next 0 Direntry Info:
        (0)allocnode: id 0, shift 0, nchild=2, nall 4096, nfree 2522, next 0 Inode Info:
        (0)allocnode: id 0, shift 0, nchild=2, nall 4096, nfree 2522, next 0
        """

        # Blktag Info
        blk_split = out_msg.split("Blktag Info: ")[-1]
        blk_info, dir_split = blk_split.split("Direntry Info:")
        dir_info = dir_split.split("Inode Info:")[0]
        # block usage
        blk_usage = blk_info.split(",")
        for infor_content in blk_usage:
            if "nall" in infor_content:
                blk_numbers = int(infor_content.split(" ")[-1])
                pfs_disk_info['blk_numbers'] = blk_numbers
            elif "nchild" in infor_content:
                chunks = int(infor_content.split("=")[-1])  # 1chunks = 10GB
                pfs_disk_info['current_chunks'] = chunks
            elif "nfree" in infor_content:
                blk_free_numbers = int(infor_content. split(" ")[-1])
                free_size = blk_free_numbers * 4 / 1024  # GB
                pfs_disk_info['blk_free_numbers'] = blk_free_numbers
                pfs_disk_info['free_size'] = round(free_size, 2)
        # add blk usage info
        blk_usaged = round(1 - (pfs_disk_info['blk_free_numbers'] / pfs_disk_info['blk_numbers']), 4)
        pfs_disk_info['blk_use_rate'] = blk_usaged * 100

        # directory usage
        directory_usage = dir_info. split(",")
        for infor in directory_usage:
            if "nall" in infor:
                dir_numbers = infor. split(" ")[-1]
                pfs_disk_info['dir_numbers'] = int(dir_numbers)
            elif "nfree" in infor:
                dir_free_numbers = infor. split(" ")[-1]
                pfs_disk_info['dir_free_numbers'] = int(dir_free_numbers)
        # add directory usage
        dir_usaged = round(1 - (pfs_disk_info['dir_free_numbers'] / pfs_disk_info['dir_numbers']), 4)
        pfs_disk_info['dir_use_rate'] = dir_usaged * 100

        # if params has directory_name,need get the directory usage
        if directory_name:
            # get the directory_name usage
            cmd = f"echo `pfs -C disk du /{pfs_disk_name}/{directory_name}/`"
            err_code, err_msg, out_msg = rpc. run_cmd_result(cmd)
            if err_code != 0:
                return -1, f"{step}: get the directory usage failed, {err_msg}."
            else:
                # ..256 /nvme1n1/shared_data//pg_replslot 1006080 /nvme1n1/shared_data/
                directory_used = int(out_msg.split(" ")[-2])  # KB
                # directory_used = info_lines[-1].split(" ")[0]
                pfs_disk_info['directory_used'] = {
                    directory_name: round(directory_used / 1024 / 1024, 2)  # GB
                }
        return 0, pfs_disk_info
    except Exception:
        return -1, traceback.format_exc()
    finally:
        if rpc:
            rpc.close()


def pfs_growfs(db_info, pfs_disk_name, current_chunks, target_chunks):
    """扩容pfs 磁盘

    Args:
        host (_type_): _description_
        pfs_disk_name (_type_): _description_
        current_chunks (_type_): _description_
        target_chunks (_type_): _description_
    """

    step = "Pfs disk growfs"
    host = db_info['host']

    try:
        # connect the host
        err_code, err_msg = rpc_utils.get_rpc_connect(host, 2)
        if err_code != 0:
            return -1, f"{step} failed, {err_msg}."
        rpc = err_msg

        # disk growfs
        cmd = f"echo `pfs -C disk growfs -o {current_chunks} -n {target_chunks} {pfs_disk_name}`"
        err_code, err_msg, _out_msg = rpc.run_cmd_result(cmd)
        if err_code != 0:
            return -1, f"{step} failed, {err_msg}."
        rpc.close()

        # test create extension
        sql = "CREATE EXTENSION IF NOT EXISTS polar_vfs"
        err_code, err_msg = pg_utils.sql_exec(host, db_info['port'], 'template1', db_info['db_user'], db_info['db_pass'], sql)
        if err_code != 0:
            return -1, f"Test to create extension on database(host={host}, port={db_info['port']}, db='template1') failed, {err_msg}."

        # database growfs
        sql = f"SELECT polar_vfs_disk_expansion('{pfs_disk_name}')"
        err_code, err_msg = pg_utils.sql_exec(host, db_info['port'], 'template1', db_info['db_user'], db_info['db_pass'], sql)
        if err_code != 0:
            return -1, f"Growfs on database(host={host}, port={db_info['port']}, db='template1') failed, {err_msg}."

    except Exception:
        return -1, f"Pfs growfs with unexpected error, {traceback.format_exc()}."
    finally:
        if rpc:
            rpc.close()

    return 0, "Growfs success"


def get_polar_major_version(db_id):
    """获取PolarDB的主版本号

    Args:
        db_id (_type_): _description_
    """
    sql = "SELECT db_detail->'version' as version FROM clup_db WHERE db_id=%s"
    rows = dbapi.query(sql, (db_id, ))
    if not rows:
        return -1, f"Cant find any records for the instance(db_id={db_id})."

    version = rows[0]["version"]
    if not version:
        return -1, f"Get the version for the instance(db_id={db_id}) failed."

    major_version = int(version.split(".")[0])
    return 0, major_version
