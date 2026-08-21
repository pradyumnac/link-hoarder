"""Generate the committed OpenAPI contract."""

import json
import tempfile
from pathlib import Path

from pydantic import SecretStr

from link_hoarder.api.app import create_app
from link_hoarder.core.config import Settings

_CONTRACT_PATH = Path("docs/openapi.json")


def contract_json() -> str:
    """Return the stable OpenAPI contract as formatted JSON."""
    with tempfile.TemporaryDirectory() as temporary:
        app = create_app(
            Settings(
                database_path=Path(temporary) / "contract.db",
                api_key=SecretStr("contract-key"),
            )
        )
        return f"{json.dumps(app.openapi(), indent=2, sort_keys=True)}\n"


def main() -> None:
    """Write the OpenAPI contract to its documentation path."""
    _CONTRACT_PATH.write_text(contract_json(), encoding="utf-8")


if __name__ == "__main__":
    main()
