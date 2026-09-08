"""
Multi-provider LLM support.

Anthropic Claude uses its own SDK (different message shape: system prompt
is a top-level param, content comes back as typed blocks). OpenAI, Groq,
DeepSeek, and Ollama are all OpenAI-Chat-Completions-API-compatible, so a
single client class handles all four just by pointing at a different
base_url.

PROVIDER_CATALOG is the single source of truth for what the frontend's
settings panel renders (provider list, model list, whether a key is
required, cost hints) — it's served as-is via GET /api/providers so the
UI never hardcodes this.
"""
import json
import logging

from anthropic import Anthropic, APIError as AnthropicAPIError
from openai import OpenAI, APIError as OpenAIAPIError

logger = logging.getLogger("llm_providers")

PROVIDER_CATALOG = [
    {
        "id": "anthropic",
        "label": "Anthropic Claude",
        "requires_api_key": True,
        "key_help_url": "https://console.anthropic.com/settings/keys",
        "base_url_editable": False,
        "default_base_url": None,
        "cost_hint": "~$0.01–0.15 per scan depending on model and forum size",
        "models": [
            {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5 (Fast, cheaper)"},
            {"id": "claude-sonnet-5", "label": "Claude Sonnet 5 (Balanced)"},
            {"id": "claude-opus-5", "label": "Claude Opus 5 (Best)"},
        ],
    },
    {
        "id": "openai",
        "label": "OpenAI (ChatGPT)",
        "requires_api_key": True,
        "key_help_url": "https://platform.openai.com/api-keys",
        "base_url_editable": False,
        "default_base_url": "https://api.openai.com/v1",
        "cost_hint": "~$0.01–0.10 per scan depending on model and forum size",
        "models": [
            {"id": "gpt-5-mini", "label": "GPT-5 Mini (Fast, cheaper)"},
            {"id": "gpt-4o", "label": "GPT-4o (Balanced, widely supported)"},
            {"id": "gpt-5.5", "label": "GPT-5.5 (Best)"},
        ],
    },
    {
        "id": "gemini",
        "label": "Google Gemini",
        "requires_api_key": True,
        "key_help_url": "https://aistudio.google.com/apikey",
        "base_url_editable": False,
        # Gemini's official OpenAI-compatibility layer — same request/response
        # shape as OpenAI, so it works through the same OpenAICompatibleClient
        # below with zero extra code, just a different base_url.
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "cost_hint": "~$0.005–0.08 per scan depending on model and forum size",
        "models": [
            {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash-Lite (Fastest, cheapest)"},
            {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash (Balanced)"},
            {"id": "gemini-3.5-pro", "label": "Gemini 3.5 Pro (Best)"},
        ],
    },
    {
        "id": "groq",
        "label": "Groq (Fast)",
        "requires_api_key": True,
        "key_help_url": "https://console.groq.com/keys",
        "base_url_editable": False,
        "default_base_url": "https://api.groq.com/openai/v1",
        "cost_hint": "Free tier available; very low cost per scan otherwise",
        "models": [
            {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B (Fastest)"},
            {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B (General purpose)"},
            {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B (Strong open-weight)"},
            {"id": "moonshotai/kimi-k2-instruct-0905", "label": "Kimi K2 (Best, largest context)"},
        ],
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "requires_api_key": True,
        "key_help_url": "https://platform.deepseek.com/api_keys",
        "base_url_editable": False,
        "default_base_url": "https://api.deepseek.com",
        "cost_hint": "~$0.002–0.02 per scan — one of the cheapest options",
        "models": [
            {"id": "deepseek-chat", "label": "DeepSeek Chat (V3.2, non-thinking)"},
            {"id": "deepseek-reasoner", "label": "DeepSeek Reasoner (V3.2, thinking mode)"},
        ],
    },
    {
        "id": "ollama",
        "label": "Ollama (Local, Free)",
        "requires_api_key": False,
        "key_help_url": None,
        "base_url_editable": True,
        "default_base_url": "http://localhost:11434/v1",
        "cost_hint": "Free — runs on your own machine, no API cost",
        "models": [
            {"id": "llama3.1", "label": "Llama 3.1"},
            {"id": "qwen2.5", "label": "Qwen 2.5"},
            {"id": "gpt-oss:20b", "label": "GPT-OSS 20B"},
        ],
        # Ollama model names depend entirely on what the user has pulled
        # locally (`ollama pull <name>`), so the frontend also lets them
        # type a custom model id instead of only picking from this list.
        "allow_custom_model": True,
    },
]

_CATALOG_BY_ID = {p["id"]: p for p in PROVIDER_CATALOG}


class LLMError(Exception):
    pass


class AnthropicClient:
    def __init__(self, api_key: str, model: str):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def complete(self, system: str, user_content: str) -> str:
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                system=system,
                messages=[{"role": "user", "content": user_content}],
            )
        except AnthropicAPIError as e:
            raise LLMError(f"Anthropic API error: {e}") from e
        return "".join(block.text for block in resp.content if block.type == "text")


class OpenAICompatibleClient:
    """Covers OpenAI, Groq, DeepSeek, and Ollama — all speak the same
    Chat Completions API shape, differing only in base_url and whether
    a real API key is required."""

    def __init__(self, api_key: str, model: str, base_url: str):
        # Ollama's OpenAI-compatible endpoint ignores the key but the SDK
        # requires a non-empty string.
        self.client = OpenAI(api_key=api_key or "not-required", base_url=base_url)
        self.model = model

    def complete(self, system: str, user_content: str) -> str:
        # OpenAI's GPT-5 (and o-series reasoning) models reject the classic
        # `max_tokens` param outright — they 400 with "Unsupported parameter:
        # max_tokens... use max_completion_tokens instead." Every other
        # OpenAI-compatible backend we support (Groq, DeepSeek, Gemini's
        # compat layer, Ollama) still expects the older `max_tokens`, so we
        # branch on model name rather than switching everyone over.
        token_param = "max_completion_tokens" if self.model.startswith(("gpt-5", "o1", "o3", "o4")) else "max_tokens"
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                **{token_param: 8000},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
            )
        except OpenAIAPIError as e:
            raise LLMError(f"{self.client.base_url} API error: {e}") from e
        return resp.choices[0].message.content or ""


def get_provider_info(provider: str) -> dict:
    info = _CATALOG_BY_ID.get(provider)
    if not info:
        raise LLMError(f"Unknown AI provider '{provider}'.")
    return info


def get_client(provider: str, api_key: str, model: str, base_url: str | None = None):
    info = get_provider_info(provider)

    if info["requires_api_key"] and not (api_key and api_key.strip()):
        raise LLMError(f"{info['label']} requires an API key.")

    if provider == "anthropic":
        return AnthropicClient(api_key=api_key, model=model)

    resolved_base_url = base_url or info["default_base_url"]
    return OpenAICompatibleClient(api_key=api_key, model=model, base_url=resolved_base_url)


def parse_json_response(text: str) -> list[dict]:
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Failed to parse model output as JSON: %s", cleaned[:500])
        return []
