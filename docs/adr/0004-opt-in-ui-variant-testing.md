# 0004 — Opt-in UI variant testing

## Status

accepted

## Implemented

not-started

## Context

ADR 0003 adds stable and staging frontend containers for local UI tests. The normal Docker workflow must not start test
services or show test controls by default.

Operators need an explicit feature flag in `stack/.env`. The sample setting must keep A/B switching disabled.

## Decision

Keep the normal single-frontend Docker stack as the default. Put the A/B proxy and two frontend services in a separate Compose
file.

Enable the A/B stack only when `LINK_HOARDER_AB_ENABLED=true`. Use `false` as the sample and implicit default value.
Reject A/B deployment commands when the flag is not `true`.

Compile the UI variant switcher only into A/B frontend images. Do not show the switcher in the normal frontend image.

Use the routing, cookie, shared API, and branch workflow from ADR 0003 only while the feature flag is active.

## Consequences

A normal stack start keeps one frontend container and has no A/B controls. An operator must edit `stack/.env` before any A/B
service can start through a mise task.

The project must maintain normal and A/B Compose files. The stack helper must select one file from the feature flag.

## Alternatives considered

- **Enable A/B mode by default** — This option can expose test controls and extra containers to users who do not need them.
- **Use a top-bar control as the only opt-in** — This option starts all test services before the user gives consent.
- **Use separate host ports** — This option removes session routing and does not meet the single-URL test requirement.

## Changelog

None.
