from __future__ import annotations
import httpx
from .config import settings

class OpenAICompatible:
    def __init__(self):
        self.api_key = settings.api_key
        self.base_url = settings.base_url.rstrip("/")
        self.model = settings.model
    @property
    def enabled(self): return bool(self.api_key)
    def complete(self, messages, tools=None):
        payload = {"model": self.model, "messages": messages, "temperature": 0.1}
        if tools:
            payload.update({"tools": tools, "tool_choice": "auto"})
        r = httpx.post(self.base_url + "/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json=payload, timeout=60)
        r.raise_for_status(); return r.json()["choices"][0]["message"]
