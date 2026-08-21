"""Typer command-line interface."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from pydantic import ValidationError

from link_hoarder.api.app import create_app
from link_hoarder.cli.api_backend import ApiBookmarkBackend
from link_hoarder.core.backend import BookmarkBackend, BookmarkBackendError
from link_hoarder.core.config import (
    BackendKind,
    CliConfigError,
    Settings,
    default_config_path,
    load_cli_config,
    resolve_cli_config,
)
from link_hoarder.core.importers import import_html_export, import_profiles
from link_hoarder.core.logging import configure_logging
from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkUpdate,
    Browser,
    ImportSummary,
)
from link_hoarder.core.repository import BookmarkRepository

app = typer.Typer(
    name="link-hoarder",
    help="Store bookmarks locally or through a Link Hoarder API.",
    no_args_is_help=True,
)


@dataclass(frozen=True)
class CliState:
    """Values selected by global CLI options."""

    backend: BackendKind | None


@app.callback()
def select_backend(
    context: typer.Context,
    backend: Annotated[
        BackendKind | None,
        typer.Option(
            "--backend",
            help="Use the local SQLite or remote API backend.",
            case_sensitive=False,
        ),
    ] = None,
) -> None:
    """Select global CLI settings."""
    context.obj = CliState(backend=backend)


@contextmanager
def _backend(context: typer.Context) -> Iterator[BookmarkBackend]:
    """Create the selected backend and convert failures to stable CLI errors."""
    current: BookmarkBackend | None = None
    try:
        settings = Settings()
        configure_logging(settings.log_level)
        state = context.obj
        selected = state.backend if isinstance(state, CliState) else None
        config = resolve_cli_config(settings, selected)
        if config.backend is BackendKind.LOCAL:
            repository = BookmarkRepository(settings.database_url)
            repository.initialize()
            current = repository
        else:
            if config.api_url is None or config.api_key is None:
                raise CliConfigError("API mode requires an API URL and API key.")
            current = ApiBookmarkBackend(
                config.api_url,
                config.api_key,
                config.api_timeout_seconds,
            )
        yield current
    except (BookmarkBackendError, CliConfigError, ValidationError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    finally:
        if current is not None:
            current.close()


@app.command("create")
def create_bookmark(
    context: typer.Context,
    url: Annotated[
        str, typer.Argument(help="HTTP, HTTPS, or JavaScript bookmark URL.")
    ],
    title: Annotated[str, typer.Option("--title", "-t", help="Bookmark title.")],
    folder: Annotated[str | None, typer.Option(help="Optional folder path.")] = None,
    tag: Annotated[
        list[str] | None, typer.Option("--tag", help="Repeat for each tag.")
    ] = None,
) -> None:
    """Create one bookmark."""
    try:
        bookmark = BookmarkCreate(url=url, title=title, folder=folder, tags=tag or [])
    except ValidationError as error:
        raise typer.BadParameter(str(error)) from error
    with _backend(context) as backend:
        typer.echo(backend.create(bookmark).model_dump_json(indent=2))


@app.command("list")
def list_bookmarks(
    context: typer.Context,
    query: Annotated[
        str | None, typer.Option("--query", "-q", help="Search title and URL.")
    ] = None,
    limit: Annotated[
        int, typer.Option(min=1, max=1000, help="Maximum result count.")
    ] = 100,
    offset: Annotated[int, typer.Option(min=0, help="Result offset.")] = 0,
) -> None:
    """List bookmarks as JSON."""
    with _backend(context) as backend:
        bookmarks = backend.list(query=query, limit=limit, offset=offset)
    typer.echo(
        "[\n" + ",\n".join(item.model_dump_json(indent=2) for item in bookmarks) + "\n]"
    )


@app.command("get")
def get_bookmark(
    context: typer.Context,
    bookmark_id: Annotated[int, typer.Argument(min=1, help="Bookmark identifier.")],
) -> None:
    """Get one bookmark as JSON."""
    with _backend(context) as backend:
        bookmark = backend.get(bookmark_id)
    if bookmark is None:
        typer.echo(f"Bookmark {bookmark_id} was not found.", err=True)
        raise typer.Exit(1)
    typer.echo(bookmark.model_dump_json(indent=2))


@app.command("update")
def update_bookmark(
    context: typer.Context,
    bookmark_id: Annotated[int, typer.Argument(min=1, help="Bookmark identifier.")],
    url: Annotated[
        str | None, typer.Option(help="New HTTP, HTTPS, or JavaScript URL.")
    ] = None,
    title: Annotated[
        str | None, typer.Option("--title", "-t", help="New title.")
    ] = None,
    folder: Annotated[str | None, typer.Option(help="New folder path.")] = None,
    tag: Annotated[
        list[str] | None, typer.Option("--tag", help="Replacement tags.")
    ] = None,
) -> None:
    """Update supplied fields on one bookmark."""
    values: dict[str, str | list[str]] = {}
    if url is not None:
        values["url"] = url
    if title is not None:
        values["title"] = title
    if folder is not None:
        values["folder"] = folder
    if tag is not None:
        values["tags"] = tag
    try:
        update = BookmarkUpdate.model_validate(values)
    except ValidationError as error:
        raise typer.BadParameter(str(error)) from error
    with _backend(context) as backend:
        bookmark = backend.update(bookmark_id, update)
    if bookmark is None:
        typer.echo(f"Bookmark {bookmark_id} was not found.", err=True)
        raise typer.Exit(1)
    typer.echo(bookmark.model_dump_json(indent=2))


@app.command("delete")
def delete_bookmark(
    context: typer.Context,
    bookmark_id: Annotated[int, typer.Argument(min=1, help="Bookmark identifier.")],
) -> None:
    """Delete one bookmark."""
    with _backend(context) as backend:
        deleted = backend.delete(bookmark_id)
    if not deleted:
        typer.echo(f"Bookmark {bookmark_id} was not found.", err=True)
        raise typer.Exit(1)
    typer.echo(f"Deleted bookmark {bookmark_id}.")


@app.command("import-browser")
def import_browser(
    context: typer.Context,
    browser: Annotated[Browser, typer.Argument(help="Browser family.")],
    profile: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Bookmarks or places.sqlite file. Omit to discover profiles.",
        ),
    ] = None,
) -> None:
    """Import native browser profile bookmarks."""
    with _backend(context) as backend:
        result = import_profiles(backend, browser, profile)
    _emit_import_result(result)


@app.command("import-file")
def import_file(
    context: typer.Context,
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Netscape bookmark HTML export file.",
        ),
    ],
) -> None:
    """Import a browser bookmark HTML export."""
    with _backend(context) as backend:
        result = import_html_export(backend, path)
    _emit_import_result(result)


@app.command("config")
def show_config() -> None:
    """Show the saved CLI backend configuration without secrets."""
    try:
        config = load_cli_config()
    except CliConfigError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    typer.echo(f"Path: {default_config_path()}")
    typer.echo(f"Backend: {config.backend.value}")
    typer.echo(f"API URL: {config.api_url or 'not set'}")
    typer.echo(f"API key: {'set' if config.api_key is not None else 'not set'}")


@app.command("api")
def run_api(
    host: Annotated[str | None, typer.Option(help="Server host.")] = None,
    port: Annotated[
        int | None, typer.Option(min=1, max=65535, help="Server port.")
    ] = None,
) -> None:
    """Run the authenticated FastAPI server."""
    settings = Settings()
    if settings.api_key is None:
        typer.echo("Set LINK_HOARDER_API_KEY before you start the API.", err=True)
        raise typer.Exit(2)
    configure_logging(settings.log_level)
    uvicorn.run(
        create_app(settings),
        host=host or settings.host,
        port=port or settings.port,
        date_header=False,
        server_header=False,
    )


def _emit_import_result(result: ImportSummary) -> None:
    for warning in result.warnings:
        typer.echo(
            f"Warning [{warning.code.value}] {warning.profile}: {warning.message}",
            err=True,
        )
    typer.echo(result.model_dump_json(indent=2))


def main() -> None:
    """Run the command-line application."""
    app()
