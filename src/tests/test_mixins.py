"""Tests for mixin classes.

This module tests the mixin classes that provide common property patterns
for PostgreSQL objects. Tests cover property getters/setters, initialization,
composition, and change tracking behavior.
"""

from hypothesis import given
from hypothesis import strategies as st

from pgmob.objects.generic import _DynamicObject
from pgmob.objects.mixins import (
    NamedObjectMixin,
    OwnedObjectMixin,
    SchemaObjectMixin,
    TablespaceObjectMixin,
)


# Test helper classes that combine mixins with _DynamicObject
class NamedTestObject(NamedObjectMixin, _DynamicObject):
    """Test object with name property."""

    def __init__(self, name: str, cluster=None):
        _DynamicObject.__init__(self, kind="TEST", name=name, cluster=cluster)
        self._init_name(name)


class OwnedTestObject(OwnedObjectMixin, _DynamicObject):
    """Test object with owner property."""

    def __init__(self, name: str, owner: str | None = None, cluster=None):
        _DynamicObject.__init__(self, kind="TEST", name=name, cluster=cluster)
        self._init_owner(owner)


class SchemaTestObject(SchemaObjectMixin, _DynamicObject):
    """Test object with schema property."""

    def __init__(self, name: str, schema: str = "public", cluster=None):
        _DynamicObject.__init__(self, kind="TEST", name=name, schema=schema, cluster=cluster)
        self._init_schema(schema)


class TablespaceTestObject(TablespaceObjectMixin, _DynamicObject):
    """Test object with tablespace property."""

    def __init__(self, name: str, tablespace: str | None = None, cluster=None):
        _DynamicObject.__init__(self, kind="TEST", name=name, cluster=cluster)
        self._init_tablespace(tablespace)


class ComposedTestObject(
    NamedObjectMixin,
    OwnedObjectMixin,
    SchemaObjectMixin,
    TablespaceObjectMixin,
    _DynamicObject,
):
    """Test object with all four mixins."""

    def __init__(
        self,
        name: str,
        owner: str | None = None,
        schema: str = "public",
        tablespace: str | None = None,
        cluster=None,
    ):
        _DynamicObject.__init__(self, kind="TEST", name=name, schema=schema, cluster=cluster)
        self._init_name(name)
        self._init_owner(owner)
        self._init_schema(schema)
        self._init_tablespace(tablespace)


class TestNamedObjectMixin:
    """Tests for NamedObjectMixin."""

    def test_init_name_sets_private_attribute(self):
        """Test that _init_name sets the _name attribute."""
        obj = NamedTestObject("test_name")
        assert obj._name == "test_name"

    def test_name_getter_returns_private_attribute(self):
        """Test that name property getter returns _name."""
        obj = NamedTestObject("test_name")
        assert obj.name == obj._name
        assert obj.name == "test_name"

    def test_name_getter_with_various_values(self):
        """Test name getter with different string values."""
        test_values = ["simple", "with-dash", "with_underscore", "with.dot", "123numeric"]
        for value in test_values:
            obj = NamedTestObject(value)
            assert obj.name == value

    def test_name_setter_creates_change_tracking_entry(self, mock_cluster):
        """Test that setting name creates a change tracking entry."""
        obj = NamedTestObject("original", cluster=mock_cluster)
        obj.name = "new_name"

        assert "name" in obj._changes
        assert obj._name == "new_name"

    def test_name_setter_with_same_value_no_change(self, mock_cluster):
        """Test that setting name to same value doesn't create change."""
        obj = NamedTestObject("test_name", cluster=mock_cluster)
        obj.name = "test_name"

        assert "name" not in obj._changes

    # Feature: mixin-based-inheritance, Property 1: Mixin Property Getters Return Private Attributes
    @given(name=st.text(min_size=1, max_size=100))
    def test_property_name_getter_returns_private_attr(self, name):
        """Property test: name getter returns _name for any valid name."""
        obj = NamedTestObject(name)
        assert obj.name == obj._name
        assert obj.name == name


