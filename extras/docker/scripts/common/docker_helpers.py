import json
import os
import stat
import subprocess
import sys
import time

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))
DOCKER_RUN = (
    "docker",
    "run",
    "-d",
    "-v",
    f"{os.path.expanduser('~/.w3af')}:/root/.w3af",
    "-v",
    f"{os.path.expanduser('~/w3af-shared')}:/root/w3af-shared",
    "-p",
    "44444:44444",
    "andresriancho/w3af",
)


def start_container(tag, command=DOCKER_RUN):
    """
    Start a new w3af container so we can connect using SSH and run w3af

    :return: The container id we just started
    """

    image = command[-1]
    image_tag = tag if tag is not None else "latest"
    docker_run = (*command[:-1], f"{image}:{image_tag}")

    try:
        container_id = subprocess.check_output(docker_run)
    except subprocess.CalledProcessError as cpe:
        print(f'w3af container failed to start: "{cpe}"')
        sys.exit(1)
    else:
        # Let the container start the ssh daemon
        time.sleep(1)
        return container_id.strip()


def stop_container(container_id):
    """
    Stop a running w3af container
    """
    try:
        subprocess.check_output(("docker", "stop", container_id))
    except subprocess.CalledProcessError as cpe:
        print(f'w3af container failed to stop: "{cpe}"')
        sys.exit(1)


def create_volumes():
    """
    Create the directories if they don't exist
    """
    w3af_home = os.path.expanduser("~/.w3af")
    w3af_shared = os.path.expanduser("~/w3af-shared")

    if not os.path.exists(w3af_home):
        os.mkdir(w3af_home)

    if not os.path.exists(w3af_shared):
        os.mkdir(w3af_shared)


def connect_to_container(container_id, cmd, extra_ssh_flags=()):
    """
    Connect to a running container, start one if not running.
    """
    try:
        cont_data = subprocess.check_output(("docker", "inspect", container_id))
    except subprocess.CalledProcessError:
        print(f"Failed to inspect container with id {container_id}")
        sys.exit(1)

    try:
        ip_address = json.loads(cont_data)[0]["NetworkSettings"]["IPAddress"]
    except ValueError:
        print("Invalid JSON output from inspect command")
        sys.exit(1)

    ssh_key = os.path.join(ROOT_PATH, "w3af-docker.prv")

    # git can't store this
    # https://stackoverflow.com/questions/11230171
    original_mode = stat.S_IMODE(os.stat(ssh_key).st_mode)
    os.chmod(ssh_key, 0o600)

    # Create the SSH connection command
    ssh_cmd = [
        "ssh",
        "-i",
        ssh_key,
        "-t",
        "-t",
        "-oStrictHostKeyChecking=no",
        "-o UserKnownHostsFile=/dev/null",
        "-o LogLevel=quiet",
    ]

    # Add the extra ssh flags
    ssh_cmd.extend(extra_ssh_flags)

    ssh_cmd.append("root@" + ip_address)
    ssh_cmd.append(cmd)

    try:
        subprocess.run(ssh_cmd, check=False)
    finally:
        # revert previous chmod to avoid annoying git change
        os.chmod(ssh_key, original_mode)


def check_root():
    # if not root...kick out
    if os.geteuid() != 0:
        sys.exit("Only root can run this script")


def restore_file_ownership():
    """
    There are some issues with "sudo w3af_api_docker" (and any other *_docker)
    where we write to the ~/.w3af/ file but we're doing it as root, and then
    the user wants to execute ./w3af_api and this message appears:

    Either the w3af home directory "/home/user/.w3af" or its contents are not
    writable or readable. Please set the correct permissions and ownership.
    This usually happens when running w3af as root using "sudo"

    So we restore the file ownership of all files inside ~/.w3af/ before exit

    :return: True if we were able to apply the changes
    """
    path = os.path.join(os.path.expanduser("~/"), ".w3af")
    if not os.path.exists(path):
        return False

    try:
        # These two are set by sudo, which is the most common way our users
        # will run w3af inside docker: sudo w3af_console_docker
        sudo_uid = os.getenv("SUDO_UID")
        sudo_gid = os.getenv("SUDO_GID")
        if sudo_uid is None or sudo_gid is None:
            return False

        uid = int(sudo_uid)
        gid = int(sudo_gid)
    except (TypeError, ValueError):
        # TODO: More things to be implemented here
        return False

    try:
        _chown(path, uid, gid)
    except OSError:
        return False

    return True


def _chown(path, uid, gid):
    """
    Change permissions recursively

    :param path: The path to apply changes to
    :param uid: User id
    :param gid: Group id
    :return: None
    """
    os.chown(path, uid, gid)

    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path):
            os.chown(item_path, uid, gid)
        elif os.path.isdir(item_path):
            os.chown(item_path, uid, gid)
            _chown(item_path, uid, gid)
