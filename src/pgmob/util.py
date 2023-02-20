"""Internal module utilities."""
from typing import Callable, Dict, List, Sequence, Type, TypeVar
from pgmob.sql import SQL
from pathlib import Path
import re
from functools import reduce
from collections import defaultdict
from packaging.version import Version as _Version


_T = TypeVar("_T")


def group_by(key: Callable[..., str], seq: Sequence[_T]) -> Dict[str, List[_T]]:
    """Groups a list by key

    Args:
        key: lambda function to extract the key from a value
        seq: input items

    Returns:
        dict: a dictionary grouped by keys
    """
    return reduce(lambda grp, val: grp[key(val)].append(val) or grp, seq, defaultdict(list))  # type: ignore


class Version(_Version):
    """Version object. Allows to track major, minor, build and revision versions, left to right."""

    @property
    def build(self):
        return self.micro

    @property
    def revision(self):
        return 0 if len(self.release) < 4 else self.release[3]

    def __new__(cls, version):
        try:
            parts = [int(x) for x in version.split(".")]
        except:
            raise ValueError("Unsupported version string. Only dot-separated numbers are supported.")
        if len(parts) == 0:
            raise ValueError("Empty version string")
        return _Version.__new__(cls)


def get_sql(name: str, version: Version = None) -> SQL:
    """Retrieves SQL code from a file in a 'sql' folder

    Args:
        name (str): file name w/o extension"
        version (Version): specific Postgres version to search for

    Returns:
        SQL: sql code
    """
    root_path = Path(__file__).parent / "scripts" / "sql"
    if version:
        filename = f"{name}.sql"
        matcher = re.compile(re.escape(name) + "_(\\d+)\\.sql")
        files = list(root_path.glob(f"{name}_*.sql"))
        files.sort()
        for file in files:
            match = matcher.match(file.name)
            if match and version.major >= int(match[1]):
                filename = file.name
    else:
        filename = f"{name}.sql"
    path = root_path / filename
    with path.open() as sql_file:
        return SQL(sql_file.read())


def get_shell(name: str) -> str:
    """Retrieves shell code from a file in a 'shell' folder

    Args:
        name (str): file name w/o extension

    Returns:
        str: file contents
    """
    path = Path(__file__).parent / "scripts" / f"shell/{name}.sh"
    with path.open() as sql_file:
        return sql_file.read()
