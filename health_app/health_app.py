import streamlit as st

# 1. 设置网页标题
st.title('🏥 个人健康评估助手')
st.write('输入您的身体数据，AI 将为您生成健康报告。')

# 2. 获取用户输入 (把 input 换成 st 组件)
# 使用单选按钮选择性别，比输入文字更方便
gender_option = st.radio("请选择您的性别：", ('男', '女'))
is_male = (gender_option == '男')

# 使用数字输入框
user_height = st.number_input("身高 (米)", min_value=0.5, max_value=2.5, value=1.75, step=0.01)
user_weight = st.number_input("体重 (千克)", min_value=20.0, max_value=200.0, value=70.0, step=0.1)
user_waist = st.number_input("腰围 (厘米)", min_value=40.0, max_value=150.0, value=80.0, step=1.0)

# 3. 添加一个“开始计算”的按钮
if st.button('生成健康报告'):

    # 计算 BMI
    if user_height > 0:
        user_BMI = user_weight / (user_height ** 2)
        st.metric(label="您的 BMI 指数", value=f"{user_BMI:.2f}")  # 漂亮的指标显示
    else:
        st.error("身高不能为0！")
        st.stop()

    # 核心判断逻辑 (复制你的逻辑，稍微修饰一下输出)
    # 这里的逻辑我帮你微调了，防止刚好等于24或28时出现两句话

    # 判断结果容器
    result_text = ""

    if user_BMI < 18.5:
        if (is_male and user_waist < 85) or (not is_male and user_waist < 80):
            st.success('✅ 您很健康！整体内脏脂肪无明显风险，但体重不足需关注营养摄入。')
        else:
            st.warning('⚠️ 体重偏轻却伴随内脏脂肪堆积，属于“瘦胖子”，需调整饮食结构。')

    elif 18.5 <= user_BMI < 24:  # 注意这里改成 < 24，避免重叠
        if (is_male and user_waist < 85) or (not is_male and user_waist < 80):
            st.success('🌟 完美！体重与内脏脂肪状态均理想，请继续保持！')
        else:
            st.warning('⚠️ 隐形肥胖警告：表面体重正常但内脏脂肪过多，建议增加有氧运动。')

    elif 24 <= user_BMI < 28:  # 注意这里改成 < 28
        if (is_male and user_waist < 85) or (not is_male and user_waist < 80):
            st.info('💪 壮实型：体重超标但内脏脂肪未堆积，建议通过塑形将体重回归正常。')
        else:
            st.error('🚫 危险：体重与内脏脂肪双重超标，代谢疾病风险升高！')

    else:  # BMI >= 28
        if (is_male and user_waist < 85) or (not is_male and user_waist < 80):
            st.warning('⚖️ 需减重：虽内脏脂肪暂未严重堆积，但整体肥胖已对身体造成负担。')
        else:
            st.error('🚑 高风险：体重与内脏脂肪均处于高危状态，建议咨询医生进行干预。')