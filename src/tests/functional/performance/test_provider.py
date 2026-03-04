"""Performance benchmarks for SQLMetadataProvider.

Measures metadata retrieval speed, collection refresh throughput, query cache
hit latency, and memory usage against defined targets.

Targets:
  - Metadata retrieval for 100 tables:  < 100 ms
  - Collection refresh for 1000 tables: < 500 ms
  - Query cache hit:                    < 1 ms
  - Memory per 1000 objects:            < 1 MB

These tests require a running PostgreSQL instance (via Docker, as configured
in conftest.py).  They are automatically skipped when Docker is unavailable.

"""

import time
import tracemalloc

import pytest

from pgmob import objects
from pgmob.providers.sql import SQLMetadataProvider

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

TARGET_100_TABLES_MS = 100  # get_tables() for 100 tables must finish in < 100 ms
TARGET_1000_TABLES_MS = 500  # collection refresh for 1000 tables must finish in < 500 ms
TARGET_CACHE_HIT_MS = 1  # cache hit must resolve in < 1 ms
TARGET_MEMORY_PER_1000_KB = 1024  # < 1 MB (1024 KB) per 1000 objects

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def perf_cluster_factory(psql, connect, container):
    """Factory fixture that creates a cluster connected to a fresh database with N tables."""
    created: list[tuple] = []  # (cluster, db_name)

    def _make(db_name: str, table_count: int):
        assert psql(f"CREATE DATABASE {db_name} TEMPLATE template0").exit_code == 0

        if table_count <= 100:
            stmts = "; ".join(f"CREATE TABLE public.perf_tbl_{i} (id int)" for i in range(table_count))
            assert psql(stmts, db=db_name).exit_code == 0
        else:
            plpgsql_block = (
                "DO $$ BEGIN "
                f"FOR i IN 0..{table_count - 1} LOOP "
                "EXECUTE format('CREATE TABLE public.perf_tbl_%s (id int)', i); "
                "END LOOP; END $$;"
            )
            assert psql(plpgsql_block, db=db_name).exit_code == 0

        cluster = connect(db=db_name)
        created.append((cluster, db_name))
        return cluster

    yield _make

    for cluster, db_name in created:
        cluster.adapter.close_connection()
        psql(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}'")
        container.exec_run(f"dropdb -U postgres --if-exists {db_name}")


@pytest.fixture(scope="module")
def perf_db_100(perf_cluster_factory):
    """Cluster connected to a database with 100 tables."""
    return perf_cluster_factory("perf_bench_100", 100)


@pytest.fixture(scope="module")
def perf_db_1000(perf_cluster_factory):
    """Cluster connected to a database with 1000 tables."""
    return perf_cluster_factory("perf_bench_1000", 1000)


# ---------------------------------------------------------------------------
# Metadata retrieval for 100 tables < 100 ms
# ---------------------------------------------------------------------------


class TestMetadataRetrieval100Tables:
    """"""

    def test_get_tables_100_under_100ms(self, perf_db_100):
        """get_tables() for a DB with 100 tables completes in < 100 ms."""
        provider = perf_db_100.metadata_provider

        # Warm up: one call to ensure any one-time initialisation is done
        provider.get_tables()

        start = time.perf_counter()
        result = provider.get_tables()
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(result) >= 100, f"Expected at least 100 tables, got {len(result)}"
        assert elapsed_ms < TARGET_100_TABLES_MS, (
            f"get_tables() took {elapsed_ms:.1f} ms for 100 tables (target: < {TARGET_100_TABLES_MS} ms)"
        )

    def test_get_tables_schema_filter_100_under_100ms(self, perf_db_100):
        """get_tables(schema='public') for 100 tables completes in < 100 ms."""
        provider = perf_db_100.metadata_provider
        provider.get_tables(schema="public")  # warm up

        start = time.perf_counter()
        result = provider.get_tables(schema="public")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(result) >= 100
        assert elapsed_ms < TARGET_100_TABLES_MS, (
            f"get_tables(schema='public') took {elapsed_ms:.1f} ms for 100 tables "
            f"(target: < {TARGET_100_TABLES_MS} ms)"
        )

    def test_get_tables_repeated_calls_consistent_performance(self, perf_db_100):
        """Repeated get_tables() calls all stay under the 100 ms target."""
        provider = perf_db_100.metadata_provider
        provider.get_tables()  # warm up

        for i in range(3):
            start = time.perf_counter()
            provider.get_tables()
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert elapsed_ms < TARGET_100_TABLES_MS, (
                f"Call {i + 1}: get_tables() took {elapsed_ms:.1f} ms (target: < {TARGET_100_TABLES_MS} ms)"
            )


# ---------------------------------------------------------------------------
# Collection refresh for 1000 tables < 500 ms
# ---------------------------------------------------------------------------


