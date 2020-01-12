A simple systemd service and timer to run the script on a schedule.

I have chosen to use the [`podman`](https://podman.io) container runtime, not the docker run time.
However, it should be very easy to change the `ExecStart*` commands to use the `docker` binary if you don't feel that
podman will work for you

The provided service and timer file are nearly identical to what I use in my personal environment, but with the
personal details omitted and replaced with tokens like `YOUR_USER_HERE`. Where appropriate, i've left comments
explaining how to determine the value *you* should use in *your* copy of the file.


Make copies of both the timer and service file, changing as you see fit.
There are a few ways to install the files into a systemd systemd, but this will likely work for you:

```bash

# Move the files into the systemd directory
$ mv duo-to-exist.service /etc/systemd/system
$ mv duo-to-exist.timer /etc/systemd/system

# Make systemd aware of the new service/timer
$ sudo systemctl daemon-reload

# Enable the service and timer
$ sudo systemctl enable duo-to-exist.service
$ sudo systemctl enable duo-to-exist.timer

# Start the timer ticking...
$ sudo systemctl start duo-to-exist.timer

```