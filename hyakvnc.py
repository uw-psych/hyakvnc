#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

VERSION = 0.6

# Created by Hansem Ro <hansem7@uw.edu> <hansemro@outlook.com>
# Maintained by ECE TAs

# Quick start guide
#
# 1. Install python3 dependencies (psutil)
#    From Login node, run the following
#      $ ./setup.sh
#
# 2. To start VNC session for 5 hours on node with 16 cores and 32GB of memory,
#    run the following
#      $ ./hyakvnc.py -t 5 -c 16 --mem 32G
#      ...
#      =====================
#      Run the following in a new terminal window:
#              ssh -N -f -L 5901:127.0.0.1:5901 hansem7@klone.hyak.uw.edu
#      then connect to VNC session at localhost:5901
#      =====================
#
#    This should print a command to setup port forwarding. Copy it for the
#    following step.
#
# 3. Set up port forward between your computer and HYAK login node.
#    On your machine, in a new terminal window, run the the copied command.
#      $ ./ssh -N -f -L 5901:127.0.0.1:5901 hansem7@klone.hyak.uw.edu
#
# 4. Connect to VNC session
#
# 5. To close VNC session, run the following
#      $ ./hyakvnc.py --kill-all
#
# 6. Kill port forward process from step 3


# Usage: ./hyakvnc.py [-h/--help] [OPTIONS]
#
# Options:
#   -h, --help : print help message and exit
#
#   -v, --version : print program version and exit
#
#   -d, --debug : [default: disabled] enable debug logging at ~/hyakvnc.log
#
#   -f, --force : [default: single VNC job] allow multiple VNC jobs/sessions
#
#   -p <part>, --partition <part> : [default: compute-hugemem] Slurm partition
#
#   -A <account>, --account <account> : [default: ece] Slurm account
#
#   -p <port>, --port <port> : [default: automatically found] override
#                              User<->LoginNode port
#
#   -t <time>, --time <time> : [default: 3] VNC node reservation length in hours
#
#   -c <ncpus>, --cpus <ncpus> : [default: 8] VNC node CPU count
#
#   --mem <size[units]> : [default: 16G] VNC node memory
#                         Valid units: K, M, G, T
#
#   --status : print details of active VNC jobs and exit. Details include the
#              following for each active job:
#                - Job ID
#                - Subnode name
#                - VNC display number
#                - Subnode/VNC port
#                - User/LoginNode port
#                - Time left
#
#   --kill <job_id> : kill specific job
#
#   --kill-all : kill all VNC jobs
#
#   --set-passwd : prompt to set VNC password
#

import argparse # for argument handling
import logging # for debug logging
import time # for sleep
import psutil # for netstat utility
import os
import subprocess # for running shell commands
import re # for regex

# tasks:
# - [x] user arguments to control hours
# - [x] user arguments to close active vnc sessions and vnc slurm jobs
# - [x] user arguments to override automatic port forward (with conflict checking)
# - [x] reserve node with slurm
# - [x] start vnc session (also check for active vnc sessions)
# - [1/2] identify used ports : current implementation needs improvements
# - [x] map node<->login port to unused user<->login port
# - [x] port forward between login<->subnode
# - [x] print instructions to user to setup user<->login port forwarding
# - [x] print time left for node with --status argument
# - [ ] Set vnc settings via file (~/.config/hyakvnc.conf)
# - [ ] Write unit tests for functions

BASE_VNC_PORT = 5900
LOGIN_NODE_LIST = ["klone1.hyak.uw.edu", "klone2.hyak.uw.edu"]
SINGULARITY_BIN = "/opt/ohpc/pub/libs/singularity/3.7.1/bin/singularity"
XFCE_CONTAINER = "/gscratch/ece/xfce_singularity/xfce.sif"
XSTARTUP_FILEPATH = "/gscratch/ece/xfce_singularity/xstartup"
AUTH_KEYS_FILEPATH = os.path.expanduser("~/.ssh/authorized_keys")
SINGULARITY_BINDPATH = os.getenv("SINGULARITY_BINDPATH")
if SINGULARITY_BINDPATH is None:
    SINGULARITY_BINDPATH = "/tmp:/tmp,$HOME,$PWD,/gscratch,/opt:/opt,/:/hyak_root"

