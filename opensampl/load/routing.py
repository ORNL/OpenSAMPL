"""Decorator which ensures we are routing our db operations through a backend if configured, or directly if not."""

import json
from functools import wraps
from typing import Callable, Literal, Optional

import requests
import requests.exceptions
import urllib3
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from opensampl.config.base import BaseConfig

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

request_methods = Literal["POST", "GET", "PUT", "DELETE"]


def route(route_endpoint: str, method: request_methods = "POST", send_file: bool = False):
    """
    Handle routing to backend or direct database operations based on environment configuration via decorator.

    Args:
        route_endpoint: The backend endpoint to route to if ROUTE_TO_BACKEND is True.
        method: If routing through backend, the request method. Default: POST.
        send_file: If True sends a file to backend. Otherwise, json. Default: False.

    Returns:
        Decorator function that handles routing logic.

    """

    def decorator(func: Callable) -> Callable:
        """
        Wrap the function with routing logic.

        Args:
            func: The function to be decorated.

        Returns:
            Wrapped function with routing capabilities.

        """

        @wraps(func)
        def wrapper(*args: list, **kwargs: dict) -> Optional[Callable]:
            """
            Handle the actual routing logic.

            Args:
                *args: Positional arguments passed to the wrapped function.
                **kwargs: Keyword arguments passed to the wrapped function.

            Returns:
                Result from either backend request or direct function call.

            Raises:
                requests.exceptions.RequestException: If backend request fails.

            """
            session = kwargs.pop("session", None)
            config = BaseConfig()
            config.check_routing_dependencies()

            logger.debug(f"{config.ROUTE_TO_BACKEND=}")

            # Config Validation deals with making sure we have a backend url if going through backend and
            # a database url if we are doing db operations directly
            if config.ROUTE_TO_BACKEND:
                headers = {
                    "access-key": config.API_KEY,
                }

                pyld = func(*args, **kwargs, _config=config)
                if send_file:
                    request_params = pyld
                    logger.debug(f"data={pyld.get('data')}")
                    logger.debug(f"filesize in bytes={len(pyld.get('files').get('file')[1])}")
                else:
                    request_params = {
                        "json": pyld,
                    }
                    headers.update({"Content-Type": "application/json"})
                    logger.debug(f"headers={json.dumps(headers, indent=4)}")
                    logger.debug(f"json={json.dumps(pyld, indent=4)}")
                # Extract data from the function
                try:
                    logger.debug(f"method={method} type={type(method)}")
                    logger.debug(f"request url={config.BACKEND_URL}/{route_endpoint}")
                    response = requests.request(
                        method=str(method),
                        url=f"{config.BACKEND_URL}/{route_endpoint}",
                        headers=headers,
                        **request_params,
                        timeout=300,
                        verify=not config.INSECURE_REQUESTS,
                    )
                    logger.debug(f"{response.request.method=}, {response.status_code=}, {response.url=}")
                    response.raise_for_status()
                    logger.debug(f"Response: {response.json()}")
                except requests.exceptions.RequestException as e:
                    logger.debug(f"Error making request to backend: {e}")
                    raise
            else:
                if not session:
                    session = sessionmaker(create_engine(config.DATABASE_URL))()  # ty: ignore[no-matching-overload]

                return func(*args, **kwargs, session=session, _config=config)

        return wrapper

    return decorator
