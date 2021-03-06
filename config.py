import os
from datetime import datetime


def get_env(key, required=False, or_else=None):
    value = os.environ.get(key)

    if required and or_else:
        print(f"get_env(): for {key}, or_else parameter was ignored because this variable is required")

    if value is not None:
        return value
    else:
        if required:
            raise RuntimeError(f"Required environment variable {key} is missing.")
        else:
            return or_else


DB_CONNECTION_STRING = get_env("CONNECTION_STRING", required=True)
SECRET_KEY = get_env("FLASK_SECRET_KEY", required=True)