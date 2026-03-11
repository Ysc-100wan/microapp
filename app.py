import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import chardet
import json
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="宏观全周期复盘与切片分析系统", layout="wide")

# --- 2. 笔记记忆持久化逻辑 ---
NOTES_FILE = "macro_notes.json"

def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 确保必要字段存在
                if "annotations" not in data: data["annotations"] = []
                if "general_notes" not in data: data["general_notes"] = ""
                return data
        except Exception:
            st.error("检测到笔记文件损坏，已重置。")
            return {"annotations": [], "general_notes": ""}
    return {"annotations": [], "general_notes": ""}

def save_notes(notes):
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"保存笔记失败: {e}")

# --- 3. 数据处理逻辑 ---
@st.cache_data
def load_and_process_data(window):
    default_filename = 'macro_data.csv'
    if not os.path.exists(default_filename):
        return None
    
    try:
        # 检测编码
        with open(default_filename, 'rb') as f:
            rawdata = f.read(20000)
            enc = chardet.detect(rawdata)['encoding'] or 'utf-8'
        if 'gb' in enc.lower() or 'ansi' in enc.lower(): enc = 'gbk'
        
        # 读取CSV，增加容错跳过错误行
        df = pd.read_csv(default_filename, header=1, encoding=enc, on_bad_lines='skip')
        
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

        # 分段逻辑
        df['Group_ID'] = df.index // window
        regime_map = df.groupby('Group_ID').apply(
            lambda g: f"{'美元涨' if (g['USD'].iloc[-1]-g['USD'].iloc[0])>0 else '美元跌'} & {'黄金涨' if (g['Gold'].iloc[-1]-g['Gold'].iloc[0])>0 else '黄金跌'}"
            if len(g)>1 else "数据不足"
        ).to_dict()
        df['Regime'] = df['Group_ID'].map(regime_map)
        return df
    except Exception as e:
        st.error(f"读取数据失败: {e}")
        return None

# --- 4. 界面展示 ---
st.sidebar.header("⚙️ 全局配置")
window_choice = st.sidebar.select_slider("切片判定维度 (天)", options=[7, 21, 42, 63, 126], value=21)

df = load_and_process_data(window_choice)
notes_data = load_notes()

if df is None:
    st.warning("⚠️ 请确保根目录下有 macro_data.csv 文件。")
    st.stop()

tab1, tab2 = st.tabs(["🏛️ 全历史复盘", "📉 象限切片分析"])

# --- Tab 1: 全历史复盘 (新功能) ---
with tab1:
    st.subheader("全历史周期深度复盘")
    all_inds = ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds', 'Unemployment']
    selected_inds = st.multiselect("选择展示指标 (支持8轴独立)", all_inds, default=['USD', 'Gold', 'UST_10Y'])
    
    if selected_inds:
        fig = go.Figure()
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880']
        
        # 设置基础布局 (左4轴 右4轴)
        fig.update_layout(
            xaxis=dict(domain=[0.2, 0.8], rangeslider=dict(visible=True), type="date", title="时间"),
            height=800, template="plotly_white", hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5)
        )

        for i, ind in enumerate(selected_inds[:8]):
            axis_key = f"y{i+1}" if i > 0 else "y"
            fig.add_trace(go.Scatter(x=df['Date'], y=df[ind], name=ind, yaxis=axis_key, line=dict(color=colors[i])))
            
            side = "left" if i % 2 == 0 else "right"
            # 计算偏移量
            off = (i // 2) * 0.06
            pos = 0.2 - off if side == "left" else 0.8 + off
            
            ax_config = dict(
                title=dict(text=ind, font=dict(color=colors[i])),
                tickfont=dict(color=colors[i]),
                anchor="free", overlaying="y" if i > 0 else None,
                side=side, position=pos, showgrid=True if i == 0 else False
            )
            if i == 0: fig.update_layout(yaxis=ax_config)
            elif i == 1: fig.update_layout(yaxis2=ax_config)
            elif i == 2: fig.update_layout(yaxis3=ax_config)
            elif i == 3: fig.update_layout(yaxis4=ax_config)
            elif i == 4: fig.update_layout(yaxis5=ax_config)
            elif i == 5: fig.update_layout(yaxis6=ax_config)
            elif i == 6: fig.update_layout(yaxis7=ax_config)
            elif i == 7: fig.update_layout(yaxis8=ax_config)

        # 绘制历史标注
        for ann in notes_data["annotations"]:
            fig.add_vline(x=ann["date"], line_width=1, line_dash="dash", line_color="grey")
            fig.add_annotation(x=ann["date"], text=ann["text"], showarrow=True)

        st.plotly_chart(fig, use_container_width=True)

    # 笔记与标注保存
    c1, c2 = st.columns([1, 2])
    with c1:
        st.write("📍 **添加事件标注**")
        d = st.date_input("日期", value=datetime(1971, 8, 15))
        t = st.text_input("描述", placeholder="例如：布雷顿森林体系瓦解")
        if st.button("保存至图表"):
            notes_data["annotations"].append({"date": str(d), "text": t})
            save_notes(notes_data)
            st.rerun()
    with c2:
        st.write("📝 **复盘笔记**")
        txt = st.text_area("在此记录深度分析心得...", value=notes_data["general_notes"], height=150)
        if txt != notes_data["general_notes"]:
            notes_data["general_notes"] = txt
            save_notes(notes_data)

# --- Tab 2: 象限切片分析 (原有功能) ---
with tab2:
    st.subheader("象限特征历史切片")
    selected_regime = st.sidebar.selectbox("选择目标象限", ["美元涨 & 黄金涨", "美元涨 & 黄金跌", "美元跌 & 黄金涨", "美元跌 & 黄金跌"])
    
    slice_summary = df[df['Regime'] == selected_regime].groupby('Group_ID').agg({'Date':['min','max','count']}).reset_index()
    slice_summary.columns = ['Group_ID', 'Start', 'End', 'Days']
    slice_summary = slice_summary.sort_values('Start', ascending=False)

    if not slice_summary.empty:
        opts = slice_summary.apply(lambda x: f"{x['Start'].date()} 至 {x['End'].date()} ({x['Days']}天)", axis=1).tolist()
        sel_slice = st.selectbox("查看具体历史切片", opts)
        target_id = slice_summary.iloc[opts.index(sel_slice)]['Group_ID']
        slice_data = df[df['Group_ID'] == target_id]

        fig_s = go.Figure()
        sub_inds = st.multiselect("对比指标", all_inds, default=['USD', 'Gold'], key="sub_inds")
        for i, si in enumerate(sub_inds[:4]):
            fig_s.add_trace(go.Scatter(x=slice_data['Date'], y=slice_data[si], name=si, yaxis=f"y{i+1}" if i>0 else "y"))
            # 简化版多轴逻辑... (同上)
        
        st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.info("该周期下未发现符合条件的象限切片。")
