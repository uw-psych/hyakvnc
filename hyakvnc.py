#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

# default node allocation settings
RES_TIME = 4 # hours
TIMEOUT = 120 # seconds
CPUS = 8
MEM = "16G"
PARTITION = "compute-hugemem"
ACCOUNT = "ece"
JOB_NAME = "ece_vnc"

VERSION = 1.1

# Created by Hansem Ro <hansem7@uw.edu> <hansemro@outlook.com>
# Maintained by ECE TAs

# Quick start guide
#
# 1. To start VNC session for 5 hours on node with 16 cores and 32GB of memory,
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
# 2. Set up port forward between your computer and HYAK login node.
#    On your machine, in a new terminal window, run the the copied command.
#
#    In this example, run
#      $ ssh -N -f -L 5901:127.0.0.1:5901 hansem7@klone.hyak.uw.edu
#
# 3. Connect to VNC session at instructed address (in example: localhost:5901)
#
# 4. To close VNC session, run the following
#      $ ./hyakvnc.py --kill-all
#
# 5. Kill port forward process from step 2


# Usage: ./hyakvnc.py [-h/--help] [OPTIONS]
#
# Options:
#   -h, --help : print help message and exit
#
#   -v, --version : print program version and exit
#
#   -d, --debug : [default: disabled] show debug messages and enable debug
#                 logging at ~/hyakvnc.log
#
#   -f, --force : [default: single VNC job] allow multiple VNC jobs/sessions
#
#   -p <part>, --partition <part> : [default: compute-hugemem] Slurm partition
#
#   -A <account>, --account <account> : [default: ece] Slurm account
#
#   -J <job_name> : [default: ece_vnc] Slurm job name
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
#                - VNC session status
#                - VNC display number
#                - Subnode/VNC port
#                - User/LoginNode port
#                - Time left
#                - SSH port forward command
#
#   --restart <job_id> : restart VNC session (with same port) for specific job
#
#   --kill <job_id> : kill specific job
#
#   --kill-all : kill all VNC jobs with targeted Slurm job name
#
#   --set-passwd : prompt to set VNC password and exit
#

# Dependencies:
# - Python 3.6 or newer
# - Singularity 3.7
# - Slurm
# - netstat utility
# - XFCE container:
#   - xfce4
#   - tigervnc with vncserver

import argparse # for argument handling
import logging # for debug logging
import time # for sleep
import signal # for signal handling
import glob
import pwd
import os # for path, file/dir checking, hostname
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
# - [x] Remove psutil dependency
# - [x] Handle SIGINT and SIGTSTP signals
# - [x] Add user argument to restart VNC session of active node
# - [ ] Specify singularity container to run
# - [x] Document dependencies of external tools: slurm, singularity, xfce container, tigervnc
# - [ ] Use pyslurm to interface with Slurm: https://github.com/PySlurm/pyslurm
# - [x] Delete ~/.ssh/known_hosts before ssh'ing into subnode
# - [ ] Replace netstat with ss
# - [x] Create and use singularity instance. Then share instructions to enter instance.
# - [x] Delete /tmp/.X11-unix/X<DISPLAY_NUMBER> if display number is not used on subnode
#       Info: This can cause issues for vncserver (tigervnc)
# - [x] Delete all owned socket files in /tmp/.ICE-unix/
# - [ ] Add singularity to $PATH if missing.
# - [x] Remove stale VNC processes
# - [ ] Add user argument to restart container instance

# Base VNC port cannot be changed due to vncserver not having a stable argument
# interface:
BASE_VNC_PORT = 5900

# List of Klone login nodes
LOGIN_NODE_LIST = ["klone1.hyak.uw.edu", "klone2.hyak.uw.edu"]

# Full path to Singularity binary
SINGULARITY_BIN = "/opt/ohpc/pub/libs/singularity/3.7.1/bin/singularity"

# Singularity container with XFCE + vncserver (tigervnc)
XFCE_CONTAINER = "/gscratch/ece/xfce_singularity/xfce.sif"

# Script used to start desktop environment (XFCE)
XSTARTUP_FILEPATH = "/gscratch/ece/xfce_singularity/xstartup"

# Checked to see if klone is authorized for intracluster access
AUTH_KEYS_FILEPATH = os.path.expanduser("~/.ssh/authorized_keys")

