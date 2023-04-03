hyakvnc
=======

Create and manage VNC Slurm jobs on UW HYAK Klone cluster.

`hyakvnc` allocates resources then starts a VNC session within an Apptainer
environment.

## Get started

### Prerequisites

Before running `hyakvnc`, you'll need the following:
- SSH client
- VNC client
- HYAK Klone access with compute resources
- VNC Apptainer with a desktop environment and miscellaneous tools/libraries
- xstartup script used to launch a desktop environment

### Building

Update pip:
```
python3 -m pip install --upgrade --user pip
```

Clone repo and build package:
```
cd hyakvnc
python3 -m pip install --user .
```

If successful, then `hyakvnc` should be installed to `~/.local/bin/`.

### Creating a VNC session

1. Start a VNC session with the `create` command followed by arguments to
   specify the Slurm account and partition, compute resource needs, reservation
   time, and paths to a VNC apptainer and xstartup script.

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
        ssh -N -f -L 5901:127.0.0.1:5901 hansem7@klone.hyak.uw.edu
then connect to VNC session at localhost:5901
=====================
```

Copy this port forward command for the following step.

3. Set up port forward between your computer and HYAK login node. On your
   machine, in a new terminal window, run the the copied command.

```
# Following the example, run:
ssh -N -f -L 5901:127.0.0.1:5901 hansem7@klone.hyak.uw.edu
```

4. Connect to VNC session at instructed address (in example: localhost:5901)

5. To close VNC session, run the following

```bash
hyakvnc kill-all
```

## License

`hyakvnc` is licensed under [MIT License](LICENSE).
