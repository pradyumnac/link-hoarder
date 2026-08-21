# Export bookmarks

Run the export command.

```console
link-hoarder export
```

The command prompts for an export directory.
The first suggested directory is `link-hoarder-exports` in the current directory.
After a successful export, the command saves the selected directory.
The next export suggests the saved directory.

The command creates these files:

```text
SELECTED-DIRECTORY/
├── html/
│   └── bookmarks.html
└── json/
    └── bookmarks.json
```

Use `html/bookmarks.html` with browsers that support Netscape bookmark HTML.
Use `json/bookmarks.json` for Link Hoarder data processing.

## Override the suggested directory

Give a directory as an argument.
Interactive mode shows the argument as the prompt default.
You can enter a different directory at the prompt.

```console
link-hoarder export /path/to/exports
```

## Run without prompts

Disable interactive mode for scripts.
Give a directory or save one with an earlier interactive export.

```console
link-hoarder export /path/to/exports --no-interactive
```

The command stops if an export file exists.
Use force mode to overwrite both export files without confirmation.

```console
link-hoarder export /path/to/exports --no-interactive --force
```

Interactive mode asks for confirmation before it overwrites an existing file.
Declining the confirmation leaves both files unchanged and returns exit code 1.
A write or configuration failure returns exit code 2 without a traceback.
Completion feedback shows the bookmark count and selected directory.
