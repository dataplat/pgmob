import pytest
from pgmob import objects


@pytest.fixture
def slot_cursor(cursor, slot_tuples):
    """Cursor that returns db tuples"""
    cursor.fetchall.return_value = slot_tuples
    return cursor


@pytest.fixture
def slot_collection(cluster, slot_cursor):
    """Returns an initialized ReplicationSlotCollection object"""
    collection = objects.ReplicationSlotCollection(cluster=cluster)
    return collection


@pytest.fixture
def slot(cluster, slot_tuples):
    """Returns an initialized ReplicationSlot object"""
    data = slot_tuples[0]
    collection = objects.ReplicationSlot(
        cluster=cluster,
        name=data.slot_name,
        plugin=data.plugin,
    )
    return collection


class TestReplicationSlot:
    def test_init(self, slot: objects.ReplicationSlot, slot_tuples):
        slot_tuple = slot_tuples[0]
        assert slot.name == slot_tuple.slot_name
        assert slot.plugin == slot_tuple.plugin
        assert slot.slot_type == slot_tuple.slot_type
        assert slot.database == None
        assert slot.temporary == slot_tuple.temporary
        assert slot.is_active == None
        assert slot.active_pid == None
        assert slot.xmin == None
        assert slot.catalog_xmin == None
        assert slot.restart_lsn == None
        assert slot.confirmed_flush_lsn == None
        assert str(slot) == f"ReplicationSlot('{slot_tuple.slot_name}')"

    def test_drop(self, slot: objects.ReplicationSlot, slot_cursor, pgmob_tester):
        slot.drop()
        pgmob_tester.assertSql("pg_drop_replication_slot", slot_cursor)

    def test_refresh(self, slot: objects.ReplicationSlot, slot_tuples, slot_cursor, pgmob_tester):
        slot_tuple = slot_tuples[0]
        assert slot.database == None
        # recreate slot tuple with a different database name
        slot_dict = slot_tuple._asdict()
        slot_dict.update({"database": "foobar"})
        slot_tuple = slot_tuple.__class__(**slot_dict)
        # database should have a different name after refresh
        slot_cursor.fetchall.return_value = [slot_tuple]
        slot.refresh()
        pgmob_tester.assertSql("FROM pg_catalog.pg_replication_slots", slot_cursor)
        assert slot.database == "foobar"
        assert slot.name == slot_tuple.slot_name
        assert slot.plugin == slot_tuple.plugin
        assert slot.slot_type == slot_tuple.slot_type
        assert slot.temporary == slot_tuple.temporary
        assert slot.is_active == slot_tuple.active
        assert slot.active_pid == slot_tuple.active_pid
        assert slot.xmin == slot_tuple.xmin
        assert slot.catalog_xmin == slot_tuple.catalog_xmin
        assert slot.restart_lsn == slot_tuple.restart_lsn
        assert slot.confirmed_flush_lsn == slot_tuple.confirmed_flush_lsn

    def test_disconnect(self, slot: objects.ReplicationSlot, cursor, pgmob_tester):
        slot.disconnect()
        pgmob_tester.assertSql("pg_terminate_backend", cursor)

    def test_create(self, slot: objects.ReplicationSlot, slot_cursor, pgmob_tester):
        slot.create()
        pgmob_tester.assertSql("pg_create_logical_replication_slot", slot_cursor)

    def test_script(self, slot: objects.ReplicationSlot, cursor, pgmob_tester):
        cursor.mogrify.return_value = "foo"
        assert slot.script() == "foo"
        pgmob_tester.assertSql("pg_create_logical_replication_slot", cursor, mogrify=True)


class TestReplicationSlotCollection:
    def test_init(self, slot_tuples, slot_collection):
        for result in slot_collection:
            assert isinstance(result, objects.ReplicationSlot)
        for slot_tuple in slot_tuples:
            slot = slot_collection[slot_tuple.slot_name]
            assert slot.name == slot_tuple.slot_name
            assert result.parent == slot_collection

    def test_refresh(
        self, pgmob_tester, slot_collection: objects.ReplicationSlotCollection, slot_tuples, slot_cursor
    ):
        slot_collection.refresh()
        slot = slot_collection[slot_tuples[0].slot_name]
        assert slot.name == slot_tuples[0].slot_name
        assert len(slot._changes) == 0
        pgmob_tester.assertSql("FROM pg_catalog.pg_replication_slots", slot_cursor)
