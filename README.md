# Link Hoarder

Link Hoarder manages browser bookmarks through a typed CLI and HTTP API. It stores data in SQLite.

## Install

Run Link Hoarder without a permanent installation:

```console
uvx link-hoarder --help
```

Install the CLI with uv:

```console
uv tool install link-hoarder
```

## Use the CLI

```console
link-hoarder create https://example.com --title Example
link-hoarder list
link-hoarder import-browser firefox
```

Run `link-hoarder COMMAND --help` for command details. Unix users can also read `docs/man/link-hoarder.1`.

## Run the API

Set `LINK_HOARDER_API_KEY`. Then start the server.

```console
link-hoarder api
```

Send the key in the `X-API-Key` header. Open `http://127.0.0.1:8000/docs` for the OpenAPI interface.

## Run the Docker stack

```console
cp stack/.env.example stack/.env
mise run stack-up
```

Open `http://127.0.0.1:8080`. The stack generates and provisions its API key.
See the [Docker guide](docs/readthedocs/how-to/run-with-docker.md) for PowerShell commands.

## Documentation

Start with [the documentation index](docs/readthedocs/index.md).

## Develop

```console
mise run install
mise run hooks
mise run check
```

Run `mise tasks` to list all project actions.

## Release

Push a signed `v*` tag. The release workflow publishes to PyPI, GitHub Releases, and GitHub Container Registry.

## Licence

MIT
