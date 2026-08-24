# 0005 — Bookmark metadata cache

## Status

accepted

## Implemented

in-progress

## Context

Bookmark cards need site icons, concise link text, and optional thumbnail previews. The browser must not contact every
bookmarked site when the collection loads.

A server-side fetcher can expose internal services through server-side request forgery. Remote HTML and images are untrusted
content. The application must also work when a site is unavailable or has no useful metadata.

## Decision

Show the domain and a shortened path on each bookmark card. Hide the protocol, query, fragment, and trailing slash from the
card text. Keep the complete URL as the link target and accessible text.

Fetch favicons and Open Graph images through the API. Do not load remote metadata directly in the browser. Serve cached images
from same-origin endpoints that use bookmark identifiers or opaque cache keys.

Store metadata records in SQLite. Store sanitized image files in the application data directory. Refresh stale entries in the
background. Cache failures for a limited period. Use a generated domain icon when no cached favicon is available. Show
thumbnails in gallery view only.

Apply these controls to each remote request:

- Permit HTTP and HTTPS on ports 80 and 443 only.
- Reject credentials and non-public IPv4 and IPv6 destinations.
- Resolve and validate the destination before each connection.
- Validate each redirect target and limit the redirect count.
- Send no cookies, authorization headers, or user request headers.
- Limit connection time, total time, response bytes, and decoded image dimensions.
- Parse only the HTML head and do not run JavaScript.
- Verify image content, decode it, remove metadata, and encode a safe raster image.
- Do not pass remote SVG or image bytes directly to the browser.

Record blocked and failed fetches with structured logs. Do not make bookmark creation or import fail when metadata fetching
fails.

## Consequences

Bookmark cards can show useful identity and preview information without exposing browser activity to bookmarked sites. Cached
assets continue to work when remote sites are slow or offline.

The API gains an outbound network boundary that needs security tests and resource limits. The project needs metadata storage,
cache cleanup, background refresh behavior, and image processing. Container deployments need a writable cache directory.

Gallery cards can use thumbnails. List rows stay compact. A missing icon or thumbnail uses a local fallback and does not create
an empty visual region.

## Alternatives considered

- **Load remote icons and thumbnails in the browser** — This option exposes the user address and viewing activity to remote
  sites. It also makes rendering depend on remote availability.
- **Use a public favicon or preview service** — This option sends the bookmark domains to another provider and adds an external
  availability dependency.
- **Use generated icons only** — This option avoids remote requests but does not provide recognizable site identity or preview
  images.
- **Render full-page screenshots** — This option needs a browser runtime, uses more resources, and increases the attack surface.

## Changelog

None.
