import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import chardet
import json
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="宏观全周期复盘系统", layout="wide")

# --- 2. 笔记记忆逻辑 ---
NOTES_FILE = "macro_notes.json"

def load_notes():
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"annotations": [], "general_notes": ""}

def save_notes(notes):
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=4)

# --- 3. 数据处理 ---
def smart_read_csv(file_path):
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read(20000))
        encoding = result['encoding'] or 'utf-8'
    if 'gb' in encoding.lower() or 'ansi' in encoding.lower(): encoding = 'gbk'
    return pd.read_csv(file_path, header=1, encoding=encoding)

@st.cache_data
def load_data(window):
    default_filename = 'macro_data.csv'
    if not os.path.exists(default_filename): return None
    df = smart_read_csv(default_filename)
    column_mapping = {
        'Unnamed: 0': 'Date', '美元指数': 'USD', '标准普尔500指数': 'SP500',
        '美国:国债收益率:10年': 'UST_10Y', '伦敦市场黄金下午定盘价:按美元': 'Gold',
        '美国:联邦基金利率': 'Fed_Funds', 'CPI:所有项目:同比:美国': 'CPI_YoY',
        '原油': 'Oil', '铜': 'Copper', '美国失业率': 'Unemployment'
    }
    df = df.rename(columns=column_mapping)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True)
    num_cols = ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds', 'CPI_YoY', 'Unemployment']
    for col in num_cols: df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 区间判定逻辑
    df['Group_ID'] = df.index // window
    regime_map = df.groupby('Group_ID').apply(
        lambda g: f"{'美元涨' if (g['USD'].iloc[-1]-g['USD'].iloc[0])>0 else '美元跌'} & {'黄金涨' if (g['Gold'].iloc[-1]-g['Gold'].iloc[0])>0 else '黄金跌'}"
    ).to_dict()
    df['Regime'] = df['Group_ID'].map(regime_map)
    return df

# --- 4. 主界面选项卡 ---
tab1, tab2 = st.tabs(["📊 历史周期复盘 (新模块)", "🔍 象限切片分析"])

# 全局变量
window_choice = st.sidebar.select_slider("判定周期 (天)", options=[7, 21, 42, 63, 126], value=21)
df = load_data(window_choice)
notes_data = load_notes()

if df is None:
    st.error("未找到 macro_data.csv。请确保数据已嵌入根目录。")
    st.stop()

# --- 模块1：全历史周期复盘 ---
with tab1:
    st.header("全历史周期复盘（1971 - 至今）")
    
    # 侧边栏指标选择
    all_inds = ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds', 'Unemployment']
    selected_inds = st.multiselect("显示指标 (支持8轴同步)", all_inds, default=['USD', 'Gold', 'SP500'])

    fig = go.Figure()
    colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880']

    # 构建 8 轴布局
    layout_config = {
        "xaxis": dict(domain=[0.15, 0.85], rangeslider=dict(visible=True), type="date"),
        "height": 800, "template": "plotly_white", "hovermode": "x unified",
        "legend": dict(orientation="h", y=1.1)
    }

    for i, ind in enumerate(selected_inds):
        fig.add_trace(go.Scatter(x=df['Date'], y=df[ind], name=ind, yaxis=f"y{i+1}" if i > 0 else "y", line=dict(color=colors[i % 8])))
        
        # 轴位置计算 (左4右4)
        side = "left" if i % 2 == 0 else "right"
        pos = 0.15 - (i // 2) * 0.05 if side == "left" else 0.85 + (i // 2) * 0.05
        
        axis_key = f"yaxis{i+1}" if i > 0 else "yaxis"
        layout_config[axis_key] = dict(
            title=dict(text=ind, font=dict(color=colors[i % 8])),
            tickfont=dict(color=colors[i % 8]),
            anchor="free" if i > 1 else "x",
            overlaying="y" if i > 0 else None,
            side=side, position=pos, showgrid=True if i == 0 else False
        )

    # 插入历史标注
    for ann in notes_data["annotations"]:
        fig.add_vline(x=ann["date"], line_width=1, line_dash="dash", line_color="red")
        fig.add_annotation(x=ann["date"], text=ann["text"], showarrow=True, arrowhead=1)

    fig.update_layout(**layout_config)
    st.plotly_chart(fig, use_container_width=True)

    # 笔记区
    st.divider()
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.subheader("🖋️ 添加历史标注")
        ann_date = st.date_input("选择重大事件日期", value=datetime(1971, 8, 15))
        ann_text = st.text_input("事件说明 (如: 布雷顿森林体系瓦解)")
        if st.button("保存标注"):
            notes_data["annotations"].append({"date": str(ann_date), "text": ann_text})
            save_notes(notes_data)
            st.rerun()
        
        if st.button("清除所有标注"):
            notes_data["annotations"] = []
            save_notes(notes_data)
            st.rerun()

    with col_b:
        st.subheader("📝 复盘笔记")
        current_notes = st.text_area("记录您的心得 (自动保存)", value=notes_data.get("general_notes", ""), height=200)
        if current_notes != notes_data.get("general_notes", ""):
            notes_data["general_notes"] = current_notes
            save_notes(notes_data)

# --- 模块2：象限切片分析 (保持原有逻辑) ---
with tab2:
    st.header("象限切片深度分析")
    # ... 此处放您之前的切片逻辑代码 ...
    st.info("请参考上一版代码中的切片逻辑填充此处。")
