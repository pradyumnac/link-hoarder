"""Typer command-line interface."""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from pydantic import ValidationError

from link_hoarder.api.app import create_app
from link_hoarder.cli.api_backend import ApiBookmarkBackend
from link_hoarder.core.backend import (
    BookmarkBackend,
    BookmarkBackendError,
    DuplicateBookmarkError,
)
from link_hoarder.core.config import (
    BackendKind,
    CliConfigError,
    Settings,
    default_config_path,
    load_cli_config,
    resolve_cli_config,
    save_cli_config,
)
from link_hoarder.core.exporters import (
    ExportExistsError,
    export_bookmarks,
    export_paths,
)
from link_hoarder.core.importers import import_html_export, import_profiles
from link_hoarder.core.logging import configure_logging
from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkRead,
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


class CliExitCode(IntEnum):
    """Stable CLI error states."""

    NOT_COMPLETED = 1
    INVALID_OPERATION = 2


@dataclass(frozen=True)
class CliState:
    """Values selected by global CLI options."""

    backend: BackendKind | None
    debug: bool


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
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Write diagnostic checkpoints to standard error."),
    ] = False,
) -> None:
    """Select global CLI settings."""
    context.obj = CliState(backend=backend, debug=debug)


def _debug(context: typer.Context, checkpoint: str, **details: object) -> None:
    state = context.obj
    if not isinstance(state, CliState) or not state.debug:
        return
    suffix = " ".join(f"{key}={value}" for key, value in details.items())
    message = f"DEBUG checkpoint={checkpoint}"
    typer.echo(f"{message} {suffix}".rstrip(), err=True)


def _bookmark_text(bookmark: BookmarkRead) -> str:
    lines = [
        f"[{bookmark.id}] {bookmark.title}",
        f"  URL: {bookmark.url}",
        f"  Source: {bookmark.source.value}",
    ]
    if bookmark.folder:
        lines.append(f"  Folder: {bookmark.folder}")
    if bookmark.tags:
        lines.append(f"  Tags: {', '.join(bookmark.tags)}")
    return "\n".join(lines)


@contextmanager
def _backend(context: typer.Context) -> Iterator[BookmarkBackend]:
    """Create the selected backend and convert failures to stable CLI errors."""
    current: BookmarkBackend | None = None
    try:
        settings = Settings()
        configure_logging(settings.log_level, stream=sys.stderr)
        state = context.obj
        selected = state.backend if isinstance(state, CliState) else None
        config = resolve_cli_config(settings, selected)
        _debug(context, "backend_selected", backend=config.backend.value)
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
    except DuplicateBookmarkError as error:
        _debug(context, "backend_conflict", error_type=type(error).__name__)
        typer.echo(str(error), err=True)
        raise typer.Exit(CliExitCode.NOT_COMPLETED) from error
    except (BookmarkBackendError, CliConfigError, ValidationError) as error:
        _debug(context, "backend_failed", error_type=type(error).__name__)
        typer.echo(str(error), err=True)
        raise typer.Exit(CliExitCode.INVALID_OPERATION) from error
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
        existing = backend.find_by_url(bookmark.url)
        if existing is not None:
            same_metadata = (
                existing.title == bookmark.title
                and existing.folder == bookmark.folder
                and existing.tags == bookmark.tags
                and existing.source == bookmark.source
            )
            if not same_metadata:
                typer.echo(
                    "A bookmark with this URL exists with different metadata.",
                    err=True,
                )
                raise typer.Exit(CliExitCode.NOT_COMPLETED)
            _debug(context, "create_unchanged", bookmark_id=existing.id)
            typer.echo(
                f"Bookmark {existing.id} already exists; no changes made.",
                err=True,
            )
            typer.echo(existing.model_dump_json(indent=2))
            return
        created = backend.create(bookmark)
    _debug(context, "create_complete", bookmark_id=created.id)
    typer.echo(f"Created bookmark {created.id}: {created.title}", err=True)
    typer.echo(created.model_dump_json(indent=2))


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
    json_output: Annotated[
        bool, typer.Option("--json", help="Write structured JSON output.")
    ] = False,
) -> None:
    """List bookmarks as JSON."""
    with _backend(context) as backend:
        bookmarks = backend.list(query=query, limit=limit, offset=offset)
    _debug(context, "list_complete", count=len(bookmarks), offset=offset)
    if json_output:
        typer.echo(
            "[\n"
            + ",\n".join(item.model_dump_json(indent=2) for item in bookmarks)
            + "\n]"
        )
    elif bookmarks:
        typer.echo("\n\n".join(_bookmark_text(bookmark) for bookmark in bookmarks))
    else:
        typer.echo("No bookmarks found.")


@app.command("get")
def get_bookmark(
    context: typer.Context,
    bookmark_id: Annotated[int, typer.Argument(min=1, help="Bookmark identifier.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Write structured JSON output.")
    ] = False,
) -> None:
    """Get one bookmark as JSON."""
    with _backend(context) as backend:
        bookmark = backend.get(bookmark_id)
    if bookmark is None:
        _debug(context, "get_missing", bookmark_id=bookmark_id)
        typer.echo(f"Bookmark {bookmark_id} was not found.", err=True)
        raise typer.Exit(CliExitCode.NOT_COMPLETED)
    _debug(context, "get_complete", bookmark_id=bookmark.id)
    if json_output:
        typer.echo(bookmark.model_dump_json(indent=2))
    else:
        typer.echo(_bookmark_text(bookmark))


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
        raise typer.Exit(CliExitCode.NOT_COMPLETED)
    _debug(context, "update_complete", bookmark_id=bookmark.id)
    typer.echo(f"Updated bookmark {bookmark.id}: {bookmark.title}", err=True)
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
        _debug(context, "delete_unchanged", bookmark_id=bookmark_id)
        typer.echo(f"Bookmark {bookmark_id} is already absent; no changes made.")
        return
    _debug(context, "delete_complete", bookmark_id=bookmark_id)
    typer.echo(f"Deleted bookmark {bookmark_id}.")


