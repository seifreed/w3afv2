"""HTTP providers for local and hosted language models."""

import json
import os
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlsplit

MAX_PROVIDER_RESPONSE_BYTES = 2_000_000


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider cannot answer a request."""


@dataclass(frozen=True)
class LLMAnswer:
    """Normalized answer returned by a provider."""

    content: str
    provider: str
    model: str


class HTTPProvider:
    """Small provider adapter using only the standard library."""

    def __init__(
        self, name: str, model: str, base_url: str, api_key: str, timeout: int
    ):
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def complete(self, prompt: str) -> LLMAnswer:
        url, payload, headers = self._request_data(prompt)
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise LLMProviderError("LLM provider URL must use HTTP or HTTPS")
        connection_class = (
            HTTPSConnection if parts.scheme == "https" else HTTPConnection
        )
        connection = connection_class(parts.netloc, timeout=self.timeout)
        try:
            connection.request(
                "POST",
                parts.path + (f"?{parts.query}" if parts.query else ""),
                body=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", **headers},
            )
            response = connection.getresponse()
            if response.status >= 400:
                raise LLMProviderError(f"LLM provider returned HTTP {response.status}")
            with response:
                data = json.loads(
                    response.read(MAX_PROVIDER_RESPONSE_BYTES).decode("utf-8")
                )
        except (TimeoutError, OSError, ValueError) as exc:
            raise LLMProviderError(f"LLM provider {self.name} failed: {exc}") from exc
        finally:
            connection.close()

        content = self._content_from_response(data)
        return LLMAnswer(content, self.name, self.model)

    def _request_data(self, prompt: str) -> tuple[str, dict, dict[str, str]]:
        if self.name == "ollama":
            return (
                f"{self.base_url}/api/generate",
                {"model": self.model, "prompt": prompt, "stream": False},
                {},
            )
        if self.name == "gemini":
            return (
                f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}",
                {"contents": [{"parts": [{"text": prompt}]}]},
                {},
            )
        if self.name == "anthropic":
            return (
                f"{self.base_url}/messages",
                {
                    "model": self.model,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
                {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            )
        endpoint = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        return (
            endpoint,
            {
                "model": self.model,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            },
            headers,
        )

    def _content_from_response(self, data: dict) -> str:
        try:
            if self.name == "ollama":
                return data["response"]
            if self.name == "gemini":
                return data["candidates"][0]["content"]["parts"][0]["text"]
            if self.name == "anthropic":
                return data["content"][0]["text"]
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("LLM provider returned an invalid response") from exc


DEFAULTS = {
    "ollama": ("llama3.2", "http://127.0.0.1:11434"),
    "lmstudio": ("local-model", "http://127.0.0.1:1234/v1"),
    "grok": ("grok-3-mini", "https://api.x.ai/v1"),
    "gemini": ("gemini-2.5-flash", "https://generativelanguage.googleapis.com/v1beta"),
    "openai": ("gpt-4o-mini", "https://api.openai.com/v1"),
    "anthropic": ("claude-3-5-haiku-latest", "https://api.anthropic.com/v1"),
}


def provider_from_configuration(configuration) -> HTTPProvider | None:
    """Build the configured provider, or return ``None`` when disabled."""
    name = configuration.get("llm_provider") or os.getenv("W3AF_LLM_PROVIDER", "")
    if not name:
        return None
    name = name.lower()
    if name not in DEFAULTS:
        raise LLMProviderError(f"Unsupported LLM provider: {name}")
    default_model, default_url = DEFAULTS[name]
    model = configuration.get("llm_model") or os.getenv("W3AF_LLM_MODEL", default_model)
    base_url = configuration.get("llm_base_url") or os.getenv(
        "W3AF_LLM_BASE_URL", default_url
    )
    api_key = os.getenv(
        f"W3AF_LLM_{name.upper()}_API_KEY", os.getenv("W3AF_LLM_API_KEY", "")
    )
    timeout = int(configuration.get("llm_timeout") or 60)
    return HTTPProvider(name, model, base_url, api_key, timeout)
