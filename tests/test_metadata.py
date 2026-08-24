"""Bookmark metadata security and cache tests.

Test plan
=========

core-metadata-scheduling (bounded, prioritized queue):
- primary: `queue_refresh_many` and `asset_availability` each issue exactly
  one `list_metadata` call for a batch.
- alternate: `queue_backfill` uses the smaller backfill cap and does not
  starve `queue_refresh`/`queue_refresh_many` (reserved headroom for
  visible work).
- edge: a burst larger than the cap drops the excess and logs a warning,
  without growing the pending set past the cap.
- negative: a `javascript:` bookmark is never queued at all.

core-metadata-failure-cache (normalized errors + backoff):
- primary: each hostile/malformed URL (empty host, over-long host, empty
  label, IDNA-invalid, control characters) records a FAILED/BLOCKED row
  with a future `retry_after` instead of raising past `refresh`.
- alternate: an unexpected non-`MetadataFetchError` exception from the
  fetcher still records a backed-off row (fail-safe path).
- edge: repeated failures back off progressively (doubling) and cap at
  the maximum interval instead of growing forever.
- negative: a fresh cached row (status READY) is not treated as a prior
  failure, so the next failure starts back at the base interval.

core-metadata-retirement (generation-scoped retirement):
- primary: `purge_assets` stops an in-flight refresh for the purged id
  from writing a metadata row or files.
- alternate: a new bookmark that reuses a purged id refreshes normally
  (no permanent suppression).
- edge: `purge_assets` with no in-flight work for that id is a no-op
  beyond deleting cached files (no generation entry created).
"""

import socket
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from io import BytesIO
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

import pytest
import structlog.testing
from PIL import Image

import link_hoarder.core.metadata as metadata_module
from link_hoarder.core.backend import BookmarkStorageError
from link_hoarder.core.metadata import (
    BookmarkMetadataService,
    FetchedMetadata,
    MetadataBlockedError,
    MetadataFetchError,
    RemoteResponse,
    SecureMetadataFetcher,
    _sanitize_image,
    _validated_destination,
    generated_domain_icon,
)
from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkMetadataRecord,
    MetadataStatus,
)
from link_hoarder.core.repository import BookmarkRepository


class SuccessfulFetcher:
    """Return deterministic sanitized image candidates."""

    def __init__(self, image: bytes) -> None:
        self.image = image
        self.calls = 0

    def fetch(self, url: str) -> FetchedMetadata:
        """Return the configured image for both presentation assets."""
        del url
        self.calls += 1
        return FetchedMetadata(favicon=self.image, thumbnail=self.image)


class FailedFetcher:
    """Reject each metadata request without network access."""

    def fetch(self, url: str) -> FetchedMetadata:
        """Raise a bounded remote fetch failure."""
        del url
        raise MetadataFetchError("Unavailable")


class CrashingFetcher:
    """Raise an exception outside the metadata error hierarchy."""

    def fetch(self, url: str) -> FetchedMetadata:
        """Raise an exception `refresh` did not anticipate."""
        del url
        raise RuntimeError("boom")


class BlockingFetcher:
    """Block each fetch until released, to hold work in the pending set."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.requested_urls: list[str] = []

    def fetch(self, url: str) -> FetchedMetadata:
        """Record the request, then block until the test releases it."""
        self.requested_urls.append(url)
        self.release.wait(timeout=5)
        return FetchedMetadata()


def _wait_until(predicate: Callable[[], bool], *, timeout: float = 5.0) -> bool:
    """Poll a predicate until it is true or the timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class CountingRepository(BookmarkRepository):
    """Repository that counts calls to `list_metadata`."""

    def __init__(self, database_url: str) -> None:
        super().__init__(database_url)
        self.list_metadata_calls = 0

    def list_metadata(
        self, bookmark_ids: Sequence[int]
    ) -> dict[int, BookmarkMetadataRecord]:
        """Delegate to the base implementation while counting invocations."""
        self.list_metadata_calls += 1
        return super().list_metadata(bookmark_ids)


def _counting_repository(tmp_path: Path) -> CountingRepository:
    """Create a counting repository at an isolated database path."""
    resolved = (tmp_path / "bookmarks.db").expanduser().resolve()
    repository = CountingRepository(f"sqlite:///{resolved.as_posix()}")
    repository.initialize()
    return repository


