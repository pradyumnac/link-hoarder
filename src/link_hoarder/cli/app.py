"""Typer command-line interface."""

from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from pydantic import ValidationError

from link_hoarder.api.app import create_app
from link_hoarder.core.config import Settings
from link_hoarder.core.importers import import_profiles
from link_hoarder.core.logging import configure_logging
from link_hoarder.core.models import BookmarkCreate, BookmarkUpdate, Browser
from link_hoarder.core.repository import BookmarkRepository

app = typer.Typer(
    name="link-hoarder",
    help="Store bookmarks and import native browser profiles.",
    no_args_is_help=True,
)


def _repository(settings: Settings) -> BookmarkRepository:
    repository = BookmarkRepository(settings.database_url)
    repository.initialize()
    return repository


@app.command("create")
def create_bookmark(
    url: Annotated[str, typer.Argument(help="HTTP or HTTPS bookmark URL.")],
    title: Annotated[str, typer.Option("--title", "-t", help="Bookmark title.")],
    folder: Annotated[str | None, typer.Option(help="Optional folder path.")] = None,
    tag: Annotated[
        list[str] | None, typer.Option("--tag", help="Repeat for each tag.")
    ] = None,
) -> None:
    """Create one bookmark."""
    settings = Settings()
    configure_logging(settings.log_level)
    try:
        bookmark = BookmarkCreate(url=url, title=title, folder=folder, tags=tag or [])
    except ValidationError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(_repository(settings).create(bookmark).model_dump_json(indent=2))


@app.command("list")
def list_bookmarks(
    query: Annotated[
        str | None, typer.Option("--query", "-q", help="Search title and URL.")
    ] = None,
    limit: Annotated[
        int, typer.Option(min=1, max=1000, help="Maximum result count.")
    ] = 100,
    offset: Annotated[int, typer.Option(min=0, help="Result offset.")] = 0,
) -> None:
    """List bookmarks as JSON."""
    settings = Settings()
    bookmarks = _repository(settings).list(query=query, limit=limit, offset=offset)
    typer.echo(
        "[\n" + ",\n".join(item.model_dump_json(indent=2) for item in bookmarks) + "\n]"
    )


@app.command("get")
def get_bookmark(
    bookmark_id: Annotated[int, typer.Argument(min=1, help="Bookmark identifier.")],
) -> None:
    """Get one bookmark as JSON."""
    settings = Settings()
    bookmark = _repository(settings).get(bookmark_id)
    if bookmark is None:
        typer.echo(f"Bookmark {bookmark_id} was not found.", err=True)
        raise typer.Exit(1)
    typer.echo(bookmark.model_dump_json(indent=2))


@app.command("update")
def update_bookmark(
    bookmark_id: Annotated[int, typer.Argument(min=1, help="Bookmark identifier.")],
    url: Annotated[str | None, typer.Option(help="New HTTP or HTTPS URL.")] = None,
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
    settings = Settings()
    bookmark = _repository(settings).update(bookmark_id, update)
    if bookmark is None:
        typer.echo(f"Bookmark {bookmark_id} was not found.", err=True)
        raise typer.Exit(1)
    typer.echo(bookmark.model_dump_json(indent=2))


@app.command("delete")
def delete_bookmark(
    bookmark_id: Annotated[int, typer.Argument(min=1, help="Bookmark identifier.")],
) -> None:
    """Delete one bookmark."""
    settings = Settings()
    if not _repository(settings).delete(bookmark_id):
        typer.echo(f"Bookmark {bookmark_id} was not found.", err=True)
        raise typer.Exit(1)
    typer.echo(f"Deleted bookmark {bookmark_id}.")


@app.command("import-browser")
def import_browser(
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
    settings = Settings()
    result = import_profiles(_repository(settings), browser, profile)
    typer.echo(result.model_dump_json(indent=2))


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
        create_app(settings), host=host or settings.host, port=port or settings.port
    )


def main() -> None:
    """Run the command-line application."""
    app()