def _all_bookmarks(backend: BookmarkBackend) -> list[BookmarkRead]:
    bookmarks: list[BookmarkRead] = []
    limit = 1000
    while True:
        batch = backend.list(limit=limit, offset=len(bookmarks))
        bookmarks.extend(batch)
        if len(batch) < limit:
            return bookmarks


@app.command("export")
def export_command(
    context: typer.Context,
    directory: Annotated[
        Path | None,
        typer.Argument(file_okay=False, help="Export root directory."),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive/--no-interactive",
            help="Prompt for the export directory and overwrite confirmation.",
        ),
    ] = True,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite export files without confirmation."),
    ] = False,
) -> None:
    """Export bookmarks to HTML and JSON subdirectories."""
    try:
        saved = load_cli_config()
    except CliConfigError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(CliExitCode.INVALID_OPERATION) from error

    suggested = directory or saved.export_directory
    if interactive:
        default = suggested or (Path.cwd() / "link-hoarder-exports")
        target = Path(typer.prompt("Export directory", default=str(default)))
    elif suggested is not None:
        target = suggested
    else:
        typer.echo(
            "Specify an export directory or run interactive mode first.",
            err=True,
        )
        raise typer.Exit(CliExitCode.INVALID_OPERATION)

    _debug(context, "export_target_selected", directory=target)
    existing = [path for path in export_paths(target) if path.exists()]
    overwrite = force
    if existing and not force:
        if not interactive:
            typer.echo(
                "Export files already exist. Use --force to overwrite them.", err=True
            )
            raise typer.Exit(CliExitCode.INVALID_OPERATION)
        files = "\n".join(f"  {path}" for path in existing)
        typer.echo(f"Existing export files:\n{files}")
        if not typer.confirm("Overwrite existing export files?", default=False):
            typer.echo("Export cancelled.")
            raise typer.Exit(CliExitCode.NOT_COMPLETED)
        overwrite = True

    with _backend(context) as backend:
        bookmarks = _all_bookmarks(backend)
    try:
        result = export_bookmarks(bookmarks, target, overwrite=overwrite)
        save_cli_config(saved.model_copy(update={"export_directory": result.directory}))
    except (CliConfigError, ExportExistsError, OSError) as error:
        _debug(context, "export_failed", error_type=type(error).__name__)
        typer.echo(f"Export failed: {error}", err=True)
        raise typer.Exit(CliExitCode.INVALID_OPERATION) from error
    _debug(context, "export_complete", bookmarks=result.bookmarks)
    noun = "bookmark" if result.bookmarks == 1 else "bookmarks"
    typer.echo(
        f"Exported {result.bookmarks} {noun} to {result.directory}.",
        err=True,
    )
    typer.echo(result.model_dump_json(indent=2))


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
    _debug(context, "browser_import_started", browser=browser.value)
    with _backend(context) as backend:
        result = import_profiles(backend, browser, profile)
    _debug(context, "browser_import_complete", imported=result.imported)
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
    _debug(context, "file_import_started", path=path)
    with _backend(context) as backend:
        result = import_html_export(backend, path)
    _debug(context, "file_import_complete", imported=result.imported)
    _emit_import_result(result)


@app.command("config")
def show_config(context: typer.Context) -> None:
    """Show the saved CLI backend configuration without secrets."""
    try:
        config = load_cli_config()
    except CliConfigError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(CliExitCode.INVALID_OPERATION) from error
    _debug(context, "config_loaded", path=default_config_path())
    typer.echo(f"Path: {default_config_path()}")
    typer.echo(f"Backend: {config.backend.value}")
    typer.echo(f"API URL: {config.api_url or 'not set'}")
    typer.echo(f"API key: {'set' if config.api_key is not None else 'not set'}")
    typer.echo(f"Export directory: {config.export_directory or 'not set'}")


@app.command("api")
def run_api(
    context: typer.Context,
    host: Annotated[str | None, typer.Option(help="Server host.")] = None,
    port: Annotated[
        int | None, typer.Option(min=1, max=65535, help="Server port.")
    ] = None,
) -> None:
    """Run the authenticated FastAPI server."""
    settings = Settings()
    if settings.api_key is None:
        typer.echo("Set LINK_HOARDER_API_KEY before you start the API.", err=True)
        raise typer.Exit(CliExitCode.INVALID_OPERATION)
    configure_logging(settings.log_level)
    _debug(context, "api_start", host=host or settings.host, port=port or settings.port)
    uvicorn.run(
        create_app(settings),
        host=host or settings.host,
        port=port or settings.port,
        date_header=False,
        server_header=False,
    )


def _emit_import_result(result: ImportSummary) -> None:
    if result.profiles == 0:
        typer.echo("No browser profiles were found.", err=True)
    for warning in result.warnings:
        typer.echo(
            f"Warning [{warning.code.value}] {warning.profile}: {warning.message}",
            err=True,
        )
    typer.echo(
        "Import complete: "
        f"{result.imported} imported, {result.skipped} skipped, "
        f"{len(result.warnings)} warnings.",
        err=True,
    )
    typer.echo(result.model_dump_json(indent=2))


def main() -> None:
    """Run the command-line application."""
    app()
