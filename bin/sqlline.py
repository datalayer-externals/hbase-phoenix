#!/usr/bin/env python
############################################################################
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
############################################################################

from __future__ import print_function
from phoenix_utils import tryDecode
import os
import subprocess
import sys
import phoenix_utils
import atexit

# import argparse
try:
    import argparse
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(os.path.join(current_dir, 'argparse-1.4.0'))
    import argparse

global childProc
childProc = None
def kill_child():
    if childProc is not None:
        childProc.terminate()
        childProc.kill()
        if os.name != 'nt':
            os.system("reset")
atexit.register(kill_child)

phoenix_utils.setPath()

parser = argparse.ArgumentParser(description='Launches the Apache Phoenix Client.')
# Positional argument 'zookeepers' is optional. The PhoenixDriver will automatically populate
# this if it's not provided by the user (so, we want to leave a default value of empty)
parser.add_argument('zookeepers', nargs='?', help='The ZooKeeper quorum string or full JDBC URL', default='')
# Positional argument 'sqlfile' is optional
parser.add_argument('sqlfile', nargs='?', help='A file of SQL commands to execute', default='')
parser.add_argument('--noconnect', help='Start without making a connection',
                    action="store_true")
parser.add_argument('--verbose-command',
                    help='Show the Java command on the console before executing it',
                    action="store_true")
# Common arguments across sqlline.py and sqlline-thin.py
phoenix_utils.common_sqlline_args(parser)
# Parse the args
args=parser.parse_args()

zookeeper = tryDecode(args.zookeepers)
if zookeeper.startswith('jdbc:phoenix'):
    jdbc_url = zookeeper
else:
    # We do want to use the default "jdbc:phoenix:" URL if no URL was specified
    jdbc_url = 'jdbc:phoenix:' + zookeeper
sqlfile = tryDecode(args.sqlfile)

# HBase configuration folder path (where hbase-site.xml reside) for
# HBase/Phoenix client side property override
hbase_config_path = phoenix_utils.hbase_conf_dir

if sqlfile and not os.path.isfile(sqlfile):
    parser.print_help()
    sys.exit(-1)

if sqlfile:
    sqlfile = "--run=" + phoenix_utils.shell_quote([sqlfile])

java_home = os.getenv('JAVA_HOME')

# load hbase-env.??? to extract JAVA_HOME, HBASE_PID_DIR, HBASE_LOG_DIR
hbase_env_path = None
hbase_env_cmd  = None
if os.name == 'posix':
    hbase_env_path = os.path.join(hbase_config_path, 'hbase-env.sh')
    hbase_env_cmd = ['bash', '-c', 'source %s && env' % hbase_env_path]
elif os.name == 'nt':
    hbase_env_path = os.path.join(hbase_config_path, 'hbase-env.cmd')
    hbase_env_cmd = ['cmd.exe', '/c', 'call %s & set' % hbase_env_path]
if not hbase_env_path or not hbase_env_cmd:
    sys.stderr.write("hbase-env file unknown on platform {}{}".format(os.name, os.linesep))
    sys.exit(-1)

hbase_env = {}
if os.path.isfile(hbase_env_path):
    p = subprocess.Popen(hbase_env_cmd, stdout = subprocess.PIPE)
    for x in p.stdout:
        (k, _, v) = x.decode().partition('=')
        hbase_env[k.strip()] = v.strip()

if 'JAVA_HOME' in hbase_env:
    java_home = hbase_env['JAVA_HOME']

if java_home:
    java = os.path.join(java_home, 'bin', 'java')
else:
    java = 'java'

colorSetting = tryDecode(args.color)
# disable color setting for windows OS
if os.name == 'nt':
    colorSetting = "false"

#See PHOENIX-6661
if os.uname()[4].startswith('ppc'):
    disable_jna = " -Dorg.jline.terminal.jna=false "
else:
    disable_jna = ""

java_cmd = java + ' $PHOENIX_OPTS ' + \
    ' -cp "' + phoenix_utils.hbase_conf_dir + os.pathsep + \
    phoenix_utils.hadoop_conf + os.pathsep + \
    phoenix_utils.sqlline_with_deps_jar + os.pathsep + \
    phoenix_utils.slf4j_backend_jar + os.pathsep + \
    phoenix_utils.logging_jar + os.pathsep + \
    phoenix_utils.phoenix_client_embedded_jar + \
    '" -Dlog4j2.configurationFile=file:' + os.path.join(phoenix_utils.current_dir, "log4j2.properties") + \
    disable_jna + \
    " sqlline.SqlLine -d org.apache.phoenix.jdbc.PhoenixDriver" + \
    (not args.noconnect and " -u " + phoenix_utils.shell_quote([jdbc_url]) or "") + \
    " -n none -p none --color=" + \
        (args.color and "true" or "false") + \
        " --fastConnect=" + (args.fastconnect and "true" or "false") + \
    " --verbose=" + (args.verbose and "true" or "false") + \
        " --incremental=false --isolation=TRANSACTION_READ_COMMITTED " + sqlfile

if args.verbose_command:
    print("Executing java command: " + java_cmd)

os.execl("/bin/sh", "/bin/sh", "-c", java_cmd)
