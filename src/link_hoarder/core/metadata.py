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
from dataclasses import dataclass
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
_MAX_REDIRECTS = 5
_REFRESH_AFTER = timedelta(days=7)
_RETRY_AFTER_FAILURE = timedelta(hours=1)
_MAX_RETRY_AFTER_FAILURE = timedelta(hours=24)
_ALLOWED_IMAGE_FORMATS = frozenset({"GIF", "ICO", "JPEG", "PNG", "WEBP"})
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
# Link relations that can name a site icon. A site often declares several,
# and the first one is not always an image this application can decode.
_ICON_RELATIONS = frozenset(
    {"icon", "shortcut", "apple-touch-icon", "apple-touch-icon-precomposed"}
)

# Hard cap on the total number of bookmarks with queued or in-flight
# refresh work. Bulk backlog work (`queue_backfill`) may only fill a
# fraction of this cap, so visible-bookmark work (`queue_refresh`,
# `queue_refresh_many`) always has reserved headroom to run without being
# crowded out by a large import or collection scan.
_MAX_PENDING_REFRESHES = 200
_MAX_BACKFILL_PENDING = 100

# Bound on the in-process backoff kept for a bookmark whose failure record
# could not be written to the database (`core-metadata-failure.memory`).
# Without this cap, a bookmark stuck failing both the metadata write and the
# failure-record write would grow the map forever. Sized well above the
# pending-work caps above, because a failing database can back up more ids
# than are ever queued at once.
_MAX_FAILURE_BACKOFF_ENTRIES = 1000

