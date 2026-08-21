# Security policy

## Report a vulnerability

Do not open a public issue for a vulnerability. Use the GitHub private vulnerability report for this repository.

## Deployment

Keep the API key secret. Use a key with at least 32 characters.
Bind the direct API to loopback. Use TLS through a secure reverse proxy for remote access.

The Docker stack binds only the frontend proxy to loopback. It generates a persistent
API key and keeps the API container on an internal network. The proxy adds request
limits and browser security headers.

Do not publish the API container port from Docker Compose. The API key does not
provide user accounts or authorization levels.

## Uploads

The API accepts browser profile uploads up to 16 MiB. It does not accept server-local
profile paths. Keep browser profiles private because they can contain browsing data.