class Node:
    def __init__(self, name, debug=False):
        self.debug = debug
        self.name = name
        self.cmd_prefix = f"{SINGULARITY_BIN} exec -B {SINGULARITY_BINDPATH} {XFCE_CONTAINER}"

class SubNode(Node):
    def __init__(self, name, job_id, debug=False):
        assert os.path.exists(AUTH_KEYS_FILEPATH)
        super().__init__(name, debug)
        self.hostname = name + ".hyak.local"
        self.job_id = job_id
        self.vnc_display_number = None
        self.vnc_port = None

    def print_props(self):
        print("Subnode properties:")
        props = vars(self)
        for item in props:
            msg = f"{item} : {props[item]}"
            print(f"\t{msg}")
            if self.debug:
                logging.debug(msg)

    def run_command(self, command:str):
        """
        Run command (with arguments) on subnode

        Args:
          command:str : command and its arguments to run on subnode

        Returns ssh subprocess with stderr->stdout and stdout->PIPE
        """
        assert self.name is not None
        cmd = ["ssh", self.hostname, command]
        if self.debug:
            msg = f"Running on {self.name}: {cmd}"
            print(msg)
            logging.info(msg)
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def get_vnc_pid(self, hostname, display_number):
        """
        Returns pid from file <hostname>:<display_number>.pid or None if file
        does not exist.
        """
        if hostname is None:
            hostname = self.hostname
        if display_number is None:
            display_number = self.vnc_display_number
        assert(hostname is not None)
        assert(display_number is not None)
        filepath = os.path.expanduser(f"~/.vnc/{hostname}:{display_number}.pid")
        if self.debug:
            logging.info(f"Opening PID file {filepath}")
        if os.path.exists(filepath):
            f = open(filepath, "r")
            if f is not None:
                pid = int(f.readline())
                if self.debug:
                    logging.info(f"{filepath}: {pid}")
                f.close()
                return pid
        return None

    def check_vnc(self):
        """
        Returns True if VNC session is active and False otherwise.
        """
        assert(self.name is not None)
        assert(self.job_id is not None)
        pid = self.get_vnc_pid(self.hostname, self.vnc_display_number)
        cmd = f"ps -U {os.getlogin()}"
        proc = self.run_command(cmd)
        while proc.poll() is None:
            line = str(proc.stdout.readline(), "utf-8").strip()
            if str(pid) in line:
                if self.debug:
                    msg = "Matched line: {line}"
                    logging.debug(msg)
                return True
        return False

    def start_vnc(self):
        """
        Starts VNC session

        Returns True if VNC session was started successfully and False otherwise
        """
        timer = 15
        vnc_cmd = f"timeout {timer} {self.cmd_prefix} vncserver -xstartup {XSTARTUP_FILEPATH} -baseHttpPort {BASE_VNC_PORT} -depth 24 &"
        proc = self.run_command(vnc_cmd)

        # get display number and port number
        while proc.poll() is None:
            line = str(proc.stdout.readline(), 'utf-8')

            if line is not None:
                if self.debug:
                    logging.debug(f"start_vnc: {line}")
                if "desktop at :" in line:
                    # match against the following pattern:
                    #New 'n3000.hyak.local:1 (hansem7)' desktop at :1 on machine n3000.hyak.local
                    pattern = re.compile("""
                            (New\s)
                            (\'([^:]+:(?P<display_number>[0-9]+))\s([^\s]+)\s)
                            """, re.VERBOSE)
                    match = re.match(pattern, line)
                    assert match is not None
                    self.vnc_display_number = int(match.group("display_number"))
                    self.vnc_port = self.vnc_display_number + BASE_VNC_PORT
                    if self.debug:
                        logging.debug(f"Obtained display number: {self.vnc_display_number}")
                        logging.debug(f"Obtained VNC port: {self.vnc_port}")
                    return True
        if self.debug:
            logging.error("Failed to start vnc session (Timeout/?)")
        print("start_vnc: Error: Timed out...")
        return False

    def kill_vnc(self, display_number=None):
        """
        Kill specified VNC session with given display number or all VNC sessions.
        """
        if display_number is None:
            target = ":*"
        else:
            assert display_number is not None
            target = ":" + str(display_number)
        if self.debug:
            print(f"Attempting to kill VNC session {target}")
            logging.debug(f"Attempting to kill VNC session {target}")
        cmd = self.cmd_prefix + " vncserver -kill " + target
        self.run_command(cmd)

