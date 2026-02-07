# Contributing

This module is very much work-in-progress, and if you see a potential improvement, feel free to submit your code!

## Requirements

**Python 3.13 or higher** is required for development.

## Support questions

Use one of the following options:

* #pgmob channel of the [PostgreSQL Slack](https://postgresteam.slack.com/).
* New GitHub issue. Add a thorough description of what you want to achieve and the code that you're using.

## Contributing Opportunities

Please check out the GitHub issues for the ideas to work on. If you want to implement a feature that has not been
created yet, create a new issue and assign it to yourself. It is expected to wait for a comment from one of the
maintainers before starting your work on the contribution.

## Style guide

Baseline for all contributions:
* Each public method/function/class should have docstrings, in accordance with [Google Python style guide](http://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings). Docstrings should exist for any public class, method or function, and should include:
    * General description
    * Args: typed arguments and their descriptions
    * Attributes: for public classes
    * Returns: return type and description
    * Example: how to use and expected output
* Code formatter: `ruff format`. All submitted code should be formatted with Ruff using the settings in `pyproject.toml`
* Linter: `ruff check`. Code should pass all Ruff linting checks.
* Type checker: `ty check`. The code should have necessary typing hints for any code in `src/pgmob`.
    * Lists, Dicts or any Generic types should specify the member type in all cases.
    * Use `Union` or a parent class when multiple types are involved.
    * Try to avoid using `Any` at all costs.
* VSCode recommended plugins:
    * Python
    * Pylance
    * Ruff
    * ty
    * Dev Containers

## Tests

Tests are designed to use a `pytest` framework and consist of two separate varieties:

* Unittests `src/tests`: validates all the API surface without connecting to PostgreSQL.
* Functional tests `src/tests/functional`: validates the most common use cases and baseline functionality by interacting with a PostgreSQL container.
    * The PostgreSQL container is spawned at the beginning of the execution and is destroyed once the tests are done.
    * Docker environment should be properly configured for the tests to work, for example, the `DOCKER_HOST` variable if Docker Server is not hosted locally.
    * All the examples in the docstrings are expected to be tested via doctest as a part of the corresponding functional test.

Use the following guidelines when writing tests:

* A separate file should be created for each corresponding module.
* A combination of unittests and functional tests is expected to exist for each module.
* Use `pytest` fixtures whenever you see an opportunity for code reuse.
* Make sure your test fails without your contribution.

### Executing the tests

```shell

# Install dependencies and run tests
$ uv sync --all-extras
$ uv run pytest
```

## Building the docs

Build the docs in the docs directory using Sphinx.

```shell
$ cd docs
$ uv sync
$ uv run make html
```

Open _build/html/index.html in your browser to view the docs.
