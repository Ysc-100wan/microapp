import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="宏观资产象限分析模型",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式：优化夜间（凌晨1点）阅读体验
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 数据加载函数 ---
@st.cache_data
def process_data(file):
    try:
        # 支持 CSV 和 Excel
        if file.name.endswith('.csv'):
            df = pd.read_csv(file, header=1)
        else:
            df = pd.read_excel(file, header=1)
        
        # 统一列名映射（基于您提供的Excel结构）
        column_mapping = {
            'Unnamed: 0': 'Date',
            '美元指数': 'USD',
            '标准普尔500指数': 'SP500',
            '美国:国债收益率:10年': 'UST_10Y',
            '伦敦市场黄金下午定盘价:按美元': 'Gold',
            '美国:联邦基金利率': 'Fed_Funds',
            'CPI:所有项目:同比:美国': 'CPI_YoY',
            '原油': 'Oil',
            '铜': 'Copper',
            '美国失业率': 'Unemployment'
        }
        df = df.rename(columns=column_mapping)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        
        # 核心逻辑：以1个月（21个交易日）为维度计算变化率
        window = 21
        df['USD_Ret'] = df['USD'].pct_change(periods=window)
        df['Gold_Ret'] = df['Gold'].pct_change(periods=window)
        
        # 定义四种组合象限
        def get_regime(row):
            if pd.isna(row['USD_Ret']) or pd.isna(row['Gold_Ret']):
                return "初始化中"
            u = "美元涨" if row['USD_Ret'] > 0 else "美元跌"
            g = "黄金涨" if row['Gold_Ret'] > 0 else "黄金跌"
            return f"{u} & {g}"

        df['Regime'] = df.apply(get_regime, axis=1)
        
        # 识别连续的市场状态切片
        df['Regime_Grp'] = (df['Regime'] != df['Regime'].shift(1)).cumsum()
        return df
    except Exception as e:
        st.error(f"数据处理出错: {e}")
        return None

# --- 3. 侧边栏 ---
st.sidebar.header("🛠️ 数据控制面板")

# 文件上传器
uploaded_file = st.sidebar.file_uploader("上传您的美国数据文件 (Excel/CSV)", type=['csv', 'xlsx'])

if uploaded_file:
    df = process_data(uploaded_file)
else:
    st.info("👋 请在侧边栏上传数据文件开始分析。")
    st.stop()

# --- 4. 象限筛选逻辑 ---
st.sidebar.subheader("🔍 切片筛选")
regime_list = ["美元涨 & 黄金涨", "美元涨 & 黄金跌", "美元跌 & 黄金涨", "美元跌 & 黄金跌"]
selected_regime = st.sidebar.selectbox("选择目标象限", regime_list)

# 提取该象限的所有历史切片
regime_df = df[df['Regime'] == selected_regime]
slice_summary = regime_df.groupby('Regime_Grp').agg({
    'Date': ['min', 'max', 'count']
}).reset_index()
slice_summary.columns = ['ID', 'Start', 'End', 'Days']
# 过滤掉极短的波动（小于3天），按时间倒序排列
slice_summary = slice_summary[slice_summary['Days'] >= 3].sort_values('Start', ascending=False)

slice_options = slice_summary.apply(
    lambda x: f"{x['Start'].date()} 至 {x['End'].date()} ({x['Days']}天)", axis=1
).tolist()

selected_slice_str = st.sidebar.selectbox("选择具体历史切片", slice_options)

# 定位具体切片数据
slice_idx = slice_options.index(selected_slice_str)
target_id = slice_summary.iloc[slice_idx]['ID']
current_slice_data = df[df['Regime_Grp'] == target_id].copy()

# --- 5. 展示设置 ---
st.sidebar.subheader("📊 图表设置")
all_indicators = ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds', 'CPI_YoY', 'Unemployment']
show_indicators = st.sidebar.multiselect("选择展示指标", all_indicators, default=['USD', 'Gold', 'UST_10Y', 'Oil'])
use_norm = st.sidebar.checkbox("归一化显示 (起点=100)", value=True)

# --- 6. 主界面展示 ---
st.title(f"市场状态：{selected_regime}")
st.caption(f"当前分析切片周期: {selected_slice_str}")

# 指标概览卡片
cols = st.columns(len(show_indicators))
for i, ind in enumerate(show_indicators):
    start_val = current_slice_data[ind].iloc[0]
    end_val = current_slice_data[ind].iloc[-1]
    change = (end_val - start_val) / start_val * 100
    cols[i].metric(ind, f"{end_val:.2f}", f"{change:.2f}%")

# Plotly 交互图表
fig = go.Figure()
for ind in show_indicators:
    y_data = current_slice_data[ind]
    if use_norm:
        y_data = (y_data / y_data.iloc[0]) * 100
    
    fig.add_trace(go.Scatter(
        x=current_slice_data['Date'],
        y=y_data,
        name=ind,
        mode='lines+markers' if len(current_slice_data) < 20 else 'lines',
        hovertemplate='日期: %{x}<br>数值: %{y:.2f}'
    ))

fig.update_layout(
    height=600,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=20, r=20, t=80, b=20),
    xaxis=dict(gridcolor='lightgrey'),
    yaxis=dict(gridcolor='lightgrey', title="归一化数值" if use_norm else "原始数值")
)
st.plotly_chart(fig, use_container_width=True)

# --- 7. 数据摘要表格 ---
with st.expander("查看该切片完整数据摘要"):
    summary_data = []
    for ind in all_indicators:
        s = current_slice_data[ind].iloc[0]
        e = current_slice_data[ind].iloc[-1]
        summary_data.append({
            "指标": ind,
            "起点值": s,
            "终点值": e,
            "区间涨跌幅": f"{((e-s)/s*100):.2f}%",
            "均值": round(current_slice_data[ind].mean(), 2)
        })
    st.table(pd.DataFrame(summary_data))

# --- 8. 凌晨1点决策参考 (最新状态提醒) ---
st.divider()
latest_date = df['Date'].max().date()
latest_regime = df['Regime'].iloc[-1]
st.info(f"📅 **数据最后更新日期**: {latest_date} | **当前最新市场状态**: {latest_regime}")
if latest_regime == selected_regime:
    st.success("🎯 **提示**: 当前市场正处于您选中的象限内，可参考上述历史切片的资产联动规律。")

# 下载功能
st.download_button(
    "导出当前切片数据",
    current_slice_data.to_csv(index=False).encode('utf-8-sig'),
    f"{selected_regime}_{selected_slice_str}.csv",
    "text/csv"
)
