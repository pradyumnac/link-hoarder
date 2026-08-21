# Link Hoarder

[![PyPI](https://img.shields.io/pypi/v/link-hoarder?style=flat-square)](https://pypi.org/project/link-hoarder/)
[![Python](https://img.shields.io/pypi/pyversions/link-hoarder?style=flat-square)](https://pypi.org/project/link-hoarder/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](#license)
[![GitHub stars](https://img.shields.io/github/stars/pradyumnac/link-hoarder?style=flat-square)](https://github.com/pradyumnac/link-hoarder/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/pradyumnac/link-hoarder?style=flat-square)](https://github.com/pradyumnac/link-hoarder/network/members)

Link Hoarder stores browser bookmarks in SQLite. Use it through the CLI, the versioned HTTP API, or the Vue web interface.

## Highlights

- Manage bookmarks, folders, and tags.
- Search titles, URLs, and tags.
- Import native Chrome, Chromium, Edge, and Firefox profiles through the CLI.
- Import standard bookmark HTML exports through the CLI or web interface.
- Preserve JavaScript bookmarklets and add the `bookmarklet` tag automatically.
- Use the same CLI commands with local SQLite or a remote HTTP API.
- Run a local web stack with automatic API-key provisioning.

## Install

Run the CLI without a permanent installation:

```console
uvx link-hoarder --help
```

Install it as a uv tool:

```console
uv tool install link-hoarder
```

From a source checkout, configure a backend and install local wrapper scripts:

```console
make setup-user
```

The setup task offers local SQLite, a local Docker API, and an existing remote API.
See [Configure the CLI backend](docs/readthedocs/how-to/configure-cli-backend.md).

### Wrapper modes

Use the saved default backend:

```console
li list
li create https://example.com --title Example
```

Force local SQLite for one command:

```console
lilocal list --query reference
```

Force the configured API for one command:

```console
liapi list
liapi import-file /path/to/bookmarks.html
```

Control the local Docker stack:

```console
liserverstart
liserverstatus
liserverstop
```

Wrapper quirks:

- The installer supports Unix-like systems and writes to `~/.local/scripts`.
- Add `~/.local/scripts` to `PATH` when your shell does not include it.
- `li` uses the saved backend. `lilocal` and `liapi` override it for one command.
- `liapi` requires a saved or environment-provided API URL and API key.
- Server wrappers keep the absolute source checkout path. Run setup again after you move the checkout.
- `liserverstop` keeps the Docker data volume.
- Server wrappers do not change the saved CLI backend.

## CLI usage

### Manage bookmarks

```console
link-hoarder create https://example.com --title Example --tag reference
link-hoarder list --query reference
link-hoarder get 1
link-hoarder update 1 --title "Updated example"
link-hoarder delete 1
```

Use repeated `--tag` options to add multiple tags.
The default backend is local SQLite.
Use `link-hoarder --backend api COMMAND` to override the backend for one command.

### Import native profiles

Discover local profiles and import them:

```console
link-hoarder import-browser brave
link-hoarder import-browser chrome
link-hoarder import-browser chromium
link-hoarder import-browser edge
link-hoarder import-browser firefox
link-hoarder import-browser zen
```

Pass an explicit native profile file when automatic discovery is not available:

```console
link-hoarder import-browser brave --profile /path/to/Brave-Browser/Default/Bookmarks
link-hoarder import-browser zen --profile /path/to/places.sqlite
```

### Import an exported file

Brave, Chrome, Chromium, Edge, Firefox, and Zen can export the Netscape bookmark HTML format.

```console
link-hoarder import-file /path/to/bookmarks.html
```

Imports skip existing URLs. The JSON result reports imported, skipped, and invalid entries.

## Web interface

Start the integrated Vue, nginx, API, and SQLite stack:

```console
cp stack/.env.example stack/.env
mise run stack-up
```

Open <http://127.0.0.1:8080>. The stack generates and provisions its API key automatically.
The web interface imports bookmark HTML exports, not native browser profile files.

Stop the stack:

```console
mise run stack-down
```

See the [Docker Compose guide](docs/readthedocs/how-to/run-with-docker.md) for more options and PowerShell commands.

## HTTP API

Set an API key with at least 32 characters, then start the server:

```console
export LINK_HOARDER_API_KEY="replace-this-with-at-least-32-characters"
link-hoarder api
```

Create and list bookmarks:

```console
curl -X POST http://127.0.0.1:8000/api/v1/bookmarks \
  -H "X-API-Key: $LINK_HOARDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","title":"Example","tags":["reference"]}'

curl http://127.0.0.1:8000/api/v1/bookmarks \
  -H "X-API-Key: $LINK_HOARDER_API_KEY"
```

See the [API reference](docs/readthedocs/reference/api.md) and committed [`docs/openapi.json`](docs/openapi.json) contract.

## Documentation

- [Quick start](docs/readthedocs/tutorials/quick-start.md)
- [CLI reference](docs/readthedocs/reference/cli.md)
- [CLI backend guide](docs/readthedocs/how-to/configure-cli-backend.md)
- [Import guide](docs/readthedocs/how-to/import-browser-profiles.md)
- [Configuration reference](docs/readthedocs/reference/configuration.md)
- [Architecture](docs/readthedocs/explanation/architecture.md)

Run `link-hoarder COMMAND --help` for command details. Unix users can also read [`docs/man/link-hoarder.1`](docs/man/link-hoarder.1).

## Development

```console
mise run install
mise run hooks
mise run check
mise run docs-build
```

Use `mise run docs-serve` for a local documentation preview.
See [Publish on Read the Docs](docs/readthedocs/how-to/publish-read-the-docs.md) for hosted builds.
Run `mise tasks` to list all project actions.

## Release

Push a signed `v*` tag. The release workflow publishes to PyPI, GitHub Releases, and GitHub Container Registry.

## License

MIT
