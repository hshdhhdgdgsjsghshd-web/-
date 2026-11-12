"""Streamlit UI for fitness-coach-agent (Sprint 1)."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from core.agent import FitnessAgent
from core.prompts import TOOL_STATUS_LABELS
from tools.profile_tool import get_user_profile
from tools.storage import ensure_data_dir
from tools.tracker_tool import get_today_summary

st.set_page_config(
    page_title="健身私教 Agent",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_data_dir()


def init_session() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent_history" not in st.session_state:
        st.session_state.agent_history = []


def clear_chat() -> None:
    st.session_state.messages = []
    st.session_state.agent_history = []


def render_sidebar() -> None:
    profile = get_user_profile()["profile"]
    summary = get_today_summary()
    basic = profile.get("basic_info") or {}
    experience = profile.get("experience_profile") or {}
    injuries = profile.get("injuries") or []
    targets = profile.get("daily_targets") or {}
    diet = summary.get("diet") or {}
    workouts = summary.get("workouts") or []

    st.sidebar.title("健身私教 Agent")
    st.sidebar.caption("Sprint 1 · 档案 / 打卡 / 对话")

    st.sidebar.subheader("基础档案")
    st.sidebar.markdown(
        f"""
- **性别**：{basic.get("gender") or "未填写"}
- **年龄**：{basic.get("age") or "未填写"}
- **身高**：{_fmt(basic.get("height_cm"), "cm")}
- **体重**：{_fmt(basic.get("weight_kg"), "kg")}
- **目标**：{basic.get("goal") or "未填写"}
"""
    )

    st.sidebar.subheader("跨界能力标签")
    tags = experience.get("cross_tags") or []
    if not tags and (experience.get("cardio_level") or experience.get("strength_level")):
        tags = [
            t
            for t in [experience.get("cardio_level"), experience.get("strength_level")]
            if t
        ]
    if tags:
        st.sidebar.write(" · ".join(f"`{tag}`" for tag in tags))
    else:
        st.sidebar.caption("暂无标签（对话中会自动沉淀）")

    cardio = experience.get("cardio_level") or "未知"
    strength = experience.get("strength_level") or "未知"
    equipment = experience.get("available_equipment") or []
    st.sidebar.markdown(
        f"""
- 有氧基础：{cardio}
- 力量基础：{strength}
- 可用器械：{", ".join(equipment) if equipment else "未填写"}
"""
    )

    st.sidebar.subheader("伤病警示")
    if injuries:
        for item in injuries:
            st.sidebar.error(f"⚠ {item}")
    else:
        st.sidebar.success("暂无记录的伤病 / 疼痛")

    st.sidebar.subheader("今日饮食进度")
    calorie_target = targets.get("calories_kcal")
    protein_target = targets.get("protein_g")
    calories = float(diet.get("calories") or 0)
    protein = float(diet.get("protein_g") or 0)

    _progress_block(
        label="热量",
        current=calories,
        target=calorie_target,
        unit="kcal",
    )
    _progress_block(
        label="蛋白质",
        current=protein,
        target=protein_target,
        unit="g",
    )

    st.sidebar.subheader("今日训练打卡")
    if workouts:
        for item in workouts:
            st.sidebar.markdown(
                f"- **{item.get('exercise')}** · "
                f"{item.get('sets')}×{item.get('reps')} @ {item.get('weight_kg')}kg"
                f" · {item.get('rpe_or_feeling')}"
            )
    else:
        st.sidebar.caption("今天还没有训练记录")

    st.sidebar.divider()
    if st.sidebar.button("清空对话历史", use_container_width=True):
        clear_chat()
        st.rerun()


def _progress_block(*, label: str, current: float, target: Any, unit: str) -> None:
    if target in (None, ""):
        st.sidebar.write(f"{label}：{current:.0f} {unit} / 目标未设定")
        st.sidebar.progress(0.0)
        return
    target_f = float(target)
    ratio = 0.0 if target_f <= 0 else min(current / target_f, 1.0)
    st.sidebar.write(f"{label}：{current:.0f} / {target_f:.0f} {unit}")
    st.sidebar.progress(ratio)


def _fmt(value: Any, unit: str) -> str:
    if value in (None, ""):
        return "未填写"
    return f"{value}{unit}"


def render_chat() -> None:
    st.title("你的专属健身私教")
    st.caption("告诉我身体数据、训练感受或今天吃了什么——我会记档案、盯进度、给建议。")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            tool_events = message.get("tool_events") or []
            if tool_events:
                with st.expander("本轮教练操作", expanded=False):
                    for event in tool_events:
                        st.markdown(f"**{event['label']}** (`{event['name']}`)")
                        st.code(
                            json.dumps(
                                {
                                    "arguments": event.get("arguments"),
                                    "result": event.get("result"),
                                },
                                ensure_ascii=False,
                                indent=2,
                            ),
                            language="json",
                        )

    prompt = st.chat_input("例如：我是跑步老手但力量新手，左膝偶尔会痛…")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        status_box = st.status("教练正在思考...", expanded=True)
        collected_events: list[dict[str, Any]] = []

        def on_tool_start(name: str, arguments: dict[str, Any]) -> None:
            label = TOOL_STATUS_LABELS.get(name, f"正在执行 {name}...")
            status_box.update(label=label, state="running")
            status_box.write(f"🔧 {label}")
            if arguments:
                status_box.code(
                    json.dumps(arguments, ensure_ascii=False, indent=2),
                    language="json",
                )

        def on_tool_end(name: str, arguments: dict[str, Any], result: Any) -> None:
            label = TOOL_STATUS_LABELS.get(name, f"完成 {name}")
            collected_events.append(
                {
                    "name": name,
                    "label": label,
                    "arguments": arguments,
                    "result": result,
                }
            )
            ok = isinstance(result, dict) and result.get("ok", True)
            status_box.write("✅ 完成" if ok else "⚠️ 工具返回异常")

        try:
            agent = FitnessAgent()
            result = agent.chat(
                prompt,
                history=st.session_state.agent_history,
                on_tool_start=on_tool_start,
                on_tool_end=on_tool_end,
            )
            status_box.update(label="教练操作完成", state="complete")
            st.markdown(result.reply)
            st.session_state.agent_history = result.messages
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result.reply,
                    "tool_events": collected_events,
                }
            )
        except Exception as exc:  # noqa: BLE001 — show setup errors in UI
            status_box.update(label="出错了", state="error")
            error_text = f"无法完成回复：{exc}"
            st.error(error_text)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_text, "tool_events": []}
            )

    st.rerun()


def main() -> None:
    init_session()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
