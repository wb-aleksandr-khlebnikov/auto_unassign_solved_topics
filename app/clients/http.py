from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config.settings import RetrySettings

logger = logging.getLogger(__name__)


class RetryableHttpError(Exception):
    pass


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, RetryableHttpError):
        return True
    return False


def _before_sleep(retry_state: RetryCallState) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "http_retry attempt=%s error=%s",
        retry_state.attempt_number,
        str(exc) if exc else "unknown",
    )


class HttpClient:
    def __init__(self, base_url: str, headers: dict[str, str], retry: RetrySettings):
        self._retry = retry
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=retry.timeout_seconds,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await self._request_with_retry(method, path, params=params, json_body=json_body)
        if response.status_code >= 400:
            text = response.text[:1000]
            raise RuntimeError(f"HTTP {response.status_code} on {path}: {text}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected JSON type for {path}")
        return payload

    async def request_status(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> int:
        response = await self._request_with_retry(method, path, params=params, json_body=json_body)
        return response.status_code

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
    ) -> httpx.Response:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_is_retryable_exception),
            stop=stop_after_attempt(self._retry.max_retries),
            wait=wait_exponential(
                multiplier=self._retry.backoff_base,
                max=self._retry.backoff_max,
            ),
            before_sleep=_before_sleep,
            reraise=True,
        ):
            with attempt:
                response = await self._client.request(method, path, params=params, json=json_body)
                if response.status_code in {429, 502, 503}:
                    raise RetryableHttpError(f"Retryable status {response.status_code}")
                return response
        raise RuntimeError("Retry exhausted")


def build_discourse_headers(api_key: str, api_username: str) -> dict[str, str]:
    return {
        "Api-Key": api_key,
        "Api-Username": api_username,
        "Content-Type": "application/json",
    }
