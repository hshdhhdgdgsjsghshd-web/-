# fitness-coach-agent

开源健身私教 Agent · Sprint 1

专业、科学、温和且有监督感的对话式私教：维护用户档案（含「有氧老手 / 力量新手」跨界标签）、记录训练与饮食，并在提到伤病时优先落档 + 保守建议 + 医疗免责声明。

## 架构

```
app.py                 # Streamlit 左右布局界面
core/
  prompts.py           # 私教 System Prompt
  agent.py             # FitnessAgent（DeepSeek multi-tool loop）
tools/
  profile_tool.py      # get/update_user_profile + Mifflin-St Jeor
  tracker_tool.py      # log_workout / log_diet / get_today_summary
  storage.py           # data/ JSON 自动初始化
data/
  user_profile.json
  workout_logs.json
  diet_logs.json
```

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 填入 DEEPSEEK_API_KEY
streamlit run app.py
```

`.env` 需要：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com`）
- 模型：`deepseek-chat`

## Sprint 1 能力

- 档案读写与局部更新；身高体重年龄性别齐全时自动推算热量 / 蛋白质目标
- 训练与饮食流水记录
- 今日训练打卡 + 热量/蛋白质进度
- 多轮对话中连续多工具调用
- 侧边栏实时可视化；聊天中用 `st.status` 展示教练正在执行的操作

## 免责声明

本项目提供的健身与动作建议不能替代执业医师或物理治疗师的诊断与治疗。
