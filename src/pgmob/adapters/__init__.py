"""Adapters are wrappers around SQL Providers, which translate internal module syntax into the proper Provider syntax
"""

from typing import TYPE_CHECKING
from .errors import *


ADAPTERS = [(".psycopg2", "Psycopg2Adapter")]
"""Use the following variable to register adapters for autodiscovery.
Should contain a tuple of module import path: "module.sub" or ".module" - and the Adapter class name.

Example:
    Add a custom adapter ``MyAdapter`` from module ``mymodule``

    >>> import pgmob.adapters
    >>> pgmob.adapters.ADAPTERS.extend(("mymodule", "MyAdapter"))
"""

if TYPE_CHECKING:
    from .base import BaseAdapter


def detect_adapter() -> "BaseAdapter":
    """Detect adapter based on installed modules. You can change the order and add your own
    adapters by modifying the ADAPTERS module variable.

    Returns:
        BaseAdapter: initialized adapter object"""
    from importlib import import_module

    for module, name in ADAPTERS:
        try:
            adapter_module = import_module(module, package="pgmob.adapters")
        except:
            pass
        else:
            return getattr(adapter_module, name)()
    else:
        raise AdapterError(
            "No adapters detected. Try installing one of the following extras: %s", [x[0] for x in ADAPTERS]
        )
