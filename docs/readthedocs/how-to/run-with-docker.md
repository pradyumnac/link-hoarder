# Run with Docker Compose

Copy the environment template and set a long random API key.

```console
cp stack/.env.example stack/.env
docker compose --env-file stack/.env -f stack/compose.yaml up --build -d
```

Windows PowerShell users can run this command:

```powershell
Copy-Item stack/.env.example stack/.env
docker compose --env-file stack/.env -f stack/compose.yaml up --build -d
```

The stack binds the API to `127.0.0.1:8000`. The named volume stores the SQLite database.
