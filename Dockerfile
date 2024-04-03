FROM python:3.9
ENV INSIDE_DOCKER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.2.2 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYSETUP_PATH="/opt/pysetup"
RUN apt-get update && apt-get install -y \
    binutils gdal-bin libproj-dev git npm \
    libpoppler-cpp-dev postgresql-client \
    && rm -rf /var/lib/apt/lists/*
RUN curl -sSL https://install.python-poetry.org | python -
ENV PATH="/root/.local/bin:$PATH"
WORKDIR $PYSETUP_PATH
COPY poetry.lock pyproject.toml ./
RUN poetry install --no-root
# Not needed (mapping handled by docker-compose)
# WORKDIR /app
# COPY . .
#RUN ./manage.py collectstatic --no-input
ARG BUILD_COMMIT
LABEL revision=$BUILD_COMMIT
WORKDIR /workspaces/caps
COPY . .
