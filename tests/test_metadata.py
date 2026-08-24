"""Bookmark metadata security and cache tests."""

import socket
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

import pytest
from PIL import Image

import link_hoarder.core.metadata as metadata_module
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
from link_hoarder.core.models import BookmarkCreate, MetadataStatus
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

    def request(url: str, *, max_bytes: int, accept: str) -> RemoteResponse:
        del max_bytes, accept
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