def _png(width: int = 20, height: int = 10) -> bytes:
    image = Image.new("RGB", (width, height), "#245c4a")
    output = BytesIO()
    image.save(output, format="PNG", pnginfo=None)
    return output.getvalue()


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@example.com",
        "https://example.com:8443",
        "file:///etc/passwd",
    ],
)
def test_metadata_destination_rejects_unsafe_urls(url: str) -> None:
    """Given credentials, a restricted port, or a non-HTTP URL, validation blocks it."""
    with pytest.raises(MetadataBlockedError):
        _validated_destination(url)


def test_metadata_destination_rejects_non_public_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given a destination with a private address, validation blocks the connection."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, type: [(socket.AF_INET, type, 6, "", ("127.0.0.1", port))],
    )

    with pytest.raises(MetadataBlockedError):
        _validated_destination("https://example.com")


def test_metadata_destination_uses_a_validated_public_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given one public DNS result, validation returns that address for the connection."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, type: [
            (socket.AF_INET, type, 6, "", ("93.184.216.34", port))
        ],
    )

    _, address, port = _validated_destination("https://example.com/path")

    assert address == "93.184.216.34"
    assert port == 443


def test_image_sanitization_reencodes_and_bounds_dimensions() -> None:
    """Given a supported image, sanitization emits a bounded PNG without source bytes."""
    source = _png(200, 100)

    sanitized = _sanitize_image(source, maximum_size=(40, 40))

    assert sanitized != source
    with Image.open(BytesIO(sanitized)) as image:
        assert image.format == "PNG"
        assert image.size == (40, 20)


def test_image_sanitization_rejects_untrusted_formats() -> None:
    """Given SVG bytes, sanitization rejects the remote image instead of serving it."""
    with pytest.raises(MetadataBlockedError):
        _sanitize_image(
            b"<svg xmlns='http://www.w3.org/2000/svg'/>", maximum_size=(40, 40)
        )


def test_image_sanitization_rejects_oversized_dimensions() -> None:
    """Given an oversized decoded image, sanitization rejects it before output."""
    with pytest.raises(MetadataBlockedError):
        _sanitize_image(_png(4097, 1), maximum_size=(40, 40))


def test_secure_fetcher_parses_only_selected_head_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given HTML metadata, the fetcher resolves and sanitizes selected head images."""
    fetcher = SecureMetadataFetcher()
    image = _png()
    requested: list[str] = []

    def request(
        url: str,
        *,
        max_bytes: int,
        accept: str,
        allow_truncation: bool = False,
    ) -> RemoteResponse:
        del max_bytes, accept, allow_truncation
        requested.append(url)
        if url == "https://example.com/path":
            return RemoteResponse(
                body=(
                    b'<head><link rel="icon" href="/icon.png">'
                    b'<meta property="og:image" content="preview.png"></head>'
                    b'<body><link rel="icon" href="https://evil.example/icon.png">'
                ),
                content_type="text/html; charset=utf-8",
                final_url=url,
            )
        return RemoteResponse(body=image, content_type="image/png", final_url=url)

    monkeypatch.setattr(fetcher, "_request", request)

    result = fetcher.fetch("https://example.com/path")

    assert requested == [
        "https://example.com/path",
        "https://example.com/icon.png",
        "https://example.com/preview.png",
    ]
    assert result.favicon is not None
    assert result.thumbnail is not None
    assert result.favicon.startswith(b"\x89PNG")


def test_secure_fetcher_validates_each_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given a redirect, the fetcher resolves the new destination before connecting."""
    destinations: list[str] = []
    responses: list[tuple[int, Mapping[str, str], bytes]] = [
        (302, {"location": "https://cdn.example/icon.png"}, b""),
        (200, {"content-type": "image/png"}, _png()),
    ]

    def validate(url: str) -> tuple[SplitResult, str, int]:
        destinations.append(url)
        return urlsplit(url), "93.184.216.34", 443

    def request_once(
        parsed: SplitResult,
        address: str,
        port: int,
        *,
        max_bytes: int,
        accept: str,
        allow_truncation: bool = False,
    ) -> tuple[int, Mapping[str, str], bytes]:
        del parsed, address, port, max_bytes, accept
        return responses.pop(0)

    monkeypatch.setattr(metadata_module, "_validated_destination", validate)
    monkeypatch.setattr(metadata_module, "_request_once", request_once)

    result = SecureMetadataFetcher()._request(
        "https://example.com/icon.png", max_bytes=1024, accept="image/png"
    )

    assert destinations == [
        "https://example.com/icon.png",
        "https://cdn.example/icon.png",
    ]
    assert result.final_url == "https://cdn.example/icon.png"