# Sweep cadence for the idle-backlog sweeper (`core-metadata-backfill.sweep`).
# A batch is queued as bulk backlog work, so it never crowds out visible
# work; see `queue_backfill`. A full batch means the backlog likely still
# has more rows, so the next sweep follows almost immediately. An empty
# batch means the backlog is drained, so the sweeper backs off to a slow
# idle poll instead of hammering the database on a live system.
_SWEEP_BATCH_SIZE = 200
_SWEEP_ACTIVE_POLL_SECONDS = 1.0
_SWEEP_IDLE_POLL_SECONDS = 300.0

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
        self.favicon_urls: list[str] = []
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
            relations = set(values.get("rel", "").lower().split())
            href = values.get("href")
            if href and relations & _ICON_RELATIONS:
                self.favicon_urls.append(href)
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
        # A large page is read up to the byte limit and then parsed. The
        # head holds every value this fetcher needs and comes first, so a
        # long body must not discard the whole response.
        page = self._request(
            url,
            max_bytes=_MAX_HTML_BYTES,
            accept="text/html",
            allow_truncation=True,
        )
        if "html" not in page.content_type.lower():
            raise MetadataFetchError("The bookmark did not return HTML.")
        parser = _HeadMetadataParser()
        parser.feed(page.body.decode("utf-8", errors="replace"))

        candidates = [
            urljoin(page.final_url, candidate)
            for candidate in _ordered_icon_candidates(parser.favicon_urls)
        ]
        candidates.append(urljoin(page.final_url, "/favicon.ico"))
        thumbnail_url = (
            urljoin(page.final_url, parser.thumbnail_url)
            if parser.thumbnail_url
            else None
        )
        favicon = self._first_available_image(candidates, maximum_size=(128, 128))
        thumbnail = (
            self._fetch_image(thumbnail_url, maximum_size=(1200, 630))
            if thumbnail_url is not None
            else None
        )
        return FetchedMetadata(favicon=favicon, thumbnail=thumbnail)

    def _first_available_image(
        self, urls: Sequence[str], *, maximum_size: tuple[int, int]
    ) -> bytes | None:
        """Return the first candidate icon this application can decode."""
        for candidate in dict.fromkeys(urls):
            image = self._fetch_image(candidate, maximum_size=maximum_size)
            if image is not None:
                return image
        return None

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

    def _request(
        self,
        url: str,
        *,
        max_bytes: int,
        accept: str,
        allow_truncation: bool = False,
    ) -> RemoteResponse:
        current = url
        for redirect_count in range(_MAX_REDIRECTS + 1):
            parsed, address, port = _validated_destination(current)
            status, headers, body = _request_once(
                parsed,
                address,
                port,
                max_bytes=max_bytes,
                accept=accept,
                allow_truncation=allow_truncation,
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


def _ordered_icon_candidates(hrefs: Sequence[str]) -> list[str]:
    """Order declared icons so decodable raster images come first.

    This application cannot decode SVG, so an SVG icon is tried last. A
    site that declares only an SVG icon still gets its `/favicon.ico`
    fallback from the caller.
    """
    raster = [href for href in hrefs if not _is_svg_href(href)]
    vector = [href for href in hrefs if _is_svg_href(href)]
    return raster + vector


def _is_svg_href(href: str) -> bool:
    return urlsplit(href).path.lower().endswith(".svg")


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
    allow_truncation: bool = False,
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
                if not allow_truncation:
                    raise MetadataBlockedError(
                        "The metadata response exceeded its size limit."
                    )
                chunks[-1] = chunks[-1][: len(chunks[-1]) - (size - max_bytes)]
                break
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
    """Cached thumbnail availability for one bookmark.

    A favicon has no field here. The favicon route always has a safe
    response: a cached file when one exists, or a locally generated SVG
    fallback otherwise (`generated_domain_icon`). No caller branches on
    favicon presence, so checking the filesystem for it up front would be
    pure waste on every collection page.
    """

    model_config = ConfigDict(frozen=True)

    has_thumbnail: bool = False


@dataclass
class _PendingEntry:
    """Bookkeeping for one bookmark's queued or in-flight refresh.

    `token` names the submission that currently owns this entry. A worker
    must match its own token against this field, under the lock, before it
    does any work (`core-metadata-promotion`). A visible request can
    promote a bookmark still queued as backfill by giving the entry a new
    token and switching `backfill` to false; the superseded worker then
    finds a token mismatch and becomes a silent no-op. `claimed` becomes
    true the moment a worker accepts its token, which blocks any later
    promotion, because the real work is already running by then.
    """

    token: int
    backfill: bool
    claimed: bool = False


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

    Promotion (`core-metadata-promotion`): a bookmark already queued for
    backfill, but not yet running, is moved onto the visible executor the
    moment a visible request names it, instead of waiting behind the rest
    of the backfill queue. `_pending` therefore stores a `_PendingEntry`
    per bookmark id, not a bare id, so it can record which queue owns the
    work and whether it has started. Exactly one worker ever does the real
    work for one bookmark id; see `_PendingEntry` and `_submit`.

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

    Undurable-failure backoff (`core-metadata-failure.memory`): if a
    failure cannot even be recorded to the database, `_failure_backoff`
    holds a short-lived in-process retry time for that bookmark id, so
    admission (`_needs_refresh`) does not retry it on every request while
    the database stays unavailable. It is bounded by
    `_MAX_FAILURE_BACKOFF_ENTRIES` and cleared once a durable record is
    written for the id.

    Idle-backlog sweeper (`core-metadata-backfill.sweep`): a daemon thread
    periodically asks the repository for a bounded batch of bookmarks
    needing metadata and queues it through `queue_backfill`, so bookmarks
    with no metadata row are eventually filled even if the user never
    looks at their page. It runs its first sweep immediately at startup,
    stays on `_SWEEP_ACTIVE_POLL_SECONDS` while it keeps finding full
    batches, and backs off to `_SWEEP_IDLE_POLL_SECONDS` once the backlog
    is empty. `queue_backfill`'s existing admission checks make repeated
    sweeps idempotent.
    """

    def __init__(
        self,
        repository: BookmarkRepository,
        cache_path: Path,
        *,
        fetcher: MetadataFetcher | None = None,
        enabled: bool = True,
        sweep_enabled: bool = True,
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
        self._pending: dict[int, _PendingEntry] = {}
        self._pending_token_counter = 0
        self._active_generation: dict[int, int] = {}
        self._failure_backoff: dict[int, datetime] = {}
        self._lock = threading.Lock()
        self._sweep_stop = threading.Event()
        self._sweep_thread: threading.Thread | None = None
        if enabled and sweep_enabled:
            self._sweep_thread = threading.Thread(
                target=self._sweep_loop, name="metadata-sweep", daemon=True
            )
            self._sweep_thread.start()

    def close(self) -> None:
        """Stop queued metadata work during application shutdown."""
        self._sweep_stop.set()
        if self._sweep_thread is not None:
            self._sweep_thread.join(timeout=5.0)
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
            return
        self._clear_failure_backoff(bookmark.id)

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
            existing = self._pending.get(bookmark.id)
            if existing is not None:
                # Only a visible request finding a not-yet-running backfill
                # entry is promotable; every other combination (a duplicate
                # request, or work that has already started) is a no-op.
                promotable = existing.backfill and not backfill and not existing.claimed
                if not promotable:
                    return
                token = self._next_pending_token()
                existing.token = token
                existing.backfill = False
            else:
                if len(self._pending) >= cap:
                    _LOGGER.warning(
                        "bookmark_metadata_queue_full",
                        bookmark_id=bookmark.id,
                        pending=len(self._pending),
                        cap=cap,
                    )
                    return
                token = self._next_pending_token()
                self._pending[bookmark.id] = _PendingEntry(
                    token=token, backfill=backfill
                )
            generation = self._active_generation.get(bookmark.id, 0)
            self._active_generation[bookmark.id] = generation
            target_backfill = self._pending[bookmark.id].backfill
        executor = self._backfill_executor if target_backfill else self._executor
        if executor is not None:
            executor.submit(self._refresh_and_release, bookmark, generation, token)

    def _next_pending_token(self) -> int:
        """Return a fresh submission token. Callers must hold `self._lock`."""
        self._pending_token_counter += 1
        return self._pending_token_counter

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
            self._set_failure_backoff(bookmark.id, now + interval)
            return
        self._clear_failure_backoff(bookmark.id)
        _LOGGER.warning(
            "bookmark_metadata_fetch_failed",
            bookmark_id=bookmark.id,
            reason=error.__class__.__name__,
            status=status.value,
            retry_after_seconds=interval.total_seconds(),
        )

    def _needs_refresh(
        self, bookmark: BookmarkRead, cached: BookmarkMetadataRecord | None
    ) -> bool:
        with self._lock:
            backoff_until = self._failure_backoff.get(bookmark.id)
            if backoff_until is not None:
                if backoff_until > datetime.now(UTC):
                    return False
                # The backoff has expired; evict it now instead of waiting
                # for the next `_set_failure_backoff` sweep.
                del self._failure_backoff[bookmark.id]
        return (
            cached is None
            or cached.source_url != bookmark.url
            or _as_utc(cached.retry_after) <= datetime.now(UTC)
        )

    def _set_failure_backoff(self, bookmark_id: int, retry_after: datetime) -> None:
        """Record an in-process retry time for a failure that could not be persisted.

        Bounded by `_MAX_FAILURE_BACKOFF_ENTRIES`: expired entries are
        evicted first, and a new id is dropped, with a warning, if the map
        is still full afterward.
        """
        with self._lock:
            now = datetime.now(UTC)
            expired = [
                key for key, value in self._failure_backoff.items() if value <= now
            ]
            for key in expired:
                del self._failure_backoff[key]
            if (
                bookmark_id not in self._failure_backoff
                and len(self._failure_backoff) >= _MAX_FAILURE_BACKOFF_ENTRIES
            ):
                _LOGGER.warning(
                    "bookmark_metadata_failure_backoff_full",
                    bookmark_id=bookmark_id,
                    entries=len(self._failure_backoff),
                )
                return
            self._failure_backoff[bookmark_id] = retry_after

    def _clear_failure_backoff(self, bookmark_id: int) -> None:
        with self._lock:
            self._failure_backoff.pop(bookmark_id, None)

    def _refresh_and_release(
        self, bookmark: BookmarkRead, generation: int, token: int
    ) -> None:
        with self._lock:
            entry = self._pending.get(bookmark.id)
            if entry is None or entry.token != token:
                # A visible request promoted this bookmark to the visible
                # executor after this task was queued. The new owner does
                # the work and the cleanup below; this run touches nothing.
                return
            entry.claimed = True
        try:
            self._refresh_with_generation(bookmark, generation)
        finally:
            with self._lock:
                entry = self._pending.get(bookmark.id)
                if entry is not None and entry.token == token:
                    self._pending.pop(bookmark.id, None)
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

    def _sweep_loop(self) -> None:
        """Repeatedly queue backfill work for bookmarks needing metadata.

        Runs on a daemon thread until `close()` sets `_sweep_stop`. The
        first sweep runs immediately, so a fresh start with a large backlog
        does not wait for the idle poll interval before doing anything.
        """
        while not self._sweep_stop.is_set():
            try:
                found = self._sweep_once()
            except Exception as error:  # noqa: BLE001 - the sweeper must never crash
                _LOGGER.error(
                    "bookmark_metadata_sweep_failed", reason=error.__class__.__name__
                )
                found = 0
            self._sweep_stop.wait(_sweep_delay_seconds(found))

    def _sweep_once(self) -> int:
        """Queue one bounded batch of bookmarks needing metadata.

        Returns the batch size, so the caller can decide the next delay.
        Idempotent: `queue_backfill` already skips a bookmark that is
        pending or whose cached metadata is still fresh.
        """
        bookmarks = self._repository.list_needing_metadata(limit=_SWEEP_BATCH_SIZE)
        if bookmarks:
            self.queue_backfill(bookmarks)
        return len(bookmarks)


def _sweep_delay_seconds(found: int) -> float:
    """Return the sweep wait after a batch of `found` bookmarks was queued.

    A full batch means the backlog likely still has more rows, so the next
    sweep should follow almost immediately. Anything less means the
    backlog is drained for now, so the sweeper backs off to the idle poll.
    """
    return (
        _SWEEP_ACTIVE_POLL_SECONDS
        if found >= _SWEEP_BATCH_SIZE
        else _SWEEP_IDLE_POLL_SECONDS
    )


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
