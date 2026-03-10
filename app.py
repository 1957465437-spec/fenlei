import streamlit as st
import pandas as pd
import json
import io
import time
from openai import OpenAI

# ================= 1. 工业级 UI 样式配置 =================
st.set_page_config(page_title="学科分类工具", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    .main-header { text-align: center; padding: 20px 0; }
    .main-title { color: #4F46E5; font-size: 32px; font-weight: 700; margin-bottom: 8px; }
    .main-subtitle { color: #6B7280; font-size: 16px; }
    div[data-testid="stPopover"] > button {
        border: 1px solid #E5E7EB !important;
        background-color: transparent !important;
        color: #374151 !important;
        width: auto !important;
        padding: 5px 15px !important;
        border-radius: 4px !important;
    }
    div.stButton > button, div.stDownloadButton > button {
        background-color: #4F46E5 !important;
        color: white !important;
        border: none !important;
        height: 50px !important;
        width: 100% !important;
        font-size: 16px !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
    }
    div.stDownloadButton > button { background-color: #6366F1 !important; }
    div.stButton > button:disabled, div.stDownloadButton > button:disabled {
        background-color: #E5E7EB !important;
        color: #9CA3AF !important;
    }
    .section-header { font-size: 18px; font-weight: 600; color: #111827; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# ================= 2. 核心提示词配置 =================
SYSTEM_PROMPT = """请将以下内容分类为：数学、物理、化学、生物。如果不是学科题目或内容不完整，输出‘其他’。
【核心判据：主导领域原则 (Primary Domain Principle)】
请判断题目最终是为了解决哪个领域的问题，而非仅看使用了什么工具。
主体优先： 依据题目中主要研究实体或现象所属的学科进行分类。
工具剥离： 如果题目引用了其他学科的公式、定律或计算方法作为工具，来解释当前研究对象的性质，请忽略这些工具的学科属性。
逻辑示例： 用 B 学科的方法解决 A 学科的问题 归类为 A 学科。
【形式服从目标】：忽略编程语法或抽象符号的表现形式，以最终考核的任务目标为准。
若交付是数值、公式证明或计算结论，归类为数学/物理等。
若交付是程序实现、代码逻辑或形式系统描述，归类为其他。

请仅以 JSON 格式输出结果：
{
  "subject": "分类结果",
  "reason": "简短理由",
  "confidence": 0.95
}"""

# ================= 3. 页面顶部 =================
st.markdown(f"""
    <div class="main-header">
        <div class="main-title">学科分类工具</div>
        <div class="main-subtitle">基于“主导领域原则”与“形式服从目标”的工业级自动化分类平台</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")
with st.popover("核心分类判据 (SOP)"):
    st.markdown(SYSTEM_PROMPT)

st.write("")

# ================= 4. 内容展示区 (输入与监测) =================
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown('<div class="section-header">任务参数配置</div>', unsafe_allow_html=True)
    st.caption("DeepSeek API Key")
    api_key = st.text_input("api_input", label_visibility="collapsed", type="password", placeholder="请输入您的 API Key...")
    st.write("")
    st.caption("上传待分类 Excel 文件")
    uploaded_file = st.file_uploader("uploader", label_visibility="collapsed", type=["xlsx"])

with col_right:
    st.markdown('<div class="section-header">处理结果反馈</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div style="color:#6366F1; font-size:12px; font-weight:600; margin-bottom:10px;">运行状态实时监测</div>', unsafe_allow_html=True)
        status_text = st.empty()
        progress_bar = st.progress(0)
        time_display = st.empty()
        status_text.write("等待任务启动...")
        st.write("")

# ================= 5. 按钮操作区 (水平对齐) =================
st.write("") 
btn_left, btn_right = st.columns([1, 1], gap="large")

with btn_left:
    start_btn = st.button("开启智能学科分类") if uploaded_file else st.button("开启智能学科分类", disabled=True)

with btn_right:
    download_area = st.empty()
    download_area.button("点击下载分类审计报告", disabled=True, key="init_dl")

# ================= 6. 后端执行逻辑 =================
if uploaded_file and start_btn:
    if not api_key:
        st.error("请输入有效的 API Key")
    else:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        df = pd.read_excel(uploaded_file)
        results = []
        start_time = time.time()
        
        # 自动定位列
        blacklist = ['结果', 'label', 'reason', 'score', '信心分', '分类', '预测', '学科', 'subject']
        text_cols = [c for c in df.select_dtypes(include=['object']).columns if not any(b in str(c).lower() for b in blacklist)]
        target_col = text_cols[0] if text_cols else df.columns[0]

        for i, text in enumerate(df[target_col]):
            # --- 真实的 API 调用逻辑 ---
            subject, reason, confidence = "Error", "API异常", 0.0
            if not pd.isna(text) and str(text).strip() != "":
                for attempt in range(3): # 3次重试
                    try:
                        completion = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": str(text)}
                            ],
                            response_format={"type": "json_object"},
                            temperature=0.1
                        )
                        res = json.loads(completion.choices[0].message.content)
                        subject = res.get("subject")
                        reason = res.get("reason")
                        confidence = res.get("confidence")
                        break
                    except:
                        if attempt < 2: time.sleep(1)
            
            results.append((subject, reason, confidence))
            
            # 更新 UI
            cur = (i + 1) / len(df)
            progress_bar.progress(cur)
            status_text.markdown(f"**正在处理: {i+1} / {len(df)}**")
            time_display.markdown(f'<div style="text-align:right; font-size:14px;">已运行: {time.time() - start_time:.1f}s</div>', unsafe_allow_html=True)

        # 保存结果
        res_df = pd.DataFrame(results, columns=['分类结果', '原因分析', '信心分'])
        final_df = pd.concat([df, res_df], axis=1)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False)
        
        download_area.empty()
        download_area.download_button(label="点击下载分类审计报告", data=output.getvalue(), file_name="分类结果.xlsx")
        st.success("分类任务处理完成！")