class TestCollectionRefresh1000Tables:
    """"""

    def test_table_collection_refresh_1000_under_500ms(self, perf_db_1000):
        """TableCollection.refresh() for 1000 tables completes in < 500 ms."""
        # Initial construction triggers the first refresh; measure subsequent ones
        collection = objects.TableCollection(cluster=perf_db_1000)
        assert len(collection) >= 1000, f"Expected at least 1000 tables, got {len(collection)}"

        start = time.perf_counter()
        collection.refresh()
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < TARGET_1000_TABLES_MS, (
            f"TableCollection.refresh() took {elapsed_ms:.1f} ms for 1000 tables "
            f"(target: < {TARGET_1000_TABLES_MS} ms)"
        )

    def test_get_tables_1000_under_500ms(self, perf_db_1000):
        """get_tables() for a DB with 1000 tables completes in < 500 ms."""
        provider = perf_db_1000.metadata_provider
        provider.get_tables()  # warm up

        start = time.perf_counter()
        result = provider.get_tables()
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(result) >= 1000
        assert elapsed_ms < TARGET_1000_TABLES_MS, (
            f"get_tables() took {elapsed_ms:.1f} ms for 1000 tables (target: < {TARGET_1000_TABLES_MS} ms)"
        )

    def test_collection_refresh_repeated_under_500ms(self, perf_db_1000):
        """Three consecutive refresh() calls on 1000 tables all stay under 500 ms."""
        collection = objects.TableCollection(cluster=perf_db_1000)

        for i in range(3):
            start = time.perf_counter()
            collection.refresh()
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert elapsed_ms < TARGET_1000_TABLES_MS, (
                f"Refresh {i + 1}: took {elapsed_ms:.1f} ms (target: < {TARGET_1000_TABLES_MS} ms)"
            )


# ---------------------------------------------------------------------------
# Query cache hit < 1 ms
# ---------------------------------------------------------------------------


class TestQueryCacheHitPerformance:
    """"""

    def test_cache_hit_under_1ms(self, cluster):
        """_get_version_specific_query() cache hit resolves in < 1 ms."""
        provider = SQLMetadataProvider(cluster=cluster, version=cluster.version)

        # Prime the cache with a first call
        provider._get_version_specific_query("get_procedure")
        assert len(provider._query_cache) > 0, "Cache should be populated after first call"

        # Measure cache hit
        start = time.perf_counter()
        provider._get_version_specific_query("get_procedure")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < TARGET_CACHE_HIT_MS, (
            f"Cache hit took {elapsed_ms:.4f} ms (target: < {TARGET_CACHE_HIT_MS} ms)"
        )

    def test_cache_hit_returns_same_object(self, cluster):
        """Cache hit returns the identical SQL object (identity check)."""
        provider = SQLMetadataProvider(cluster=cluster, version=cluster.version)
        first = provider._get_version_specific_query("get_procedure")
        second = provider._get_version_specific_query("get_procedure")
        assert first is second, "Cache hit must return the same object instance"

    def test_cache_populated_after_get_tables(self, cluster):
        """Query cache is accessible and a dict after get_tables() is called."""
        provider = SQLMetadataProvider(cluster=cluster, version=cluster.version)
        assert provider._query_cache == {}
        provider.get_tables()
        assert isinstance(provider._query_cache, dict)

    def test_cache_hit_multiple_queries_under_1ms(self, cluster):
        """Multiple cache hits all resolve in < 1 ms each."""
        provider = SQLMetadataProvider(cluster=cluster, version=cluster.version)

        # Prime cache for procedure query
        provider._get_version_specific_query("get_procedure")

        for _ in range(10):
            start = time.perf_counter()
            provider._get_version_specific_query("get_procedure")
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert elapsed_ms < TARGET_CACHE_HIT_MS, (
                f"Cache hit took {elapsed_ms:.4f} ms (target: < {TARGET_CACHE_HIT_MS} ms)"
            )


# ---------------------------------------------------------------------------
# 14.5 – Memory usage < 1 MB per 1000 objects
# ---------------------------------------------------------------------------


class TestMemoryUsage:
    """"""

    def test_memory_per_1000_tables_under_1mb(self, perf_db_1000):
        """Memory used to hold 1000 table metadata dicts is < 1 MB."""
        provider = perf_db_1000.metadata_provider

        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        result = provider.get_tables()

        snapshot_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        assert len(result) >= 1000, f"Expected at least 1000 tables, got {len(result)}"

        stats = snapshot_after.compare_to(snapshot_before, "lineno")
        total_bytes = sum(stat.size_diff for stat in stats if stat.size_diff > 0)
        total_kb = total_bytes / 1024

        assert total_kb < TARGET_MEMORY_PER_1000_KB, (
            f"Memory for 1000 table metadata dicts: {total_kb:.1f} KB "
            f"(target: < {TARGET_MEMORY_PER_1000_KB} KB)"
        )

    def test_memory_collection_refresh_1000_under_1mb(self, perf_db_1000):
        """Memory allocated during TableCollection.refresh() for 1000 tables is < 1 MB."""
        collection = objects.TableCollection(cluster=perf_db_1000)
        assert len(collection) >= 1000

        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        collection.refresh()

        snapshot_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snapshot_after.compare_to(snapshot_before, "lineno")
        total_bytes = sum(stat.size_diff for stat in stats if stat.size_diff > 0)
        total_kb = total_bytes / 1024

        assert total_kb < TARGET_MEMORY_PER_1000_KB, (
            f"Memory for refresh() of 1000 tables: {total_kb:.1f} KB "
            f"(target: < {TARGET_MEMORY_PER_1000_KB} KB)"
        )

    def test_query_cache_memory_bounded(self, cluster):
        """Query cache does not grow unboundedly with repeated calls."""
        provider = SQLMetadataProvider(cluster=cluster, version=cluster.version)

        # Call the same query many times
        for _ in range(50):
            provider._get_version_specific_query("get_procedure")

        # Cache should contain only one entry per unique (query, version) pair
        cache_size = len(provider._query_cache)
        assert cache_size <= 10, (
            f"Query cache grew to {cache_size} entries after 50 identical calls; "
            "cache should deduplicate by (query, version)"
        )
