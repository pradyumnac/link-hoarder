# 0001 — Application architecture

## Status

accepted

## Implemented

not-started

## Context

The application must expose the same bookmark features through a CLI and an HTTP API. It must run on Windows and Linux.

## Decision

Use a core package for models, configuration, storage, browser imports, and logging.
Keep Typer and FastAPI in separate interface packages.

Use SQLModel with SQLite. Validate boundary values with Pydantic models. Require one API key for all HTTP requests.

Use platform-native data paths. Support native Chromium and Firefox profiles in the first release.

## Consequences

The CLI and API share one behavior layer. SQLite keeps deployment small but does not support concurrent multi-host writes.

Native browser imports require local file access. The API can import only profiles visible inside its host or container.

## Alternatives considered

- **SQLAlchemy with separate models** — This option gives more control but adds mapping code.
- **Exported bookmark files** — These files are portable but are outside the first release scope.

## Changelog

None.
