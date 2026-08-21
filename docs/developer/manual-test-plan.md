# Manual test plan

Run these checks after you build a local package.

## 1. Use the source checkout

Set a temporary database path. This keeps the test data separate from your normal data.

Linux or macOS:

```console
export LINK_HOARDER_DATABASE_PATH="$PWD/.manual-test.db"
uv run link-hoarder --help
```

Windows PowerShell:

```powershell
$env:LINK_HOARDER_DATABASE_PATH = "$PWD\.manual-test.db"
uv run link-hoarder --help
```

Confirm that help lists `create`, `list`, `get`, `update`, `delete`, `import-browser`, `import-file`, and `api`.

## 2. Test CLI CRUD

```console
uv run link-hoarder create https://example.com --title Example --tag test
uv run link-hoarder list
uv run link-hoarder get 1
uv run link-hoarder update 1 --title Updated
uv run link-hoarder list --query Updated
uv run link-hoarder delete 1
uv run link-hoarder get 1
```

Expected results:

- `create` prints one bookmark with an identifier.
- `list` shows the bookmark.
- `update` changes the title.
- `delete` succeeds.
- The final `get` returns a not-found error.

## 3. Test browser import

Close the browser before you import its profile.

Use an explicit profile file when you do not want to change the real profile:

```console
uv run link-hoarder import-browser brave --profile /path/to/Bookmarks
uv run link-hoarder import-browser chrome --profile /path/to/Bookmarks
uv run link-hoarder import-browser firefox --profile /path/to/places.sqlite
uv run link-hoarder import-browser zen --profile /path/to/places.sqlite
```

Import a Netscape bookmark HTML export:

```console
uv run link-hoarder import-file /path/to/bookmarks.html
```

Run each import command a second time. The second run must report skipped URLs.

## 4. Test the API

Set an API key and use a separate database.

Linux or macOS:

```console
export LINK_HOARDER_API_KEY=test-secret-with-at-least-32-characters
export LINK_HOARDER_DATABASE_PATH="$PWD/.manual-api.db"
uv run link-hoarder api
```

Windows PowerShell:

```powershell
$env:LINK_HOARDER_API_KEY = "test-secret-with-at-least-32-characters"
$env:LINK_HOARDER_DATABASE_PATH = "$PWD\.manual-api.db"
uv run link-hoarder api
```

Use `docs/openapi.json` with an HTTP client.

Test these cases:

1. Call `/health` without a key. Confirm HTTP 401.
2. Send the key in `X-API-Key`. Confirm HTTP 200.
3. Create a bookmark with `/api/v1/bookmarks`.
4. List, update, and delete the bookmark.
5. Upload an invalid bookmark HTML export. Confirm a structured import warning.
6. Confirm that `/docs` and `/openapi.json` return HTTP 404.

## 5. Test responsive browser layouts

Start the web interface and use browser responsive-design tools.

Test these viewport widths:

1. Use 3840 px to confirm the 4K layout uses the available width.
2. Use 1920 px to confirm the wide desktop layout.
3. Use 1080 px to confirm the standard desktop layout.
4. Use 760 px to confirm the tablet layout.
5. Use 320 px to confirm the minimum mobile layout.
6. Change between the five widths while the import controls are open.

Confirm that forms, bookmark cards, notifications, and pagination stay in the viewport.
Confirm that wide layouts show more bookmark cards without excessive empty margins.
Confirm that text lines remain readable on wide layouts.
Confirm that all controls remain visible and usable.
Confirm that the page does not have horizontal scrolling.

## 6. Build the package

```console
uv build
```

Confirm that `dist/` contains a wheel and a source distribution. Git ignores both files.

## 7. Install and test the wheel

Install the local wheel into the project virtual environment:

```console
mise run install-local
```

The task uses `uv pip install --python .venv`. It does not install a uv tool or
write to a user-level tool directory.

Test the installed command through the project virtual environment:

```console
uv run link-hoarder --help
```

Set `LINK_HOARDER_DATABASE_PATH` to a temporary path and repeat the CLI CRUD test.

Confirm the package is in the project virtual environment:

```console
uv pip show --python .venv link-hoarder
```

## 8. Remove test data

Linux or macOS:

```console
rm -f .manual-test.db .manual-api.db
```

Windows PowerShell:

```powershell
Remove-Item .manual-test.db, .manual-api.db -ErrorAction SilentlyContinue
```

## Test data location

The default database path uses `platformdirs`:

| Platform | Default path |
| --- | --- |
| Linux | `~/.local/share/link-hoarder/bookmarks.db` |
| Windows | `%LOCALAPPDATA%\link-hoarder\bookmarks.db` |

Override the path with `LINK_HOARDER_DATABASE_PATH`.
The application creates the parent directory when it initializes the database.
