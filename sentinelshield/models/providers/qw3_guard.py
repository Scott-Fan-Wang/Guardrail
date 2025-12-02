from __future__ import annotations

import asyncio
import os
from typing import List, Dict, Any
from ...core.logger import logger

try:
    import aiohttp
except Exception as e:
    logger.warning("aiohttp not available: %s", e)
    aiohttp = None


class QW3GuardProvider:
    name = "qw3_guard"

    def __init__(self) -> None:
        self.api_key = os.getenv("QW3_GUARD_API_KEY", "EMPTY")
        self.api_base = os.getenv("QW3_GUARD_API_BASE", "http://172.16.21.51:8036/v1")
        self.model = os.getenv("QW3_GUARD_MODEL", "qw3-guard")
        self.session = None

    async def _get_session(self):
        """Get or create aiohttp session"""
        if aiohttp is None:
            return None
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

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
            session = await self._get_session()
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    logger.warning(f"QW3-Guard API returned status {resp.status}")
                    return 0.0, None
                
                data = await resp.json()
                # Extract the content from the response
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    return await self._parse_response(content)
                else:
                    logger.warning(f"QW3-Guard API response missing choices: {data}")
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

