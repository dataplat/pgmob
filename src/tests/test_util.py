from collections import namedtuple
import pytest
from pgmob.sql import SQL
from pgmob.util import *
import re


class TestVersion:
    def test_equality(self):
        assert Version("1.2") == Version("1.2")
        assert Version("1.2.3") == Version("1.2.3")
        assert Version("1.2.3.4") == Version("1.2.3.4")
        assert Version("1.2.3") == Version("1.2.3.0")
        assert Version("1.2.3") == Version("1.2.03")
        assert Version("1.2.0") == Version("1.2")
        assert Version("1.2.0.0") == Version("1.2")

    def test_greater(self):
        assert Version("1.3") > Version("1.2")
        assert Version("1.2.4") > Version("1.2.3")
        assert Version("1.2.3.5") > Version("1.2.3.4")
        assert Version("1.2.3.1") > Version("1.2.3.0")
        assert Version("1.2.12") > Version("1.2.10")
        assert Version("1.2.0.1") > Version("1.2")
        assert Version("1.2.0.1") > Version("1.2.0")

    def test_inequality(self):
        assert Version("1.2") != Version("1.1")
        assert Version("1.2.3") != Version("1.2.4")
        assert Version("1.2.3.4") != Version("1.2.3.5")
        assert Version("1.2") != Version("1.2.1")
        assert Version("1.2") != Version("1.2.1.1")

    def test_attributes(self):
        ver = Version("1.2.3.4")
        assert ver.major == 1
        assert ver.minor == 2
        assert ver.build == 3
        assert ver.revision == 4
        ver = Version("1.2.3")
        assert ver.major == 1
        assert ver.minor == 2
        assert ver.build == 3
        assert ver.revision == 0
        ver = Version("1.2")
        assert ver.major == 1
        assert ver.minor == 2
        assert ver.build == 0
        assert ver.revision == 0

    def test_str(self):
        assert str(Version("1.2")) == "1.2"
        assert str(Version("1.2.3")) == "1.2.3"
        assert str(Version("1.2.3.4")) == "1.2.3.4"

    def test_exceptions(self):
        with pytest.raises(ValueError):
            Version("1.2.1a")

        with pytest.raises(ValueError):
            Version("foobar")

        with pytest.raises(ValueError):
            Version("")


class TestUtil:
    def test_get_sql(self):
        assert isinstance(get_sql("get_database"), SQL)
        assert re.search("datname", get_sql("get_database").value())

        assert isinstance(get_sql("get_procedure"), SQL)
        assert re.search("proiswindow", get_sql("get_procedure").value())
        assert not re.search("p\\.prokind", get_sql("get_procedure").value())

        assert isinstance(get_sql("get_procedure", Version("10.0")), SQL)
        assert re.search("proiswindow", get_sql("get_procedure", Version("10.0")).value())
        assert not re.search("p\\.prokind", get_sql("get_procedure", Version("10.0")).value())

        assert isinstance(get_sql("get_procedure", Version("11.0")), SQL)
        assert re.search("p\\.prokind", get_sql("get_procedure", Version("11.0")).value())
        assert not re.search("proiswindow", get_sql("get_procedure", Version("11.0")).value())

        assert isinstance(get_sql("get_procedure", Version("12.0")), SQL)
        assert re.search("p\\.prokind", get_sql("get_procedure", Version("12.0")).value())
        assert not re.search("proiswindow", get_sql("get_procedure", Version("12.0")).value())

    def test_group_by(self):
        Seq = namedtuple("Seq", "a b c d")
        items = [
            Seq(1, 2, 3, 4),
            Seq(1, 2, 4, 5),
            Seq(1, 3, 4, 6),
        ]
        result = group_by(lambda pair: (pair[0], pair[1]), items)
        assert result == {(1, 2): [items[0], items[1]], (1, 3): [items[2]]}
