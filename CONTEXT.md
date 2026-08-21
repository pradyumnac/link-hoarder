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
The `cli` and `api` packages call the core interfaces.

SQLite is the only storage backend.
SQLModel provides the object-relational mapping layer.

## Glossary

| Term | Meaning |
| --- | --- |
| Bookmark | A stored URL and its user-visible metadata. |
| Browser profile | A native Chrome, Chromium, Edge, or Firefox profile directory. |
| Import | A one-way copy from a browser profile or bookmark export into Link Hoarder. |
| Core | The modules that implement behavior without a CLI or HTTP dependency. |
| API key | The secret value that authorizes every HTTP request. |
