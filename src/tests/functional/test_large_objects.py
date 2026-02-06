import pytest

from pgmob import objects


@pytest.fixture
def large_objects(lo_ids, cluster):
    """Creates a set of large objects"""
    los = objects.LargeObjectCollection(cluster=cluster)
    yield los


class TestLargeObjects:
    lo_query = (
        "SELECT {field} "
        "FROM pg_largeobject_metadata lo "
        "JOIN pg_catalog.pg_roles r on lo.lomowner = r.oid "
        "WHERE lo.oid = '{oid}'"
    )

    def test_init(self, large_objects, lo_ids):
        for lo_id in lo_ids:
            largeobject = large_objects[lo_id]
            assert largeobject.owner == "postgres"
            assert largeobject.oid == lo_id

    def test_owner(self, large_objects, lo_ids, psql, role):
        lo_id = lo_ids[0]

        def get_current():
            return psql(
                self.lo_query.format(field="r.rolname", oid=lo_id),
            ).output

        largeobject = large_objects[lo_id]
        largeobject.owner = role
        assert get_current() == "postgres"
        largeobject.alter()
        assert get_current() == role
        assert largeobject.owner == role
        psql(f"\\lo_unlink {lo_id}")

    def test_drop(self, large_objects, lo_ids, psql):
        def get_current(oid):
            return psql(
                self.lo_query.format(field="lo.oid", oid=oid),
            ).output

        for lo in lo_ids:
            large_objects[lo].drop()
            assert get_current(lo) == ""

    def test_read(self, large_objects, lo_ids):
        for lo in lo_ids:
            assert large_objects[lo].read() in ["foobar\n", "zoobar\n"]

    def test_write(self, large_objects, lo_ids, psql):
        lo_id = lo_ids[0]
        large_objects[lo_id].write(b"new data")
        lo = psql(f"SELECT encode(data, 'escape') FROM pg_largeobject WHERE loid = {lo_id}")
        assert lo.output == "new data"

    def test_truncate(self, large_objects, lo_ids, psql):
        lo_id = lo_ids[0]

        def get_current():
            return psql(f"SELECT encode(data, 'escape') FROM pg_largeobject WHERE loid = {lo_id}").output

        large_objects[lo_id].truncate(len=1)
        assert get_current() == "f"
        large_objects[lo_id].truncate()
        assert get_current() == ""
