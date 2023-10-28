# hyakvnc

hyakvnc -- A tool for launching VNC sessions on Hyak.

`hyakvnc` is a command-line tool that makes it easy to start a graphical [VNC](https://en.wikipedia.org/wiki/Virtual_Network_Computing) session on the University of Washington [Hyak](https://hyak.uw.edu/) cluster, allowing you to interact with the system in a point-and-click environment, with support for graphical applications such as [Freesurfer](https://surfer.nmr.mgh.harvard.edu/). `hyakvnc` sessions run in [Apptainer](https://apptainer.org) containers, which provide reproducible environments that can run anywhere and be shared with other researchers.

*If you're already familiar with Hyak and VNC and you just want to install `hyakvnc` immediately, you can skip to the [quick install](#quick-install) section.*

## Prerequisites

Before running `hyakvnc`, you'll need the following:

- A Linux, macOS, or Windows machine
- The OpenSSH client (usually included with Linux and macOS, and available for Windows via [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) or [Cygwin](https://www.cs.odu.edu/~zeil/cs252/latest/Public/loggingin/cygwin.mmd.html) [note that the Windows 10+ built-in OpenSSH client will not work])
- A VNC client/viewer ([TurboVNC viewer](https://www.turbovnc.org) is recommended for all platforms)
- HYAK Klone access with compute resources
- A private SSH key on your local machine which has been added to the authorized keys on the login node of the HYAK Klone cluster (see below)
- A HyakVNC-compatible Apptainer container image in a directory on Hyak (usually with the file extension `.sif`) or the URL to one (e.g,., `oras://ghcr.io/maouw/hyakvnc_apptainer/ubuntu22.04_turbovnc:latest`)

Follow the instructions below to set up your machine correctly:

### Installing OpenSSH and TurboVNC

#### Linux

If you are using Linux, OpenSSH is probably installed already -- if not, you can install it via `apt-get install openssh-client` on Debian/Ubuntu or `yum install openssh-clients` on RHEL/CentOS/Rocky/Fedora. To open a terminal window, search for "Terminal" in your desktop environment's application launcher.

To install TurboVNC, download the latest version from [here](https://sourceforge.net/projects/turbovnc/files). On Debian/Ubuntu, you will need to download the file ending with `arm64.deb`. On RHEL/CentOS/Rocky/Fedora, you will need to download the file ending with `x86_64.rpm`. Then, install it by running `sudo dpkg -i <filename>` on Debian/Ubuntu or `sudo rpm -i <filename>` on RHEL/CentOS/Rocky/Fedora.

#### macOS

If you're on macOS, OpenSSH will already be installed. To open a terminal window, open `/Applications/Utilities/Terminal.app` or search for "Terminal" in Launchpad or Spotlight.

To install TurboVNC, download the latest version from [here](https://sourceforge.net/projects/turbovnc/files). On an M1 Mac (newer), you will need to download the file ending with `arm64.dmg`. On an Intel Mac (older), you will need the file ending with `x86_64.dmg`. Then, open the `.dmg` file and launch the installer inside.

#### Windows

Windows needs a little more setup. You'll need to install a terminal emulator as well as the OpenSSH client. The easiest way to do this is to install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) (recommended for Windows versions 10+, comes with the OpenSSH client already installed) or [Cygwin](https://www.cs.odu.edu/~zeil/cs252/latest/Public/loggingin/cygwin.mmd.html) (not recommended, needs additional setup). See the links for instructions on how to install these. You can start a terminal window by searching for "Terminal" in the Start menu.

To install TurboVNC, download the latest version from [here](https://sourceforge.net/projects/turbovnc/files). You will need the file ending with `x64.exe`. Run the program to install TurboVNC.

### Setting up SSH keys to connect to Hyak compute nodes

Before you are allowed to connect to a compute node where your VNC session will be running, you must add your SSH public key to the authorized keys on the login node of the HYAK Klone cluster.

If you don't, you will receive an error like this when you try to connect:

```text
Permission denied (publickey,gssapi-keyex,gssapi-with-mic)
```

To set this up quickly on Linux, macOS, or Windows (WSL2/Cygwin), open a new terminal window on your machine and enter the following 2 commands before you try again. Replace `your-uw-netid` with your UW NetID:

```bash
[ ! -r ~/.ssh/id_rsa ] && ssh-keygen -t rsa -b 4096 -N '' -C "your-uw-netid@uw.edu" -f ~/.ssh/id_rsa
ssh-copy-id -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa "your-uw-netid"@klone.hyak.uw.edu
```

See https://hyak.uw.edu/docs/setup/intracluster-keys for more information.

### Finding a HyakVNC-compatible container image

You'll need to find a HyakVNC-compatible container image to run your VNC session in. The following images are provided by us and can be used with `hyakvnc` by copying and pasting the URL into the `hyakvnc create` command:

- `oras://ghcr.io/maouw/hyakvnc_apptainer/ubuntu22.04_turbovnc:latest` -- Ubuntu 22.04 with TurboVNC
- `oras://ghcr.io/maouw/ubuntu22.04_freesurfer:latest` -- Ubuntu 22.04 with TurboVNC and Freesurfer

## Installing `hyakvnc`

`hyakvnc` should be installed on the login node of the HYAK Klone cluster.

To connect to the login node, you'll need to enter the following command into a terminal window (replacing `your-uw-netid` with your UW NetID) and provide your password when prompted:

```bash
ssh your-uw-netid@klone.hyak.uw.edu
```

### Quick install

After you've connected to the login node, you can download and install `hyakvnc` by running the following command. Copy and paste it into the terminal window where you are connected to the login node and press enter:

```bash
eval "$(curl -fsSL https://raw.githubusercontent.com//maouw/hyakvnc/main/install.sh)"
```

This will download and install `hyakvnc` to your `~/.local/bin` directory and add it to your `$PATH` so you can run it by typing `hyakvnc` into the terminal window.

### Installing manually

In a terminal window connected to a login node, enter this command to clone the repository and navigate into the repository directory:

```bash
git clone --depth 1 --single-branch https://github.com/maouw/hyakvnc && cd hyakvnc
```

Then, run the following command to install `hyakvnc`:

```bash
./hyakvnc install
```

If you prefer, you may continue to use `hyakvnc` from the directory where you cloned it by running `./hyakvnc` from that directory instead of using the command `hyakvnc`.

## Getting started

### Creating a VNC session

Start a VNC session with the `hyakvnc create` command followed by arguments to specify the container. In this example, we'll use a basic container for a graphical environment from the HyakVNC GitHub Container Registry:

```bash
hyakvnc create --container oras://maouw/hyakvnc_apptainer/ubuntu22.04_turbovnc:latest
```

It may take a few minutes to download the container if you're running it the first time. If successful, `hyakvnc` should print commands and instructions to connect:

```text
==========
Copy and paste these instructions into a command line terminal on your local machine to connect to the VNC session.
You may need to install a VNC client if you don't already have one.

NOTE: If you receive an error that looks like "Permission denied (publickey,gssapi-keyex,gssapi-with-mic)", you don't have an SSH key set up.
See https://hyak.uw.edu/docs/setup/intracluster-keys for more information.
To set this up quickly on Linux, macOS, or Windows (WSL2/Cygwin), open a new terminal window on your machine and enter the following 2 commands before you try again:

[ ! -r ~/.ssh/id_rsa ] && ssh-keygen -t rsa -b 4096 -N '' -C "your-uw-netid@uw.edu" -f ~/.ssh/id_rsa
ssh-copy-id -o StrictHostKeyChecking=no your-uw-netid@klone.hyak.uw.edu
---------
LINUX TERMINAL (bash/zsh):
ssh -f -o StrictHostKeyChecking=no -L 5901:/mmfs1/home/your-uw-netid/.hyakvnc/jobs/15042104/vnc/socket.uds -J your-uw-netid@klone.hyak.uw.edu your-uw-netid@g3053 sleep 20 && vncviewer localhost:5901 || xdg-open vnc://localhost:5901 || echo 'No VNC viewer found. Please install one or try entering the connection information manually.'

MACOS TERMINAL
ssh -f -o StrictHostKeyChecking=no -L 5901:/mmfs1/home/your-uw-netid/.hyakvnc/jobs/15042104/vnc/socket.uds -J your-uw-netid@klone.hyak.uw.edu your-uw-netid@g3053 sleep 20 && open -b com.turbovnc.vncviewer.VncViewer --args localhost:5901 2>/dev/null || open -b com.realvnc.vncviewer --args localhost:5901 2>/dev/null || open -b com.tigervnc.vncviewer --args localhost:5901 2>/dev/null || open vnc://localhost:5901 2>/dev/null || echo 'No VNC viewer found. Please install one or try entering the connection information manually.'

WINDOWS
ssh -f -o StrictHostKeyChecking=no -L 5901:/mmfs1/home/your-uw-netid/.hyakvnc/jobs/15042104/vnc/socket.uds -J your-uw-netid@klone.hyak.uw.edu your-uw-netid@g3053 sleep 20 && cmd.exe /c cmd /c "$(cmd.exe /c where "C:\Program Files\TurboVNC;C:\Program Files(x86)\TurboVNC:vncviewerw.bat")" localhost:5901 || echo 'No VNC viewer found. Please install one or try entering the connection information manually.'

==========
```

## Usage

`hyakvnc` is command-line tool that only works on the login node of the Hyak cluster.

### Create a VNC session on Hyak

```text
Usage: hyakvnc create [create options...] -c <container> [extra args to pass to apptainer...]

Description:
    Create a VNC session on Hyak.

Options:
    -h, --help  Show this help message and exit
    -c, --container Path to container image (required)
    -A, --account   Slurm account to use (default: )
    -p, --partition Slurm partition to use (default: )
    -C, --cpus  Number of CPUs to request (default: 4)
    -m, --mem   Amount of memory to request (default: 4G)
    -t, --timelimit Slurm timelimit to use (default: 12:00:00)
    -g, --gpus  Number of GPUs to request (default: )

Advanced options:
    --no-ghcr-oras-preload  Don't preload ORAS GitHub Container Registry images

Extra arguments:
    Any extra arguments will be passed to apptainer run.
    See 'apptainer run --help' for more information.

Examples:
    # Create a VNC session using the container ~/containers/mycontainer.sif
    hyakvnc create -c ~/containers/mycontainer.sif
    # Create a VNC session using the URL for a container:
    hyakvnc create -c oras://ghcr.io/maouw/hyakvnc_apptainer/ubuntu22.04_turbovnc:latest
    # Use the SLURM account escience, the partition gpu-a40, 4 CPUs, 1GB of memory, 1 GPU, and 1 hour of time:
    hyakvnc create -c ~/containers/mycontainer.sif -A escience -p gpu-a40 -C 4 -m 1G -t 1:00:00 -g 1

```

### Show the status of running HyakVNC sessions

```text
Usage: hyakvnc status [status options...]

Description:
    Check status of VNC session(s) on Hyak.

Options:
    -h, --help  Show this help message and exit
    -d, --debug Print debug info
    -j, --jobid Only check status of provided SLURM job ID (optional)

Examples:
    # Check the status of job no. 12345:
    hyakvnc status -j 12345
    # Check the status of all VNC jobs:
    hyakvnc status
```

### Show connection information for a HyakVNC sesssion

```text
Usage: hyakvnc show <jobid>
    
Description:
    Show connection information for a HyakVNC sesssion. 
    If no job ID is provided, a menu will be shown to select from running jobs.
    
Options:
    -h, --help  Show this help message and exit

Examples:
    # Show connection information for session running on job 123456:
    hyakvnc show 123456
    # Interactively select a job to show connection information for:
    hyakvnc show

    # Show connection information for session running on job 123456 for macOS:
    hyakvnc show -s mac 123456
```

### Stop a HyakVNC session

```text
Usage: hyakvnc stop [-a] [<jobids>...]
    
Description:
    Stop a provided HyakVNC sesssion and clean up its job directory.
    If no job ID is provided, a menu will be shown to select from running jobs.

Options:
    -h, --help  Show this help message and exit
    -n, --no-cancel Don't cancel the SLURM job
    -a, --all   Stop all jobs

Examples:
    # Stop a VNC session running on job 123456:
    hyakvnc stop 123456
    # Stop a VNC session running on job 123456 and do not cancel the job:
    hyakvnc stop --no-cancel 123456
    # Stop all VNC sessions:
    hyakvnc stop -a
    # Stop all VNC sessions but do not cancel the jobs:
    hyakvnc stop -a -n
```

### Show the current configuration for hyakvnc

```text
Usage: hyakvnc config [config options...]
    
Description:
    Show the current configuration for hyakvnc, as set in the user configuration file at /home/runner/.hyakvnc/hyakvnc-config.env, in the current environment, or the default values set by hyakvnc.

Options:
    -h, --help      Show this help message and exit

Examples:
    # Show configuration
    hyakvnc config
```

### Update hyakvnc

```text
Usage: hyakvnc update [update options...]
    
Description:
    Update hyakvnc.

Options:
    -h, --help          Show this help message and exit

Examples:
    # Update hyakvnc
    hyakvnc update
```

### Install the hyakvnc command

```text
Usage: hyakvnc install [install options...]
    
Description:
    Install hyakvnc so the "hyakvnc" command can be run from anywhere.

Options:
    -h, --help          Show this help message and exit
    -i, --install-dir       Directory to install hyakvnc to (default: ~/.local/bin)
    -s, --shell [bash|zsh]  Shell to install hyakvnc for (default: $SHELL or bash)

Examples:
    # Install
    hyakvnc install
    # Install to ~/bin:
    hyakvnc install -i ~/bin
```

## Configuration

The following [environment variables](https://wiki.archlinux.org/title/environment_variables) can be used to override the default settings. Any arguments passed to `hyakvnc create` will override the environment variables.

You can modify the values of these variables by:

- Setting and exporting them in your shell session, e.g. `export HYAKVNC_SLURM_MEM='8G'` (which will only affect the current shell session)
- Setting them in your shell's configuration file, e.g. `~/.bashrc` or `~/.zshrc` (which will affect all shell sessions)
- Setting them by prefixing the `hyakvnc` command with the variable assignment, e.g. `HYAKVNC_SLURM_MEM='8G' hyakvnc create ...` (which will only affect the current command)
- Setting them in the file `~/.hyakvnc/hyakvnc-config.env` (which will affect all `hyakvnc` commands)

When you set an environment variable, it is advisable to surround the value with single quotes (`'`) to prevent your shell from interpreting special characters. There should be no spaces between the variable name, the equals sign, and the value.

The following variables are available:

- HYAKVNC_DIR: Local directory to store application data (default: `$HOME/.hyakvnc`)
- HYAKVNC_CONFIG_FILE: Configuration file to use (default: `$HYAKVNC_DIR/hyakvnc-config.env`)
- HYAKVNC_CHECK_UPDATE_FREQUENCY: How often to check for updates in `[d]`ays or `[m]`inutes (default: `0` for every time. Use `1d` for daily, `10m` for every 10 minutes, etc. `-1` to disable.)
- HYAKVNC_LOG_FILE: Log file to use (default: `$HYAKVNC_DIR/hyakvnc.log`)
- HYAKVNC_LOG_LEVEL: Log level to use for interactive output (default: `INFO`)
- HYAKVNC_LOG_FILE_LEVEL: Log level to use for log file output (default: `DEBUG`)
- HYAKVNC_SSH_HOST: Default SSH host to use for connection strings (default: `klone.hyak.uw.edu`)
- HYAKVNC_DEFAULT_TIMEOUT: Seconds to wait for most commands to complete before timing out (default: `30`)
- HYAKVNC_VNC_PASSWORD: Password to use for new VNC sessions (default: `password`)
- HYAKVNC_VNC_DISPLAY: VNC display to use (default: `:1`)
- HYAKVNC_APPTAINER_CONTAINERS_DIR: Directory to look for apptainer containers (default: (none))
- HYAKVNC_APPTAINER_GHCR_ORAS_PRELOAD: Whether to preload SIF files from the ORAS GitHub Container Registry (default: `0`)
- HYAKVNC_APPTAINER_BIN: Name of apptainer binary (default: `apptainer`)
- HYAKVNC_APPTAINER_CONTAINER: Path to container image to use (default: (none; set by `--container` option))
- HYAKVNC_APPTAINER_APP_VNCSERVER: Name of app in the container that starts the VNC session (default: `vncserver`)
- HYAKVNC_APPTAINER_APP_VNCKILL: Name of app that cleanly stops the VNC session in the container (default: `vnckill`)
- HYAKVNC_APPTAINER_WRITABLE_TMPFS: Whether to use a writable tmpfs for the container (default: `1`)
- HYAKVNC_APPTAINER_CLEANENV: Whether to use a clean environment for the container (default: `1`)
- HYAKVNC_APPTAINER_ADD_BINDPATHS: Bind paths to add to the container (default: (none))
- HYAKVNC_APPTAINER_ADD_ENVVARS: Environment variables to add to before invoking apptainer (default: (none))
- HYAKVNC_APPTAINER_ADD_ARGS: Additional arguments to give apptainer (default: (none))
- HYAKVNC_SLURM_JOB_PREFIX: Prefix to use for hyakvnc SLURM job names (default: `hyakvnc-`)
- HYAKVNC_SLURM_SUBMIT_TIMEOUT: Seconds after submitting job to wait for the job to start before timing out (default: `120`)
- HYAKVNC_SLURM_OUTPUT_DIR: Directory to store SLURM output files (default: `$HYAKVNC_DIR/slurm-output`)
- HYAKVNC_SLURM_OUTPUT: Where to send SLURM job output (default: `$HYAKVNC_SLURM_OUTPUT_DIR/job-%j.out`)
- HYAKVNC_SLURM_JOB_NAME: What to name the launched SLURM job (default: (set according to container name))
- HYAKVNC_SLURM_ACCOUNT: Slurm account to use (default: (autodetected))
- HYAKVNC_SLURM_PARTITION: Slurm partition to use (default: (autodetected))
- HYAKVNC_SLURM_CLUSTER: Slurm cluster to use (default: (autodetected))
- HYAKVNC_SLURM_GPUS: Number of GPUs to request (default: (none))
- HYAKVNC_SLURM_MEM: Amount of memory to request, in [M]egabytes or [G]igabytes (default: `4G`)
- HYAKVNC_SLURM_CPUS: Number of CPUs to request (default: `4`)
- HYAKVNC_SLURM_TIMELIMIT: Time limit for SLURM job (default: `12:00:00`)

## License

`hyakvnc` is licensed under [MIT License](LICENSE).
