"""Secure bookmark metadata fetching and caching."""

import html
import http.client
import ipaddress
import socket
import ssl
import threading
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Protocol
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

import structlog
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict

from link_hoarder.core.models import (
    BookmarkMetadataRecord,
    BookmarkRead,
    MetadataStatus,
)
from link_hoarder.core.repository import BookmarkRepository

_CONNECT_TIMEOUT_SECONDS = 3.0
_TOTAL_TIMEOUT_SECONDS = 10.0
_MAX_HTML_BYTES = 512 * 1024
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_IMAGE_DIMENSION = 4096
_MAX_IMAGE_PIXELS = 16_000_000
_MAX_REDIRECTS = 3
_REFRESH_AFTER = timedelta(days=7)
_RETRY_AFTER_FAILURE = timedelta(hours=1)
_MAX_RETRY_AFTER_FAILURE = timedelta(hours=24)
_ALLOWED_IMAGE_FORMATS = frozenset({"GIF", "ICO", "JPEG", "PNG", "WEBP"})
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

# Hard cap on the total number of bookmarks with queued or in-flight
# refresh work. Bulk backlog work (`queue_backfill`) may only fill a
# fraction of this cap, so visible-bookmark work (`queue_refresh`,
# `queue_refresh_many`) always has reserved headroom to run without being
# crowded out by a large import or collection scan.
_MAX_PENDING_REFRESHES = 200
_MAX_BACKFILL_PENDING = 100

_LOGGER = structlog.get_logger(__name__)


class MetadataFetchError(Exception):
    """Remote bookmark metadata could not be fetched safely."""


class MetadataBlockedError(MetadataFetchError):
    """A remote bookmark metadata request violated a security control."""


class RemoteResponse(BaseModel):
    """Validated bounded remote HTTP response."""

    model_config = ConfigDict(frozen=True)

    body: bytes
    content_type: str
    final_url: str


class FetchedMetadata(BaseModel):
    """Sanitized presentation assets fetched for one bookmark."""

    model_config = ConfigDict(frozen=True)

    favicon: bytes | None = None
    thumbnail: bytes | None = None


class MetadataFetcher(Protocol):
    """Fetch sanitized metadata for one public bookmark URL."""

    def fetch(self, url: str) -> FetchedMetadata:
        """Return safe presentation assets for a bookmark URL."""
        ...


class _HeadMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.favicon_url: str | None = None
        self.thumbnail_url: str | None = None
        self.in_head = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "body":
            self.in_head = False
            return
        if not self.in_head:
            return
        values = {name.lower(): value for name, value in attrs if value is not None}
        if tag.lower() == "link":
            relations = values.get("rel", "").lower().split()
            if "icon" in relations and self.favicon_url is None:
                self.favicon_url = values.get("href")
        elif (
            tag.lower() == "meta"
            and values.get("property", "").lower() == "og:image"
            and self.thumbnail_url is None
        ):
            self.thumbnail_url = values.get("content")


