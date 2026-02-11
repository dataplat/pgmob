# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-02-10

### Changed

- **Internal Refactoring**: Introduced mixin-based architecture to eliminate code duplication
  - Created reusable mixin classes for common properties (name, owner, schema, tablespace)
  - Refactored 8 object classes (Table, View, Sequence, Database, Schema, Role, Procedure/Function/Aggregate/WindowFunction, LargeObject) to use mixins
  - Reduced code duplication by 30-40% across object types
  - Improved maintainability - common property changes now only need to be made in one place
  - Enhanced type safety with proper type hints on all mixin properties
  - Full backward compatibility maintained - no API changes

## [0.3.0] - 2026-02-06

### Breaking Changes

- **Python 3.13 Required**: Minimum Python version upgraded from 3.9 to 3.13
  - Python 3.9, 3.10, 3.11, and 3.12 are no longer supported
  - This change enables the use of modern Python features and performance improvements

### Added

- Support for Python 3.13 features and performance improvements
- Modern type annotation syntax using PEP 604 (union operator `|`) and PEP 585 (built-in generics)
- Enhanced type safety with refined type hints throughout the codebase
- Improved developer experience with better error messages and REPL features from Python 3.13

### Changed

- **Type Annotations Modernized**: All type annotations now use modern Python 3.10+ syntax
  - `Union[X, Y]` replaced with `X | Y` syntax
  - `Optional[X]` replaced with `X | None` syntax
  - `List`, `Dict`, `Set`, `Tuple` from typing module replaced with built-in `list`, `dict`, `set`, `tuple`
  - Removed legacy typing imports (List, Dict, Optional, Union)
- **Dependency Versions Updated**: All dependencies locked to latest stable releases
  - `packaging` updated to >=26.0 (from >=21.3)
  - `psycopg2` updated to >=2.9.11,<3 (from >=2.9.5,<3)
  - `pytest` updated to >=9.0.0 (from >=7.1.1)
  - `pytest-cov` updated to >=7.0.0 (from >=3.0.0)
  - `pytest-mock` updated to >=3.15.0 (from >=3.7.0)
  - `pytest-asyncio` updated to >=1.3.0 (from >=0.21.0)
  - `docker` updated to >=7.1.0 (from >=6.0.0)
  - `ruff` updated to >=0.15.0 (from >=0.1.0)
- **Code Quality Improvements**:
  - Removed UP006 and UP035 from ruff ignore list (legacy type annotation rules)
  - Refined type: ignore comments with specific error codes
  - Minimized type suppressions where possible

### Removed

- Support for Python 3.9, 3.10, 3.11, and 3.12
- Legacy typing imports (List, Dict, Set, Tuple, Optional, Union) from codebase

### Documentation

- Updated README.md to specify Python 3.13 requirement
- Updated CONTRIBUTING.md with Python 3.13 development setup instructions
- Added migration guide for users upgrading from 0.2.x

---

## [0.2.0-dev] - Previous Development Version

Previous development version supporting Python 3.9+.

