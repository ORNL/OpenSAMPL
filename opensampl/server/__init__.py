"""Module for openSAMPL-server functionality"""

import subprocess


def check_command(command):
    """Check if a command exists by running it and capturing output."""
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


if not check_command(["docker", "--version"]):
    raise ImportError("Docker is not installed or not found in PATH. Please install Docker.")

compose_installed = check_command(["docker", "compose", "version"]) or check_command(["docker-compose", "--version"])

if not compose_installed:
    raise ImportError("Neither 'docker compose' nor 'docker-compose' is installed. Please install Docker Compose.")
