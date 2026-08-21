FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    LINK_HOARDER_HOST=0.0.0.0 \
    LINK_HOARDER_DATABASE_PATH=/data/bookmarks.db

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8000

CMD ["uv", "run", "--no-sync", "link-hoarder", "api", "--host", "0.0.0.0"]
