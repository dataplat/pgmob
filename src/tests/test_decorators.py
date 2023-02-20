from pgmob._decorators import lazy_property, get_lazy_property, LAZY_PREFIX
from dataclasses import dataclass, field


def test_lazy_property():
    class B:
        """foo"""

        pass

    class A:
        @lazy_property
        def b(self) -> B:
            return B()

    assert isinstance(A().b, B)
    assert A().b.__doc__ == "foo"


def test_get_lazy_property():
    class B:
        """foo"""

        pass

    class A:
        @property
        def b(self) -> B:
            return get_lazy_property(self, "b", lambda: B())

    assert isinstance(A().b, B)
    assert A().b.__doc__ == "foo"
