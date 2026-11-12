# fitness-coach-agent

开源健身私教 Agent · 三表架构 + 软状态引擎

## 架构

```
data/
  user_profile.json   # 静态/低频档案 + calculated_baselines
  active_plan.json    # 动态周计划（versioned）
  daily_logs.json     # 按日期索引的训练/饮食流水

tools/
  profile_manager.py  # 档案读写 + Mifflin-St Jeor 确定性基线
  plan_manager.py     # 周计划读写与版本历史
  log_manager.py      # 打卡流水 + volume/营养累计

core/
  state.py            # get_system_snapshot() → ONBOARDING / PLANNING / DAILY_COACHING
  prompts.py          # 动态注入快照的 System Prompt（全工具开放）
  agent.py            # DeepSeek FitnessAgent 多工具闭环

app.py                # Streamlit：三模块侧边栏 + 对话
```

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
streamlit run app.py
python scripts/smoke_tools.py
```

## 软状态策略

| 阶段 | 条件 | 优先任务 |
| --- | --- | --- |
| ONBOARDING | 档案必填项未齐 | 补齐性别/年龄/身高/体重/目标/运动基础 |
| PLANNING | 档案齐但计划空 | 生成并保存第一版周计划 |
| DAILY_COACHING | 档案+计划就绪 | 日常督促、打卡、动态修订 |

状态只影响优先级提示，**不锁死工具**；可随时跨阶段改体重/伤病、修订计划或记录打卡。

体重或目标变化且已有生效计划时，`update_user_profile` 会返回 `action_required`，提示模型询问是否同步修订计划。

## 免责声明

本项目提供的健身建议不能替代执业医师或物理治疗师的诊断与治疗。
