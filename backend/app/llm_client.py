import json
import os

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
PROVIDER = os.getenv("LLM_PROVIDER", "ollama")


def _extract_json(text: str) -> dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in LLM output: {text[:200]}")
    return json.loads(text[start : end + 1])


async def _call_ollama(system_prompt: str, user_prompt: str) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{system_prompt}\n\n{user_prompt}",
        "stream": False,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(OLLAMA_URL, json=payload)
        resp.raise_for_status()
        body = resp.json()
        return _extract_json(body["response"])


async def _call_claude(system_prompt: str, user_prompt: str) -> dict:
    import anthropic

    client = anthropic.AsyncAnthropic()
    resp = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=system_prompt + "\nRespond with a single valid JSON object only, no prose.",
        messages=[{"role": "user", "content": user_prompt}],
    )
    return _extract_json(resp.content[0].text)


async def call_llm(system_prompt: str, user_prompt: str) -> dict:
    if PROVIDER == "claude":
        return await _call_claude(system_prompt, user_prompt)
    return await _call_ollama(system_prompt, user_prompt)
