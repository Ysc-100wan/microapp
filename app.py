import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import json
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="宏观全周期复盘与切片分析", layout="wide")

# --- 2. 记忆持久化 (标注与笔记) ---
NOTES_FILE = "macro_notes.json"

def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except:
            return {"annotations": [], "general_notes": ""}
    return {"annotations": [], "general_notes": ""}

def save_notes(notes):
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=4)

# --- 3. 数据加载 (适配 microdata.xlsx) ---
@st.cache_data
def load_and_process_data(window):
    # 修改后的内嵌文件名
    target_file = 'microdata.xlsx'
    
    if not os.path.exists(target_file):
        return None
    
    try:
        # 读取 Excel，跳过第一行空行(如有)，header=1 代表第二行是列名
        df = pd.read_excel(target_file, header=1, engine='openpyxl')
        
        # 标准化列名
        column_mapping = {
            'Unnamed: 0': 'Date', '美元指数': 'USD', '标准普尔500指数': 'SP500',
            '美国:国债收益率:10年': 'UST_10Y', '伦敦市场黄金下午定盘价:按美元': 'Gold',
            '美国:联邦基金利率': 'Fed_Funds', 'CPI:所有项目:同比:美国': 'CPI_YoY',
            '原油': 'Oil', '铜': 'Copper', '美国失业率': 'Unemployment'
        }
        df = df.rename(columns=column_mapping)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True)
        
        # 强制转换为数值
        num_cols = ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds', 'CPI_YoY', 'Unemployment']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 分段判定逻辑
        df['Group_ID'] = df.index // window
        def calculate_regime(g):
            if len(g) < 2: return "数据不足"
            u_change = g['USD'].iloc[-1] - g['USD'].iloc[0]
            g_change = g['Gold'].iloc[-1] - g['Gold'].iloc[0]
            return f"{'美元涨' if u_change > 0 else '美元跌'} & {'黄金涨' if g_change > 0 else '黄金跌'}"
        
        regime_map = df.groupby('Group_ID').apply(calculate_regime).to_dict()
        df['Regime'] = df['Group_ID'].map(regime_map)
        return df
    except Exception as e:
        st.error(f"解析 microdata.xlsx 失败: {e}")
        return None

# --- 4. 界面加载 ---
window_choice = st.sidebar.select_slider("判定周期 (天)", options=[7, 21, 42, 63, 126], value=21)
df = load_and_process_data(window_choice)
notes_data = load_notes()

if df is None:
    st.warning("⚠️ 目录下未找到 microdata.xlsx 文件。请确保文件名正确并已上传。")
    st.stop()

tab1, tab2 = st.tabs(["🏛️ 全历史复盘", "📉 象限切片分析"])

# --- TAB 1: 全历史复盘 (8轴+记忆) ---
with tab1:
    st.subheader("全历史周期复盘系统")
    all_inds = ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds', 'Unemployment']
    selected_inds = st.multiselect("选择展示指标 (最多8个独立轴)", all_inds, default=['USD', 'Gold', 'UST_10Y'])
    
    if selected_inds:
        fig = go.Figure()
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880']
        
        # 布局配置 (左4轴 右4轴)
        fig.update_layout(
            xaxis=dict(domain=[0.2, 0.8], rangeslider=dict(visible=True), type="date"),
            height=850, template="plotly_white", hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
        )

        for i, ind in enumerate(selected_inds[:8]):
            axis_key = f"y{i+1}" if i > 0 else "y"
            fig.add_trace(go.Scatter(x=df['Date'], y=df[ind], name=ind, yaxis=axis_key, line=dict(color=colors[i])))
            
            side = "left" if i % 2 == 0 else "right"
            off = (i // 2) * 0.06
            pos = 0.2 - off if side == "left" else 0.8 + off
            
            ax_config = dict(
                title=dict(text=ind, font=dict(color=colors[i])),
                tickfont=dict(color=colors[i]),
                anchor="free", overlaying="y" if i > 0 else None,
                side=side, position=pos, showgrid=True if i == 0 else False
            )
            if i == 0: fig.update_layout(yaxis=ax_config)
            else: fig.update_layout({f"yaxis{i+1}": ax_config})

        # 加载记忆中的标注
        for ann in notes_data["annotations"]:
            fig.add_vline(x=ann["date"], line_width=1, line_dash="dash", line_color="grey")
            fig.add_annotation(x=ann["date"], text=ann["text"], showarrow=True)

        st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns([1, 2])
    with c1:
        st.write("📍 **添加标注**")
        d = st.date_input("日期", value=datetime(1971, 8, 15))
        t = st.text_input("描述", placeholder="重大事件...")
        if st.button("确定保存"):
            notes_data["annotations"].append({"date": str(d), "text": t})
            save_notes(notes_data)
            st.rerun()
    with c2:
        st.write("📝 **复盘笔记**")
        txt = st.text_area("记录分析...", value=notes_data["general_notes"], height=150)
        if txt != notes_data["general_notes"]:
            notes_data["general_notes"] = txt
            save_notes(notes_data)

# --- TAB 2: 切片分析 ---
with tab2:
    st.subheader("历史切片深度复盘")
    selected_regime = st.sidebar.selectbox("选择目标象限", ["美元涨 & 黄金涨", "美元涨 & 黄金跌", "美元跌 & 黄金涨", "美元跌 & 黄金跌"])
    
    slice_summary = df[df['Regime'] == selected_regime].groupby('Group_ID').agg({'Date':['min','max','count']}).reset_index()
    slice_summary.columns = ['Group_ID', 'Start', 'End', 'Days']
    slice_summary = slice_summary.sort_values('Start', ascending=False)

    if not slice_summary.empty:
        opts = slice_summary.apply(lambda x: f"{x['Start'].date()} 至 {x['End'].date()}", axis=1).tolist()
        sel_slice = st.selectbox("选择切片", opts)
        target_id = slice_summary.iloc[opts.index(sel_slice)]['Group_ID']
        slice_data = df[df['Group_ID'] == target_id]

        fig_s = go.Figure()
        sub_inds = st.multiselect("对比指标", all_inds, default=['USD', 'Gold'], key="sub_inds")
        for i, si in enumerate(sub_inds[:4]):
            fig_s.add_trace(go.Scatter(x=slice_data['Date'], y=slice_data[si], name=si, yaxis=f"y{i+1}" if i>0 else "y"))
            # 此处同样应用左1右1左2右2的多轴逻辑...
        st.plotly_chart(fig_s, use_container_width=True)
