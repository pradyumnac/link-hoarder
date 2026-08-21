# CLI reference

Run `link-hoarder COMMAND --help` for command details.
Place global options before the command.

| Global option | Purpose |
| --- | --- |
| `--backend local|api` | Select the local SQLite or remote API backend. |
| `--debug` | Write diagnostic checkpoints to standard error. |

Debug checkpoints do not contain API keys or bookmark content.
Warnings and other diagnostics also use standard error.

## Commands

| Command | Purpose |
| --- | --- |
| `create` | Create one bookmark. |
| `list` | List and search bookmarks. |
| `get` | Get one bookmark. |
| `update` | Update supplied bookmark fields. |
| `delete` | Delete one bookmark. |
| `import-browser` | Import Brave, Chrome, Chromium, Edge, Firefox, or Zen profile files. |
| `import-file` | Import a Netscape bookmark HTML export. |
| `export` | Export bookmarks to HTML and JSON subdirectories. |
| `config` | Show saved backend and export configuration without secrets. |
| `api` | Run the HTTP API. |

All bookmark, import, and export commands use the selected backend.
Native browser import files remain on the CLI host.

## Output

`list` and `get` write readable text by default.
Add `--json` to either command for structured JSON.
Create, update, import, and export results use JSON on standard output.
These commands write concise completion feedback to standard error.

An empty text list prints `No bookmarks found.`.
An empty JSON list prints `[]`.

## Repeat behavior

A repeated create with the same URL and metadata returns the existing bookmark.
The command reports a conflict when the URL has different metadata.
A repeated delete reports that the bookmark is already absent and returns success.
An unchanged update keeps the existing modification timestamp.
Repeated imports skip URLs that are already stored.

## Export behavior

Export prompts for a directory by default.
The command saves each successful directory and suggests it during the next export.
Use `--no-interactive` to disable prompts.
Use `--force` to overwrite existing files without confirmation.

## Exit states

| Code | Meaning |
| --- | --- |
| `0` | The action succeeded, or the requested final state already exists. |
| `1` | The action was valid but did not complete, such as a conflict or cancellation. |
| `2` | Input, configuration, storage, export, or connection failed. |

Expected failures use concise messages without a traceback.

See [Configure the CLI backend](../how-to/configure-cli-backend.md) for setup and wrapper scripts.
Unix users can open `docs/man/link-hoarder.1` with `man -l`.
