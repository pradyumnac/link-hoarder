# A/B Switching

Use this workflow only to test one UI redesign branch against the accepted UI.
The A/B stack is disabled by default.

## Enable A/B switching

Copy the environment template if `stack/.env` does not exist:

```console
cp stack/.env.example stack/.env
```

Set this value in `stack/.env`:

```dotenv
LINK_HOARDER_AB_ENABLED=true
```

Start the stack:

```console
mise run stack-up
```

The stack runs stable and staging frontend containers. A reverse proxy serves both variants on port 8080.
Both variants use the same API and bookmark database.

## Select a variant

Open `http://127.0.0.1:8080`. Use the **Test UI** control in the top bar.
The proxy keeps the selection during the current browser session.
The proxy sets the cookie, then redirects to a clean URL before it loads UI assets.

You can also select a variant with a URL:

```text
http://127.0.0.1:8080/?version=stable
http://127.0.0.1:8080/?version=staging
```

The proxy uses the stable UI when the selection is missing or invalid.

## Test one redesign

Create one branch from the accepted baseline:

```console
git switch main
git switch -c ui/short-change-name
```

Make one UI change. Deploy the active branch to staging:

```console
mise run ab-stage
```

Switch between **Stable** and **Staging** in the top bar.
Verify both selections and their assets:

```console
mise run ab-check
```

Do not compare data mutations because both variants use the same database.

Reset staging when you reject the change:

```console
mise run ab-reset
```

Merge an accepted branch into `main`. Then update the stable image:

```console
git switch main
mise run ab-promote
```

Create the next redesign branch after the accepted change is on `main`.

## Disable A/B switching

Set this value in `stack/.env`:

```dotenv
LINK_HOARDER_AB_ENABLED=false
```

Restart the stack:

```console
mise run stack-down
mise run stack-up
```

The normal stack runs one frontend container. The normal UI does not contain the variant switcher.
A/B deployment tasks stop with an error while the feature flag is false.

See [Configuration](../reference/configuration.md#ui-variant-session) for the session cookie details.
