# 0003 — Testing UI variants

## Status

superseded by 0004

## Implemented

not-started

## Context

Each UI redesign change needs a separate test branch. The current Docker stack serves one frontend on port 8080.

A tester needs to compare the stable UI with one staging UI. The selected UI must remain active during the browser session.
Both UIs must use the same API and bookmark data.

## Decision

Run stable and staging frontend containers at the same time. Run a reverse proxy on port 8080 in front of both containers.

Route each request with the `link_hoarder_variant` session cookie. Accept `stable` and `staging` as the only values.
Use the stable frontend when the cookie is absent or invalid.

Accept a valid `version` query parameter as an explicit selection. Set the session cookie after an explicit selection.
Add a UI control that reloads the application with the selected version.

Use one API container and one data volume for both frontend containers. Limit this routing mode to local redesign tests.
Build the stable image only when the accepted baseline changes. Build the staging image from the active redesign branch.

## Consequences

A tester can change variants without a second port or browser profile. The session cookie keeps the selected variant until the
browser session ends or the tester selects a different variant.

Both variants change the same bookmark data. This design compares frontend behavior, not isolated data changes.

The stack uses more memory because it runs two frontend containers and one proxy container. The stable image can become stale
unless the tester rebuilds it after accepting a redesign.

## Alternatives considered

- **Separate ports** — This option makes comparison simple, but it does not test session routing through one application URL.
- **Random assignment** — This option prevents the tester from selecting a specific variant.
- **Browser-local storage only** — The proxy cannot read browser-local storage before it selects an upstream service.
- **Separate API and data stacks** — This option isolates data, but it does not compare both UIs against the same state.

## Changelog

None.