def test_secure_fetcher_stops_redirect_loops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given too many redirects, the fetcher stops before another connection."""

    def validate(url: str) -> tuple[SplitResult, str, int]:
        return urlsplit(url), "93.184.216.34", 443

    def redirect(
        parsed: SplitResult,
        address: str,
        port: int,
        *,
        max_bytes: int,
        accept: str,
        allow_truncation: bool = False,
    ) -> tuple[int, Mapping[str, str], bytes]:
        del parsed, address, port, max_bytes, accept
        return 302, {"location": "https://example.com/again"}, b""

    monkeypatch.setattr(metadata_module, "_validated_destination", validate)
    monkeypatch.setattr(metadata_module, "_request_once", redirect)

    with pytest.raises(MetadataBlockedError):
        SecureMetadataFetcher()._request(
            "https://example.com", max_bytes=1024, accept="text/html"
        )


def test_metadata_service_stores_assets_and_reuses_fresh_cache(
    repository: BookmarkRepository, tmp_path: Path
) -> None:
    """Given fetched metadata, the service stores assets and skips a fresh refresh."""
    fetcher = SuccessfulFetcher(_png())
    service = BookmarkMetadataService(
        repository,
        tmp_path / "cache",
        fetcher=fetcher,
        enabled=False,
    )
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com/path", title="Example")
    )

    service.refresh(bookmark)
    service.queue_refresh(bookmark)

    cached = repository.get_metadata(bookmark.id)
    assert cached is not None
    assert cached.status is MetadataStatus.READY
    assert service.asset_path(bookmark.id, "favicon") is not None
    assert service.asset_path(bookmark.id, "thumbnail") is not None
    assert fetcher.calls == 1

    service.purge_assets(bookmark.id)

    assert service.asset_path(bookmark.id, "favicon") is None
    assert service.asset_path(bookmark.id, "thumbnail") is None
    service.close()


def test_metadata_service_caches_remote_failures(
    repository: BookmarkRepository, tmp_path: Path
) -> None:
    """Given a remote failure, the service stores a retry time and no image files."""
    service = BookmarkMetadataService(
        repository,
        tmp_path / "cache",
        fetcher=FailedFetcher(),
        enabled=False,
    )
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com", title="Example")
    )

    service.refresh(bookmark)

    cached = repository.get_metadata(bookmark.id)
    assert cached is not None
    assert cached.status is MetadataStatus.FAILED
    assert cached.retry_after > cached.refreshed_at
    assert service.asset_path(bookmark.id, "favicon") is None
    service.close()


def test_generated_domain_icon_contains_no_remote_asset() -> None:
    """Given a bookmark URL, the fallback is a local SVG with the domain initial."""
    icon = generated_domain_icon("https://example.com/path")

    assert ">E</text>" in icon
    assert "http://www.w3.org/2000/svg" in icon
    assert "example.com" not in icon


# -- core-metadata-failure-cache -------------------------------------------


@pytest.mark.parametrize(
    "hostile_url",
    [
        "https://",
        "https://" + "a" * 70 + ".com",
        "https://a..b.com",
        "https://．.com",
        "https://exa\x00mple.com",
    ],
    ids=[
        "empty-host",
        "over-long-host",
        "empty-label",
        "idna-invalid",
        "control-characters",
    ],
)
def test_refresh_records_a_backed_off_row_for_hostile_urls(
    repository: BookmarkRepository, tmp_path: Path, hostile_url: str
) -> None:
    """Given a hostile destination URL, refresh records a FAILED/BLOCKED row instead of raising."""
    service = BookmarkMetadataService(repository, tmp_path / "cache", enabled=False)
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com", title="Example")
    )
    hostile = bookmark.model_copy(update={"url": hostile_url})

    service.refresh(hostile)

    cached = repository.get_metadata(bookmark.id)
    assert cached is not None
    assert cached.status in (MetadataStatus.FAILED, MetadataStatus.BLOCKED)
    assert cached.retry_after > cached.refreshed_at
    assert not service._needs_refresh(hostile, cached)
    service.close()


def test_refresh_records_a_backed_off_row_for_an_unexpected_exception(
    repository: BookmarkRepository, tmp_path: Path
) -> None:
    """Given a fetcher error outside the metadata hierarchy, refresh still backs off."""
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=CrashingFetcher(), enabled=False
    )
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com", title="Example")
    )

    service.refresh(bookmark)

    cached = repository.get_metadata(bookmark.id)
    assert cached is not None
    assert cached.status is MetadataStatus.FAILED
    assert cached.retry_after > cached.refreshed_at
    service.close()


def test_repeated_failures_back_off_progressively_and_cap(
    repository: BookmarkRepository, tmp_path: Path
) -> None:
    """Given repeated failures for one source URL, the backoff doubles and then caps."""
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=FailedFetcher(), enabled=False
    )
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com", title="Example")
    )

    intervals: list[float] = []
    for _ in range(7):
        service.refresh(bookmark)
        cached = repository.get_metadata(bookmark.id)
        assert cached is not None
        interval = (cached.retry_after - cached.refreshed_at).total_seconds()
        intervals.append(interval)

    assert intervals == sorted(intervals)
    assert intervals[1] == pytest.approx(intervals[0] * 2)
    assert intervals[-1] <= metadata_module._MAX_RETRY_AFTER_FAILURE.total_seconds()
    assert intervals[-1] == intervals[-2]
    service.close()


def test_a_fresh_success_resets_the_backoff_to_the_base_interval(
    repository: BookmarkRepository, tmp_path: Path
) -> None:
    """Given a prior success, the next failure starts back at the base interval."""
    service = BookmarkMetadataService(repository, tmp_path / "cache", enabled=False)
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com", title="Example")
    )

    service._fetcher = SuccessfulFetcher(_png())
    service.refresh(bookmark)
    service._fetcher = FailedFetcher()
    service.refresh(bookmark)

    cached = repository.get_metadata(bookmark.id)
    assert cached is not None
    interval = (cached.retry_after - cached.refreshed_at).total_seconds()
    assert interval == pytest.approx(
        metadata_module._RETRY_AFTER_FAILURE.total_seconds()
    )
    service.close()


# -- core-metadata-retirement ------------------------------------------------


def test_purge_assets_cancels_an_in_flight_refresh_for_the_purged_id(
    repository: BookmarkRepository, tmp_path: Path
) -> None:
    """Given an in-flight refresh, purge_assets stops it from writing a row or files."""
    fetcher = BlockingFetcher()
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=fetcher, enabled=True
    )
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com", title="Example")
    )

    service.queue_refresh(bookmark)
    assert _wait_until(lambda: bookmark.url in fetcher.requested_urls)

    service.purge_assets(bookmark.id)
    fetcher.release.set()
    service.close()

    assert repository.get_metadata(bookmark.id) is None
    assert service.asset_path(bookmark.id, "favicon") is None


def test_a_bookmark_id_reused_after_purge_refreshes_normally(
    repository: BookmarkRepository, tmp_path: Path
) -> None:
    """Given a bookmark id reused after purge_assets, the new bookmark refreshes normally."""
    fetcher = SuccessfulFetcher(_png())
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=fetcher, enabled=False
    )
    first = repository.create(
        BookmarkCreate(url="https://example.com/first", title="First")
    )
    service.refresh(first)
    service.purge_assets(first.id)
    repository.delete(first.id)

    second = repository.create(
        BookmarkCreate(url="https://example.com/second", title="Second")
    )
    assert second.id == first.id

    service.refresh(second)

    cached = repository.get_metadata(second.id)
    assert cached is not None
    assert cached.status is MetadataStatus.READY
    assert cached.source_url == second.url
    assert service.asset_path(second.id, "favicon") is not None
    service.close()


def test_purge_assets_with_no_in_flight_work_only_deletes_files(
    repository: BookmarkRepository, tmp_path: Path
) -> None:
    """Given no in-flight refresh for an id, purge_assets deletes files and tracks nothing."""
    service = BookmarkMetadataService(repository, tmp_path / "cache", enabled=False)

    service.purge_assets(999)

    assert service._active_generation == {}
    service.close()


# -- core-metadata-scheduling -------------------------------------------------


def test_queue_refresh_many_issues_one_list_metadata_call(tmp_path: Path) -> None:
    """Given many bookmarks, queue_refresh_many reads cached metadata in one call."""
    repository = _counting_repository(tmp_path)
    try:
        fetcher = SuccessfulFetcher(_png())
        service = BookmarkMetadataService(
            repository, tmp_path / "cache", fetcher=fetcher, enabled=True
        )
        bookmarks = [
            repository.create(
                BookmarkCreate(url=f"https://example.com/{index}", title=f"B{index}")
            )
            for index in range(5)
        ]

        repository.list_metadata_calls = 0
        service.queue_refresh_many(bookmarks)

        assert repository.list_metadata_calls == 1
        service.close()
    finally:
        repository.close()


def test_asset_availability_issues_one_list_metadata_call(tmp_path: Path) -> None:
    """Given many bookmarks, asset_availability reads cached metadata in one call."""
    repository = _counting_repository(tmp_path)
    try:
        fetcher = SuccessfulFetcher(_png())
        service = BookmarkMetadataService(
            repository, tmp_path / "cache", fetcher=fetcher, enabled=False
        )
        bookmarks = [
            repository.create(
                BookmarkCreate(url=f"https://example.com/{index}", title=f"B{index}")
            )
            for index in range(5)
        ]
        for bookmark in bookmarks:
            service.refresh(bookmark)

        repository.list_metadata_calls = 0
        availability = service.asset_availability(bookmarks)

        assert repository.list_metadata_calls == 1
        assert all(item.has_favicon for item in availability.values())
        assert all(item.has_thumbnail for item in availability.values())
        service.close()
    finally:
        repository.close()


def test_asset_availability_reports_false_for_uncached_bookmarks(
    repository: BookmarkRepository, tmp_path: Path
) -> None:
    """Given a bookmark with no cached metadata, availability reports no assets."""
    service = BookmarkMetadataService(repository, tmp_path / "cache", enabled=False)
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com", title="Example")
    )

    availability = service.asset_availability([bookmark])

    assert availability[bookmark.id] == metadata_module.BookmarkAssetAvailability()
    service.close()


def test_a_javascript_bookmark_is_never_queued(
    repository: BookmarkRepository, tmp_path: Path
) -> None:
    """Given a bookmarklet URL, no refresh work is queued for it."""
    fetcher = BlockingFetcher()
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=fetcher, enabled=True
    )
    bookmark = repository.create(
        BookmarkCreate(url="javascript:void(0)", title="Bookmarklet")
    )

    service.queue_refresh(bookmark)
    service.close()

    assert fetcher.requested_urls == []


def test_queue_refresh_many_drops_work_past_the_cap(
    repository: BookmarkRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a burst larger than the cap, the excess is dropped and logged, not queued."""
    monkeypatch.setattr(metadata_module, "_MAX_PENDING_REFRESHES", 2)
    fetcher = BlockingFetcher()
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=fetcher, enabled=True
    )
    bookmarks = [
        repository.create(
            BookmarkCreate(url=f"https://example.com/{index}", title=f"B{index}")
        )
        for index in range(5)
    ]

    with structlog.testing.capture_logs() as logs:
        service.queue_refresh_many(bookmarks)

    # The two accepted tasks are already running (blocked on the fetch),
    # so releasing them lets `close` drain the executor without racing
    # `cancel_futures` against a task that has not started yet.
    assert _wait_until(lambda: len(fetcher.requested_urls) >= 2)
    fetcher.release.set()
    service.close()

    assert len(fetcher.requested_urls) == 2
    dropped_warnings = [
        entry for entry in logs if entry.get("event") == "bookmark_metadata_queue_full"
    ]
    assert len(dropped_warnings) == 3


