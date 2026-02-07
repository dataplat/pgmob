"""Internal module utilities."""

import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

from packaging.version import Version as _Version

from pgmob.sql import SQL


def group_by[T](key: Callable[..., str], seq: Sequence[T]) -> dict[str, list[T]]:
    """Groups a list by key

    Args:
        key: lambda function to extract the key from a value
        seq: input items

    Returns:
        dict: a dictionary grouped by keys
    """
    # Type checker needs explicit annotation for defaultdict with lambda in reduce
    result: dict[str, list[T]] = defaultdict(list)
    for val in seq:
        result[key(val)].append(val)
    return result


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
        except (ValueError, AttributeError):
            raise ValueError("Unsupported version string. Only dot-separated numbers are supported.")
        if len(parts) == 0:
            raise ValueError("Empty version string")
        return _Version.__new__(cls)


def get_sql(name: str, version: Version | None = None) -> SQL:
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
