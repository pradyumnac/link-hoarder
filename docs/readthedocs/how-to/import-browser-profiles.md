# Import browser profiles

Close the browser before you import its profile. This action gives the importer a stable source file.

## Discover profiles

Choose one supported browser family.

```console
link-hoarder import-browser chrome
link-hoarder import-browser chromium
link-hoarder import-browser edge
link-hoarder import-browser firefox
```

The command checks the standard Windows and Linux profile directories.

## Select one profile

Pass a Chromium `Bookmarks` file or a Firefox `places.sqlite` file.

```console
link-hoarder import-browser firefox --profile /path/to/places.sqlite
```

The importer skips a URL that already exists in the Link Hoarder database.
The command writes each import warning to standard error. The JSON result also
contains the warnings. Valid bookmarks continue to import after an entry failure.