# Singularity bindpaths can be overwritten if $SINGULARITY_BINDPATH is defined.
# Bindpaths are used to mount storage paths to containerized environment.
SINGULARITY_BINDPATH = os.getenv("SINGULARITY_BINDPATH")
if SINGULARITY_BINDPATH is None:
    SINGULARITY_BINDPATH = "/tmp:/tmp,$HOME,$PWD,/gscratch,/opt:/opt,/:/hyak_root"

class Node:
    """
    The Node class has the following initial data: bool: debug, string: name,
    string: sing_exec_container.

    debug: Print and log debug messages if True.
    name: Shortened hostname of node.
    sing_exec_container: Add before command to execute inside a singularity
                         container (but note that it cannot interact with
                         processes inside a container instance since they are
                         isolated).
    """

    def __init__(self, name, debug=False):
        self.debug = debug
        self.name = name
        self.sing_exec_container = f"{SINGULARITY_BIN} exec -B {SINGULARITY_BINDPATH} {XFCE_CONTAINER}"

class SubNode(Node):
    """
    The SubNode class specifies a node requested via Slurm (also known as work
    or interactive node). SubNode class is initialized with the following:
    bool: debug, string: name, string: sing_exec, string: hostname, int: job_id.

    SubNode class with active VNC session may contain vnc_display_number and
    vnc_port.

    debug: Print and log debug messages if True.
    name: Shortened subnode hostname (e.g. n3000) described inside `/etc/hosts`.
    hostname: Full subnode hostname (e.g. n3000.hyak.local).
    job_id: Slurm Job ID that allocated the node.
    vnc_display_number: X display number used for VNC session.
    vnc_port: vnc_display_number + BASE_VNC_PORT.
    sing_exec: Add before command to execute inside singularity container
               instance.
    """

    def __init__(self, name, job_id, debug=False):
        assert os.path.exists(AUTH_KEYS_FILEPATH)
        super().__init__(name, debug)
        self.hostname = f"{name}.hyak.local"
        self.job_id = job_id
        self.vnc_display_number = None
        self.vnc_port = None
        self.sing_exec = f"{SINGULARITY_BIN} exec -B {SINGULARITY_BINDPATH} instance://{self.job_id}"

    def print_props(self):
        """
        Print properties of SubNode object.
        """
        print("SubNode properties:")
        props = vars(self)
        for item in props:
            msg = f"{item} : {props[item]}"
            print(f"\t{msg}")
            if self.debug:
                logging.debug(msg)

    def run_command(self, command:str, timeout=None):
        """
        Run command (with arguments) on subnode

        Args:
          command:str : command and its arguments to run on subnode
          timeout : [Default: None] timeout length in seconds

        Returns ssh subprocess with stderr->stdout and stdout->PIPE
        """
        assert self.name is not None
        cmd = ["ssh", self.hostname, command]
        if timeout is not None:
            cmd.insert(0, "timeout")
            cmd.insert(1, str(timeout))
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
        if display_number is not None:
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
        cmd = f"{self.sing_exec} ps -U {os.getlogin()}"
        proc = self.run_command(cmd)
        while proc.poll() is None:
            line = str(proc.stdout.readline(), "utf-8").strip()
            if str(pid) in line:
                if self.debug:
                    msg = f"Matched PID in line: {line}"
                    logging.debug(msg)
                return True
        return False

    def check_singularity_instance(self):
        """
        Returns True if singularity instance with job_id as its name exists and
        False otherwise.
        """
        cmd = f"{SINGULARITY_BIN} instance list | grep {self.job_id}"
        proc = self.run_command(cmd)
        while proc.poll() is None:
            line = str(proc.stdout.readline(), "utf-8").strip()
            if self.debug:
                logging.debug(line)
            if self.job_id in line:
                return True
        return False

    def start_singularity_instance(self):
        """
        Starts singularity instance with job_id as its name.

        Returns True on success and False on failure.
        """
        cmd = f'{SINGULARITY_BIN} instance start -B {SINGULARITY_BINDPATH} {XFCE_CONTAINER} {self.job_id}'
        proc = self.run_command(cmd)
        while proc.poll() is None:
            line = str(proc.stdout.readline(), "utf-8").strip()
            if self.debug:
                logging.debug(line)
            if "instance started successfully" in line:
                return True
        return False

    def stop_singularity_instance(self):
        """
        Stops singularity instance with job_id as its name.

        Returns True if instance was stopped and False otherwise.
        """
        cmd = f"{SINGULARITY_BIN} instance stop {self.job_id}"
        proc = self.run_command(cmd)
        while proc.poll() is None:
            line = str(proc.stdout.readline(), "utf-8").strip()
            if self.debug:
                logging.debug(line)
            if "no instance found" in line:
                return False
            if f"Stopping {self.job_id} instance of" in line:
                return True
        return False

    def start_vnc(self, display_number=None):
        """
        Starts VNC session

        Args:
          display_number: Attempt to acquire specified display number if set.
                          If None, then let vncserver determine display number.

        Returns True if VNC session was started successfully and False otherwise
        """
        timer = 15
        target = ""
        if display_number is not None:
            target = f":{display_number}"
        vnc_cmd = f"{self.sing_exec} vncserver {target} -xstartup {XSTARTUP_FILEPATH} &"
        proc = self.run_command(vnc_cmd, timeout=timer)

        # get display number and port number
        while proc.poll() is None:
            line = str(proc.stdout.readline(), 'utf-8').strip()

            if line is not None:
                if self.debug:
                    logging.debug(f"start_vnc: {line}")
                if "desktop" in line:
                    # match against the following pattern:
                    #New 'n3000.hyak.local:1 (hansem7)' desktop at :1 on machine n3000.hyak.local
                    #New 'n3000.hyak.local:6 (hansem7)' desktop is n3000.hyak.local:6
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

    def list_vnc(self):
        """
        Returns a list of active and stale vnc sessions on subnode.
        """
        active = list()
        stale = list()
        cmd = f"{self.sing_exec} vncserver -list"
        proc = self.run_command(cmd)
        skip = True
        while proc.poll() is None:
            line = str(proc.stdout.readline(), "utf-8").strip()
            #TigerVNC server sessions:
            #
            #X DISPLAY #	PROCESS ID
            #:1		7280 (stale)
            #:12		29 (stale)
            #:2		83704 (stale)
            #:20		30
            #:3		84266 (stale)
            #:4		90576 (stale)
            if "server sessions" in line:
                pass
            elif "X DISPLAY" in line:
                skip = False
            elif not skip and ":" in line:
                if self.debug:
                    msg = f"list_vnc: {line}"
                    logging.debug(msg)
                pattern = re.compile("""
                        (:)
                        (?P<display_number>[0-9]+)
                        """, re.VERBOSE)
                match = pattern.match(line)
                if match is not None:
                    display_number = match.group("display_number")
                    if "stale" in line:
                        stale.append(display_number)
                    else:
                        active.append(display_number)
        return (active,stale)

    def __path_exists__(self, path):
        """
        Returns True if path exists on subnode and False otherwise.
        """
        status = subprocess.call(['ssh', self.hostname, f"test -e {path}"])
        if status == 0:
            return True
        return False

    def __get_owner__(self, path):
        """
        Returns owner of file as a string and None if there was an error.
        """
        cmd=f"stat --format '%U' {path}"
        proc = self.run_command(cmd)
        if proc.poll() is None:
            line = str(proc.stdout.readline(), "utf-8").strip()
            if "stat" in line:
                return None
            return line
        return None

    def __remove_file__(self, filepath:str):
        """
        Removes file on subnode and returns True on success and False otherwise.
        """
        if self.__path_exists__(filepath) and self.__get_owner__(filepath) == os.getlogin():
            if self.debug:
                logging.debug(f"Deleting {filepath}...")
            status = subprocess.call(['ssh', self.hostname, f"rm {filepath}"])
            if status == 0:
                return True
            return False

    def __listdir__(self, dirpath):
        """
        Returns a list of contents inside directory.
        """
        ret = list()
        if self.__path_exists__(dirpath):
            cmd = f"ls -al {dirpath} | tail -n+4"
            proc = self.run_command(cmd)
            while proc.poll() is None:
                line = str(proc.stdout.readline(), "utf-8").strip()
                pattern = re.compile("""
                    ([^\s]+\s+){8}
                    (?P<name>.*)
                    """, re.VERBOSE)
                match = re.match(pattern, line)
                if match is not None:
                    name = match.group("name")
                    ret.append(name)
        return ret

    def kill_vnc(self, display_number=None):
        """
        Kill specified VNC session with given display number or all VNC sessions.
        """
        if display_number is None:
            active,stale = self.list_vnc()
            for entry in active:
                if self.debug:
                    logging.debug(f"kill_vnc: active entry: {entry}")
                self.kill_vnc(entry)
            for entry in stale:
                if self.debug:
                    logging.debug(f"kill_vnc: stale entry: {entry}")
                self.kill_vnc(entry)
            # Remove all remaining pid files
            pid_list = glob.glob(os.path.expanduser("~/.vnc/*.pid"))
            for pid_file in pid_list:
                self.__remove_file__(pid_file)
            # Remove all owned socket files on subnode
            # Note: subnode maintains its own /tmp/ directory
            x11_unix = "/tmp/.X11-unix"
            ice_unix = "/tmp/.ICE-unix"
            for entry in self.__listdir__(x11_unix):
                self.__remove_file__(f"{x11_unix}/{entry}")
            for entry in self.__listdir__(ice_unix):
                self.__remove_file__(f"{x11_unix}/{entry}")
        else:
            assert display_number is not None
            target = f":{display_number}"
            if self.debug:
                print(f"Attempting to kill VNC session {target}")
                logging.debug(f"Attempting to kill VNC session {target}")
            cmd = f"{self.sing_exec} vncserver -kill {target}"
            proc = self.run_command(cmd)
            killed = False
            while proc.poll() is None:
                line = str(proc.stdout.readline(), "utf-8").strip()
                # Failed attempt:
                #Can't kill '29': Operation not permitted
                #Killing Xtigervnc process ID 29...
                # On successful attempt:
                #Killing Xtigervnc process ID 29... success!
                if self.debug:
                    logging.debug(f"kill_vnc: {line}")
                if "success" in line:
                    killed = True
            if self.debug:
                logging.debug(f"kill_vnc: killed? {killed}")
            # Remove target's pid file if present
            local_vnc_pid_file = os.path.expanduser(f"~/.vnc/{self.hostname}{target}.pid")
            self.__remove_file__(local_vnc_pid_file)
            # Remove associated /tmp/.X11-unix/<display_number> socket
            socket_file = f"/tmp/.X11-unix/{display_number}"
            self.__remove_file__(socket_file)

    def restart_vnc(self, display_number=None):
        """
        Restart VNC sesion with same port.

        Basic assumptions:
          - Assumes LoginNode<->SubNode port forward is alive. Otherwise, we
            would have to create a new portforward.
        """
        if display_number is None:
            assert self.vnc_display_number is not None
            display_number = self.vnc_display_number
        # kill VNC job
        self.kill_vnc(display_number)
        # start VNC job with same port
        status = self.start_vnc(display_number)
        print(status)

