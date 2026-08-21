# Run with Docker Compose

Copy the optional environment template.

```console
cp stack/.env.example stack/.env
mise run stack-up
```

Windows PowerShell users can run this command:

```powershell
Copy-Item stack/.env.example stack/.env
mise run stack-up
```

Open `http://127.0.0.1:8080`. Set `LINK_HOARDER_PORT` in `stack/.env` to use a different port.

The API container generates a random API key during its first start. The secret volume keeps the key across container restarts. The frontend proxy adds the key to API requests. Browser JavaScript cannot read the key.

Set `LINK_HOARDER_API_KEY` in `stack/.env` only when you must supply your own key.
The data volume stores the SQLite database.

Run the stack in the foreground during development:

```console
mise run serve-web
```

Stop the stack:

```console
mise run stack-down
```
