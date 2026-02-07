ARG PYTHON_VERSION=3.13-bookworm
FROM python:$PYTHON_VERSION
ARG UV_EXTRAS=psycopg2-binary

WORKDIR /opt/pgmob

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY ./src ./src/
COPY uv.lock .
COPY pyproject.toml .
COPY *.md ./

# Install dependencies with UV
RUN uv sync --extra $UV_EXTRAS --extra dev --no-dev