class SecureMetadataFetcher:
    """Fetch and sanitize remote metadata with SSRF and resource controls."""

    def fetch(self, url: str) -> FetchedMetadata:
        """Fetch one HTML head and its selected presentation images."""
        page = self._request(url, max_bytes=_MAX_HTML_BYTES, accept="text/html")
        if "html" not in page.content_type.lower():
            raise MetadataFetchError("The bookmark did not return HTML.")
        parser = _HeadMetadataParser()
        parser.feed(page.body.decode("utf-8", errors="replace"))

        favicon_url = (
            urljoin(page.final_url, parser.favicon_url)
            if parser.favicon_url
            else urljoin(page.final_url, "/favicon.ico")
        )
        thumbnail_url = (
            urljoin(page.final_url, parser.thumbnail_url)
            if parser.thumbnail_url
            else None
        )
        favicon = self._fetch_image(favicon_url, maximum_size=(128, 128))
        thumbnail = (
            self._fetch_image(thumbnail_url, maximum_size=(1200, 630))
            if thumbnail_url is not None
            else None
        )
        return FetchedMetadata(favicon=favicon, thumbnail=thumbnail)

    def _fetch_image(self, url: str, *, maximum_size: tuple[int, int]) -> bytes | None:
        try:
            response = self._request(
                url,
                max_bytes=_MAX_IMAGE_BYTES,
                accept="image/avif,image/webp,image/png,image/jpeg,image/gif,image/x-icon",
            )
            return _sanitize_image(response.body, maximum_size=maximum_size)
        except MetadataFetchError as error:
            _LOGGER.warning(
                "bookmark_metadata_image_fetch_failed",
                reason=error.__class__.__name__,
            )
            return None

    def _request(self, url: str, *, max_bytes: int, accept: str) -> RemoteResponse:
        current = url
        for redirect_count in range(_MAX_REDIRECTS + 1):
            parsed, address, port = _validated_destination(current)
            status, headers, body = _request_once(
                parsed,
                address,
                port,
                max_bytes=max_bytes,
                accept=accept,
            )
            if status in _REDIRECT_STATUSES:
                location = headers.get("location")
                if location is None:
                    raise MetadataFetchError("The redirect has no destination.")
                if redirect_count == _MAX_REDIRECTS:
                    raise MetadataBlockedError("The redirect limit was exceeded.")
                current = urljoin(current, location)
                continue
            if status < 200 or status >= 300:
                raise MetadataFetchError(f"The remote server returned HTTP {status}.")
            return RemoteResponse(
                body=body,
                content_type=headers.get("content-type", ""),
                final_url=current,
            )
        raise MetadataBlockedError("The redirect limit was exceeded.")


