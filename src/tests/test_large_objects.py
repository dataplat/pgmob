from unittest.mock import call

import pytest

from pgmob import objects
from pgmob.sql import SQL, Identifier, Literal


@pytest.fixture
def large_object_cursor(cursor, large_object_tuples):
    """Cursor that returns lo tuples"""
    cursor.fetchall.return_value = large_object_tuples
    return cursor


@pytest.fixture
def large_object_collection(cluster, large_object_cursor):
    """Returns an initialized LargeObjectCollection object"""
    collection = objects.LargeObjectCollection(cluster=cluster)
    return collection


@pytest.fixture
def large_object(cluster, large_object_tuples):
    """Returns an initialized LargeObject object"""
    data = large_object_tuples[0]
    collection = objects.LargeObject(
        cluster=cluster,
        owner=data[1],
        oid=data.oid,
    )
    return collection


class TestLargeObject:
    def test_init(self, large_object: objects.LargeObject, large_object_tuples):
        lo_tuple = large_object_tuples[0]
        assert large_object.owner == lo_tuple.lomowner
        assert large_object.oid == lo_tuple.oid
        assert str(large_object) == f"LargeObject('{lo_tuple.oid}')"

    def test_drop(self, large_object: objects.LargeObject, lobject):
        large_object.drop()
        lobject.unlink.assert_called_with()

    def test_read(self, large_object: objects.LargeObject, lobject):
        large_object.read()
        lobject.read.assert_called_with()

    def test_write(self, large_object: objects.LargeObject, lobject):
        large_object.write(b"new data")
        lobject.write.assert_called_with(b"new data")

    def test_truncate(self, large_object: objects.LargeObject, lobject):
        large_object.truncate()
        lobject.truncate.assert_called_with(0)
        large_object.truncate(1)
        lobject.truncate.assert_called_with(1)

    def test_refresh(self, large_object: objects.LargeObject, large_object_cursor, large_object_tuples):
        x = large_object_tuples[0]
        large_object.owner = "foo"
        large_object.refresh()
        assert large_object.owner == x.lomowner

    def test_alter(self, large_object: objects.LargeObject, large_object_cursor, large_object_tuples):
        largeobject_src = large_object_tuples[0]
        large_object_cursor.execute.side_effect = [
            [],
            [largeobject_src],
            [largeobject_src],
        ]
        fqn = Literal(large_object.oid)
        large_object.owner = "foo"
        large_object.alter()
        large_object_cursor.execute.assert_has_calls(
            [
                call(
                    SQL("ALTER LARGE OBJECT {largeobject} OWNER TO {owner}").format(
                        largeobject=fqn,
                        owner=Identifier("foo"),
                    ),
                    None,
                )
            ]
        )


class TestLargeObjectCollection:
    def test_init(self, large_object_collection, large_object_tuples):
        for result in large_object_collection:
            assert isinstance(result, objects.LargeObject)
        for lo_tuple in large_object_tuples:
            key = lo_tuple.oid
            result = large_object_collection[key]
            assert result.owner == lo_tuple.lomowner
            assert result.oid == lo_tuple.oid
            assert str(result) == f"LargeObject('{lo_tuple.oid}')"

    def test_refresh(self, large_object_collection: objects.LargeObjectCollection, large_object_tuples):
        large_object_collection[large_object_tuples[0].oid].owner = "foo"
        large_object_collection.refresh()
        assert large_object_collection[large_object_tuples[0].oid].owner == large_object_tuples[0].lomowner
        assert len(large_object_collection[large_object_tuples[0].oid]._changes) == 0
