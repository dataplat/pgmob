from datetime import datetime
import pytest
from pgmob.sql import *


class TestSQL:
    def test_init(self):
        assert SQL("asd")._value == "asd"
        assert SQL("asd") == SQL("asd")
        assert SQL(None) == SQL("")
        assert SQL("asd") != SQL("asf")
        assert SQL("asd") * 4 == Composed(SQL("asd"), SQL("asd"), SQL("asd"), SQL("asd"))
        assert SQL("asd") + SQL("asf") == Composed(SQL("asd"), SQL("asf"))
        assert str(SQL("asd")) == 'SQL("asd")'

        with pytest.raises(TypeError):
            SQL()

    def test_format(self):
        result = SQL("SELECT {field} FROM {table}").format(field=Identifier("foo"), table=Identifier("bar"))
        assert len(result._parts) == 4
        assert [x.__class__ for x in result._parts] == [SQL, Identifier, SQL, Identifier]
        result = SQL("SELECT {field} FROM table WHERE {field} = {value}").format(
            field=Identifier("foo"), value=Literal(1)
        )
        assert len(result._parts) == 6
        assert [x.__class__ for x in result._parts] == [SQL, Identifier, SQL, Identifier, SQL, Literal]

    def test_join(self):
        result = SQL(".").join([Identifier("foo"), Identifier("bar")])
        assert len(result._parts) == 3
        assert [x.__class__ for x in result._parts] == [Identifier, SQL, Identifier]
        result = SQL(",").join([Literal("foo"), Literal("bar")])
        assert len(result._parts) == 3
        assert [x.__class__ for x in result._parts] == [Literal, SQL, Literal]

    def test_compose(self):
        result = SQL("asd").compose()
        assert len(result) == 1
        assert list(iter(result))[0] == SQL("asd")

    def test_value(self):
        assert SQL("asd").value() == "asd"


class TestIdentifier:
    def test_init(self):
        assert Identifier("asd")._value == "asd"
        assert Identifier("asd") == Identifier("asd")
        assert Identifier("asd") != Identifier("asf")
        assert str(Identifier("asd")) == 'Identifier("asd")'

        with pytest.raises(TypeError):
            Identifier()

    def test_compose(self):
        result = Identifier("asd").compose()
        assert len(result) == 1
        assert list(iter(result))[0] == Identifier("asd")

    def test_value(self):
        assert Identifier("asd").value() == "asd"


class TestLiteral:
    def test_init(self):
        assert Literal("asd")._value == "asd"
        date = datetime.now()
        assert Literal(date)._value == date
        assert Literal(1)._value == 1
        assert Literal("asd") == Literal("asd")
        assert Literal("asd") != Literal("asf")
        assert Literal(1) == Literal(1)
        assert Literal(1) != Literal(2)
        assert Literal(date) == Literal(date)
        assert Literal(date) != Literal(datetime.now())
        assert str(Literal("asd")) == 'Literal("asd")'

        with pytest.raises(TypeError):
            Literal()

    def test_value(self):
        assert Literal("asd").value() == "asd"

    def test_compose(self):
        result = Literal("asd").compose()
        assert len(result) == 1
        assert list(iter(result))[0] == Literal("asd")


class TestComposed:
    def test_init(self):
        result = Composed(SQL("SELECT * FROM "), Identifier("table"), SQL(" WHERE x = "), Literal(1))
        assert len(result) == 4
        assert [x.__class__ for x in result] == [SQL, Identifier, SQL, Literal]

        result = Composed(
            SQL("SELECT * FROM "),
            Identifier("table"),
            SQL(" WHERE x IN ("),
            Composed(Literal(1), SQL(","), Literal(2)),
            SQL(")"),
        )
        assert len(result) == 7
        assert [x.__class__ for x in result] == [SQL, Identifier, SQL, Literal, SQL, Literal, SQL]
        assert str(result) == (
            'Composed(SQL("SELECT * FROM ") + Identifier("table") + SQL(" WHERE x IN (") + '
            'Literal(1) + SQL(",") + Literal(2) + SQL(")"))'
        )
        result = Composed(Composed(SQL("foo")))
        assert result == Composed(SQL("foo"))
        assert str(result) == 'Composed(SQL("foo"))'

        result = SQL("asd") + Composed(SQL("asf"))
        assert result == Composed(SQL("asd"), Composed(SQL("asf")))

        assert Composed(SQL("asd")) == Composed(SQL("asd"))
        assert Composed(SQL("asd")) == SQL("asd")
        assert SQL("asd") == Composed(SQL("asd"))

        assert Literal("asd") != Identifier("asd")
        assert Literal("asd") != SQL("asd")
        assert Composed(Literal("asd")) != Identifier("asd")
        assert Literal("asd") != Composed(SQL("asd"))

    def test_compose(self):
        result = Composed(Literal("asd")).compose()
        assert len(result) == 1
        assert list(iter(result))[0] == Literal("asd")
