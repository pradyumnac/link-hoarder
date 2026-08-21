# Configure the CLI backend

Use the same CLI commands with local SQLite or a Link Hoarder API.

## Run interactive setup

Run this command from a source checkout:

```console
make setup-user
```

Select one setup mode:

- Local SQLite.
- Local Docker API.
- Existing remote API.

Local Docker API setup creates `stack/.env` and starts Docker Compose.
Remote API setup asks for the server root URL and API key.
Setup also installs local wrapper scripts.
See the [README wrapper modes](https://github.com/pradyumnac/link-hoarder#wrapper-modes) for commands and constraints.

Native profile imports always read files on the CLI host.
In API mode, the CLI sends each parsed bookmark to the configured server.

## Override the saved backend

Use a global option before the command:

```console
link-hoarder --backend local list
link-hoarder --backend api list
```

You can also set environment variables:

```console
export LINK_HOARDER_BACKEND=api
export LINK_HOARDER_API_URL=https://links.example.com
export LINK_HOARDER_API_KEY=replace-this-with-at-least-32-characters
link-hoarder list
```

Do not add `/api/v1` to `LINK_HOARDER_API_URL`.

Run this command to inspect saved configuration without showing the API key:

```console
link-hoarder config
```

See the [configuration reference](../reference/configuration.md) for precedence and all variables.
