"""Synchronous HTTP bookmark backend for the CLI."""

import json
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, HttpUrl, SecretStr, ValidationError

from link_hoarder.core.backend import (
    BookmarkBackendError,
    DuplicateBookmarkError,
)
from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkPage,
    BookmarkRead,
    BookmarkUpdate,
)


class ApiErrorDetail(BaseModel):
    """Validated API error response."""

    detail: str


class ApiResponseError(BookmarkBackendError):
    """The API returned an unsuccessful HTTP status."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ApiBookmarkBackend:
    """Access bookmark operations through the versioned HTTP API."""

    def __init__(self, api_url: HttpUrl, api_key: SecretStr, timeout: float) -> None:
        self._base_url = f"{str(api_url).rstrip('/')}/api/v1"
        self._api_key = api_key.get_secret_value()
        self._timeout = timeout

    def create(self, bookmark: BookmarkCreate) -> BookmarkRead:
        """Create one bookmark."""
        try:
            response = self._request(
                "POST",
                "/bookmarks",
                bookmark.model_dump(mode="json"),
            )
        except ApiResponseError as error:
            if error.status_code == 409:
                raise DuplicateBookmarkError(bookmark.url) from error
            raise
        return self._validate(BookmarkRead, response)

    def get(self, bookmark_id: int) -> BookmarkRead | None:
        """Get one bookmark by identifier."""
        try:
            response = self._request("GET", f"/bookmarks/{bookmark_id}")
        except ApiResponseError as error:
            if error.status_code == 404:
                return None
            raise
        return self._validate(BookmarkRead, response)

    def find_by_url(self, url: str) -> BookmarkRead | None:
        """Get one bookmark by its normalized URL."""
        query = urlencode({"url": url})
        try:
            response = self._request("GET", f"/bookmarks/by-url?{query}")
        except ApiResponseError as error:
            if error.status_code == 404:
                return None
            raise
        return self._validate(BookmarkRead, response)

    def list(
        self, *, query: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[BookmarkRead]:
        """List bookmarks with optional search and pagination."""
        parameters: dict[str, str | int] = {"limit": limit, "offset": offset}
        if query is not None:
            parameters["query"] = query
        response = self._request("GET", f"/bookmarks?{urlencode(parameters)}")
        return self._validate(BookmarkPage, response).items

    def update(self, bookmark_id: int, update: BookmarkUpdate) -> BookmarkRead | None:
        """Update one bookmark."""
        try:
            response = self._request(
                "PATCH",
                f"/bookmarks/{bookmark_id}",
                update.model_dump(mode="json", exclude_unset=True),
            )
        except ApiResponseError as error:
            if error.status_code == 404:
                return None
            if error.status_code == 409:
                raise DuplicateBookmarkError(
                    update.url or "the supplied URL"
                ) from error
            raise
        return self._validate(BookmarkRead, response)

    def delete(self, bookmark_id: int) -> bool:
        """Delete one bookmark."""
        try:
            self._request("DELETE", f"/bookmarks/{bookmark_id}")
        except ApiResponseError as error:
            if error.status_code == 404:
                return False
            raise
        return True

    def close(self) -> None:
        """Release backend resources."""

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
    ) -> object | None:
        data = None
        headers = {
            "Accept": "application/json",
            "X-API-Key": self._api_key,
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self._base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                content = response.read()
        except HTTPError as error:
            detail = self._error_detail(error)
            raise ApiResponseError(error.code, detail) from error
        except (OSError, URLError) as error:
            raise BookmarkBackendError(
                f"The Link Hoarder API is unavailable: {error.reason if isinstance(error, URLError) else error}"
            ) from error
        if not content:
            return None
        try:
            payload: object = json.loads(content)
            return payload
        except (JSONDecodeError, UnicodeDecodeError) as error:
            raise BookmarkBackendError(
                "The Link Hoarder API returned invalid JSON."
            ) from error

    @staticmethod
    def _error_detail(error: HTTPError) -> str:
        try:
            content = error.read()
            payload: object = json.loads(content)
            return ApiErrorDetail.model_validate(payload).detail
        except JSONDecodeError, UnicodeDecodeError, ValidationError:
            return f"The Link Hoarder API returned HTTP {error.code}."

    @staticmethod
    def _validate[ModelT: BaseModel](
        model: type[ModelT], payload: object | None
    ) -> ModelT:
        try:
            return model.model_validate(payload)
        except ValidationError as error:
            raise BookmarkBackendError(
                "The Link Hoarder API returned an invalid response."
            ) from error
