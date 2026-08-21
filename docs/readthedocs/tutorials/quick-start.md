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

## Start the API

Set an API key before you start the server.

```console
export LINK_HOARDER_API_KEY="replace-this-secret"
link-hoarder api
```

On PowerShell, use this command:

```powershell
$env:LINK_HOARDER_API_KEY = "replace-this-secret"
link-hoarder api
```

Open `http://127.0.0.1:8000/docs`. Select **Authorize** and enter the API key.
