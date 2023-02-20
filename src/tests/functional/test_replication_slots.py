from pgmob import objects


class TestFunctionalReplicationSlot:
    slot_query = "SELECT {field} FROM pg_catalog.pg_replication_slots" " WHERE slot_name = '{slot}'"

    def test_init(self, connect, replication_slot, plugin, db):
        cluster = connect()
        slots = objects.ReplicationSlotCollection(cluster=cluster)
        slot_item = slots[replication_slot]
        assert slot_item.name == replication_slot
        assert slot_item.plugin == plugin
        assert slot_item.slot_type == "logical"
        assert slot_item.database == db
        assert slot_item.temporary == False
        assert slot_item.is_active == False
        assert slot_item.active_pid is None
        assert slot_item.xmin is None
        assert slot_item.catalog_xmin is not None
        assert slot_item.restart_lsn is not None
        assert slot_item.confirmed_flush_lsn is not None
        assert str(slot_item) == f"ReplicationSlot('{replication_slot}')"

    def test_drop(self, connect, replication_slot, db, psql):
        cluster = connect()
        slots = objects.ReplicationSlotCollection(cluster=cluster)
        slots[replication_slot].drop()
        slots.refresh()
        assert replication_slot not in slots
        assert psql(self.slot_query.format(field="slot_name", slot=replication_slot)).output == ""

    def test_script(self, connect, replication_slot, plugin):
        cluster = connect()
        slots = objects.ReplicationSlotCollection(cluster=cluster)
        assert slots[
            replication_slot
        ].script() == f"SELECT pg_create_logical_replication_slot('{replication_slot}', '{plugin}')".encode(
            "utf8"
        )

    def test_create(self, connect, db, psql, plugin):
        cluster = connect(db=db)
        slots = objects.ReplicationSlotCollection(cluster=cluster)
        slot = slots.new(name="foobar", plugin=plugin)
        slot.create()
        slots.refresh()
        assert "foobar" in slots
        assert psql(self.slot_query.format(field="slot_name", slot="foobar")).output == "foobar"

    def test_disconnect(self, connect, replication_slot, psql):
        cluster = connect()
        slots = objects.ReplicationSlotCollection(cluster=cluster)
        slots[replication_slot].disconnect()
        assert psql(self.slot_query.format(field="active_pid", slot=replication_slot)).output == ""
