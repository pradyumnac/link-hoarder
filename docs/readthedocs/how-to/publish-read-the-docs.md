# Publish on Read the Docs

Link Hoarder includes `.readthedocs.yaml` and `mkdocs.yml` at the repository root.
Read the Docs uses Python 3.14 and the locked `docs` dependency group.

## Validate the production site

Run the same strict MkDocs build before you push:

```console
mise run docs-build
```

The task writes the site to `site/`.
MkDocs stops the build when it finds a configuration, navigation, or link warning.

## Connect the repository

1. Sign in to Read the Docs.
2. Import the `pradyumnac/link-hoarder` repository.
3. Keep `.readthedocs.yaml` as the project configuration file.
4. Start the first build.

Read the Docs will build the default branch after each repository push.
A pull request can also get a preview when the project enables pull request builds.

## Preview changes locally

Start the live-reload server:

```console
mise run docs-serve
```

Open the URL that MkDocs prints.
Stop the server with `Ctrl+C`.
