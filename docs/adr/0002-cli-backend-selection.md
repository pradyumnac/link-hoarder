# 0002 — CLI backend selection

## Status

accepted

## Implemented

done

## Context

The CLI must work with a local SQLite database or an HTTP API. Users need one command set for both backends.

Users must select a backend with a global option, an environment variable, or saved configuration.
Local setup must also support a Docker Compose API server.

## Decision

Define a typed bookmark backend interface for the CLI and import services.
Implement the interface with SQLite and a synchronous HTTP client.

Use this configuration precedence, from highest to lowest:

1. The global `--backend` option.
2. `LINK_HOARDER_BACKEND` and other environment variables.
3. The saved user configuration.
4. The local SQLite backend.

Store user configuration in the platform configuration directory.
Store the file with user-only permissions where the platform supports them.

Provide an interactive local setup task.
Let the user select local SQLite, a local Docker Compose API, or an existing remote API.

Install short wrapper scripts in `~/.local/scripts`. Use names that start with `li` and contain no hyphens.

## Consequences

The CLI command behavior and JSON output stay consistent across both backends.
Native browser imports read local files and send each parsed bookmark through the selected backend.

API mode requires a reachable server URL and an API key. HTTP failures become stable CLI errors instead of Python tracebacks.

Saved API keys exist as local secrets. The installer must restrict file permissions and must not print API keys.

The Docker wrappers depend on the project checkout and Docker Compose.
The wrapper installer is for Unix-like systems because Windows does not use `~/.local/scripts`.

## Alternatives considered

- **Separate local and API commands** — This option duplicates the command surface and makes scripts harder to reuse.
- **API-only CLI** — This option requires a server for simple local use.
- **SQLite-only CLI** — This option cannot manage a remote Link Hoarder instance.
- **Background API process** — This option has weaker lifecycle management than the existing Docker Compose stack.
- **System user service** — This option does not provide one setup path for Linux and Windows.

## Changelog

None.
