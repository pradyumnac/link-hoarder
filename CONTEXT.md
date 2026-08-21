# Project context

## Purpose

Link Hoarder stores personal browser bookmarks in SQLite. It provides the same features through a CLI and an HTTP API.

## Scope

The first release provides these features:

- Create, read, update, and delete bookmarks.
- Import native Chromium and Firefox browser profiles.
- Import Netscape bookmark HTML export files.
- Run a FastAPI server with API-key authentication.
- Provide a static Vue web interface.
- Store application data in platform-native directories.
- Run the server with Docker Compose.
- Publish Python packages, container images, and GitHub releases.

The first release does not provide browser synchronization.

## Architecture

The `core` package owns models, storage, imports, configuration, and logging.
The `api` package calls the SQLite repository and import services.
The `cli` package selects a SQLite or HTTP implementation of the core backend interface.

Each Link Hoarder server stores data in SQLite.
SQLModel provides the object-relational mapping layer.

## Glossary

| Term | Meaning |
| --- | --- |
| Bookmark | A stored URL and its user-visible metadata. |
| Browser profile | A native Chrome, Chromium, Edge, or Firefox profile directory. |
| Import | A one-way copy from a browser profile or bookmark export into Link Hoarder. |
| Core | The modules that implement behavior without a CLI or HTTP dependency. |
| CLI backend | The local SQLite or HTTP implementation selected by the CLI. |
| API key | The secret value that authorizes every HTTP request. |
