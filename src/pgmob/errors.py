"""A list of PGMob errors raised by the module"""
import logging


class PostgresError(Exception):
    """An error raised by the PGMob module"""

    def __init__(self, *args):
        super().__init__(*args)
        logger = logging.getLogger(__name__)
        self._arguments = None
        self._message = "PostgresError has been raised"
        if args:
            self._message = args[0]
            if len(args) > 1:
                self._arguments = args[1:]
        if self._arguments:
            logger.debug(self._message, self._arguments)
        else:
            logger.debug(self._message)

    def __str__(self):
        return self._message % self._arguments if self._arguments else self._message


class PostgresShellCommandError(PostgresError):
    """An error raised when OS Command has returned a non-zero exit code"""

    def __init__(self, command, error_message):
        message = f"Error while executing shell command [{command}]: %s"
        super().__init__(message, error_message)


class PostgresTypeError(TypeError):
    """Incorrect type provided"""

    pass


class PostgresNameError(NameError):
    """Incorrect name provided"""

    pass
