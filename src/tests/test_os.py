import pytest
from pgmob import os


@pytest.fixture
def shell_env():
    return os.ShellEnv()


def test_shell_join(shell_env):
    assert shell_env.join_path("foo") == "foo"
    assert shell_env.join_path("/foo") == "/foo"
    assert shell_env.join_path("foo/") == "foo"
    assert shell_env.join_path("/foo/") == "/foo"

    assert shell_env.join_path("foo", "bar") == "foo/bar"
    assert shell_env.join_path("foo/", "bar") == "foo/bar"
    assert shell_env.join_path("/foo", "bar") == "/foo/bar"
    assert shell_env.join_path("", "bar") == "bar"
    assert shell_env.join_path("", "/bar") == "/bar"
    assert shell_env.join_path("/foo", "") == "/foo"
    assert shell_env.join_path("/foo/", "") == "/foo"

    assert shell_env.join_path("/foo", "bar", "zar") == "/foo/bar/zar"

    assert shell_env.join_path("gs://foo/", "bar") == "gs://foo/bar"
    assert shell_env.join_path("gs://foo", "bar") == "gs://foo/bar"
    assert shell_env.join_path("gs://foo", "") == "gs://foo"
    assert shell_env.join_path("", "gs://foo") == "gs://foo"
