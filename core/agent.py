"""FitnessAgent — DeepSeek multi-turn + multi-tool calling loop."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from core.prompts import SYSTEM_PROMPT, TOOL_STATUS_LABELS
from tools import ALL_TOOLS, TOOL_HANDLERS

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

OnToolStart = Callable[[str, dict[str, Any]], None]
OnToolEnd = Callable[[str, dict[str, Any], Any], None]


@dataclass
class ToolCallEvent:
    name: str
    arguments: dict[str, Any]
    result: Any
    label: str


@dataclass
class AgentTurnResult:
    reply: str
    messages: list[dict[str, Any]]
    tool_events: list[ToolCallEvent] = field(default_factory=list)


class FitnessAgent:
    """DeepSeek chat agent with OpenAI-compatible function calling."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "deepseek-chat",
        max_tool_rounds: int = 8,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url = (
            base_url
            or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
        )
        self.model = model
        self.max_tool_rounds = max_tool_rounds

        if not self.api_key:
            raise ValueError(
                "缺少 DEEPSEEK_API_KEY。请在项目根目录创建 .env 并填写密钥。"
            )

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        user_message: str,
        history: list[dict[str, Any]] | None = None,
        *,
        on_tool_start: OnToolStart | None = None,
        on_tool_end: OnToolEnd | None = None,
    ) -> AgentTurnResult:
        """Run one user turn with multi-tool calling until a final text reply."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        tool_events: list[ToolCallEvent] = []

        for _ in range(self.max_tool_rounds):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=ALL_TOOLS,
                tool_choice="auto",
            )
            choice = response.choices[0]
            message = choice.message
            assistant_message = self._message_to_dict(message)
            messages.append(assistant_message)

            tool_calls = message.tool_calls or []
            if not tool_calls:
                reply = (message.content or "").strip()
                return AgentTurnResult(
                    reply=reply or "（教练本轮没有返回文字，请再试一次。）",
                    messages=self._public_history(messages),
                    tool_events=tool_events,
                )

            for tool_call in tool_calls:
                name = tool_call.function.name
                arguments = self._parse_arguments(tool_call.function.arguments)
                label = TOOL_STATUS_LABELS.get(name, f"正在执行 {name}...")

                if on_tool_start:
                    on_tool_start(name, arguments)

                result = self._dispatch_tool(name, arguments)

                if on_tool_end:
                    on_tool_end(name, arguments, result)

                tool_events.append(
                    ToolCallEvent(
                        name=name,
                        arguments=arguments,
                        result=result,
                        label=label,
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        # Safety exit if the model keeps calling tools.
        fallback = (
            "本轮工具调用次数过多，我先根据已有信息给你建议。"
            "如果你愿意，可以再说一句，我继续跟进。"
        )
        return AgentTurnResult(
            reply=fallback,
            messages=self._public_history(messages),
            tool_events=tool_events,
        )

    def _dispatch_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            return {"ok": False, "error": f"未知工具: {name}"}
        try:
            return handler(**arguments)
        except TypeError as exc:
            return {"ok": False, "error": f"参数错误: {exc}", "arguments": arguments}
        except Exception as exc:  # noqa: BLE001 — surface tool failures to the model
            return {"ok": False, "error": str(exc), "arguments": arguments}

    @staticmethod
    def _parse_arguments(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _message_to_dict(message: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "role": message.role,
            "content": message.content or "",
        }
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        return payload

    @staticmethod
    def _public_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep full multi-turn context including tool messages for the next turn."""
        return [m for m in messages if m.get("role") != "system"]
