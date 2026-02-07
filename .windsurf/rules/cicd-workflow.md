---
# Kiro: Always include this file
inclusion: always

# Windsurf: Apply to CI/CD and build files
applies_to:
  - ".github/**/*"
  - "Dockerfile"
  - "pyproject.toml"
  - ".devcontainer/**/*"

# GitHub Copilot: Apply to CI/CD and build files
applyTo:
  - ".github/**/*"
  - "Dockerfile"
  - "pyproject.toml"
  - ".devcontainer/**/*"
---

# CI/CD Workflow Guidelines for PGMob

## Build System

### UV Package Manager
- Use UV for all dependency management
- UV is faster and more reliable than Poetry
- Lock file: `uv.lock`
- Configuration: `pyproject.toml`

### Installation Commands
```bash
# Install all dependencies with extras
uv sync --all-extras

# Install specific extras
uv sync --extra psycopg2-binary --extra dev

# Update dependencies
uv sync --upgrade

# Add new dependency
uv add package-name

# Add dev dependency
uv add --dev package-name
```

## Testing

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=pgmob --cov-report=html --cov-report=term

# Run specific markers
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m "not slow"

# Run with verbose output
uv run pytest -vv

# Run specific test file
uv run pytest src/tests/test_cluster.py

# Run specific test function
uv run pytest src/tests/test_cluster.py::test_cluster_init
```

### Test Markers
- `unit`: Unit tests (fast, no external dependencies)
- `integration`: Integration tests (require PostgreSQL)
- `slow`: Slow tests (may take several seconds)
- `asyncio`: Async tests

### Coverage Requirements
- Overall coverage: >90%
- New code: 100%
- Critical paths: 100%

## Code Quality

### Formatting with Ruff
```bash
# Format all code
uv run ruff format .

# Check formatting without changes
uv run ruff format --check .

# Format specific file
uv run ruff format src/pgmob/cluster.py
```

### Linting with Ruff
```bash
# Lint and auto-fix
uv run ruff check --fix .

# Lint without fixes
uv run ruff check .

# Lint specific file
uv run ruff check src/pgmob/cluster.py
```

### Type Checking with ty
```bash
# Type check entire package
uv run ty check src/pgmob

# Type check specific file
uv run ty check src/pgmob/cluster.py

# Watch mode (for development)
uv run ty watch src/pgmob
```

## Docker Builds

### Main Dockerfile
- Uses UV for dependency installation
- Base image: `python:3.10-bullseye`
- Build args:
  - `PYTHON_VERSION`: Python version (default: 3.10-bullseye)
  - `UV_EXTRAS`: Extras to install (default: psycopg2-binary)

### Building Docker Image
```bash
# Build with defaults
docker build -t pgmob .

# Build with specific Python version
docker build -t pgmob --build-arg PYTHON_VERSION=3.11-bullseye .

# Build with specific extras
docker build -t pgmob --build-arg UV_EXTRAS=psycopg2 .
```

### Running Tests in Docker
```bash
# Run tests
docker run --rm pgmob uv run pytest

# Run with coverage
docker run --rm pgmob uv run pytest --cov=pgmob

# Run ty
docker run --rm pgmob uv run ty check src/pgmob
```

## GitHub Actions

### CI Workflow
- Location: `.github/workflows/CI.yaml`
- Triggers: Push (except docs), Pull requests to main
- Uses custom action: `.github/actions/test`

### Test Action
- Location: `.github/actions/test/action.yaml`
- Inputs:
  - `PYTHON_VERSION`: Python version (default: 3.9)
  - `UV_EXTRAS`: Extras to install (default: psycopg2-binary)
  - `POSTGRES_VERSION`: PostgreSQL version (default: 12)
  - `CONTAINER_NETWORK`: Docker network (default: pgmob-network)

### Running CI Locally
```bash
# Build test container
docker build . -t pgmobtest

# Run ty
docker run --rm pgmobtest uv run ty check src/pgmob

