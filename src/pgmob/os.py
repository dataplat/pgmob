"""PGMob will try to abstract OS commands using classes that provide support for a specific OS."""
from abc import abstractmethod
import shlex
from . import util
from .errors import PostgresShellCommandError


class _BaseShellEnv(object):
    """Base OS class interface that outlines necessary shell-dependent operations"""

    @staticmethod
    @abstractmethod
    def quote(cmd: str) -> str:
        """Quotes command line argument for a shell function
        Args:
            cmd (str): command line argument to escape

        Returns:
            str: quoted command line argument
        """
        raise NotImplementedError()

    @staticmethod
    def join_path(*args) -> str:
        """Joins path according to the local OS rules. Deals with URLs and Posix paths

        Args:
            *args: paths that need to be joined

        Returns:
            str: Joined path string
        """
        path = ""
        for arg in args:
            path = path + ("/" if path and arg else "") + (arg.strip("/") if path else arg.rstrip("/"))
        return path

    @staticmethod
    @abstractmethod
    def get_os_command_wrapper() -> str:
        """Returns a wrapper for an OS command used by run_os_command method

        Returns:
            str: wrapper for an OS command
        """
        raise NotImplementedError()


class ShellEnv(_BaseShellEnv):
    """Shell-like command line operations (/bin/sh)"""

    @staticmethod
    def quote(cmd: str) -> str:
        """Quotes command line argument for a shell function

        Args:
            cmd (str): command line argument to escape

        Returns:
            str: quoted command line argument"""
        return shlex.quote(cmd)

    @staticmethod
    def get_os_command_wrapper() -> str:
        return util.get_shell("run_postgres_command")


class OSCommandResult(object):
    """Results of the OS command execution

    Attributes:
        exit_code (int): command exit code
        text (str): stdout and stderr together
    """

    _exit_code: int
    text: str

    def __init__(self, command: str) -> None:
        self.command = command

    @property
    def exit_code(self) -> int:
        return self._exit_code

    @exit_code.setter
    def exit_code(self, value: int):
        try:
            self._exit_code = int(value)
        except (ValueError, TypeError):
            raise PostgresShellCommandError(self.command, self.text)

    def raise_for_error(self):
        """Raises an exception when exist code is not 0.

        Raises:
            PostgresShellCommandError: when exit code is not 0
        """
        if self.exit_code != 0:
            raise PostgresShellCommandError(self.command, self.text)
