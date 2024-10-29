#!/bin/sh

# Taken from https://github.com/sosy-lab/benchexec/blob/3.24/doc/benchexec-in-container.md#benchexec-in-interactive-containers

set -eu

# Create new sub-cgroups
# Note: While "init" can be renamed, the name "benchexec" is important
mkdir -p /sys/fs/cgroup/init /sys/fs/cgroup/benchexec
# Move the init process to that cgroup
echo $$ >/sys/fs/cgroup/init/cgroup.procs

# Enable controllers in subtrees for benchexec to use
for controller in $(cat /sys/fs/cgroup/cgroup.controllers); do
  echo "+$controller" >/sys/fs/cgroup/cgroup.subtree_control
  echo "+$controller" >/sys/fs/cgroup/benchexec/cgroup.subtree_control
done

# ... or whatever your init process should be
exec "$@"
