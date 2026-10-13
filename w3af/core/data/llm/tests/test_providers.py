"""Provider tests using a real local HTTP server."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from w3af.core.data.kb.config import Config
from w3af.core.data.llm.providers import (
    LLMProviderError,
    provider_from_configuration,
)


class ProviderHandler(BaseHTTPRequestHandler):
    """Return the response shape used by each provider family."""

    def do_POST(self):
        size = int(self.headers["Content-Length"])
        json.loads(self.rfile.read(size))
        if self.path.endswith("/generate"):
            payload = {"response": "ollama answer"}
        elif self.path.endswith("/messages"):
            payload = {"content": [{"text": "anthropic answer"}]}
        elif ":generateContent" in self.path:
            payload = {
                "candidates": [{"content": {"parts": [{"text": "gemini answer"}]}}]
            }
        else:
            payload = {"choices": [{"message": {"content": "openai answer"}}]}
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


class ProviderTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.addCleanup(self.thread.join)
        self.addCleanup(self.server.shutdown)

    def configuration(self, provider):
        configuration = Config()
        configuration.save("llm_provider", provider)
        configuration.save("llm_model", "test-model")
        configuration.save(
            "llm_base_url", f"http://127.0.0.1:{self.server.server_port}"
        )
        configuration.save("llm_timeout", 2)
        return configuration

    def test_supported_providers(self):
        for provider in ("ollama", "lmstudio", "grok", "gemini", "openai", "anthropic"):
            with self.subTest(provider=provider):
                answer = provider_from_configuration(
                    self.configuration(provider)
                ).complete("test")
                self.assertIn("answer", answer.content)
                self.assertEqual(answer.provider, provider)

    def test_missing_provider_is_disabled(self):
        self.assertIsNone(provider_from_configuration(Config()))

    def test_unknown_provider_is_rejected(self):
        configuration = Config()
        configuration.save("llm_provider", "unknown")
        with self.assertRaises(LLMProviderError):
            provider_from_configuration(configuration)
