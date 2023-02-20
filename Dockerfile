ARG PYTHON_VERSION=3.10-bullseye
FROM python:$PYTHON_VERSION
ARG POETRY_VERSION=1.3.2
ARG POETRY_EXTRAS=psycopg2

WORKDIR /opt/pgmob

RUN pip install poetry==$POETRY_VERSION
RUN poetry config virtualenvs.create false

COPY ./src ./src/
COPY poetry.lock .
COPY pyproject.toml .
COPY *.md .

RUN poetry install -E $POETRY_EXTRAS
