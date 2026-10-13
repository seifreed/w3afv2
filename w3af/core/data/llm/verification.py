"""Asynchronous, bounded LLM vulnerability verification."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

from w3af.core.data.db.exceptions import DBException
from w3af.core.data.db.history import HistoryItem
from w3af.core.data.kb.vuln import Vuln
from w3af.core.data.llm.providers import LLMProviderError, provider_from_configuration
from w3af.core.data.llm.storage import VerificationStorage

LOGGER = logging.getLogger(__name__)
MAX_TRAFFIC_BYTES = 20_000
MAX_WORKERS = 8
MAX_POC_STEPS = 20


class LLMVerificationService:
    """Queue one verification per vulnerability without blocking the scan."""

    def __init__(self, database, uri_opener, configuration):
        self._database = database
        self._uri_opener = uri_opener
        self._configuration = configuration
        self._storage = VerificationStorage(database)
        self._executor = ThreadPoolExecutor(
            max_workers=max(
                1, min(int(configuration.get("llm_workers") or 2), MAX_WORKERS)
            ),
            thread_name_prefix="w3af-llm",
        )

    def submit(self, finding: Vuln) -> None:
        if not isinstance(finding, Vuln) or not self._configuration.get(
            "llm_verification_enabled"
        ):
            return
        if not self._storage.create_pending(finding.get_uniq_id()):
            return
        self._executor.submit(self._verify, finding)

    def retry(self, finding: Vuln) -> None:
        self._storage.create_pending(finding.get_uniq_id())
        self._executor.submit(self._verify, finding)

    def get(self, finding: Vuln) -> dict | None:
        return self._storage.get(finding.get_uniq_id())

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _verify(self, finding: Vuln) -> None:
        finding_id = finding.get_uniq_id()
        try:
            provider = provider_from_configuration(self._configuration)
            if provider is None:
                raise LLMProviderError("No LLM provider configured")
            self._storage.update(finding_id, "running")
            answer = provider.complete(self._prompt_for(finding))
            result = self._parse_answer(answer.content)
            evidence = self._execute_poc(finding, result.get("poc", []))
            result["evidence"] = evidence
            status = (
                "confirmed"
                if evidence and any(e["success"] for e in evidence)
                else "not_confirmed"
            )
            self._storage.update(
                finding_id,
                status,
                provider=answer.provider,
                model=answer.model,
                result=result,
            )
        except (
            LLMProviderError,
            ValueError,
            KeyError,
            TypeError,
            OSError,
            RuntimeError,
        ) as exc:
            LOGGER.warning("LLM verification failed for %s: %s", finding_id, exc)
            self._storage.update(finding_id, "failed", error=str(exc))

    def _prompt_for(self, finding: Vuln) -> str:
        traffic = []
        history = HistoryItem(db=self._database)
        for response_id in finding.get_id():
            try:
                item = history.read(response_id)
            except (DBException, OSError, ValueError, AttributeError) as exc:
                traffic.append({"response_id": response_id, "error": str(exc)})
                continue
            traffic.append(
                {
                    "response_id": response_id,
                    "request": item.request.dump()[:MAX_TRAFFIC_BYTES].decode(
                        "utf-8", "replace"
                    ),
                    "response": item.response.dump()[:MAX_TRAFFIC_BYTES].decode(
                        "utf-8", "replace"
                    ),
                }
            )
        payload = {
            "name": finding.get_name(),
            "description": finding.get_desc(),
            "severity": finding.get_severity(),
            "plugin": finding.get_plugin_name(),
            "url": finding.get_url().url_string if finding.get_url() else None,
            "traffic": traffic,
        }
        return (
            "You are a web security verifier. Return JSON only with keys "
            "confirmed (boolean), confidence (number 0..1), rationale (string), "
            "poc (array of objects with method,url,headers,data). "
            "The POC must use the same origin and only validate the finding.\n"
            + json.dumps(payload, ensure_ascii=True)
        )

    @staticmethod
    def _parse_answer(content: str) -> dict:
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise LLMProviderError("LLM response did not contain JSON")
        result = json.loads(content[start : end + 1])
        if not isinstance(result, dict) or not isinstance(result.get("poc", []), list):
            raise LLMProviderError("LLM response has an invalid verification shape")
        return result

    def _execute_poc(self, finding: Vuln, steps: list[dict]) -> list[dict]:
        base_url = finding.get_url()
        if base_url is None:
            return []
        base_parts = urlsplit(base_url.url_string)
        origin = (base_parts.scheme, base_parts.netloc)
        evidence = []
        max_steps = max(
            1,
            min(int(self._configuration.get("llm_max_poc_steps") or 3), MAX_POC_STEPS),
        )
        for step in steps[:max_steps]:
            url = step.get("url")
            method = str(step.get("method", "GET")).upper()
            url_parts = urlsplit(url) if isinstance(url, str) else None
            if url_parts is None or (url_parts.scheme, url_parts.netloc) != origin:
                raise LLMProviderError("POC URL is outside the vulnerability origin")
            if method not in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"}:
                raise LLMProviderError(f"POC method is not allowed: {method}")
            data = step.get("data")
            if data is not None and not isinstance(data, (str, bytes)):
                raise LLMProviderError("POC data must be text or bytes")
            headers = step.get("headers")
            if headers is not None and not isinstance(headers, dict):
                raise LLMProviderError("POC headers must be an object")
            request_method = getattr(self._uri_opener, method)
            response = request_method(
                url,
                data=data,
                headers=headers,
                grep=False,
                cache=False,
                timeout=int(self._configuration.get("llm_timeout") or 60),
                follow_redirects=False,
            )
            evidence.append(
                {
                    "method": method,
                    "url": url,
                    "code": response.get_code(),
                    "success": response.get_code() < 500,
                    "response": response.dump().decode("utf-8", "replace")[:10000],
                }
            )
        return evidence
