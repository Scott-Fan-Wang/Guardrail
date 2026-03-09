from __future__ import annotations

import asyncio
import os
import random
from typing import List, Dict, Any
from ...core.logger import logger

try:
    import aiohttp
except Exception as e:
    logger.warning("aiohttp not available: %s", e)
    aiohttp = None


def _env_int(name: str, default: int) -> int:
    try:
        v = int(os.getenv(name, str(default)))
        return v if v > 0 else default
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        v = float(os.getenv(name, str(default)))
        return v if v > 0 else default
    except Exception:
        return default


class QW3GuardProvider:
    name = "qw3_guard"

    def __init__(self) -> None:
        self.api_key = os.getenv("QW3_GUARD_API_KEY", "EMPTY")
        self.api_base = os.getenv("QW3_GUARD_API_BASE", "http://172.16.21.51:8036/v1")
        self.model = os.getenv("QW3_GUARD_MODEL", "qw3-guard")
        self.session = None
        self._sem = asyncio.Semaphore(_env_int("QW3_GUARD_CONCURRENCY", 200))
        self._max_retries = _env_int("QW3_GUARD_MAX_RETRIES", 2)
        self._retry_base_s = _env_float("QW3_GUARD_RETRY_BASE_S", 0.2)
        self._retry_max_s = _env_float("QW3_GUARD_RETRY_MAX_S", 2.0)

    async def _get_session(self):
        """Get or create aiohttp session"""
        if aiohttp is None:
            return None
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=_env_int("QW3_GUARD_CONN_LIMIT", 500),
                limit_per_host=_env_int("QW3_GUARD_CONN_LIMIT_PER_HOST", 500),
                ttl_dns_cache=_env_int("QW3_GUARD_DNS_TTL_S", 300),
                enable_cleanup_closed=True,
            )
            timeout = aiohttp.ClientTimeout(
                total=_env_float("QW3_GUARD_TIMEOUT_TOTAL_S", 30.0),
                connect=_env_float("QW3_GUARD_TIMEOUT_CONNECT_S", 5.0),
                sock_read=_env_float("QW3_GUARD_TIMEOUT_READ_S", 20.0),
            )
            self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self.session

    async def _post_json_with_retries(self, url: str, *, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any] | None:
        session = await self._get_session()
        if session is None:
            return None

        retryable_statuses = {408, 425, 429, 500, 502, 503, 504}
        attempt = 0
        while True:
            try:
                async with self._sem:
                    async with session.post(url, headers=headers, json=payload) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        if resp.status in retryable_statuses and attempt < self._max_retries:
                            await resp.release()
                            raise aiohttp.ClientResponseError(
                                request_info=resp.request_info,
                                history=resp.history,
                                status=resp.status,
                                message=f"retryable status {resp.status}",
                                headers=resp.headers,
                            )
                        logger.warning("QW3-Guard API returned status %s", resp.status)
                        return None
            except Exception as e:
                if attempt >= self._max_retries:
                    logger.error("Error calling QW3-Guard API (attempt %s/%s): %s", attempt + 1, self._max_retries + 1, e)
                    return None

                backoff = min(self._retry_max_s, self._retry_base_s * (2**attempt))
                # full jitter
                sleep_s = random.random() * backoff
                attempt += 1
                await asyncio.sleep(sleep_s)

    async def _parse_response(self, response_text: str) -> tuple[float, str | None]:
        """
        Parse qw3-guard response text to extract safety score and category.
        
        Expected format:
        Safety: Safe/Unsafe
        Categories: None or category names
        Refusal: Yes/No
        """
        score = 0.0
        label = None
        
        lines = response_text.strip().split('\n')
        safety = None
        categories = None
        
        for line in lines:
            if line.startswith("Safety:"):
                safety = line.split(":", 1)[1].strip()
            elif line.startswith("Categories:"):
                categories = line.split(":", 1)[1].strip()
        
        # If unsafe, set score to 1.0; if safe, score is 0.0
        if safety and safety.lower() != "safe":
            score = 1.0
            label = categories if categories and categories.lower() != "none" else "unsafe"
        else:
            score = 0.0
            label = "safe"
        
        return score, label

    async def moderate_messages(self, messages: List[Dict[str, str]]) -> tuple[float, str | None]:
        """
        Moderate messages in OpenAI chat completions format.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys,
                     e.g., [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        
        Returns:
            Tuple of (score, label) where score is 0.0-1.0 and label is category string
        """
        if not messages:
            return 0.0, None
        
        if aiohttp is None:
            logger.warning("aiohttp not available, cannot call QW3-Guard API")
            await asyncio.sleep(0)
            return 0.0, None
        
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": messages
        }
        
        try:
            data = await self._post_json_with_retries(url, headers=headers, payload=payload)
            if not data:
                return 0.0, None
            # Extract the content from the response
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                return await self._parse_response(content)
            logger.warning("QW3-Guard API response missing choices: %s", data)
            return 0.0, None
        except Exception as e:
            logger.error(f"Error calling QW3-Guard API: {e}")
            return 0.0, None

    async def moderate(self, text: str) -> tuple[float, str | None]:
        """
        Moderate single text (for compatibility with other providers).
        This creates a simple user message for moderation.
        """
        messages = [{"role": "user", "content": text}]
        return await self.moderate_messages(messages)

    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()


provider = QW3GuardProvider()