class LoginNode(Node):
    def __init__(self, name, debug=False):
        assert os.path.exists(XSTARTUP_FILEPATH)
        assert os.path.exists(SINGULARITY_BIN)
        assert os.path.exists(XFCE_CONTAINER)
        super().__init__(name, debug)
        self.subnode = None

    def find_node(self, job_name="vnc"):
        """
        Returns a set of subnodes and returns None otherwise
        """
        ret = set()
        command = f"squeue | grep {os.getlogin()} | grep {job_name}"
        proc = self.run_command(command)
        while True:
            line = str(proc.stdout.readline(), 'utf-8')
            if self.debug:
                logging.debug(f"find_node: {line}")
            if not line:
                if not ret:
                    return None
                return ret
            if os.getlogin() in line:
                # match against pattern:
                #            864877 compute-h      vnc  hansem7  R       4:05      1 n3000
                # or the following if a node is in the process of being acquired
                #            870400 compute-h      vnc  hansem7 PD       0:00      1 (Resources)
                pattern = re.compile("""
                        (\s+)
                        (?P<job_id>[0-9]+)
                        (\s+[^ ]+\s+[^ ]+\s+[^ ]+\s+[^ ]+\s+[^ ]+\s+[^ ]+\s+)
                        (?P<subnode_name>[^\s]+)
                        """, re.VERBOSE)
                match = pattern.match(line)
                assert match is not None
                name = match.group("subnode_name")
                job_id = match.group("job_id")
                if "Resources" in name:
                    # Quit if another node is being allocated (from another process?)
                    proc.kill()
                    msg = f"Warning: Already allocating node with job {job_id}"
                    print(msg)
                    print("Please try again later or run again with --force argument")
                    if self.debug:
                        logging.info(f"name: {name}")
                        logging.info(f"job_id: {job_id}")
                        logging.warning(msg)
                elif self.debug:
                    msg = f"Found active subnode {name} with job ID {job_id}"
                    logging.debug(msg)
                tmp = SubNode(name, job_id, self.debug)
                ret.add(tmp)
        return None

    def check_vnc_password(self):
        """
        Returns True if vnc password is set and False otherwise
        """
        return os.path.exists(os.path.expanduser("~/.vnc/passwd"))

    def set_vnc_password(self):
        """
        Set VNC password
        """
        cmd = self.cmd_prefix + " vncpasswd"
        self.call_command(cmd)

    def call_command(self, command:str):
        """
        Call command (with arguments) on login node (to allow user interaction).

        Args:
          command:str : command and its arguments to run on subnode

        Returns None
        """
        if self.debug:
            msg = f"Calling on {self.name}: {command}"
            print(msg)
            logging.debug(msg)
        subprocess.call(command, shell=True)
        return None

    def run_command(self, command):
        """
        Run command (with arguments) on login node.
        Commands can be in either str or list format.

        Example:
          cmd_str = "echo hi"
          cmd_list = ["echo", "hi"]

        Args:
          command : command and its arguments to run on subnode

        Returns ssh subprocess with stderr->stdout and stdout->PIPE
        """
        assert command is not None
        if self.debug:
            msg = f"Running on {self.name}: {command}"
            print(msg)
            logging.debug(msg)
        if isinstance(command, list):
            return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        elif isinstance(command, str):
            return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def reserve_node(self, res_time=3, timeout=10, cpus=8, mem="16G", partition="compute-hugemem", account="ece", job_name="vnc"):
        """
        Reserves a node and waits until the node has been acquired.

        Args:
          res_time: Number of hours to reserve sub node
          timeout: Number of seconds to wait for node allocation
          cpus: Number of cpus to allocate
          mem: Amount of memory to allocate (Examples: "8G" for 8GiB of memory)
          partition: Partition name (see `man salloc` on --partition option for more information)
          account: Account name (see `man salloc` on --account option for more information)
          job_vnc: Slurm job name displayed in `squeue`

        Returns SubNode object if it has been acquired successfully and None otherwise.
        """
        cmd = ["timeout", str(timeout), "salloc", "-J", job_name, "--no-shell", "--exclusive", "-p", partition,
            "-A", account, "-t", str(res_time) + ":00:00", "--mem=" + mem, "-c", str(cpus)]
        proc = self.run_command(cmd)

        alloc_stat = False

        print("Allocating node...")
        while proc.poll() is None and not alloc_stat:
            print("...")
            line = str(proc.stdout.readline(), 'utf-8').strip()
            if self.debug:
                msg = f"reserve_node: {line}"
                logging.debug(msg)
            if "Granted job allocation" in line:
                # match against pattern:
                #salloc: Granted job allocation 864875
                pattern = re.compile("""
                        (salloc:\sGranted\sjob\sallocation\s)
                        (?P<job_id>[0-9]+)
                        """, re.VERBOSE)
                match = pattern.match(line)
                subnode_job_id = match.group("job_id")
            elif "are ready for job" in line:
                # match against pattern:
                #salloc: Nodes n3000 are ready for job
                pattern = re.compile("""
                        (salloc:\sNodes\s)
                        (?P<node_name>[ngz][0-9]{4})
                        (\sare\sready\sfor\sjob)
                        """, re.VERBOSE)
                match = pattern.match(line)
                subnode_name = match.group("node_name")
                alloc_stat = True
                break
            elif self.debug:
                msg = f"Skipping line: {line}"
                print(msg)
                logging.debug(msg)
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()

        if not alloc_stat:
            msg = "Error: node allocation timed out."
            print(msg)
            if self.debug:
                logging.error(msg)
            return None

        assert subnode_job_id is not None
        assert subnode_name is not None
        sn = self.subnode = SubNode(name=subnode_name, job_id=subnode_job_id, debug=self.debug)
        sn.res_time=res_time
        sn.timeout=timeout
        sn.cpus=cpus
        sn.mem=mem
        sn.partition=partition
        sn.account=account
        sn.job_name=job_name
        return self.subnode

    def cancel_job(self, job_id:int):
        """
        Cancel specified job ID

        Reference:
            See `man scancel` for more information on usage
        """
        msg = f"Canceling job ID {job_id}"
        print(f"\t{msg}")
        if self.debug:
            logging.debug(msg)
        proc = self.run_command(["scancel", str(job_id)])
        print(str(proc.communicate()[0], 'utf-8'))

    def check_port(self, port:int):
        """
        Returns True if port is unused and False if used.
        """
        if self.debug:
            logging.debug(f"Checking if port {port} is used...")
        netstat = psutil.net_connections()
        for entry in netstat:
            # Too verbose
            #if self.debug:
            #    logging.debug(f"Checking entry: {entry}")
            if port == entry[3].port:
                return False
        return True

    def get_port(self):
        """
        Returns unused port number if found and None if not found.
        """
        for i in range(0,300):
            port = BASE_VNC_PORT + i
            if self.check_port(port):
                return port
        return None

    def create_port_forward(self, login_port:int, subnode_port:int):
        """
        Port forward between login node and subnode

        Args:
          login_port:int : Login node port number
          subnode_port:int : Subnode port number

        Returns ssh-portforward subprocess with stderr->stdout and stdout->PIPE
        """
        assert self.subnode is not None
        assert self.subnode.name is not None
        if self.debug:
            msg = f"Creating port forward: Login node({login_port})<->Subnode({subnode_port})"
            logging.debug(msg)
        cmd = ["ssh", "-N", "-f", "-L", f"{login_port}:127.0.0.1:{subnode_port}", self.subnode.hostname]
        self.run_command(cmd)

    def get_port_forwards(self, nodes=None):
        """
        For each node in the SubNodes set `nodes`, get a port map between login
        node port and subnode port, and then fill `vnc_port` and
        `vnc_display_number` subnode attributes if None.

        Example:
          Suppose we have the following VNC sessions (on a single user account):
            n3000 with a login<->subnode port forward from 5900 to 5901,
            n3000 with a login<->subnode port forward from 5901 to 5902,
            n3042 with a login<->subnode port forward from 5903 to 5901.

            This function returns the following:
              { "n3000" : {5901:5900, 5902:5901}, "n3042" : {5901:5903} }

        Args:
          nodes = A set of SubNode objects with names to inspect

        Returns a dictionary with node name as keys and
        LoginNodePort (value) <-> SubNodePort (key) dictionary as value.
        """
        node_port_map = dict()
        if nodes is not None:
            for node in nodes:
                if "(" not in node.name:
                    port_map = dict()
                    cmd = f"ps aux | grep {os.getlogin()} | grep ssh | grep {node.name}"
                    proc = self.run_command(cmd)
                    while proc.poll() is None:
                        line = str(proc.stdout.readline(), 'utf-8').strip()
                        if cmd not in line:
                            pattern = re.compile("""
                                    ([^\s]+(\s)+){10}
                                    (ssh\s-N\s-f\s-L\s(?P<ln_port>[0-9]+):127.0.0.1:(?P<sn_port>[0-9]+))
                                    """, re.VERBOSE)
                            match = re.match(pattern, line)
                            if match is not None:
                                ln_port = int(match.group("ln_port"))
                                sn_port = int(match.group("sn_port"))
                                if node.vnc_port is None:
                                    node.vnc_port = sn_port
                                    node.vnc_display_number = sn_port - BASE_VNC_PORT
                                port_map.update({sn_port:ln_port})
                    node_port_map.update({node.name:port_map})
        return node_port_map

    def get_time_left(self, job_id:int, job_name="vnc"):
        """
        Returns the time remaining for given job ID or None if the job is not
        present.
        """
        cmd = f'squeue -o "%L %.18i %.8j %.8u %R" | grep {os.getlogin()} | grep {job_name} | grep {job_id}'
        proc = self.run_command(cmd)
        if proc.poll() is None:
            line = str(proc.stdout.readline(), 'utf-8')
            return line.split(' ', 1)[0]
        return None

    def print_props(self):
        """
        Print all properties (including subnode properties)
        """
        print("Login node properties:")
        props = vars(self)
        for item in props:
            msg = f"{item} : {props[item]}"
            print(f"\t{msg}")
            if self.debug:
                logging.debug(msg)
            if item == "subnode" and props[item] is not None:
                props[item].print_props()

