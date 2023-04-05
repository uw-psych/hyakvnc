hyakvnc
=======

Create and manage VNC Slurm jobs on UW HYAK Klone cluster.

`hyakvnc` allocates resources then starts a VNC session within an Apptainer
environment.

Disclaimer: VNC sessions are time-limited and will expire with all processes
closed. Save often if you can or reserve a session for a generous length of
time.

## Get started

### Prerequisites

Before running `hyakvnc`, you'll need the following:
- SSH client
- VNC client/viewer
    - TigerVNC viewer is recommended for all platforms
- HYAK Klone access with compute resources
- VNC Apptainer with TigerVNC server and a desktop environment
    - Install additional tools and libraries to the container as required by
      programs running within the VNC session.
- xstartup script used to launch a desktop environment

### Building

Update pip:
```bash
python3 -m pip install --upgrade --user pip
```

Build and install the package:

```bash
python3 -m pip install --user git+https://github.com/uw-psych/hyakvnc
```

Or, clone the repo and install the package locally:

```bash
git clone https://github.com/uw-psych/hyakvnc
python3 -m pip install --user .
```

If successful, then `hyakvnc` should be installed to `~/.local/bin/`.

### General usage

`hyakvnc` is command-line tool that only works while on the login node.

### Creating a VNC session

1. Start a VNC session with the `hyakvnc create` command followed by arguments
   to specify the Slurm account and partition, compute resource needs,
   reservation time, and paths to a VNC apptainer and xstartup script.

```bash
# example: Starting VNC session on `ece` compute resources for 5 hours on a
# node with 16 cores and 32GB of memory
hyakvnc create -A ece -p compute-hugemem \
    -t 5 -c 16 --mem 32G \
    --container /path/to/container.sif \
    --xstartup /path/to/xstartup
```

2. If successful, `hyakvnc` should print a unique port forward command:

```
...
=====================
Run the following in a new terminal window:
        ssh -N -f -L AAAA:127.0.0.1:BBBB hansem7@klone.hyak.uw.edu
then connect to VNC session at localhost:AAAA
=====================
```

Copy this port forward command for the following step.

3. Set up port forward between your computer and HYAK login node. On your
   machine, in a new terminal window, run the the copied command.

Following the example, run:

```bash
ssh -N -f -L AAAA:127.0.0.1:BBBB hansem7@klone.hyak.uw.edu
```

Alternatively, for PuTTY users, navigate to
PuTTY Configuration->Connection->SSH->Tunnels, then set:
  - source port to `AAAA`
  - destination to `127.0.0.1:BBBB`

Press `Add`, then connect to Klone as normal. Keep this window open as it
maintains a connection to the VNC session running on Klone.

4. Connect to the VNC session at instructed address (in this example:
   `localhost:AAAA`)

5. To close the VNC session, run the following

```bash
hyakvnc kill-all
```

### Checking active VNC sessions

Print details of active VNC sessions (with the same job name) with the
`hyakvnc status` command.

### Closing active VNC session(s)

To kill a specific VNC job by its job ID, run `hyakvnc kill <job_id>`.

To kill all VNC jobs (with the same job name), run `hyakvnc kill-all`.

### Resetting VNC password

To reset your VNC password, use the `hyakvnc set-passwd` with a VNC container
specified:

```bash
hyakvnc set-passwd --container /path/to/container.sif
```

This should run `vncpasswd` in the container to prompt the user to set a new
password.

### Re-connecting to VNC session after Login Node reboot

In rare circumstances, when the login node reboots, `hyakvnc status` lists VNC
jobs with an inactive VNC signal. In this case, new connections can be
re-established with new port mappings via the `hyakvnc repair` command.

Before repairing:

```
Active hyakvnc jobs:
        Job ID: NNNNNNNN
                SubNode: n3050
                Time left: 2-15:45:51
                VNC active: False
```

After repairing port forwarding:

```
Active hyakvnc jobs:
        Job ID: NNNNNNNN
                SubNode: n3050
                Time left: 2-15:34:30
                VNC active: True
                VNC display number: 1
                VNC port: 5901
                Mapped LoginNode port: 5908
                Run command: ssh -N -f -L 5908:127.0.0.1:5908 hansem7@klone.hyak.uw.edu
```

Note that `hyakvnc repair` does not attempt to restore the same port mappings,
which may require the user to set up new port forward(s).

### Override Apptainer bind paths

If present, `hyakvnc` will use `APPTAINER_BINDPATH` or `SINGULARITY_BINDPATH` to
determine how paths are mounted in the VNC container environment. If neither is
defined, `hyakvnc` will use its default bindpath.

## License

`hyakvnc` is licensed under [MIT License](LICENSE).
