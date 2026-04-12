from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CHAT_URL = "https://yunai.chat/v1/chat/completions"
DEFAULT_EXTRACT_MODEL = "qwen3.5-plus"
DEFAULT_ANSWER_MODEL = "claude-sonnet-4-6"
DEFAULT_TIMEOUT_SECONDS = 120
CONFIG_PATH = Path(__file__).resolve().parents[1] / "rag_llm.local.json"


@dataclass(frozen=True)
class RagLlmSettings:
    chat_url: str
    api_key: str
    extract_model: str
    answer_model: str
    timeout_seconds: int


def load_rag_llm_settings() -> RagLlmSettings:
    file_config = _load_local_config()
    return RagLlmSettings(
        chat_url=_setting_value("chat_url", "RAG_LLM_CHAT_URL", DEFAULT_CHAT_URL, file_config),
        api_key=_setting_value("api_key", "RAG_LLM_API_KEY", "", file_config),
        extract_model=_setting_value("extract_model", "RAG_EXTRACT_MODEL", DEFAULT_EXTRACT_MODEL, file_config),
        answer_model=_setting_value("answer_model", "RAG_ANSWER_MODEL", DEFAULT_ANSWER_MODEL, file_config),
        timeout_seconds=_setting_int_value("timeout_seconds", "RAG_LLM_TIMEOUT", DEFAULT_TIMEOUT_SECONDS, file_config),
    )


def _load_local_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"RAG 本地配置文件解析失败：{CONFIG_PATH} / {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"RAG 本地配置文件格式错误：{CONFIG_PATH}")
    return payload


def _setting_value(config_key: str, env_key: str, default: str, file_config: dict) -> str:
    if env_key in os.environ and os.environ[env_key]:
        return os.environ[env_key]
    value = file_config.get(config_key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _setting_int_value(config_key: str, env_key: str, default: int, file_config: dict) -> int:
    if env_key in os.environ and os.environ[env_key]:
        return int(os.environ[env_key])
    value = file_config.get(config_key)
    if value is None or value == "":
        return default
    return int(value)


def chat_json(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2200,
    settings: RagLlmSettings | None = None,
) -> dict:
    effective_settings = settings or load_rag_llm_settings()
    if not effective_settings.api_key:
        raise RuntimeError("未设置 RAG_LLM_API_KEY，无法调用知识卡片生成模型。")

    payload = {
        "model": model or effective_settings.extract_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    raw_text = _post_json(effective_settings, payload)
    return _extract_json_object(raw_text)


def chat_text(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2200,
    settings: RagLlmSettings | None = None,
) -> str:
    effective_settings = settings or load_rag_llm_settings()
    if not effective_settings.api_key:
        raise RuntimeError("Missing RAG_LLM_API_KEY")

    payload = {
        "model": model or effective_settings.extract_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    return _post_json(effective_settings, payload).strip()


def _post_json(settings: RagLlmSettings, payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        settings.chat_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.api_key}",
        },
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"调用 LLM 失败：{last_error}") from last_error


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        _write_debug_response(text)
        raise ValueError("模型返回中未找到 JSON 对象。")
    candidate = text[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        repaired = _repair_json(candidate)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as exc:
            _write_debug_response(candidate)
            raise ValueError(f"模型返回 JSON 解析失败：{exc}") from exc


def _repair_json(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", " ")
    text = text.replace("，}", "}")
    text = text.replace("，]", "]")
    text = text.replace(",}", "}")
    text = text.replace(",]", "]")
    return text


def _write_debug_response(text: str) -> None:
    debug_path = os.getenv("RAG_LLM_DEBUG_PATH")
    if not debug_path:
        debug_path = str(Path(__file__).resolve().parents[1] / "mock_data" / "rag_corpus" / "_last_llm_response.txt")
    Path(debug_path).write_text(text, encoding="utf-8")