class LoginNode(Node):
    """
    The LoginNode class specifies Hyak login node for its Slurm and SSH
    capabilities.
    """

    def __init__(self, name, debug=False):
        assert os.path.exists(XSTARTUP_FILEPATH)
        assert os.path.exists(SINGULARITY_BIN)
        assert os.path.exists(XFCE_CONTAINER)
        super().__init__(name, debug)
        self.subnode = None

    def find_nodes(self, job_name="vnc"):
        """
        Returns a set of subnodes with given job name and returns None otherwise
        """
        ret = set()
        command = f"squeue | grep {os.getlogin()} | grep {job_name}"
        proc = self.run_command(command)
        while True:
            line = str(proc.stdout.readline(), 'utf-8')
            if self.debug:
                logging.debug(f"find_nodes: {line}")
            if not line:
                if not ret:
                    return None
                return ret
            if os.getlogin() in line:
                # match against pattern:
                #            864877 compute-h      vnc  hansem7  R       4:05      1 n3000
                # or the following if a node is in the process of being acquired
                #            870400 compute-h      vnc  hansem7 PD       0:00      1 (Resources)
                # or the following if a node failed to be acquired and needs to be killed
                #            984669 compute-h      vnc  hansem7 PD       0:00      1 (QOSGrpCpuLimit)
                pattern = re.compile("""
                        (\s+)
                        (?P<job_id>[0-9]+)
                        (\s+[^ ]+){6}
                        (\s+)
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
                    print("Please try again later or run again with '--force' argument")
                    if self.debug:
                        logging.info(f"name: {name}")
                        logging.info(f"job_id: {job_id}")
                        logging.warning(msg)
                elif "QOS" in name:
                    proc.kill()
                    msg = f"Warning: job {job_id} needs to be killed"
                    print(msg)
                    print(f"Please run this script again with '--kill {job_id}' argument")
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
        cmd = f"{self.sing_exec_container} vncpasswd"
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

        Returns subprocess with stderr->stdout and stdout->PIPE
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
          job_name: Slurm job name displayed in `squeue`

        Returns SubNode object if it has been acquired successfully and None otherwise.
        """
        cmd = ["timeout", str(timeout), "salloc", "-J", job_name, "--no-shell", "-p", partition,
            "-A", account, "-t", str(res_time) + ":00:00", "--mem=" + mem, "-c", str(cpus)]
        proc = self.run_command(cmd)

        alloc_stat = False
        subnode_job_id = None
        subnode_name = None

        def __reserve_node_irq_handler__(signalNumber, frame):
            """
            Pass SIGINT to subprocess and exit program.
            """
            if self.debug:
                msg = f"reserve_node: Caught signal: {signalNumber}"
                print(msg)
                logging.info(msg)
            proc.send_signal(signal.SIGINT)
            print("Cancelled node allocation. Exiting...")
            exit(1)

        # Stop allocation when  SIGINT (CTRL+C) and SIGTSTP (CTRL+Z) signals
        # are detected.
        signal.signal(signal.SIGINT, __reserve_node_irq_handler__)
        signal.signal(signal.SIGTSTP, __reserve_node_irq_handler__)

        print(f"Allocating node with {cpus} CPUs and {mem} RAM for {res_time} hours...")
        while proc.poll() is None and not alloc_stat:
            print("...")
            line = str(proc.stdout.readline(), 'utf-8').strip()
            if self.debug:
                msg = f"reserve_node: {line}"
                logging.debug(msg)
            if "Pending" in line or "Granted" in line:
                # match against pattern:
                #salloc: Pending job allocation 864875
                #salloc: Granted job allocation 864875
                pattern = re.compile("""
                        (salloc:\s)
                        ((Granted)|(Pending))
                        (\sjob\sallocation\s)
                        (?P<job_id>[0-9]+)
                        """, re.VERBOSE)
                match = pattern.match(line)
                if match is not None:
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
                if match is not None:
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
            # check if node actually got reserved
            # Background: Sometimes salloc does not print allocated node names
            #             at the end, so we have to check with squeue
            if subnode_job_id is not None:
                tmp_nodes = self.find_nodes(job_name)
                for tmp_node in tmp_nodes:
                    if self.debug:
                        logging.debug(f"reserve_node: fallback: Checking {tmp_node.name} with Job ID {tmp_node.job_id}")
                    if tmp_node.job_id == subnode_job_id:
                        if self.debug:
                            logging.debug(f"reserve_node: fallback: Match found")
                        # get subnode name
                        subnode_name = tmp_node.name
                        break
            else:
                return None
            if subnode_name is None:
                msg = "Error: node allocation timed out."
                print(msg)
                if self.debug:
                    logging.error(msg)
                return None

        assert subnode_job_id is not None
        assert subnode_name is not None
        self.subnode = SubNode(name=subnode_name, job_id=subnode_job_id, debug=self.debug)
        self.subnode.res_time=res_time
        self.subnode.timeout=timeout
        self.subnode.cpus=cpus
        self.subnode.mem=mem
        self.subnode.partition=partition
        self.subnode.account=account
        self.subnode.job_name=job_name
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
        cmd = f"netstat -ant | grep LISTEN | grep {port}"
        proc = self.run_command(cmd)
        while proc.poll() is None:
            line = str(proc.stdout.readline(), 'utf-8').strip()
            if self.debug:
                logging.debug(f"netstat line: {line}")
            if str(port) in line:
                return False
        return True

    def get_port(self):
        """
        Returns unused port number if found and None if not found.
        """
        # 300 is arbitrary limit
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
          nodes : A set of SubNode objects with names to inspect

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
                            # Match against pattern:
                            #hansem7  2772462  0.0  0.0 286052   964 ?        Ss   00:53   0:00 ssh -N -f -L 5900:127.0.0.1:5901 n3000.hyak.local
                            pattern = re.compile("""
                                    ([^\s]+(\s)+){10}
                                    (ssh\s-N\s-f\s-L\s(?P<ln_port>[0-9]+):127.0.0.1:(?P<sn_port>[0-9]+))
                                    """, re.VERBOSE)
                            match = re.match(pattern, line)
                            if match is not None:
                                ln_port = int(match.group("ln_port"))
                                sn_port = int(match.group("sn_port"))
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

    def print_status(self, job_name:str, node_set=None, node_port_map=None):
        """
        Print details of each active VNC job in node_set. VNC port and display
        number should be in node_port_map.
        """
        print(f"Active {job_name} jobs:")
        if node_set is not None:
            for node in node_set:
                ln_port = None
                if node_port_map and node_port_map[node.name] and node.vnc_port in node_port_map[node.name]:
                    ln_port = node_port_map.get(node.name).pop(node.vnc_port)
                time_left = self.get_time_left(node.job_id, job_name)
                vnc_active = node.check_vnc()
                container_instance_active = node.check_singularity_instance()
                ssh_cmd = f"ssh -N -f -L {ln_port}:127.0.0.1:{ln_port} {os.getlogin()}@klone.hyak.uw.edu"
                enter_container_cmd = f"ssh -t {node.name} {SINGULARITY_BIN} shell instance://{node.job_id}"
                print(f"\tJob ID: {node.job_id}")
                print(f"\t\tSubNode: {node.name}")
                print(f"\t\tVNC active: {vnc_active}")
                print(f"\t\tVNC display number: {node.vnc_display_number}")
                print(f"\t\tVNC port: {node.vnc_port}")
                print(f"\t\tMapped LoginNode port: {ln_port}")
                print(f"\t\tTime left: {time_left}")
                if ln_port is not None:
                    print(f"\t\tRun command: {ssh_cmd}")
                if container_instance_active:
                    print(f"\t\tEnter container: {enter_container_cmd}")

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
                    help='Slurm partition',
                    default=PARTITION,
                    type=str)
    parser.add_argument('-A', '--account',
                    dest='account',
                    help='Slurm account',
                    default=ACCOUNT,
                    type=str)
    parser.add_argument('-J',
                    dest='job_name',
                    help='Slurm job name',
                    default=JOB_NAME,
                    type=str)
    parser.add_argument('--timeout',
                    dest='timeout',
                    help='Allocation timeout length (in seconds)',
                    default=TIMEOUT,
                    type=int)
    parser.add_argument('--port',
                    dest='u2h_port',
                    help='User<->Hyak Port',
                    type=int)
    parser.add_argument('-t', '--time',
                    dest='time',
                    help='Subnode reservation time (in hours)',
                    default=RES_TIME,
                    type=int)
    parser.add_argument('-c', '--cpus',
                    dest='cpus',
                    help='Subnode cpu count',
                    default=CPUS,
                    type=int)
    parser.add_argument('--mem',
                    dest='mem',
                    help='Subnode memory',
                    default=MEM,
                    type=str)
    parser.add_argument('--status',
                    dest='print_status',
                    action='store_true',
                    help='Print VNC jobs and other details, and then exit')
    parser.add_argument('--restart',
                    dest='restart_job_id',
                    help='Restart VNC session for specified job id, and then exit',
                    type=int)
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
                    help='Prompts for new VNC password and exit')
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

    # check memory format
    assert(re.match("[0-9]+[KMGT]", args.mem))

    if args.print_version:
        print(f"hyakvnc.py {VERSION}")
        exit(0)

    # Debug: setup logging
    if args.debug:
        log_filepath = os.path.expanduser("~/hyakvnc.log")
        print(f"Logging to {log_filepath}...")
        if os.path.exists(log_filepath):
            os.remove(log_filepath)
        logging.basicConfig(filename=log_filepath, level=logging.DEBUG)

    # Debug: print passed arguments
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

    # delete ~/.ssh/known_hosts in case Hyak maintenance causes node identity
    # mismatch. This can break ssh connection to subnode and cause port
    # forwarding to subnode to fail.
    ssh_known_hosts = os.path.expanduser("~/.ssh/known_hosts")
    if os.path.exists(ssh_known_hosts):
        os.remove(ssh_known_hosts)

    # create login node object
    hyak = LoginNode(hostname, args.debug)

    # set VNC password at user's request or if missing
    if not hyak.check_vnc_password() or args.set_passwd:
        if args.debug:
            logging.info("Setting new VNC password...")
        print("Please set new VNC password...")
        hyak.set_vnc_password()
        if args.set_passwd:
            exit(0)

    # check for existing subnodes with same job name
    node_set = hyak.find_nodes(args.job_name)
    if not args.print_status and \
            args.restart_job_id is None and \
            not args.kill_all and \
            args.kill_job_id is None and \
            not args.force:
        if node_set is not None:
            for node in node_set:
                print(f"Error: Found active subnode {node.name} with job ID {node.job_id}")
            exit(1)

    # get port forwards (and display numbers)
    # TODO: accurately map VNC display number and port to Slurm job
    node_port_map = hyak.get_port_forwards(node_set)

    if args.print_status:
        hyak.print_status(args.job_name, node_set, node_port_map)
        exit(0)

    if args.restart_job_id is not None or args.kill_job_id is not None:
        kill = False
        target = args.restart_job_id
        if args.kill_job_id:
            # kill single VNC job with same job name
            msg = f"Attempting to kill {args.kill_job_id}"
            kill = True
            target = args.kill_job_id
        else:
            # restart single VNC job with same job name
            msg = f"Attempting to restart {args.restart_job_id}"
        print(msg)
        if args.debug:
            logging.info(msg)
        if node_set is not None:
            # find target job (with same job name) and quit
            for node in node_set:
                if re.match(str(node.job_id), str(target)):
                    if args.debug:
                        logging.info("Found target")
                        logging.info(f"\tVNC display number: {node.vnc_display_number}")
                    if kill:
                        # stop singularity instance
                        node.stop_singularity_instance()
                        # kill vnc session
                        if node.vnc_display_number is not None:
                            node.kill_vnc(node.vnc_display_number)
                        # cancel job
                        hyak.cancel_job(target)
                    else:
                        # restart vnc session
                        node.restart_vnc()
                        pass
                    exit(0)
        msg = f"Failed to find node"
        if kill:
            msg = f"{args.kill_job_id} is not claimed or already killed"
        print(f"Error: {msg}")
        if args.debug:
            logging.error(msg)
        exit(1)

    if args.kill_all:
        # kill all VNC jobs with same job name
        msg = f"Killing all VNC sessions with job name {args.job_name}..."
        print(msg)
        if args.debug:
            logging.debug(msg)
        if node_set is not None:
            for node in node_set:
                # stop singularity instance
                node.stop_singularity_instance()
                # kill all vnc sessions
                node.kill_vnc()
                # cancel job
                hyak.cancel_job(node.job_id)
        exit(0)

    # reserve node
    # TODO: allow node count override (harder to implement)
    subnode = hyak.reserve_node(args.time, args.timeout, args.cpus, args.mem, args.partition, args.account, args.job_name)
    if subnode is None:
        exit(1)

    print(f"...Node {subnode.name} reserved with Job ID: {subnode.job_id}")

    def __irq_handler__(signalNumber, frame):
        """
        Cancel job and exit program.
        """
        if args.debug:
            msg = f"main: Caught signal: {signalNumber}"
            print(msg)
            logging.info(msg)
        print("Cancelling job...")
        hyak.cancel_job(subnode.job_id)
        print("Exiting...")
        exit(1)

    # Cancel job and exit when SIGINT (CTRL+C) or SIGTSTP (CTRL+Z) signals are
    # detected.
    signal.signal(signal.SIGINT, __irq_handler__)
    signal.signal(signal.SIGTSTP, __irq_handler__)

    # Start singularity instance
    if not subnode.start_singularity_instance():
        msg = "Error: Unable to start singularity instance"
        print(msg)
        if args.debug:
            logging.debug(msg)
        hyak.cancel_job(subnode.job_id)
        exit(1)

    # start vnc session in singularity instance
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

    # wait until port forward succeeds
    count = 0
    port_fwd_success = False
    while count < 20 and port_fwd_success:
        port_fwd_success = not hyak.check_port(hyak.u2h_port)
        count += 1
        time.sleep(1)

    if not port_fwd_success:
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
    # print command to enter container instance
    print("Run the following to enter container instance:")
    msg = f"ssh -t {subnode.name} {SINGULARITY_BIN} shell instance://{subnode.job_id}"
    print(f"\t{msg}")
    print("Info: Add -Y flag to ssh to enable X11-forwarding")
    if args.debug:
        logging.debug(msg)
    print("=====================")

    exit(0)

if __name__ == "__main__":
    main()
