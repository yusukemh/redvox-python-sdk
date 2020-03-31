"""
This module provides functions and utilities for slowing migrating API 900 towards API 1000.
"""

from typing import List, Optional, Union
import os

import numpy as np


MIGRATIONS_KEY: str = "ENABLE_MIGRATIONS"


def are_migrations_enabled() -> bool:
    from_env: str = os.getenv(MIGRATIONS_KEY, "")
    return from_env.lower() in ["true", "1"]


def enable_migrations(enable: bool) -> bool:
    prev_val: bool = are_migrations_enabled()

    if enable:
        os.environ[MIGRATIONS_KEY] = "1"
    else:
        if MIGRATIONS_KEY in os.environ:
            del os.environ[MIGRATIONS_KEY]

    return prev_val


NumericLike = Union[
    np.ndarray,
    List[int],
    List[float],
    int,
    float
]


def maybe_get_float(data: NumericLike) -> NumericLike:
    if not are_migrations_enabled():
        return data

    if isinstance(data, np.ndarray):
        return data.astype(np.float64)

    if isinstance(data, list):
        return list(map(float, data))

    if isinstance(data, int):
        return float(data)

    # We have no idea what it is, so just return we we got.
    return data


def maybe_set_int(data: NumericLike) -> NumericLike:
    if not are_migrations_enabled():
        return data

    if isinstance(data, np.ndarray):
        return data.astype(np.int32)

    if isinstance(data, list):
        return list(map(int, data))

    if isinstance(data, float):
        return int(data)

    # We have no idea what it is, so just return we we got.
    return data
