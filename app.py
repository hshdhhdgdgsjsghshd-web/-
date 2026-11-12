"""Streamlit dashboard for fitness-coach-agent (architecture refactor)."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from core.agent import FitnessAgent
from core.prompts import TOOL_STATUS_LABELS
from core.state import get_system_snapshot
from tools.plan_manager import get_active_plan
from tools.profile_manager import get_user_profile
from tools.storage import ensure_data_dir
from tools.log_manager import get_logs_by_date

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
    snapshot = get_system_snapshot()
    profile = get_user_profile()["profile"]
    plan_result = get_active_plan()
    plan = plan_result["plan"]
    today = get_logs_by_date()

    basic = profile.get("basic_metrics") or {}
    fitness = profile.get("fitness_background") or {}
    health = profile.get("health_and_constraints") or {}
    baselines = profile.get("calculated_baselines") or {}
    summary = today.get("daily_summary") or {}

    st.sidebar.title("健身私教 Agent")
    st.sidebar.caption("三表架构 · 软状态引擎")

    # ① Stage + profile card
    with st.sidebar.expander("① 系统阶段 · 身体档案", expanded=True):
        stage = snapshot["stage"]
        if stage == "ONBOARDING":
            st.warning(f"阶段：{stage}")
        elif stage == "PLANNING":
            st.info(f"阶段：{stage}")
        else:
            st.success(f"阶段：{stage}")
        st.caption(snapshot["priority"])

        missing = snapshot["onboarding"]["missing_required_fields"]
        if missing:
            st.markdown("**缺失字段**")
            st.code("\n".join(missing))

        st.markdown(
            f"""
- 性别/年龄：{basic.get("gender") or "—"} / {basic.get("age") or "—"}
- 身高/体重：{_fmt(basic.get("height_cm"), "cm")} / {_fmt(basic.get("weight_kg"), "kg")}
- 目标：{basic.get("goal") or "—"}
- 有氧/力量：{fitness.get("cardio_level") or "—"} / {fitness.get("strength_level") or "—"}
- 每周：{fitness.get("weekly_days") or "—"}天 · {fitness.get("session_duration_min") or "—"}分
- BMR/TDEE：{_fmt(baselines.get("bmr"), "")} / {_fmt(baselines.get("tdee"), "")}
- 目标热量/蛋白：{_fmt(baselines.get("target_calories"), "kcal")} / {_fmt(baselines.get("target_protein_g"), "g")}
"""
        )

        injuries = health.get("injuries") or []
        if injuries:
            for item in injuries:
                st.error(f"伤病：{item}")
        else:
            st.success("伤病：暂无记录")

        restrictions = health.get("dietary_restrictions") or []
        if restrictions:
            st.caption("饮食限制：" + " · ".join(restrictions))

    # ② Active weekly plan summary
    with st.sidebar.expander("② 生效周计划", expanded=True):
        st.markdown(
            f"- **版本**：v{plan.get('plan_version', 0)}\n"
            f"- **更新**：{plan.get('updated_at') or '尚未创建'}"
        )
        plan_summary = plan_result.get("summary") or {}
        active_days = plan_summary.get("active_training_days") or []
        if plan_result.get("is_empty"):
            st.caption("尚无生效计划（PLANNING 阶段应优先生成）")
        else:
            schedule = plan.get("weekly_schedule") or {}
            for day in active_days:
                item = schedule.get(day) or {}
                focus = item.get("focus") or "未命名重点"
                count = len(item.get("exercises") or [])
                st.markdown(
                    f"- **{day[:3]}**：{focus} · {count}动作 · `{item.get('status')}`"
                )

        history = plan.get("adjustment_history") or []
        if history:
            last = history[-1]
            st.caption(f"最近调整：v{last.get('version')} · {last.get('reason')}")

    # ③ Today nutrition + training volume
    with st.sidebar.expander("③ 今日营养 · 训练容量", expanded=True):
        _progress_block(
            label="热量",
            current=float(summary.get("total_calories") or 0),
            target=baselines.get("target_calories"),
            unit="kcal",
            in_sidebar=False,
        )
        _progress_block(
            label="蛋白质",
            current=float(summary.get("total_protein_g") or 0),
            target=baselines.get("target_protein_g"),
            unit="g",
            in_sidebar=False,
        )
        st.metric(
            "训练容量 volume",
            f"{float(summary.get('total_volume_kg') or 0):.0f} kg",
        )

        workouts = today.get("workouts") or []
        if workouts:
            for item in workouts[:5]:
                st.markdown(
                    f"- {item.get('exercise')} · "
                    f"{item.get('sets')}×{item.get('reps')}@{item.get('weight_kg')}kg"
                    f" (= {item.get('volume_kg')}kg)"
                )
        else:
            st.caption("今日尚无训练记录")

        meals = today.get("meals") or []
        if meals:
            for item in meals[:5]:
                est = "估" if item.get("is_estimated") else "实"
                st.markdown(
                    f"- [{est}] {item.get('meal_time')} · {item.get('description')} · "
                    f"{item.get('calories')}kcal"
                )

    if st.sidebar.button("清空对话历史", use_container_width=True):
        clear_chat()
        st.rerun()


def _progress_block(
    *,
    label: str,
    current: float,
    target: Any,
    unit: str,
    in_sidebar: bool = True,
) -> None:
    write = st.sidebar.write if in_sidebar else st.write
    progress = st.sidebar.progress if in_sidebar else st.progress
    if target in (None, ""):
        write(f"{label}：{current:.0f} {unit} / 目标未设定")
        progress(0.0)
        return
    target_f = float(target)
    ratio = 0.0 if target_f <= 0 else min(current / target_f, 1.0)
    write(f"{label}：{current:.0f} / {target_f:.0f} {unit}")
    progress(ratio)


def _fmt(value: Any, unit: str) -> str:
    if value in (None, ""):
        return "—"
    return f"{value}{unit}"


def render_chat() -> None:
    snapshot = get_system_snapshot()
    st.title("你的专属健身私教")
    st.caption(
        f"当前阶段 **{snapshot['stage']}** · 全工具开放 · "
        "可随时改档案 / 修订计划 / 打卡记录"
    )

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

    prompt = st.chat_input(
        "例如：男/28岁/175cm/70kg，目标减脂；有氧老手力量新手，每周练4天…"
    )
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
        except Exception as exc:  # noqa: BLE001
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