class TestOwnedObjectMixin:
    """Tests for OwnedObjectMixin."""

    def test_init_owner_sets_private_attribute(self):
        """Test that _init_owner sets the _owner attribute."""
        obj = OwnedTestObject("test", owner="test_owner")
        assert obj._owner == "test_owner"

    def test_init_owner_with_none(self):
        """Test that _init_owner accepts None."""
        obj = OwnedTestObject("test", owner=None)
        assert obj._owner is None

    def test_init_owner_default_none(self):
        """Test that _init_owner defaults to None."""
        obj = OwnedTestObject("test")
        assert obj._owner is None

    def test_owner_getter_returns_private_attribute(self):
        """Test that owner property getter returns _owner."""
        obj = OwnedTestObject("test", owner="test_owner")
        assert obj.owner == obj._owner
        assert obj.owner == "test_owner"

    def test_owner_getter_returns_none(self):
        """Test that owner getter returns None when not set."""
        obj = OwnedTestObject("test")
        assert obj.owner is None

    def test_owner_setter_creates_change_tracking_entry(self, mock_cluster):
        """Test that setting owner creates a change tracking entry."""
        obj = OwnedTestObject("test", owner="original", cluster=mock_cluster)
        obj.owner = "new_owner"

        assert "owner" in obj._changes
        assert obj._owner == "new_owner"

    def test_owner_setter_from_none(self, mock_cluster):
        """Test setting owner from None."""
        obj = OwnedTestObject("test", owner=None, cluster=mock_cluster)
        obj.owner = "new_owner"

        assert "owner" in obj._changes
        assert obj._owner == "new_owner"

    # Feature: mixin-based-inheritance, Property 1: Mixin Property Getters Return Private Attributes
    @given(owner=st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    def test_property_owner_getter_returns_private_attr(self, owner):
        """Property test: owner getter returns _owner for any valid owner."""
        obj = OwnedTestObject("test", owner=owner)
        assert obj.owner == obj._owner
        assert obj.owner == owner


class TestSchemaObjectMixin:
    """Tests for SchemaObjectMixin."""

    def test_init_schema_sets_private_attribute(self):
        """Test that _init_schema sets the _schema attribute."""
        obj = SchemaTestObject("test", schema="test_schema")
        assert obj._schema == "test_schema"

    def test_init_schema_defaults_to_public(self):
        """Test that _init_schema defaults to 'public'."""
        obj = SchemaTestObject("test")
        assert obj._schema == "public"

    def test_schema_getter_returns_private_attribute(self):
        """Test that schema property getter returns _schema."""
        obj = SchemaTestObject("test", schema="test_schema")
        assert obj.schema == obj._schema
        assert obj.schema == "test_schema"

    def test_schema_getter_returns_default(self):
        """Test that schema getter returns 'public' by default."""
        obj = SchemaTestObject("test")
        assert obj.schema == "public"

    def test_schema_setter_creates_change_tracking_entry(self, mock_cluster):
        """Test that setting schema creates a change tracking entry."""
        obj = SchemaTestObject("test", schema="original", cluster=mock_cluster)
        obj.schema = "new_schema"

        assert "schema" in obj._changes
        assert obj._schema == "new_schema"

    # Feature: mixin-based-inheritance, Property 8: Schema Default Value
    @given(name=st.text(min_size=1, max_size=100))
    def test_property_schema_defaults_to_public(self, name):
        """Property test: schema defaults to 'public' when not specified."""
        obj = SchemaTestObject(name)
        assert obj.schema == "public"
        assert obj._schema == "public"

    # Feature: mixin-based-inheritance, Property 1: Mixin Property Getters Return Private Attributes
    @given(schema=st.text(min_size=1, max_size=100))
    def test_property_schema_getter_returns_private_attr(self, schema):
        """Property test: schema getter returns _schema for any valid schema."""
        obj = SchemaTestObject("test", schema=schema)
        assert obj.schema == obj._schema
        assert obj.schema == schema


class TestTablespaceObjectMixin:
    """Tests for TablespaceObjectMixin."""

    def test_init_tablespace_sets_private_attribute(self):
        """Test that _init_tablespace sets the _tablespace attribute."""
        obj = TablespaceTestObject("test", tablespace="test_tablespace")
        assert obj._tablespace == "test_tablespace"

    def test_init_tablespace_with_none(self):
        """Test that _init_tablespace accepts None."""
        obj = TablespaceTestObject("test", tablespace=None)
        assert obj._tablespace is None

    def test_init_tablespace_default_none(self):
        """Test that _init_tablespace defaults to None."""
        obj = TablespaceTestObject("test")
        assert obj._tablespace is None

    def test_tablespace_getter_returns_private_attribute(self):
        """Test that tablespace property getter returns _tablespace."""
        obj = TablespaceTestObject("test", tablespace="test_tablespace")
        assert obj.tablespace == obj._tablespace
        assert obj.tablespace == "test_tablespace"

    def test_tablespace_getter_returns_none(self):
        """Test that tablespace getter returns None when not set."""
        obj = TablespaceTestObject("test")
        assert obj.tablespace is None

    def test_tablespace_setter_creates_change_tracking_entry(self, mock_cluster):
        """Test that setting tablespace creates a change tracking entry."""
        obj = TablespaceTestObject("test", tablespace="original", cluster=mock_cluster)
        obj.tablespace = "new_tablespace"

        assert "tablespace" in obj._changes
        assert obj._tablespace == "new_tablespace"

    def test_tablespace_setter_from_none(self, mock_cluster):
        """Test setting tablespace from None."""
        obj = TablespaceTestObject("test", tablespace=None, cluster=mock_cluster)
        obj.tablespace = "new_tablespace"

        assert "tablespace" in obj._changes
        assert obj._tablespace == "new_tablespace"

    # Feature: mixin-based-inheritance, Property 1: Mixin Property Getters Return Private Attributes
    @given(tablespace=st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    def test_property_tablespace_getter_returns_private_attr(self, tablespace):
        """Property test: tablespace getter returns _tablespace for any valid tablespace."""
        obj = TablespaceTestObject("test", tablespace=tablespace)
        assert obj.tablespace == obj._tablespace
        assert obj.tablespace == tablespace


class TestMixinComposition:
    """Tests for objects using multiple mixins."""

    def test_composed_object_has_all_properties(self):
        """Test that composed object has all mixin properties."""
        obj = ComposedTestObject(
            name="test_name",
            owner="test_owner",
            schema="test_schema",
            tablespace="test_tablespace",
        )

        assert obj.name == "test_name"
        assert obj.owner == "test_owner"
        assert obj.schema == "test_schema"
        assert obj.tablespace == "test_tablespace"

    def test_composed_object_with_defaults(self):
        """Test composed object with default values."""
        obj = ComposedTestObject(name="test_name")

        assert obj.name == "test_name"
        assert obj.owner is None
        assert obj.schema == "public"
        assert obj.tablespace is None

    def test_composed_object_all_setters_work(self, mock_cluster):
        """Test that all property setters work on composed object."""
        obj = ComposedTestObject(
            name="original_name",
            owner="original_owner",
            schema="original_schema",
            tablespace="original_tablespace",
            cluster=mock_cluster,
        )

        obj.name = "new_name"
        obj.owner = "new_owner"
        obj.schema = "new_schema"
        obj.tablespace = "new_tablespace"

        assert "name" in obj._changes
        assert "owner" in obj._changes
        assert "schema" in obj._changes
        assert "tablespace" in obj._changes

        assert obj.name == "new_name"
        assert obj.owner == "new_owner"
        assert obj.schema == "new_schema"
        assert obj.tablespace == "new_tablespace"

    # Feature: mixin-based-inheritance, Property 4: Mixin Composition Provides All Properties
    @given(
        name=st.text(min_size=1, max_size=50),
        owner=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
        schema=st.text(min_size=1, max_size=50),
        tablespace=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    def test_property_composition_all_properties_accessible(self, name, owner, schema, tablespace):
        """Property test: all mixin properties are accessible on composed object."""
        obj = ComposedTestObject(
            name=name,
            owner=owner,
            schema=schema,
            tablespace=tablespace,
        )

        assert obj.name == name
        assert obj.owner == owner
        assert obj.schema == schema
        assert obj.tablespace == tablespace


class TestMixinChangeTracking:
    """Tests for change tracking behavior with mixin properties."""

    def test_name_change_creates_sql_change(self, mock_cluster):
        """Test that name change creates correct SQL change object."""
        obj = NamedTestObject("original", cluster=mock_cluster)
        obj.name = "new_name"

        assert "name" in obj._changes
        change = obj._changes["name"]
        assert hasattr(change, "sql")

    def test_owner_change_creates_sql_change(self, mock_cluster):
        """Test that owner change creates correct SQL change object."""
        obj = OwnedTestObject("test", owner="original", cluster=mock_cluster)
        obj.owner = "new_owner"

        assert "owner" in obj._changes
        change = obj._changes["owner"]
        assert hasattr(change, "sql")

    def test_schema_change_creates_sql_change(self, mock_cluster):
        """Test that schema change creates correct SQL change object."""
        obj = SchemaTestObject("test", schema="original", cluster=mock_cluster)
        obj.schema = "new_schema"

        assert "schema" in obj._changes
        change = obj._changes["schema"]
        assert hasattr(change, "sql")

    def test_tablespace_change_creates_sql_change(self, mock_cluster):
        """Test that tablespace change creates correct SQL change object."""
        obj = TablespaceTestObject("test", tablespace="original", cluster=mock_cluster)
        obj.tablespace = "new_tablespace"

        assert "tablespace" in obj._changes
        change = obj._changes["tablespace"]
        assert hasattr(change, "sql")

    def test_multiple_changes_tracked_separately(self, mock_cluster):
        """Test that multiple property changes are tracked separately."""
        obj = ComposedTestObject(
            name="original_name",
            owner="original_owner",
            schema="original_schema",
            tablespace="original_tablespace",
            cluster=mock_cluster,
        )

        obj.name = "new_name"
        obj.owner = "new_owner"

        assert len(obj._changes) == 2
        assert "name" in obj._changes
        assert "owner" in obj._changes

    # Feature: mixin-based-inheritance, Property 2: Mixin Property Setters Create Change Tracking Entries
    @given(
        original_name=st.text(min_size=1, max_size=50),
        new_name=st.text(min_size=1, max_size=50),
    )
    def test_property_setter_creates_change_entry(self, original_name, new_name):
        """Property test: setter creates change tracking entry for different values."""
        # Skip if values are the same (no change should be tracked)
        if original_name == new_name:
            return

        # Create a mock cluster inline instead of using fixture
        from unittest.mock import Mock

        from pgmob.adapters.base import BaseAdapter
        from pgmob.cluster import Cluster

        mock_cluster = Mock(spec=Cluster)
        mock_cluster.adapter = Mock(spec=BaseAdapter)

        obj = NamedTestObject(original_name, cluster=mock_cluster)
        obj.name = new_name

        assert "name" in obj._changes
        assert obj._name == new_name


class TestMixinInitialization:
    """Tests for mixin initialization patterns."""

    def test_init_methods_called_in_constructor(self):
        """Test that _init_* methods are called during object construction."""
        obj = ComposedTestObject(
            name="test_name",
            owner="test_owner",
            schema="test_schema",
            tablespace="test_tablespace",
        )

        # Verify all private attributes are set
        assert hasattr(obj, "_name")
        assert hasattr(obj, "_owner")
        assert hasattr(obj, "_schema")
        assert hasattr(obj, "_tablespace")

    def test_init_with_edge_case_empty_string_name(self):
        """Test initialization with empty string (edge case)."""
        # Empty strings are technically valid but unusual
        obj = NamedTestObject("")
        assert obj.name == ""

    def test_init_with_special_characters(self):
        """Test initialization with special characters."""
        special_names = ["test-name", "test_name", "test.name", "test$name"]
        for name in special_names:
            obj = NamedTestObject(name)
            assert obj.name == name

    # Feature: mixin-based-inheritance, Property 3: Mixin Initialization Methods Set Private Attributes
    @given(
        name=st.text(min_size=1, max_size=50),
        owner=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
        schema=st.text(min_size=1, max_size=50),
        tablespace=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    def test_property_init_methods_set_private_attrs(self, name, owner, schema, tablespace):
        """Property test: _init_* methods set private attributes correctly."""
        obj = ComposedTestObject(
            name=name,
            owner=owner,
            schema=schema,
            tablespace=tablespace,
        )

        assert obj._name == name
        assert obj._owner == owner
        assert obj._schema == schema
        assert obj._tablespace == tablespace
