import functools
import inspect
from typing import Any, Callable, TypeVar
import warnings

T = TypeVar("T")
LAZY_PREFIX = "_pgmlazy_"


class RefreshProperty(object):
    """An instance of this class marks a lazy-evaluated property as requiring a refresh"""

    def __eq__(self, __o: object) -> bool:
        return self.__class__ == __o.__class__


def get_lazy_property(obj: object, name: str, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Retrieves a lazy property value"""
    attribute = LAZY_PREFIX + name
    has_attribute = hasattr(obj, attribute)
    if not has_attribute or (has_attribute and getattr(obj, attribute) == RefreshProperty()):
        setattr(obj, attribute, func(*args, **kwargs))
    return getattr(obj, attribute)


def lazy_property(func):
    # not used for now because of https://github.com/microsoft/pylance-release/discussions/2716
    # get_lazy_property implements that logic without having to use a decorator

    @property
    @functools.wraps(func)
    def _wrapper(self):
        return get_lazy_property(self, func.__name__, func, self)

    return _wrapper


class DeprecatedWarning(UserWarning):
    pass


def deprecated(instructions):
    """Flags a method as deprecated.

    Args:
        instructions: A warning displayed to a user. E.g. 'Use my_func() instead.'
    """

    def decorator(func):
        """This is a decorator which can be used to mark functions
        as deprecated. It will result in a warning being emitted
        when the function is used."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            message = "Call to deprecated function {}. {}".format(func.__name__, instructions)

            frame = inspect.currentframe().f_back

            warnings.warn_explicit(
                message,
                category=DeprecatedWarning,
                filename=inspect.getfile(frame.f_code),
                lineno=frame.f_lineno,
            )

            return func(*args, **kwargs)

        return wrapper

    return decorator
