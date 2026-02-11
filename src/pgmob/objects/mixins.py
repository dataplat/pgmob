"""Mixin classes for common PostgreSQL object properties.

This module provides reusable mixin classes that encapsulate common property
patterns used across PostgreSQL object types. Each mixin handles a single
property concern and can be composed into object classes through multiple
inheritance.

Mixins:
    NamedObjectMixin: Provides name property with change tracking
    OwnedObjectMixin: Provides owner property with change tracking
    SchemaObjectMixin: Provides schema property with change tracking
    TablespaceObjectMixin: Provides tablespace property with change tracking

Usage:
    Objects using these mixins must call the corresponding _init_*() method
    in their __init__ method to initialize the private attributes.

Example:
    class Table(NamedObjectMixin, OwnedObjectMixin, _DynamicObject):
        def __init__(self, name: str, owner: str | None = None):
            _DynamicObject.__init__(self, kind="TABLE", name=name)
            self._init_name(name)
            self._init_owner(owner)
"""


class NamedObjectMixin:
    """Mixin providing name property with change tracking.

    This mixin provides a name property that integrates with PGMob's change
    tracking system. When the name is modified, the change is tracked for
    later application via the alter() method.

    Objects using this mixin must call _init_name() in their __init__ method.

    Attributes:
        name: The object's name (read/write property)
    """

    def _init_name(self, name: str) -> None:
        """Initialize the name attribute.

        This method must be called from the object's __init__ method to
        properly initialize the name attribute.

        Args:
            name: The object's name
        """
        self._name: str = name

    @property
    def name(self) -> str:
        """The object's name.

        Returns:
            The current name of the object
        """
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the object's name.

        Setting the name creates a change tracking entry that will be
        applied when alter() is called on the object.

        Args:
            value: New name for the object
        """
        from . import generic

        generic._set_ephemeral_attr(self, "name", value)  # type: ignore[arg-type]  # Mixin used with _DynamicObject


class OwnedObjectMixin:
    """Mixin providing owner property with change tracking.

    This mixin provides an owner property that integrates with PGMob's change
    tracking system. When the owner is modified, the change is tracked for
    later application via the alter() method.

    Objects using this mixin must call _init_owner() in their __init__ method.

    Attributes:
        owner: The object's owner (read/write property, can be None)
    """

    def _init_owner(self, owner: str | None = None) -> None:
        """Initialize the owner attribute.

        This method must be called from the object's __init__ method to
        properly initialize the owner attribute.

        Args:
            owner: The object's owner (optional, defaults to None)
        """
        self._owner: str | None = owner

    @property
    def owner(self) -> str | None:
        """The object's owner.

        Returns:
            The current owner of the object, or None if no owner is set
        """
        return self._owner

    @owner.setter
    def owner(self, value: str) -> None:
        """Set the object's owner.

        Setting the owner creates a change tracking entry that will be
        applied when alter() is called on the object.

        Args:
            value: New owner for the object
        """
        from . import generic

        generic._set_ephemeral_attr(self, "owner", value)  # type: ignore[arg-type]  # Mixin used with _DynamicObject


class SchemaObjectMixin:
    """Mixin providing schema property with change tracking.

    This mixin provides a schema property that integrates with PGMob's change
    tracking system. When the schema is modified, the change is tracked for
    later application via the alter() method.

    Objects using this mixin must call _init_schema() in their __init__ method.

    Attributes:
        schema: The schema this object belongs to (read/write property)
    """

    def _init_schema(self, schema: str = "public") -> None:
        """Initialize the schema attribute.

        This method must be called from the object's __init__ method to
        properly initialize the schema attribute.

        Args:
            schema: The schema name (defaults to "public")
        """
        self._schema: str = schema

    @property
    def schema(self) -> str:
        """The schema this object belongs to.

        Returns:
            The current schema name
        """
        return self._schema

    @schema.setter
    def schema(self, value: str) -> None:
        """Set the object's schema.

        Setting the schema creates a change tracking entry that will be
        applied when alter() is called on the object.

        Args:
            value: New schema for the object
        """
        from . import generic

        generic._set_ephemeral_attr(self, "schema", value)  # type: ignore[arg-type]  # Mixin used with _DynamicObject


class TablespaceObjectMixin:
    """Mixin providing tablespace property with change tracking.

    This mixin provides a tablespace property that integrates with PGMob's
    change tracking system. When the tablespace is modified, the change is
    tracked for later application via the alter() method.

    Objects using this mixin must call _init_tablespace() in their __init__
    method.

    Attributes:
        tablespace: The tablespace this object is assigned to (read/write
                   property, can be None)
    """

    def _init_tablespace(self, tablespace: str | None = None) -> None:
        """Initialize the tablespace attribute.

        This method must be called from the object's __init__ method to
        properly initialize the tablespace attribute.

        Args:
            tablespace: The tablespace name (optional, defaults to None)
        """
        self._tablespace: str | None = tablespace

    @property
    def tablespace(self) -> str | None:
        """The tablespace this object is assigned to.

        Returns:
            The current tablespace name, or None if no tablespace is assigned
        """
        return self._tablespace

    @tablespace.setter
    def tablespace(self, value: str) -> None:
        """Set the object's tablespace.

        Setting the tablespace creates a change tracking entry that will be
        applied when alter() is called on the object.

        Args:
            value: New tablespace for the object
        """
        from . import generic

        generic._set_ephemeral_attr(self, "tablespace", value)  # type: ignore[arg-type]  # Mixin used with _DynamicObject
