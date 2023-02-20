from pgmob.objects import HBARule, HBARuleCollection


class TestHBARule:
    def test_equality(self):
        assert HBARule("host postgres") == HBARule("host postgres")
        assert HBARule("host postgres") == HBARule("host  postgres")
        assert HBARule("host postgres") == HBARule("host \tpostgres")
        assert HBARule("host postgres") == HBARule("host\tpostgres")
        assert HBARule("# this is a comment") == HBARule("# this is a comment")
        assert HBARule("") == HBARule("")
        assert HBARule("") == HBARule(" ")

    def test_init(self):
        rule = HBARule("local db user1 foo a=b  c=d")

        assert rule.type == "local"
        assert rule.database == "db"
        assert rule.user == "user1"
        assert rule.auth_method == "foo"
        assert rule.auth_options == "a=b c=d"

        rule = HBARule("host db user1 127.0.0.1/32 foo")

        assert rule.type == "host"
        assert rule.database == "db"
        assert rule.user == "user1"
        assert rule.address == "127.0.0.1/32"
        assert rule.auth_method == "foo"
        assert rule.auth_options == ""

        rule = HBARule("host db user1 127.0.0.1 255.255.255.255 foo a=b")

        assert rule.type == "host"
        assert rule.database == "db"
        assert rule.user == "user1"
        assert rule.address == "127.0.0.1"
        assert rule.mask == "255.255.255.255"
        assert rule.auth_method == "foo"
        assert rule.auth_options == "a=b"

        rule = HBARule("#host db user1 127.0.0.1 255.255.255.255 foo a=b")

        assert rule.type == None
        assert rule.database == None
        assert rule.user == None
        assert rule.address == None
        assert rule.mask == None
        assert rule.auth_method == None
        assert rule.auth_options == ""

        rule = HBARule("local db user1 foo #comment")

        assert rule.type == "local"
        assert rule.database == "db"
        assert rule.user == "user1"
        assert rule.auth_method == "foo"
        assert rule.auth_options == ""


class TestHBARuleCollection:
    def test_collection_equality(self):
        col1 = HBARuleCollection(None)
        col1.extend([HBARule("host postgres")])
        col2 = HBARuleCollection(None)
        col2.extend([HBARule("host postgres")])
        assert col1 == col2

        col2 = HBARuleCollection(None)
        col2.extend([HBARule("host  postgres")])
        assert col1 == col2

        col1 = HBARuleCollection(None)
        col1.extend(
            [
                HBARule("host postgres"),
                HBARule("host postgres"),
                HBARule("# this is a comment"),
                HBARule(""),
                HBARule(""),
            ]
        )

        col2 = HBARuleCollection(None)
        col2.extend(
            [
                HBARule("host \tpostgres"),
                HBARule("host\tpostgres"),
                HBARule("# this is a comment"),
                HBARule(""),
                HBARule(" "),
            ]
        )
        assert col1 == col2

    def test_inequality(self):
        assert HBARule("host postgres") != HBARule("local postgres")
        assert HBARule("host postgres") != HBARule("host postgres postgres")
        assert HBARule("host postgres") != HBARule("host  database")
        assert HBARule("host postgres") != HBARule("#host postgres")
        assert HBARule("#comment") != HBARule("")

    def test_collection_in(self):
        collection = HBARuleCollection(None)
        collection.extend(
            [
                "#hba file",
                "",
                "# empty line above",
                "local all all trust",
                "host all all 127.0.0.1/32 trust",
                "#that's enough",
            ]
        )
        # base format
        assert "#hba file" in collection
        assert "" in collection
        assert "# empty line above" in collection
        assert "local all all trust" in collection
        assert "host all all 127.0.0.1/32 trust" in collection
        assert "#that's enough" in collection

        # different spacing
        assert "#hba file " in collection
        assert " " in collection
        assert "# empty   line above" in collection
        assert "local   all  all    trust" in collection
        assert "host\tall\t all \t127.0.0.1/32\t\ttrust" in collection

    def test_collection_append(self):
        string1 = "#hba file"
        string2 = "local postgres"
        string3 = "foo bar"
        rule1 = HBARule(string1)
        rule2 = HBARule(string2)
        rule3 = HBARule(string3)
        # adding rules
        collection = HBARuleCollection(None)
        collection += [rule1]
        collection.extend([rule2])
        collection.append(rule3)
        assert collection == [rule1, rule2, rule3]
        for r in collection:
            assert isinstance(r, HBARule)
        # appending a string
        collection = HBARuleCollection(None)
        collection += [rule1]
        collection.append(string2)
        collection.extend([string3])
        assert collection == [rule1, rule2, rule3]
        for r in collection:
            assert isinstance(r, HBARule)

    def test_collection_insert(self):
        string2 = "local postgres"
        rule1 = HBARule("#hba file")
        rule2 = HBARule(string2)
        rule3 = HBARule("local  postgres")
        # adding rules
        collection = HBARuleCollection(None)
        collection += [rule1]
        collection.insert(0, rule3)
        assert collection == [rule3, rule1]
        for r in collection:
            assert isinstance(r, HBARule)
        # adding a string
        collection = HBARuleCollection(None)
        collection += [rule1]
        collection.insert(1, string2)
        assert collection == [rule1, rule2]
        for r in collection:
            assert isinstance(r, HBARule)

    def test_collection_remove(self):
        string2 = "local postgres"
        rule1 = HBARule("#hba file")
        rule2 = HBARule(string2)
        rule3 = HBARule("local  postgres")
        collection = HBARuleCollection(None)
        collection.extend([rule1, rule3])
        collection.remove(rule3)
        assert collection == [rule1]
        collection = HBARuleCollection(None)
        collection.extend([rule1, rule2])
        collection.remove(string2)
        assert collection == [rule1]

    def test_collection_index(self):
        string2 = "local postgres"
        rule1 = HBARule("#hba file")
        rule2 = HBARule(string2)
        collection = HBARuleCollection(None)
        collection.extend([rule1, rule2])
        assert collection.index(rule1) == 0
        assert collection.index(string2) == 1

    def test_init(self, mock_cluster):
        mock_cluster.execute_with_cursor.return_value = ["line1", "line2"]
        rules = HBARuleCollection(cluster=mock_cluster)
        assert "line1" in rules
        assert "line2" in rules

    def test_alter(self, mock_cluster):
        mock_cluster.execute_with_cursor.return_value = ["line1", "line2"]
        rules = HBARuleCollection(cluster=mock_cluster)
        mock_cluster.execute_with_cursor.reset_mock()
        rules.alter()
        mock_cluster.execute_with_cursor.assert_called_once()
