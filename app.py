import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import json
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="高级宏观复盘系统", layout="wide")

# --- 2. 记忆持久化 (标注与笔记) ---
NOTES_FILE = "macro_notes.json"

def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"annotations": [], "general_notes": ""}
    return {"annotations": [], "general_notes": ""}

def save_notes(notes):
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=4)

# --- 3. 数据加载 (适配 microdata.xlsx) ---
@st.cache_data
def load_and_process_data(window):
    target_file = 'microdata.xlsx'
    if not os.path.exists(target_file):
        return None
    try:
        df = pd.read_excel(target_file, header=1, engine='openpyxl')
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
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
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
        st.error(f"解析失败: {e}")
        return None

# --- 4. 辅助绘图函数 (解决多轴分布问题) ---
def create_multi_axis_fig(data_slice, selected_indicators, title_text):
    fig = go.Figure()
    colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA']
    
    # 基础布局：预留左右空间给多轴
    fig.update_layout(
        xaxis=dict(domain=[0.15, 0.85], title=dict(text="日期"), hoverformat="%Y-%m-%d"),
        hovermode="x unified",
        height=700,
        template="plotly_white",
        title=title_text,
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
    )

    for i, ind in enumerate(selected_indicators[:4]):
        axis_key = f"y{i+1}" if i > 0 else "y"
        fig.add_trace(go.Scatter(
            x=data_slice['Date'], y=data_slice[ind],
            name=ind, yaxis=axis_key, line=dict(color=colors[i], width=2.5)
        ))
        
        # 轴位置分布策略：左(轴1,轴3), 右(轴2,轴4)
        side = "left" if i % 2 == 0 else "right"
        # 轴1和轴2紧贴图表，轴3和轴4向外偏移
        position = 0.15 - (i // 2) * 0.07 if side == "left" else 0.85 + (i // 2) * 0.07
        
        ax_config = dict(
            title=dict(text=ind, font=dict(color=colors[i])),
            tickfont=dict(color=colors[i]),
            anchor="free" if i > 1 else ("x" if i == 1 else None),
            overlaying="y" if i > 0 else None,
            side=side,
            position=position,
            showgrid=True if i == 0 else False
        )
        
        if i == 0: fig.update_layout(yaxis=ax_config)
        else: fig.update_layout({f"yaxis{i+1}": ax_config})
    return fig

# --- 5. 界面加载 ---
window_choice = st.sidebar.select_slider("判定周期 (天)", options=[7, 21, 42, 63, 126], value=21)
df = load_and_process_data(window_choice)
notes_data = load_notes()

if df is None:
    st.warning("⚠️ 未找到 microdata.xlsx。")
    st.stop()

tab1, tab2 = st.tabs(["🏛️ 全历史复盘", "📉 象限切片分析"])

# --- TAB 1: 全历史复盘 ---
with tab1:
    st.subheader("全历史周期复盘系统")
    all_inds = ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds', 'Unemployment']
    selected_inds_tab1 = st.multiselect("全历史显示指标", all_inds, default=['USD', 'Gold', 'UST_10Y'], key="tab1_inds")
    
    if selected_inds_tab1:
        # 这里也调用精确日期显示逻辑
        fig1 = create_multi_axis_fig(df, selected_inds_tab1, "1971 - 至今全周期")
        fig1.update_layout(xaxis=dict(rangeslider=dict(visible=True))) # 增加全周期拉动条
        
        # 加载历史标注
        for ann in notes_data["annotations"]:
            fig1.add_vline(x=ann["date"], line_width=1, line_dash="dash", line_color="grey")
            fig1.add_annotation(x=ann["date"], text=ann["text"], showarrow=True)
        st.plotly_chart(fig1, use_container_width=True)

    c1, c2 = st.columns([1, 2])
    with c1:
        st.write("📍 **添加标注**")
        d = st.date_input("选择日期", value=datetime(1971, 8, 15))
        t = st.text_input("描述重大事件")
        if st.button("确定保存标注"):
            notes_data["annotations"].append({"date": str(d), "text": t})
            save_notes(notes_data)
            st.rerun()
    with c2:
        st.write("📝 **复盘笔记**")
        txt = st.text_area("记录您的深度分析...", value=notes_data["general_notes"], height=150)
        if txt != notes_data["general_notes"]:
            notes_data["general_notes"] = txt
            save_notes(notes_data)

# --- TAB 2: 切片分析 ---
with tab2:
    st.subheader("象限特征历史切片")
    selected_regime = st.sidebar.selectbox("选择目标象限", ["美元涨 & 黄金涨", "美元涨 & 黄金跌", "美元跌 & 黄金涨", "美元跌 & 黄金跌"])
    
    slice_summary = df[df['Regime'] == selected_regime].groupby('Group_ID').agg({'Date':['min','max','count']}).reset_index()
    slice_summary.columns = ['Group_ID', 'Start', 'End', 'Days']
    slice_summary = slice_summary.sort_values('Start', ascending=False)

    if not slice_summary.empty:
        opts = slice_summary.apply(lambda x: f"{x['Start'].date()} 至 {x['End'].date()}", axis=1).tolist()
        sel_slice = st.selectbox("选择具体切片", opts)
        target_id = slice_summary.iloc[opts.index(sel_slice)]['Group_ID']
        slice_data = df[df['Group_ID'] == target_id]

        selected_inds_tab2 = st.multiselect("对比指标", all_inds, default=['USD', 'Gold'], key="tab2_inds")
        if selected_inds_tab2:
            # 使用优化后的多轴函数，确保左右分布
            fig2 = create_multi_axis_fig(slice_data, selected_inds_tab2, f"切片分析: {selected_regime}")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("该周期下未发现匹配切片。")
