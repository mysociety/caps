FROM python:3.9.7 as base
COPY ./requirements.txt ./requirements.dev.txt /
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get -qq update && \
    apt-get install -qq -y libpoppler-cpp-dev
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.dev.txt

FROM python:3.9.7-slim
RUN apt-get -qq update && \
    apt-get install -qq libpoppler-cpp-dev && \
    apt-get install -qq libpq5 && \
    apt-get install -qq git postgresql-client
WORKDIR /workspaces/caps/
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN pip install --upgrade pip
COPY --from=base /wheels /wheels
COPY --from=base requirements.txt requirements.dev.txt ./
RUN pip install --no-cache-dir /wheels/*
ARG BUILD_COMMIT
LABEL revision=$BUILD_COMMIT
COPY . .