def check_auth_keys():
    """
    Returns True if klone exists in ~/.ssh/authorized_keys and False otherwise
    """
    assert os.path.exists(AUTH_KEYS_FILEPATH)
    f = open(AUTH_KEYS_FILEPATH, "r")
    lines = f.readlines()
    for line in lines:
        line = line.strip()
        if "klone" in line:
            return True
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--partition',
                    dest='partition',
                    help='slurm partition',
                    type=str)
    parser.add_argument('-A', '--account',
                    dest='account',
                    help='slurm account',
                    type=str)
    parser.add_argument('-J',
                    dest='job_name',
                    help='slurm job name',
                    type=str)
    parser.add_argument('--port',
                    dest='u2h_port',
                    help='User<->Hyak Port',
                    type=int)
    parser.add_argument('-t', '--time',
                    dest='time',
                    help='Sub node reservation time (in hours)',
                    type=int)
    parser.add_argument('-c', '--cpus',
                    dest='cpus',
                    help='Sub node cpu count',
                    type=int)
    parser.add_argument('--mem',
                    dest='mem',
                    help='Sub node memory',
                    type=str)
    parser.add_argument('--status',
                    dest='print_status',
                    action='store_true',
                    help='Print VNC jobs and other details, and then exit')
    parser.add_argument('--kill',
                    dest='kill_job_id',
                    help='Kill specified VNC session, cancel its VNC job, and exit',
                    type=int)
    parser.add_argument('--kill-all',
                    dest='kill_all',
                    action='store_true',
                    help='Kill all VNC sessions, cancel VNC jobs, and exit')
    parser.add_argument('--set-passwd',
                    dest='set_passwd',
                    action='store_true',
                    help='Prompts for new VNC password')
    parser.add_argument('-d', '--debug',
                    dest='debug',
                    action='store_true',
                    help='Enable debug logging')
    parser.add_argument('-f', '--force',
                    dest='force',
                    action='store_true',
                    help='Skip node check and create a new VNC session')
    parser.add_argument('-v', '--version',
                    dest='print_version',
                    action='store_true',
                    help='Print program version and exit')
    args = parser.parse_args()

    if args.print_version:
        print(f"hyakvnc.py {VERSION}")
        exit(0)

    # setup logging
    if args.debug:
        log_filepath = os.path.expanduser("~/hyakvnc.log")
        print(f"Logging to {log_filepath}...")
        if os.path.exists(log_filepath):
            os.remove(log_filepath)
        logging.basicConfig(filename=log_filepath, level=logging.DEBUG)

    if args.debug:
        print("Arguments:")
        for item in vars(args):
            msg = f"{item}: {vars(args)[item]}"
            print(f"\t{msg}")
            logging.debug(msg)

    # check if running script on login node
    hostname = os.uname()[1]
    on_subnode = re.match("[ngz]([0-9]{4}).hyak.local", hostname)
    on_loginnode = hostname in LOGIN_NODE_LIST
    if on_subnode or not on_loginnode:
        msg = "Error: Please run on login node."
        print(msg)
        if args.debug:
            logging.error(msg)
        exit(1)

    # check if authorized_keys contains klone to allow intracluster ssh access
    # Reference:
    #  - https://hyak.uw.edu/docs/setup/ssh#intracluster-ssh-keys
    if not os.path.exists(AUTH_KEYS_FILEPATH) or not check_auth_keys():
        if args.debug:
            logging.warning("Warning: Not authorized for intracluster SSH access")
        print("Warning: Please authorize for intracluster SSH access")
        print(f"\tSee here for more information:")
        print(f"\t\thttps://hyak.uw.edu/docs/setup/ssh#intracluster-ssh-keys")

        # check if ssh key exists
        pr_key_filepath = os.path.expanduser("~/.ssh/id_rsa")
        pub_key_filepath = pr_key_filepath + ".pub"
        if not os.path.exists(pr_key_filepath):
            msg = "Warning: SSH key is missing"
            if args.debug:
                logging.warning(msg)
            print(msg)
            # prompt if user wants to create key
            response = input(f"Create SSH key ({pr_key_filepath})? [y/N] ")
            if re.match("[yY]", response):
                # create key
                print(f"Creating new SSH key ({pr_key_filepath})")
                cmd = f'ssh-keygen -C klone -t rsa -b 2048 -f {pr_key_filepath} -q -N ""'
                if args.debug:
                    print(cmd)
                subprocess.call(cmd, shell=True)
            else:
                msg = "Declined SSH key creation. Quiting program..."
                if args.debug:
                    logging.info(msg)
                print(msg)
                exit(1)

        response = input("Allow intracluster access? [y/N] ")
        if re.match("[yY]", response):
            # add key to authorized_keys
            cmd = f"cat {pub_key_filepath} >> {AUTH_KEYS_FILEPATH}"
            if args.debug:
                print(cmd)
            subprocess.call(cmd, shell=True)
            cmd = f"chmod 600 {AUTH_KEYS_FILEPATH}"
            if args.debug:
                print(cmd)
            subprocess.call(cmd, shell=True)
        else:
            print("Declined SSH key creation. Quiting program...")
            exit(1)
    else:
        if args.debug:
            logging.info("Already authorized for intracluster access.")

    # create login node object
    hyak = LoginNode(hostname, args.debug)

    # check for existing subnode
    node_set = hyak.find_node(job_name)
    if not args.print_status and not args.kill_all and args.kill_job_id is None and not args.force:
        if node_set is not None:
            for node in node_set:
                print(f"Error: Found active subnode {node.name} with job ID {node.job_id}")
            exit(1)

    # get port forwards (and display numbers)
    node_port_map = hyak.get_port_forwards(node_set)

    if args.print_status:
        print("Active VNC jobs:")
        if node_set is not None:
            for node in node_set:
                ln_port = None
                if node_port_map and node_port_map[node.name] and node.vnc_port in node_port_map[node.name]:
                    ln_port = node_port_map[node.name][node.vnc_port]
                time_left = hyak.get_time_left(node.job_id, job_name)
                vnc_active = node.check_vnc()
                print(f"\tJob ID: {node.job_id}")
                print(f"\t\tSubNode: {node.name}")
                print(f"\t\tVNC active: {vnc_active}")
                print(f"\t\tVNC display number: {node.vnc_display_number}")
                print(f"\t\tVNC port: {node.vnc_port}")
                print(f"\t\tMapped LoginNode port: {ln_port}")
                print(f"\t\tTime left: {time_left}")
        exit(0)

    if args.kill_job_id is not None:
        msg = f"Attempting to kill {args.kill_job_id}"
        print(msg)
        if args.debug:
            logging.info(msg)
        if node_set is not None:
            for node in node_set:
                if re.match(str(node.job_id), str(args.kill_job_id)):
                    if args.debug:
                        logging.info("Found kill target")
                        logging.info(f"\tVNC display number: {node.vnc_display_number}")
                    # kill vnc session
                    if node.vnc_display_number is not None:
                        node.kill_vnc(node.vnc_display_number)
                    # kill job
                    hyak.cancel_job(args.kill_job_id)
                    exit(0)
        msg = f"{args.kill_job_id} is not claimed or already killed"
        print(f"Error: {msg}")
        if args.debug:
            logging.error(msg)
        exit(1)

    if args.kill_all:
        msg = "Killing all VNC sessions..."
        print(msg)
        if args.debug:
            logging.debug(msg)
        # kill all vnc sessions
        if node_set is not None:
            for node in node_set:
                node.kill_vnc()
                hyak.cancel_job(node.job_id)
        exit(0)

    # set VNC password at user's request or if missing
    if not hyak.check_vnc_password() or args.set_passwd:
        if args.debug:
            logging.info("Setting new VNC password...")
        print("Please set new VNC password...")
        hyak.set_vnc_password()

    # reserve node
    res_time = 3 # hours
    timeout = 20 # seconds
    cpus = 8
    mem = "16G"
    partition = "compute-hugemem"
    account = "ece"
    job_name = "vnc"
    if args.cpus is not None:
        cpus = args.cpus
    if args.mem is not None:
        # check format
        if re.match("[0-9]+[KMGT]", args.mem):
            mem = args.mem
    if args.account is not None:
        account = args.account
    if args.partition is not None:
        partition = args.partition
    if args.job_name is not None:
        job_name = args.job_name
    if args.time is not None:
        res_time = args.time
    # TODO: allow node count override (harder to implement)
    subnode = hyak.reserve_node(res_time, timeout, cpus, mem, partition, account, job_name)
    if subnode is None:
        exit(1)

    print("...Node reserved")

    # start vnc
    print("Starting VNC...")
    ret = subnode.start_vnc()
    if not ret:
        hyak.cancel_job(subnode.job_id)
        exit(1)

    # get unused User<->Login port
    # CHANGE ME: NOT ROBUST
    if args.u2h_port is not None and hyak.check_port(args.u2h_port):
        hyak.u2h_port = args.u2h_port
    else:
        hyak.u2h_port = hyak.get_port()

    # quit if port is still bad
    if hyak.u2h_port is None:
        msg = "Error: Unable to get port"
        print(msg)
        if args.debug:
            logging.error(msg)
        hyak.cancel_job(subnode.job_id)
        exit(1)

    if args.debug:
        hyak.print_props()

    # create port forward between login and sub nodes
    print(f"Creating port forward: Login node({hyak.u2h_port})<->Subnode({subnode.vnc_port})")
    h2s_fwd_proc = hyak.create_port_forward(hyak.u2h_port, subnode.vnc_port)

    # check if port forward succeeded
    time.sleep(2)
    tmp = hyak.get_port_forwards({subnode})
    if tmp and tmp[subnode.name] and subnode.vnc_port in tmp[subnode.name] and tmp[subnode.name][subnode.vnc_port] == hyak.u2h_port:
        msg = f"Successfully created port forward"
        print(msg)
        if args.debug:
            logging.info(msg)
    else:
        msg = f"Error: Failed to create port forward"
        print(msg)
        if args.debug:
            logging.error(msg)
        hyak.cancel_job(subnode.job_id)
        exit(1)

    # print command to setup User<->Login port forwarding
    print("=====================")
    print("Run the following in a new terminal window:")
    msg = f"ssh -N -f -L {hyak.u2h_port}:127.0.0.1:{hyak.u2h_port} {os.getlogin()}@klone.hyak.uw.edu"
    print(f"\t{msg}")
    if args.debug:
        logging.debug(msg)
    print(f"then connect to VNC session at localhost:{hyak.u2h_port}")
    print("=====================")

    exit(0)

if __name__ == "__main__":
    main()
