"""xAI/Grok LiveModelBackend for the Epoch 2 live four-arm run.

Credentials: XAI_API_KEY / MATH_ANCHOR_XAI_API_KEY, else grok CLI OIDC
(~/.grok/auth.json) with refresh. Never writes the key into reports.
Returns raw text / tool_calls / usage only — no invented scores.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from math_anchor.errors import CalculatorError

from .mcp_inprocess import chat_tool_definitions


DEFAULT_MODEL = "grok-4.6"
DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_REASONING_EFFORT = "high"
OIDC_TOKEN_URL = "https://auth.x.ai/oauth2/token"
GROK_AUTH_PATH = Path.home() / ".grok" / "auth.json"
DISABLE_AUTO_ENV = "MATH_ANCHOR_SHADOW_DISABLE_AUTO_BACKEND"
DISABLE_GROK_CLI_ENV = "MATH_ANCHOR_SHADOW_DISABLE_GROK_CLI_AUTH"


def sanitize_usage(usage: Any) -> dict[str, Any]:
    """Keep token counts only. Drop provider fee fields. Invent nothing."""

    if not isinstance(usage, dict):
        return {
            "promptTokens": None,
            "completionTokens": None,
            "totalTokens": None,
            "reasoningTokens": None,
        }
    prompt = usage.get("prompt_tokens", usage.get("promptTokens"))
    completion = usage.get("completion_tokens", usage.get("completionTokens"))
    total = usage.get("total_tokens", usage.get("totalTokens"))
    reasoning = usage.get("reasoning_tokens", usage.get("reasoningTokens"))
    details = usage.get("completion_tokens_details")
    if reasoning is None and isinstance(details, dict):
        reasoning = details.get("reasoning_tokens")
    cached = None
    prompt_details = usage.get("prompt_tokens_details")
    if isinstance(prompt_details, dict):
        cached = prompt_details.get("cached_tokens")
    return {
        "promptTokens": prompt,
        "completionTokens": completion,
        "totalTokens": total,
        "reasoningTokens": reasoning,
        "cachedTokens": cached,
    }


def add_usage(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged = sanitize_usage(left)
    extra = sanitize_usage(right)
    out: dict[str, Any] = {}
    for key in ("promptTokens", "completionTokens", "totalTokens", "reasoningTokens", "cachedTokens"):
        a = merged.get(key)
        b = extra.get(key)
        if isinstance(a, int) and isinstance(b, int):
            out[key] = a + b
        elif isinstance(a, int):
            out[key] = a
        elif isinstance(b, int):
            out[key] = b
        else:
            out[key] = None
    return out


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip() in {"1", "true", "TRUE", "yes", "YES"}


def _jwt_exp(token: str) -> int | None:
    try:
        payload = token.split(".")[1]
        pad = "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload + pad))
        exp = data.get("exp")
        return int(exp) if exp is not None else None
    except (IndexError, ValueError, json.JSONDecodeError, OSError):
        return None


def _parse_expires_at(raw: str | None) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _refresh_grok_oidc(entry: dict[str, Any]) -> dict[str, Any]:
    refresh = entry.get("refresh_token")
    client_id = entry.get("oidc_client_id")
    if not isinstance(refresh, str) or not refresh or not isinstance(client_id, str):
        raise CalculatorError(
            "E_INPUT",
            "grok CLI auth.json is missing refresh_token or oidc_client_id",
        )
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": client_id,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OIDC_TOKEN_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "math-anchor-shadow-verifier-live",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:400]
        raise CalculatorError(
            "E_UNAVAILABLE",
            f"grok CLI OIDC refresh failed (HTTP {error.code})",
            {"httpStatus": error.code, "bodyPreview": detail},
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise CalculatorError(
            "E_UNAVAILABLE",
            f"grok CLI OIDC refresh failed: {error}",
        ) from error
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        raise CalculatorError("E_UNAVAILABLE", "grok CLI OIDC refresh returned no access_token")
    entry = dict(entry)
    entry["key"] = access
    if isinstance(payload.get("refresh_token"), str) and payload["refresh_token"]:
        entry["refresh_token"] = payload["refresh_token"]
    expires_in = payload.get("expires_in")
    if isinstance(expires_in, int) and expires_in > 0:
        expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        entry["expires_at"] = expiry.isoformat().replace("+00:00", "Z")
    return entry


def _token_needs_refresh(entry: dict[str, Any], *, margin_seconds: int = 120) -> bool:
    token = entry.get("key")
    if not isinstance(token, str) or not token:
        return True
    expires = _parse_expires_at(entry.get("expires_at") if isinstance(entry.get("expires_at"), str) else None)
    now = datetime.now(timezone.utc)
    if expires is not None and expires <= now + timedelta(seconds=margin_seconds):
        return True
    exp = _jwt_exp(token)
    if exp is not None and exp <= int(time.time()) + margin_seconds:
        return True
    return False


def _resolve_grok_cli_auth() -> dict[str, Any] | None:
    if _env_flag(DISABLE_GROK_CLI_ENV):
        return None
    path = GROK_AUTH_PATH
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict) or not document:
        return None
    issuer_key, entry = next(iter(document.items()))
    if not isinstance(entry, dict):
        return None
    if _token_needs_refresh(entry):
        entry = _refresh_grok_oidc(entry)
        document[issuer_key] = entry
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    token = entry.get("key")
    if not isinstance(token, str) or not token:
        return None
    return {
        "apiKey": token,
        "source": "grok-cli-oidc",
        "provider": "xAI",
        "authPath": str(path),
    }


def resolve_xai_credentials() -> dict[str, Any] | None:
    for name in ("XAI_API_KEY", "MATH_ANCHOR_XAI_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return {"apiKey": value, "source": f"env:{name}", "provider": "xAI"}
    return _resolve_grok_cli_auth()


class XaiGrokBackend:
    """LiveModelBackend: one HTTP chat-completions turn per complete() call."""

    def __init__(
        self,
        *,
        api_key: str,
        auth_source: str,
        model: str | None = None,
        base_url: str | None = None,
        reasoning_effort: str | None = None,
        timeout_seconds: int = 180,
    ) -> None:
        if not api_key:
            raise CalculatorError("E_INPUT", "xAI backend requires an API credential")
        self._api_key = api_key
        self.auth_source = auth_source
        self.provider = "xAI"
        self.model = (
            model
            or os.environ.get("MATH_ANCHOR_SHADOW_MODEL", "").strip()
            or DEFAULT_MODEL
        )
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.reasoning_effort = (
            reasoning_effort
            or os.environ.get("MATH_ANCHOR_SHADOW_REASONING_EFFORT", "").strip()
            or DEFAULT_REASONING_EFFORT
        )
        self.timeout_seconds = timeout_seconds

    def disclosure(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "baseUrl": self.base_url,
            "authSource": self.auth_source,
            "reasoningEffort": self.reasoning_effort,
            "api": "chat.completions",
            "credentialRedacted": True,
        }

    def complete(
        self,
        prompt: str,
        *,
        arm_id: str,
        task_id: str,
        tools: list[str] | None = None,
        messages: list[dict[str, Any]] | None = None,
        tool_definitions: list[dict[str, Any]] | None = None,
        allow_reasoning_effort: bool = True,
    ) -> dict[str, Any]:
        """One model HTTP call. Returns text + toolCalls + usage. Invents no scores."""

        if messages is None:
            messages = [{"role": "user", "content": prompt}]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 4096,
        }
        if self.reasoning_effort and allow_reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        definitions = tool_definitions
        if definitions is None and tools:
            definitions = chat_tool_definitions(tools)
        if definitions:
            payload["tools"] = definitions
            payload["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "math-anchor-shadow-verifier-live",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
                http_status = response.status
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")[:800]
            if error.code == 400 and allow_reasoning_effort and "reasoning_effort" in payload:
                return self.complete(
                    prompt,
                    arm_id=arm_id,
                    task_id=task_id,
                    tools=tools,
                    messages=messages,
                    tool_definitions=tool_definitions,
                    allow_reasoning_effort=False,
                )
            raise CalculatorError(
                "E_UNAVAILABLE",
                f"xAI chat.completions failed (HTTP {error.code}) for {arm_id}×{task_id}",
                {"httpStatus": error.code, "bodyPreview": body, "model": self.model},
            ) from error
        except OSError as error:
            raise CalculatorError(
                "E_UNAVAILABLE",
                f"xAI chat.completions transport failed for {arm_id}×{task_id}: {error}",
                {"model": self.model},
            ) from error

        choices = raw.get("choices") if isinstance(raw, dict) else None
        message = {}
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
            finish = choices[0].get("finish_reason")
        else:
            finish = None
        content = message.get("content")
        text = content if isinstance(content, str) else ""
        tool_calls_out: list[dict[str, Any]] = []
        raw_tool_calls = message.get("tool_calls")
        if isinstance(raw_tool_calls, list):
            for item in raw_tool_calls:
                if not isinstance(item, dict):
                    continue
                function = item.get("function") if isinstance(item.get("function"), dict) else {}
                arguments_raw = function.get("arguments")
                parsed_args: Any
                if isinstance(arguments_raw, str) and arguments_raw.strip():
                    try:
                        parsed_args = json.loads(arguments_raw)
                    except json.JSONDecodeError:
                        parsed_args = {"_unparsed": arguments_raw}
                elif isinstance(arguments_raw, dict):
                    parsed_args = arguments_raw
                else:
                    parsed_args = {}
                tool_calls_out.append(
                    {
                        "id": item.get("id"),
                        "name": function.get("name") or item.get("name"),
                        "arguments": parsed_args,
                    }
                )
        assistant_message = {
            "role": "assistant",
            "content": text or None,
        }
        if raw_tool_calls:
            assistant_message["tool_calls"] = raw_tool_calls
        return {
            "text": text or "",
            "usage": sanitize_usage(raw.get("usage") if isinstance(raw, dict) else None),
            "toolCalls": tool_calls_out,
            "assistantMessage": assistant_message,
            "finishReason": finish,
            "provider": self.provider,
            "model": raw.get("model") if isinstance(raw, dict) else self.model,
            "httpStatus": http_status,
            "liveQualityDelta": None,
            "finalAccuracy": None,
            "dollarCost": None,
        }


def try_make_xai_backend() -> XaiGrokBackend | None:
    if _env_flag(DISABLE_AUTO_ENV):
        return None
    creds = resolve_xai_credentials()
    if creds is None:
        return None
    return XaiGrokBackend(api_key=creds["apiKey"], auth_source=str(creds["source"]))