def _validated_destination(url: str) -> tuple[SplitResult, str, int]:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise MetadataBlockedError("The remote URL has an invalid port.") from error
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise MetadataBlockedError("Only HTTP and HTTPS metadata URLs are permitted.")
    if parsed.username is not None or parsed.password is not None:
        raise MetadataBlockedError("Credentials are not permitted in metadata URLs.")
    selected_port = port or (443 if parsed.scheme == "https" else 80)
    if selected_port not in {80, 443}:
        raise MetadataBlockedError("Only ports 80 and 443 are permitted.")
    if any(character in url for character in ("\r", "\n", "\x00")):
        raise MetadataBlockedError(
            "Control characters are not permitted in metadata URLs."
        )

    try:
        hostname = parsed.hostname.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise MetadataBlockedError(
            "The metadata hostname could not be encoded."
        ) from error
    try:
        answers = socket.getaddrinfo(hostname, selected_port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise MetadataFetchError(
            "The metadata destination could not be resolved."
        ) from error
    addresses = list(
        dict.fromkeys(
            address for answer in answers if isinstance((address := answer[4][0]), str)
        )
    )
    if not addresses:
        raise MetadataFetchError("The metadata destination has no address.")
    try:
        parsed_addresses = [ipaddress.ip_address(address) for address in addresses]
    except ValueError as error:
        raise MetadataBlockedError(
            "The metadata destination address is invalid."
        ) from error
    if any(not address.is_global for address in parsed_addresses):
        raise MetadataBlockedError("The metadata destination is not public.")
    return parsed, addresses[0], selected_port


def _request_once(
    parsed: SplitResult,
    address: str,
    port: int,
    *,
    max_bytes: int,
    accept: str,
) -> tuple[int, Mapping[str, str], bytes]:
    hostname = parsed.hostname
    if not hostname:
        raise MetadataBlockedError("The metadata URL has no host.")
    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise MetadataBlockedError(
            "The metadata hostname could not be encoded."
        ) from error
    host_header = f"[{ascii_hostname}]" if ":" in ascii_hostname else ascii_hostname
    default_port = 443 if parsed.scheme == "https" else 80
    if port != default_port:
        host_header = f"{host_header}:{port}"
    try:
        target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    except ValueError as error:
        raise MetadataBlockedError("The metadata request target is invalid.") from error
    if any(character in target for character in ("\r", "\n", "\x00")):
        raise MetadataBlockedError("The metadata request target is invalid.")

    started = time.monotonic()
    connection: socket.socket | ssl.SSLSocket = socket.create_connection(
        (address, port), timeout=_CONNECT_TIMEOUT_SECONDS
    )
    try:
        if parsed.scheme == "https":
            context = ssl.create_default_context()
            connection = context.wrap_socket(connection, server_hostname=ascii_hostname)
        request = (
            f"GET {target} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            f"Accept: {accept}\r\n"
            "Accept-Encoding: identity\r\n"
            "Connection: close\r\n"
            "User-Agent: Link-Hoarder-Metadata/1\r\n\r\n"
        )
        connection.sendall(request.encode("ascii"))
        response = http.client.HTTPResponse(connection)
        response.begin()
        headers = {name.lower(): value for name, value in response.getheaders()}
        chunks: list[bytes] = []
        size = 0
        while True:
            remaining = _TOTAL_TIMEOUT_SECONDS - (time.monotonic() - started)
            if remaining <= 0:
                raise MetadataFetchError(
                    "The metadata request exceeded its time limit."
                )
            connection.settimeout(remaining)
            chunk = response.read(min(64 * 1024, max_bytes + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > max_bytes:
                raise MetadataBlockedError(
                    "The metadata response exceeded its size limit."
                )
        return response.status, headers, b"".join(chunks)
    except (OSError, ssl.SSLError, http.client.HTTPException) as error:
        raise MetadataFetchError("The metadata request failed.") from error
    finally:
        connection.close()


def _sanitize_image(content: bytes, *, maximum_size: tuple[int, int]) -> bytes:
    try:
        with Image.open(BytesIO(content)) as source:
            image_format = source.format
            if image_format not in _ALLOWED_IMAGE_FORMATS:
                raise MetadataBlockedError(
                    "The metadata image format is not permitted."
                )
            width, height = source.size
            if (
                width < 1
                or height < 1
                or width > _MAX_IMAGE_DIMENSION
                or height > _MAX_IMAGE_DIMENSION
                or width * height > _MAX_IMAGE_PIXELS
            ):
                raise MetadataBlockedError("The decoded metadata image is too large.")
            source.seek(0)
            source.load()
            sanitized = ImageOps.exif_transpose(source)
            sanitized.thumbnail(maximum_size)
            if sanitized.mode not in {"RGB", "RGBA"}:
                sanitized = sanitized.convert("RGBA")
            output = BytesIO()
            sanitized.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise MetadataBlockedError(
            "The metadata image could not be decoded."
        ) from error


class BookmarkAssetAvailability(BaseModel):
    """Cached presentation assets available for one bookmark."""

    model_config = ConfigDict(frozen=True)

    has_favicon: bool = False
    has_thumbnail: bool = False


class BookmarkMetadataService:
    """Refresh bookmark metadata in the background and serve cached assets.

    Design notes:

    Bounded, prioritized queue (`core-metadata-scheduling`): the total
    number of bookmarks with queued or in-flight refresh work is capped at
    `_MAX_PENDING_REFRESHES`. Work submitted past the cap is dropped, with a
    structlog warning, instead of growing without limit. Visible-bookmark
    work (`queue_refresh`, `queue_refresh_many`) may use the full cap.
    Bulk backlog work (`queue_backfill`) may only use the smaller
    `_MAX_BACKFILL_PENDING` cap, so it can never crowd out the headroom
    reserved for visible work.

    Admission limits alone do not give priority, because one executor runs
    its queue in first-in-first-out order: an import queued first would
    still run before a bookmark the user is looking at. Visible work and
    backfill work therefore use separate executors. Visible work never
    waits for a worker that backfill work holds.

    Retirement scoping (`core-metadata-retirement`): a deleted bookmark's
    in-flight refresh must not write files or a metadata row after
    `purge_assets` runs, but the id must be free to refresh normally if a
    later bookmark reuses it (SQLite reuses rowids). This is implemented
    with a generation counter per bookmark id (`_active_generation`),
    present only while work for that id is queued or running.
    `queue_refresh`/`queue_refresh_many`/`queue_backfill` capture the
    current generation when they submit work; `purge_assets` bumps the
    generation only if work is in flight; the worker checks the generation
    right before writing and silently discards its result on a mismatch.
    The entry is removed once the in-flight worker finishes, so nothing
    about a deleted bookmark is retained once its refresh has settled.
    """

    def __init__(
        self,
        repository: BookmarkRepository,
        cache_path: Path,
        *,
        fetcher: MetadataFetcher | None = None,
        enabled: bool = True,
    ) -> None:
        self._repository = repository
        self._cache_path = cache_path.expanduser().resolve()
        self._cache_path.mkdir(parents=True, exist_ok=True)
        self._fetcher = fetcher or SecureMetadataFetcher()
        self._enabled = enabled
        # Visible work and bulk backlog work use separate executors, so a
        # queued import can never hold a worker that visible work needs.
        # A shared executor is strictly first-in-first-out, so admission
        # limits alone cannot stop backfill from running first.
        self._executor = (
            ThreadPoolExecutor(max_workers=2, thread_name_prefix="metadata")
            if enabled
            else None
        )
        self._backfill_executor = (
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="metadata-backfill")
            if enabled
            else None
        )
        self._pending: set[int] = set()
        self._active_generation: dict[int, int] = {}
        self._lock = threading.Lock()

    def close(self) -> None:
        """Stop queued metadata work during application shutdown."""
        for executor in (self._backfill_executor, self._executor):
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)

    def queue_refresh(self, bookmark: BookmarkRead) -> None:
        """Queue a refresh for one visible bookmark.

        Visible-bookmark work is prioritized over bulk backlog work; see
        the class docstring.
        """
        self.queue_refresh_many([bookmark])

    def queue_refresh_many(self, bookmarks: Sequence[BookmarkRead]) -> None:
        """Queue refresh for many visible bookmarks with one metadata read."""
        self._queue(bookmarks, cap=_MAX_PENDING_REFRESHES, backfill=False)

    def queue_backfill(self, bookmarks: Sequence[BookmarkRead]) -> None:
        """Queue bulk backlog refresh work that only fills spare capacity."""
        self._queue(bookmarks, cap=_MAX_BACKFILL_PENDING, backfill=True)

    def asset_availability(
        self, bookmarks: Sequence[BookmarkRead]
    ) -> dict[int, BookmarkAssetAvailability]:
        """Return cached asset availability for many bookmarks with one metadata read."""
        if not bookmarks:
            return {}
        cached_map = self._repository.list_metadata(
            [bookmark.id for bookmark in bookmarks]
        )
        availability: dict[int, BookmarkAssetAvailability] = {}
        for bookmark in bookmarks:
            cached = cached_map.get(bookmark.id)
            availability[bookmark.id] = BookmarkAssetAvailability(
                has_favicon=self._verified_asset_path(
                    cached.favicon_file if cached is not None else None
                )
                is not None,
                has_thumbnail=self._verified_asset_path(
                    cached.thumbnail_file if cached is not None else None
                )
                is not None,
            )
        return availability

    def refresh(self, bookmark: BookmarkRead) -> None:
        """Fetch and store sanitized metadata for one bookmark.

        Any failure, including one this module did not anticipate, is
        normalized into a `FAILED` cache row with a backoff so a bookmark
        can never be retried in a hot loop.
        """
        with self._lock:
            tracked = bookmark.id in self._active_generation
            generation = self._active_generation.get(bookmark.id, 0)
            if not tracked:
                self._active_generation[bookmark.id] = generation
        try:
            self._refresh_with_generation(bookmark, generation)
        finally:
            if not tracked:
                with self._lock:
                    if bookmark.id not in self._pending:
                        self._active_generation.pop(bookmark.id, None)

    def _refresh_with_generation(self, bookmark: BookmarkRead, generation: int) -> None:
        now = datetime.now(UTC)
        cached = self._repository.get_metadata(bookmark.id)
        try:
            fetched = self._fetcher.fetch(bookmark.url)
        except (MetadataBlockedError, MetadataFetchError) as error:
            self._record_failure(bookmark, cached, error, now, generation)
            return
        except Exception as error:  # noqa: BLE001 - fail safe: never retry in a hot loop
            _LOGGER.error(
                "bookmark_metadata_fetch_unexpected_error",
                bookmark_id=bookmark.id,
                reason=error.__class__.__name__,
            )
            self._record_failure(
                bookmark,
                cached,
                MetadataFetchError("An unexpected metadata failure occurred."),
                now,
                generation,
            )
            return
        try:
            with self._lock:
                if self._active_generation.get(bookmark.id, 0) != generation:
                    return
                favicon_file = self._store_asset(
                    bookmark.id, "favicon", fetched.favicon
                )
                thumbnail_file = self._store_asset(
                    bookmark.id, "thumbnail", fetched.thumbnail
                )
                self._repository.save_metadata(
                    BookmarkMetadataRecord(
                        bookmark_id=bookmark.id,
                        source_url=bookmark.url,
                        status=MetadataStatus.READY,
                        favicon_file=favicon_file,
                        thumbnail_file=thumbnail_file,
                        refreshed_at=now,
                        retry_after=now + _REFRESH_AFTER,
                    )
                )
        except Exception as error:  # noqa: BLE001 - fail safe: never retry in a hot loop
            # A cache file write or a metadata write can fail after a good
            # fetch. Record the failure so the backoff applies, or the
            # bookmark is retried on every collection request.
            _LOGGER.error(
                "bookmark_metadata_store_failed",
                bookmark_id=bookmark.id,
                reason=error.__class__.__name__,
            )
            self._record_failure(
                bookmark,
                cached,
                MetadataFetchError("The metadata could not be stored."),
                now,
                generation,
            )

    def purge_assets(self, bookmark_id: int) -> None:
        """Remove cached files and cancel in-flight work for a deleted bookmark."""
        with self._lock:
            if bookmark_id in self._active_generation:
                self._active_generation[bookmark_id] += 1
            for kind in ("favicon", "thumbnail"):
                (self._cache_path / f"{bookmark_id}-{kind}.png").unlink(missing_ok=True)

    def asset_path(self, bookmark_id: int, kind: str) -> Path | None:
        """Return a verified cached asset path for one bookmark."""
        metadata = self._repository.get_metadata(bookmark_id)
        if metadata is None:
            return None
        filename = (
            metadata.favicon_file if kind == "favicon" else metadata.thumbnail_file
        )
        return self._verified_asset_path(filename)

    def _verified_asset_path(self, filename: str | None) -> Path | None:
        if filename is None:
            return None
        path = (self._cache_path / filename).resolve()
        if path.parent != self._cache_path or not path.is_file():
            return None
        return path

    def _queue(
        self, bookmarks: Sequence[BookmarkRead], *, cap: int, backfill: bool
    ) -> None:
        if not self._enabled:
            return
        eligible = [
            bookmark
            for bookmark in bookmarks
            if not bookmark.url.lower().startswith("javascript:")
        ]
        if not eligible:
            return
        cached_map = self._repository.list_metadata(
            [bookmark.id for bookmark in eligible]
        )
        for bookmark in eligible:
            if not self._needs_refresh(bookmark, cached_map.get(bookmark.id)):
                continue
            self._submit(bookmark, cap=cap, backfill=backfill)

    def _submit(self, bookmark: BookmarkRead, *, cap: int, backfill: bool) -> None:
        with self._lock:
            if bookmark.id in self._pending:
                return
            if len(self._pending) >= cap:
                _LOGGER.warning(
                    "bookmark_metadata_queue_full",
                    bookmark_id=bookmark.id,
                    pending=len(self._pending),
                    cap=cap,
                )
                return
            self._pending.add(bookmark.id)
            generation = self._active_generation.get(bookmark.id, 0)
            self._active_generation[bookmark.id] = generation
        executor = self._backfill_executor if backfill else self._executor
        if executor is not None:
            executor.submit(self._refresh_and_release, bookmark, generation)

    def _record_failure(
        self,
        bookmark: BookmarkRead,
        cached: BookmarkMetadataRecord | None,
        error: MetadataFetchError,
        now: datetime,
        generation: int,
    ) -> None:
        status = (
            MetadataStatus.BLOCKED
            if isinstance(error, MetadataBlockedError)
            else MetadataStatus.FAILED
        )
        same_source = cached is not None and cached.source_url == bookmark.url
        interval = _next_retry_after_failure(cached, bookmark)
        try:
            with self._lock:
                if self._active_generation.get(bookmark.id, 0) != generation:
                    return
                if not same_source:
                    self._store_asset(bookmark.id, "favicon", None)
                    self._store_asset(bookmark.id, "thumbnail", None)
                self._repository.save_metadata(
                    BookmarkMetadataRecord(
                        bookmark_id=bookmark.id,
                        source_url=bookmark.url,
                        status=status,
                        favicon_file=(
                            cached.favicon_file
                            if cached is not None and same_source
                            else None
                        ),
                        thumbnail_file=(
                            cached.thumbnail_file
                            if cached is not None and same_source
                            else None
                        ),
                        refreshed_at=now,
                        retry_after=now + interval,
                    )
                )
        except Exception as store_error:  # noqa: BLE001 - last resort must not raise
            _LOGGER.error(
                "bookmark_metadata_failure_not_recorded",
                bookmark_id=bookmark.id,
                reason=store_error.__class__.__name__,
            )
            return
        _LOGGER.warning(
            "bookmark_metadata_fetch_failed",
            bookmark_id=bookmark.id,
            reason=error.__class__.__name__,
            status=status.value,
            retry_after_seconds=interval.total_seconds(),
        )

    @staticmethod
    def _needs_refresh(
        bookmark: BookmarkRead, cached: BookmarkMetadataRecord | None
    ) -> bool:
        return (
            cached is None
            or cached.source_url != bookmark.url
            or _as_utc(cached.retry_after) <= datetime.now(UTC)
        )

    def _refresh_and_release(self, bookmark: BookmarkRead, generation: int) -> None:
        try:
            self._refresh_with_generation(bookmark, generation)
        finally:
            with self._lock:
                self._pending.discard(bookmark.id)
                self._active_generation.pop(bookmark.id, None)

    def _store_asset(
        self, bookmark_id: int, kind: str, content: bytes | None
    ) -> str | None:
        filename = f"{bookmark_id}-{kind}.png"
        path = self._cache_path / filename
        if content is None:
            # Removing a stale cache file is best effort. It must not stop
            # the caller from recording a failure and its retry backoff.
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                _LOGGER.warning(
                    "bookmark_metadata_asset_not_removed",
                    bookmark_id=bookmark_id,
                    reason=error.__class__.__name__,
                )
            return None
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
        return filename


def _next_retry_after_failure(
    cached: BookmarkMetadataRecord | None, bookmark: BookmarkRead
) -> timedelta:
    """Return a progressively longer backoff for repeated failures.

    The backoff doubles from `_RETRY_AFTER_FAILURE` up to
    `_MAX_RETRY_AFTER_FAILURE`, derived from the previous cached interval
    (`retry_after` minus `refreshed_at`) because this schema has no
    dedicated failure-count column.
    """
    if (
        cached is not None
        and cached.source_url == bookmark.url
        and cached.status is not MetadataStatus.READY
    ):
        previous_interval = _as_utc(cached.retry_after) - _as_utc(cached.refreshed_at)
        if previous_interval > timedelta(0):
            return min(previous_interval * 2, _MAX_RETRY_AFTER_FAILURE)
    return _RETRY_AFTER_FAILURE


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def generated_domain_icon(url: str) -> str:
    """Return a local SVG fallback icon for one bookmark domain."""
    hostname = urlsplit(url).hostname or "?"
    letter = html.escape(hostname.removeprefix("www.")[:1].upper() or "?")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="12" fill="#e4e0d3"/>'
        f'<text x="32" y="42" text-anchor="middle" font-family="sans-serif" '
        f'font-size="34" font-weight="700" fill="#35584d">{letter}</text></svg>'
    )