# Run pytest
docker network create pgmob-network || true
docker run --rm --network pgmob-network \
  -e PGMOB_IMAGE=postgres:12 \
  -e PGMOB_CONTAINER_NETWORK=pgmob-network \
  -v /var/run/docker.sock:/var/run/docker.sock \
  pgmobtest uv run pytest -vv
```

## Pre-commit Checks

### Before Committing
```bash
# Format code
uv run ruff format .

# Fix linting issues
uv run ruff check --fix .

# Run type checks
uv run ty check src/pgmob

# Run unit tests
uv run pytest -m unit

# Run all tests (if time permits)
uv run pytest
```

### Recommended Git Hooks
Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
set -e

echo "Running pre-commit checks..."

# Format check
echo "Checking formatting..."
uv run ruff format --check .

# Lint check
echo "Checking linting..."
uv run ruff check .

# Type check
echo "Checking types..."
uv run ty check src/pgmob

# Unit tests
echo "Running unit tests..."
uv run pytest -m unit

echo "All checks passed!"
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

## Release Process

### Version Bumping
- Version is in `pyproject.toml` under `[project]` section
- Follow semantic versioning: MAJOR.MINOR.PATCH
- Development versions: `0.2.0-dev`
- Release versions: `0.2.0`

### Release Checklist
1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` (if exists)
3. Run full test suite: `uv run pytest`
4. Run type checks: `uv run ty check src/pgmob`
5. Format and lint: `uv run ruff format . && uv run ruff check --fix .`
6. Build package: `uv build`
7. Test package installation: `uv pip install dist/pgmob-*.whl`
8. Create git tag: `git tag v0.2.0`
9. Push tag: `git push origin v0.2.0`
10. Publish to PyPI: `uv publish`

## Continuous Integration Best Practices

### Fast Feedback
- Run unit tests first (fast)
- Run integration tests after (slower)
- Run slow tests last or in parallel

### Caching
- Cache UV dependencies in CI
- Cache Docker layers when possible
- Cache test databases between runs

### Matrix Testing
Test against multiple versions:
- Python: 3.9, 3.10, 3.11, 3.12
- PostgreSQL: 10, 11, 12, 13, 14, 15, 16

### Fail Fast
- Stop on first failure in CI
- Use `pytest -x` to stop on first test failure
- Use `pytest --maxfail=3` to stop after 3 failures

## Troubleshooting CI

### Common Issues

#### UV Not Found
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

#### Lock File Out of Sync
```bash
# Regenerate lock file
uv lock --upgrade
```

#### Test Failures in Docker
```bash
# Check Docker network
docker network ls
docker network inspect pgmob-network

# Check PostgreSQL container
docker ps -a
docker logs <postgres-container-id>
```

#### Permission Issues
```bash
# Fix file permissions
chmod -R u+w .
chown -R $USER:$USER .
```

## Environment Variables

### Testing
- `PGMOB_IMAGE`: PostgreSQL Docker image (default: postgres:12)
- `PGMOB_CONTAINER_NETWORK`: Docker network name
- `PGHOST`: PostgreSQL host
- `PGPORT`: PostgreSQL port
- `PGUSER`: PostgreSQL user
- `PGPASSWORD`: PostgreSQL password
- `PGDATABASE`: PostgreSQL database

### CI/CD
- `UV_CACHE_DIR`: UV cache directory
- `PYTHONPATH`: Python path for imports
- `CI`: Set to `true` in CI environment

## Performance Optimization

### Parallel Testing
```bash
# Install pytest-xdist
uv add --dev pytest-xdist

# Run tests in parallel
uv run pytest -n auto
```

### Test Selection
```bash
# Run only changed tests
uv run pytest --lf  # Last failed
uv run pytest --ff  # Failed first

# Run tests matching pattern
uv run pytest -k "test_cluster"
```

### Docker Build Optimization
```dockerfile
# Use build cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --extra psycopg2-binary --extra dev
```

## Documentation

### Building Docs
```bash
# Install docs dependencies
cd docs
uv sync

# Build HTML docs
uv run make html

# View docs
open _build/html/index.html
```

### Docs Testing
```bash
# Test code examples in docs
uv run pytest --doctest-modules src/pgmob
```