def test_queue_backfill_reserves_headroom_for_visible_work(
    repository: BookmarkRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given backfill fills its lower cap, a visible refresh is still queued."""
    monkeypatch.setattr(metadata_module, "_MAX_PENDING_REFRESHES", 3)
    monkeypatch.setattr(metadata_module, "_MAX_BACKFILL_PENDING", 2)
    fetcher = BlockingFetcher()
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=fetcher, enabled=True
    )
    bookmarks = [
        repository.create(
            BookmarkCreate(url=f"https://example.com/{index}", title=f"B{index}")
        )
        for index in range(4)
    ]

    service.queue_backfill(bookmarks[:2])
    # The backfill worker is now blocked on its fetch call, so the pending
    # set is stable at the backfill cap before the next calls.
    assert _wait_until(lambda: len(fetcher.requested_urls) >= 1)
    service.queue_backfill([bookmarks[2]])
    service.queue_refresh(bookmarks[3])

    fetcher.release.set()
    # Wait for a freed worker to pick up the reserved visible-work slot
    # before shutting down, so `close` does not race `cancel_futures`
    # against a task that has not started running yet.
    assert _wait_until(lambda: bookmarks[3].url in fetcher.requested_urls)
    service.close()

    assert bookmarks[2].url not in fetcher.requested_urls
    assert bookmarks[3].url in fetcher.requested_urls


def test_purge_assets_cancels_a_direct_refresh(tmp_path: Path) -> None:
    """Given a purge during a direct refresh, no metadata row is written."""
    repository = _counting_repository(tmp_path)
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com/", title="Example")
    )
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=FailedFetcher(), enabled=False
    )

    class PurgingFetcher:
        def fetch(self, url: str) -> FetchedMetadata:
            service.purge_assets(bookmark.id)
            raise MetadataFetchError("The metadata request failed.")

    service._fetcher = PurgingFetcher()  # Simulate a concurrent purge.
    service.refresh(bookmark)

    assert repository.get_metadata(bookmark.id) is None


def test_direct_refresh_leaves_no_retirement_entry(tmp_path: Path) -> None:
    """Given a completed direct refresh, no per-bookmark state is retained."""
    repository = _counting_repository(tmp_path)
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com/", title="Example")
    )
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=FailedFetcher(), enabled=False
    )

    service.refresh(bookmark)

    assert service._active_generation == {}  # Assert no retained state.


def test_storage_failure_is_cached_with_backoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a metadata write failure after a good fetch, the failure is cached."""
    repository = _counting_repository(tmp_path)
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com/", title="Example")
    )
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=SuccessfulFetcher(_png()), enabled=False
    )
    original = repository.save_metadata
    calls = {"n": 0}

    def failing_save(record: BookmarkMetadataRecord) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise BookmarkStorageError("The bookmark metadata could not be stored.")
        original(record)

    monkeypatch.setattr(repository, "save_metadata", failing_save)
    service.refresh(bookmark)

    stored = repository.get_metadata(bookmark.id)
    assert stored is not None
    assert stored.status is MetadataStatus.FAILED
    assert stored.retry_after > stored.refreshed_at


