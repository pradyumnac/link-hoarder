# Quick start

This tutorial creates a bookmark and starts the API.

## Install the CLI

```console
uv tool install link-hoarder
```

## Create a bookmark

```console
link-hoarder create https://example.com --title Example
link-hoarder list
```

## Use an API backend

Set an API key before you start the server.

```console
export LINK_HOARDER_API_KEY="replace-this-with-at-least-32-characters"
link-hoarder api
```

On PowerShell, use this command:

```powershell
$env:LINK_HOARDER_API_KEY = "replace-this-with-at-least-32-characters"
link-hoarder api
```

Open another terminal and select the API backend:

```console
export LINK_HOARDER_BACKEND=api
export LINK_HOARDER_API_URL=http://127.0.0.1:8000
export LINK_HOARDER_API_KEY="replace-this-with-at-least-32-characters"
link-hoarder list
```

On PowerShell, set the same three environment variables with `$env:`.
Use the committed `docs/openapi.json` contract to call the API.
