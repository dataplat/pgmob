"""PGMob uses internal classes that wrap plaintext SQL queries and ensure safe parameter validation. These
classes are eventually decoded by adapters into SQL statements with appropriate syntax, parameters and quotation.
"""

import string

from typing import Generator, List, Sequence, Union


class Composable:
    """Common interface for SQL-like objects"""

    def __add__(self, other: "Composable") -> "Composed":
        return Composed(self, other)

    def __mul__(self, other: int) -> "Composed":
        if not isinstance(other, int):
            raise TypeError("int type is required")
        return Composed(*[self for _ in range(other)])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Composable):
            return self.compose() == other.compose()
        else:
            return False

    def compose(self) -> "Composed":
        """Method utilized by an adapter to retrieve a Composed object that contains
        a list of objects and is ready to be iterated upon. All iterated objects are
        guaranteed to be one of: SQL, Literal, Identifier.

        Returns:
            Composed: a composed iterable object
        """
        return Composed(self)


class _Singleton(Composable):
    """A single SQL query part"""

    def __init__(self, value: object) -> None:
        self._value = value

    def __str__(self) -> str:
        return self.__class__.__name__ + f'("{str(self._value)}")'

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Composed):
            return super().__eq__(other)
        return isinstance(other, self.__class__) and self._value == other._value

    def value(self) -> object:
        """Retrieve the underlying value of a Composable: a query string, identifier name
        or a value of a literal. Not supported on Composed objects, which need to be
        iterated upon first before calling .value() on the yielded Composable objects.

        Returns:
            object: the underlying object in a Composable
        """
        return self._value


class Composed(Composable):
    """Composed object. Finalized state of co-joined query parts. Can be
    iterated upon to retrieve the individual parts in proper order."""

    def __init__(self, *args: Composable) -> None:
        self._parts = list(self._process_parts(list(args)))

    def _process_parts(self, parts: Union[List[Composable], "Composed"]) -> Generator[_Singleton, None, None]:
        for part in iter(parts):
            if isinstance(part, Composed):
                for part in self._process_parts(part):
                    yield part
            elif isinstance(part, _Singleton):
                yield part
            else:
                raise TypeError("Unexpected type " "%s" "", part.__class__.__name__)

    def __iter__(self) -> Generator[_Singleton, None, None]:
        for part in iter(self._parts):
            yield part

    def __len__(self) -> int:
        return len(self._parts)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Composable):
            return False
        return list(iter(self.compose())) == list(iter(other.compose()))

    def __str__(self) -> str:
        return "Composed(" + (" + ".join([str(p) for p in self._parts])) + ")"

    def __repr__(self) -> str:
        return self.__str__()


class SQL(_Singleton):
    """A sql statememt

    Args:
        statement (str): query text
    """

    def __init__(self, statement: str) -> None:
        super().__init__(statement)

    def join(self, iter: Sequence[Composable]) -> Composed:
        """Joins basic query building blocks, such as SQL, Literal, Identifier.

        Args:
            iter: an iterable containing Composable elements

        Returns:
            Composed: a composed query object

        Example:
            sql = SQL("SELECT col FROM ") + SQL(".").join(Identifier("myschema"),Identifier("mytable"))
        """
        parts = []
        for i in range(len(iter)):
            parts.append(iter[i])
            if i < len(iter) - 1:
                parts.append(self)
        return Composed(*parts)

    def format(self, *args: Composable, **kwargs: Composable) -> Composed:
        """Format a query that contains a string formatter argument notation. Format
        values can be one of: Identifier, Literal.

        Args:
            *args: for {} or {0} notation
            *kwargs: for {keyword} notation

        Returns:
            Composed: a composed query object

        Example:
            sql = SQL("SELECT {column} FROM {table} WHERE id = {value}").format(
                column=Identifier("col1"),
                table=Identifier("mytable"),
                value=Literal(1)
            )
        """
        formatter = string.Formatter()
        parts = []
        field_counter = -1
        for text, field_name, format_spec, conversion in formatter.parse(str(self._value)):
            parts.append(SQL(text))
            if field_name is not None:
                if field_name:
                    if field_counter >= 0:
                        raise ValueError(
                            "cannot switch from automatic field numbering to manual field specification"
                        )
                    parts.append(formatter.get_value(field_name, args, kwargs))
                else:
                    field_counter += 1
                    parts.append(formatter.get_value(field_counter, args, kwargs))
        return Composed(*parts)


class Identifier(_Singleton):
    """A database Identifier. Ensures proper quoting for identifiers.

    Args:
        identifier (str): identifier name
    """

    def __init__(self, identifier: str) -> None:
        super().__init__(identifier)


class Literal(_Singleton):
    """A Literal query parameter. Ensures proper quoting for literal values.

    Args:
        literal (object): literal value
    """

    def __init__(self, literal: object) -> None:
        super().__init__(literal)

    def __str__(self) -> str:
        if isinstance(self._value, str):
            return super().__str__()
        return self.__class__.__name__ + f"({self._value})"
