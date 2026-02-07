from pgmob import objects


class TestHBARules:
    def test_init(self, cluster):
        rules = objects.HBARuleCollection(cluster=cluster)
        for r in rules:
            assert isinstance(r, objects.HBARule)
        assert "local replication all trust" in rules
        assert "host replication all 127.0.0.1/32 trust" in rules
        assert "host replication all ::1/128 trust" in rules
        assert "host all all all md5" in rules

    def test_alter(self, cluster, container):
        rules = objects.HBARuleCollection(cluster=cluster)
        rule = "local   postgres   postgres   any"
        # add rule
        rules.append(rule)
        rules.alter()
        rules.refresh()
        assert "local postgres postgres any" in rules
        assert "local   postgres   postgres   any" in container.exec_run(
            "cat /var/lib/postgresql/data/pg_hba.conf"
        ).output.decode("utf8").split("\n")
        # remove rule
        rules.remove(objects.HBARule(rule))
        rules.alter()
        rules.refresh()
        assert "local postgres postgres any" not in rules
        assert "local   postgres   postgres   any" not in container.exec_run(
            "cat /var/lib/postgresql/data/pg_hba.conf"
        ).output.decode("utf8").split("\n")
