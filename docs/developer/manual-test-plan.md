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

Confirm that help lists `create`, `list`, `get`, `update`, `delete`, `import-browser`, and `api`.

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
uv run link-hoarder import-browser chrome --profile /path/to/Bookmarks
uv run link-hoarder import-browser firefox --profile /path/to/places.sqlite
```

Run the import command a second time. The second run must report skipped URLs.

## 4. Test the API

Set an API key and use a separate database.

Linux or macOS:

```console
export LINK_HOARDER_API_KEY=test-secret
export LINK_HOARDER_DATABASE_PATH="$PWD/.manual-api.db"
uv run link-hoarder api
```

Windows PowerShell:

```powershell
$env:LINK_HOARDER_API_KEY = "test-secret"
$env:LINK_HOARDER_DATABASE_PATH = "$PWD\.manual-api.db"
uv run link-hoarder api
```

Open `http://127.0.0.1:8000/docs`.

Test these cases in Swagger UI:

1. Call `/health` without a key. Confirm HTTP 401.
2. Authorize with `test-secret`.
3. Create a bookmark with `/bookmarks`.
4. List, update, and delete the bookmark.
5. Call `/imports/browser` with a missing profile. Confirm HTTP 422.

## 5. Build the package

```console
uv build
```

Confirm that `dist/` contains a wheel and a source distribution. Git ignores both files.

## 6. Install and test the wheel

Install the local wheel as a uv tool:

```console
mise run install-local
```

Or run the command directly:

```console
uv tool install --force dist/link_hoarder-0.1.0-py3-none-any.whl
```

Test the installed command outside the repository:

```console
link-hoarder --help
```

Set `LINK_HOARDER_DATABASE_PATH` to a temporary path and repeat the CLI CRUD test.

Check the installed executable path:

```console
uv tool dir
```

## 7. Remove test data

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