def test_asset_write_failure_is_cached_with_backoff(tmp_path: Path) -> None:
    """Given a cache file write failure, the failure is cached with a backoff."""
    repository = _counting_repository(tmp_path)
    bookmark = repository.create(
        BookmarkCreate(url="https://example.com/", title="Example")
    )
    cache = tmp_path / "cache"
    service = BookmarkMetadataService(
        repository, cache, fetcher=SuccessfulFetcher(_png()), enabled=False
    )
    # Replace the cache directory with a file, so every asset write fails.
    for existing in cache.iterdir():
        existing.unlink()
    cache.rmdir()
    cache.write_text("not a directory", encoding="utf-8")

    service.refresh(bookmark)

    stored = repository.get_metadata(bookmark.id)
    assert stored is not None
    assert stored.status is MetadataStatus.FAILED


def test_backfill_does_not_hold_workers_needed_by_visible_work(tmp_path: Path) -> None:
    """Given a queued backfill, visible refresh work still runs without waiting."""
    repository = _counting_repository(tmp_path)
    backlog = [
        repository.create(
            BookmarkCreate(url=f"https://backlog{index}.example/", title=f"b{index}")
        )
        for index in range(6)
    ]
    visible = repository.create(
        BookmarkCreate(url="https://visible.example/", title="visible")
    )
    fetcher = BlockingFetcher()
    service = BookmarkMetadataService(
        repository, tmp_path / "cache", fetcher=fetcher, enabled=True
    )
    try:
        service.queue_backfill(backlog)
        assert _wait_until(lambda: len(fetcher.requested_urls) >= 1)
        service.queue_refresh(visible)

        assert _wait_until(
            lambda: "https://visible.example/" in fetcher.requested_urls
        ), "Visible work waited behind backfill work."
    finally:
        fetcher.release.set()
        service.close()
