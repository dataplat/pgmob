"""Tests for MetadataProvider abstract base class."""

from unittest.mock import Mock

import pytest

from pgmob.providers.base import MetadataProvider


class TestMetadataProviderAbstractMethods:
    """Test that MetadataProvider enforces abstract method contracts."""

    def test_cannot_instantiate_directly(self):
        """MetadataProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            MetadataProvider(cluster=Mock())

    def test_incomplete_implementation_rejected(self):
        """Incomplete subclass missing abstract methods is rejected."""

        class IncompleteProvider(MetadataProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider(cluster=Mock())

    def test_partial_implementation_rejected(self):
        """Subclass implementing only some methods is still rejected."""

        class PartialProvider(MetadataProvider):
            def get_tables(self, schema=None):
                return []

            def get_table(self, oid):
                return None

        with pytest.raises(TypeError):
            PartialProvider(cluster=Mock())

    def test_complete_implementation_accepted(self):
        """A complete implementation of all abstract methods is accepted."""

        class ConcreteProvider(MetadataProvider):
            def get_tables(self, schema=None):
                return []

            def get_table(self, oid):
                return None

            def get_roles(self):
                return []

            def get_role(self, name):
                return None

            def get_databases(self):
                return []

            def get_schemas(self):
                return []

            def get_sequences(self, schema=None):
                return []

            def get_sequence(self, oid):
                return None

            def get_views(self, schema=None):
                return []

            def get_procedures(self, schema=None):
                return []

        cluster = Mock()
        provider = ConcreteProvider(cluster=cluster)
        assert provider is not None
        assert provider.cluster is cluster


class TestMetadataProviderMethodSignatures:
    """Test method signatures and contracts of MetadataProvider."""

    @pytest.fixture
    def provider(self):
        """A minimal concrete implementation for signature testing."""

        class ConcreteProvider(MetadataProvider):
            def get_tables(self, schema=None):
                raise NotImplementedError

            def get_table(self, oid):
                raise NotImplementedError

            def get_roles(self):
                raise NotImplementedError

            def get_role(self, name):
                raise NotImplementedError

            def get_databases(self):
                raise NotImplementedError

            def get_schemas(self):
                raise NotImplementedError

            def get_sequences(self, schema=None):
                raise NotImplementedError

            def get_sequence(self, oid):
                raise NotImplementedError

            def get_views(self, schema=None):
                raise NotImplementedError

            def get_procedures(self, schema=None):
                raise NotImplementedError

        return ConcreteProvider(cluster=Mock())

    def test_get_tables_raises_not_implemented(self, provider):
        """get_tables() raises NotImplementedError in base stub."""
        with pytest.raises(NotImplementedError):
            provider.get_tables()

    def test_get_tables_accepts_schema_filter(self, provider):
        """get_tables() accepts optional schema parameter."""
        with pytest.raises(NotImplementedError):
            provider.get_tables(schema="public")

    def test_get_table_raises_not_implemented(self, provider):
        """get_table() raises NotImplementedError in base stub."""
        with pytest.raises(NotImplementedError):
            provider.get_table(oid=12345)

    def test_get_roles_raises_not_implemented(self, provider):
        """get_roles() raises NotImplementedError in base stub."""
        with pytest.raises(NotImplementedError):
            provider.get_roles()

    def test_get_role_raises_not_implemented(self, provider):
        """get_role() raises NotImplementedError in base stub."""
        with pytest.raises(NotImplementedError):
            provider.get_role(name="postgres")

    def test_get_databases_raises_not_implemented(self, provider):
        """get_databases() raises NotImplementedError in base stub."""
        with pytest.raises(NotImplementedError):
            provider.get_databases()

    def test_get_schemas_raises_not_implemented(self, provider):
        """get_schemas() raises NotImplementedError in base stub."""
        with pytest.raises(NotImplementedError):
            provider.get_schemas()

    def test_get_sequences_raises_not_implemented(self, provider):
        """get_sequences() raises NotImplementedError in base stub."""
        with pytest.raises(NotImplementedError):
            provider.get_sequences()

    def test_get_sequences_accepts_schema_filter(self, provider):
        """get_sequences() accepts optional schema parameter."""
        with pytest.raises(NotImplementedError):
            provider.get_sequences(schema="public")

    def test_get_views_raises_not_implemented(self, provider):
        """get_views() raises NotImplementedError in base stub."""
        with pytest.raises(NotImplementedError):
            provider.get_views()

    def test_get_views_accepts_schema_filter(self, provider):
        """get_views() accepts optional schema parameter."""
        with pytest.raises(NotImplementedError):
            provider.get_views(schema="public")

    def test_get_procedures_raises_not_implemented(self, provider):
        """get_procedures() raises NotImplementedError in base stub."""
        with pytest.raises(NotImplementedError):
            provider.get_procedures()

    def test_get_procedures_accepts_schema_filter(self, provider):
        """get_procedures() accepts optional schema parameter."""
        with pytest.raises(NotImplementedError):
            provider.get_procedures(schema="public")


class TestMetadataProviderContracts:
    """Test that MetadataProvider implementations satisfy interface contracts."""

    @pytest.fixture
    def mock_provider(self):
        """A mock-friendly concrete implementation returning typed data."""

        class MockableProvider(MetadataProvider):
            def get_tables(self, schema=None):
                return [{"name": "t1", "owner": "postgres", "schema": "public", "oid": 1}]

            def get_table(self, oid):
                return {"name": "t1", "owner": "postgres", "schema": "public", "oid": oid}

            def get_roles(self):
                return [{"name": "postgres", "oid": 10}]

            def get_role(self, name):
                return {"name": name, "oid": 10}

            def get_databases(self):
                return [{"name": "mydb", "owner": "postgres", "oid": 100}]

            def get_schemas(self):
                return [{"name": "public", "owner": "postgres", "oid": 2200}]

            def get_sequences(self, schema=None):
                return [{"name": "seq1", "schema": "public", "oid": 500}]

            def get_sequence(self, oid):
                return {"name": "seq1", "schema": "public", "oid": oid}

            def get_views(self, schema=None):
                return [{"name": "v1", "schema": "public", "oid": 600}]

            def get_procedures(self, schema=None):
                return [{"name": "fn1", "schema": "public", "oid": 700}]

        return MockableProvider(cluster=Mock())

    def test_get_tables_returns_list(self, mock_provider):
        """get_tables() returns a list."""
        result = mock_provider.get_tables()
        assert isinstance(result, list)

    def test_get_table_returns_dict_or_none(self, mock_provider):
        """get_table() returns a dict or None."""
        result = mock_provider.get_table(oid=1)
        assert result is None or isinstance(result, dict)

    def test_get_roles_returns_list(self, mock_provider):
        """get_roles() returns a list."""
        result = mock_provider.get_roles()
        assert isinstance(result, list)

    def test_get_role_returns_dict_or_none(self, mock_provider):
        """get_role() returns a dict or None."""
        result = mock_provider.get_role(name="postgres")
        assert result is None or isinstance(result, dict)

    def test_get_databases_returns_list(self, mock_provider):
        """get_databases() returns a list."""
        result = mock_provider.get_databases()
        assert isinstance(result, list)

    def test_get_schemas_returns_list(self, mock_provider):
        """get_schemas() returns a list."""
        result = mock_provider.get_schemas()
        assert isinstance(result, list)

    def test_get_sequences_returns_list(self, mock_provider):
        """get_sequences() returns a list."""
        result = mock_provider.get_sequences()
        assert isinstance(result, list)

    def test_get_views_returns_list(self, mock_provider):
        """get_views() returns a list."""
        result = mock_provider.get_views()
        assert isinstance(result, list)

    def test_get_procedures_returns_list(self, mock_provider):
        """get_procedures() returns a list."""
        result = mock_provider.get_procedures()
        assert isinstance(result, list)

    def test_provider_stores_cluster_reference(self, mock_provider):
        """Provider stores cluster reference for query execution."""
        assert mock_provider.cluster is not None

    def test_provider_is_mockable(self):
        """MetadataProvider can be mocked for unit testing."""
        mock = Mock(spec=MetadataProvider)
        mock.get_tables.return_value = []
        mock.get_roles.return_value = []
        assert mock.get_tables() == []
        assert mock.get_roles() == []
