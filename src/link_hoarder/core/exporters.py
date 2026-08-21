"""Bookmark export services."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from pydantic import BaseModel

from link_hoarder.core.models import BookmarkRead


class ExportExistsError(Exception):
    """One or more export files already exist."""

    def __init__(self, paths: Sequence[Path]) -> None:
        self.paths = tuple(paths)
        joined = ", ".join(str(path) for path in self.paths)
        super().__init__(f"Export files already exist: {joined}")


class ExportResult(BaseModel):
    """Files and bookmark count from one export."""

    bookmarks: int
    directory: Path
    html_path: Path
    json_path: Path


@dataclass
class _Folder:
    folders: dict[str, _Folder] = field(default_factory=dict)
    bookmarks: list[BookmarkRead] = field(default_factory=list)


def export_bookmarks(
    bookmarks: Sequence[BookmarkRead],
    directory: Path,
    *,
    overwrite: bool = False,
) -> ExportResult:
    """Export bookmarks to Netscape HTML and JSON subdirectories."""
    target = directory.expanduser().resolve()
    html_path = target / "html" / "bookmarks.html"
    json_path = target / "json" / "bookmarks.json"
    existing = [path for path in (html_path, json_path) if path.exists()]
    if existing and not overwrite:
        raise ExportExistsError(existing)

    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(html_path, _html_document(bookmarks))
    payload = [bookmark.model_dump(mode="json") for bookmark in bookmarks]
    _write_atomic(json_path, json.dumps(payload, indent=2) + "\n")
    return ExportResult(
        bookmarks=len(bookmarks),
        directory=target,
        html_path=html_path,
        json_path=json_path,
    )


def export_paths(directory: Path) -> tuple[Path, Path]:
    """Return the HTML and JSON paths for an export directory."""
    target = directory.expanduser().resolve()
    return target / "html" / "bookmarks.html", target / "json" / "bookmarks.json"


def _html_document(bookmarks: Sequence[BookmarkRead]) -> str:
    root = _Folder()
    for bookmark in bookmarks:
        current = root
        if bookmark.folder:
            for segment in bookmark.folder.split("/"):
                if segment:
                    current = current.folders.setdefault(segment, _Folder())
        current.bookmarks.append(bookmark)

    lines = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Link Hoarder Bookmarks</TITLE>",
        "<H1>Link Hoarder Bookmarks</H1>",
        "<DL><p>",
    ]
    _render_folder(root, lines, 1)
    lines.append("</DL><p>")
    return "\n".join(lines) + "\n"


def _render_folder(folder: _Folder, lines: list[str], depth: int) -> None:
    indent = "  " * depth
    for name, child in folder.folders.items():
        lines.append(f"{indent}<DT><H3>{escape(name)}</H3>")
        lines.append(f"{indent}<DL><p>")
        _render_folder(child, lines, depth + 1)
        lines.append(f"{indent}</DL><p>")
    for bookmark in folder.bookmarks:
        added = int(bookmark.created_at.timestamp())
        url = escape(bookmark.url, quote=True)
        title = escape(bookmark.title)
        lines.append(f'{indent}<DT><A HREF="{url}" ADD_DATE="{added}">{title}</A>')


def _write_atomic(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
