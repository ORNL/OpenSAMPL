"""Environment functions for openSAMPL"""

import os
from pathlib import Path

from dotenv import find_dotenv, set_key
from loguru import logger

from opensampl.constants import ENV_VARS


def set_env(name: str, value: str):
    """
    Set the value of an environment variable.

    Note that this will only work if the variable is set in the .env file, if it is a true environment variable the
    change will not persist.

    Examples
    --------
        opensampl config set BACKEND_URL http://localhost:8000

    """
    # TODO: if you have the env var actually set in your environment, and not in a dotenv, the "set" won't work.
    # options:
    #   1) have override in dotenv option
    #   2) have a "run with" at the end of any opensampl command to have it just be that for that run

    # Verify variable exists
    if not any(var.name == name for var in ENV_VARS.all()):
        logger.warning(
            f"Environment variable '{name}' not used by openSAMPL. Will be added to .env, but will not change "
            f"functionality."
        )

    # Set for current session
    os.environ[name] = value

    env_path = find_dotenv()
    logger.debug(f"Found env_path: {env_path}")
    if not env_path:
        env_path = ".env"
        Path(env_path).touch()

    # Update .env file
    set_key(env_path, name, value)
    logger.debug(f"Set {name}={value} in {env_path}")

    logger.debug(os.getenv(name))
