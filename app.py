import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import chardet

# --- 1. 页面配置 ---
st.set_page_config(page_title="高级宏观多轴分析模型", layout="wide")

# --- 2. 编码自动识别函数 ---
def smart_read_csv(file_path):
    with open(file_path, 'rb') as f:
        rawdata = f.read(10000)
        result = chardet.detect(rawdata)
        encoding = result['encoding']
    if encoding and ('gb' in encoding.lower() or 'ansi' in encoding.lower()):
        encoding = 'gbk'
    return pd.read_csv(file_path, header=1, encoding=encoding or 'utf-8')

@st.cache_data
def load_and_process_data(uploaded_file, window):
    try:
        if uploaded_file is not None:
            if uploaded_file.name.endswith('.csv'):
                content = uploaded_file.getvalue()
                encoding = chardet.detect(content)['encoding'] or 'utf-8'
                df = pd.read_csv(uploaded_file, header=1, encoding=encoding)
            else:
                df = pd.read_excel(uploaded_file, header=1)
        else:
            files = [f for f in os.listdir('.') if 'macro' in f.lower() and f.endswith('.csv')]
            if files:
                df = smart_read_csv(files[0])
            else:
                return None

        # 映射列名
        column_mapping = {
            'Unnamed: 0': 'Date', '美元指数': 'USD', '标准普尔500指数': 'SP500',
            '美国:国债收益率:10年': 'UST_10Y', '伦敦市场黄金下午定盘价:按美元': 'Gold',
            '美国:联邦基金利率': 'Fed_Funds', 'CPI:所有项目:同比:美国': 'CPI_YoY',
            '原油': 'Oil', '铜': 'Copper', '美国失业率': 'Unemployment'
        }
        df = df.rename(columns=column_mapping)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True)
        
        # 转换数值
        for col in ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds', 'CPI_YoY', 'Unemployment']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 核心：根据用户选择的 window 计算变化率
        df['USD_Ret'] = df['USD'].pct_change(periods=window)
        df['Gold_Ret'] = df['Gold'].pct_change(periods=window)
        
        def get_regime(row):
            if pd.isna(row['USD_Ret']) or pd.isna(row['Gold_Ret']): return "计算中"
            u = "美元涨" if row['USD_Ret'] > 0 else "美元跌"
            g = "黄金涨" if row['Gold_Ret'] > 0 else "黄金跌"
            return f"{u} & {g}"

        df['Regime'] = df.apply(get_regime, axis=1)
        df['Regime_Grp'] = (df['Regime'] != df['Regime'].shift(1)).cumsum()
        return df
    except Exception as e:
        st.error(f"数据处理出错: {e}")
        return None

# --- 3. 侧边栏设置 ---
st.sidebar.header("⚙️ 模型参数设置")
window_choice = st.sidebar.select_slider("选择时间切片判定维度 (天)", options=[7, 21, 42, 63, 126], value=21)

uploaded_file = st.sidebar.file_uploader("更新数据文件", type=['csv', 'xlsx'])
df = load_and_process_data(uploaded_file, window_choice)

if df is None:
    st.warning("请确认 macro_data.csv 文件存在或手动上传。")
    st.stop()

# 筛选逻辑
regime_list = ["美元涨 & 黄金涨", "美元涨 & 黄金跌", "美元跌 & 黄金涨", "美元跌 & 黄金跌"]
selected_regime = st.sidebar.selectbox("目标象限", regime_list)

regime_df = df[df['Regime'] == selected_regime]
slice_summary = regime_df.groupby('Regime_Grp').agg({'Date': ['min', 'max', 'count']}).reset_index()
slice_summary.columns = ['ID', 'Start', 'End', 'Days']
slice_summary = slice_summary[slice_summary['Days'] >= 3].sort_values('Start', ascending=False)

if slice_summary.empty:
    st.info(f"当前 {window_choice}天 维度下无符合切片，请尝试调整维度。")
    st.stop()

slice_options = slice_summary.apply(lambda x: f"{x['Start'].date()} 至 {x['End'].date()} ({x['Days']}天)", axis=1).tolist()
selected_slice_str = st.sidebar.selectbox("选择历史具体切片", slice_options)

slice_data = df[df['Regime_Grp'] == slice_summary.iloc[slice_options.index(selected_slice_str)]['ID']].copy()

# --- 4. 多轴绘图逻辑 ---
st.sidebar.subheader("📈 图表配置")
indicators = st.sidebar.multiselect("选择展示指标 (最多4个独立坐标轴)", 
                                    ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds'], 
                                    default=['USD', 'Gold', 'Oil'])

if len(indicators) > 0:
    fig = go.Figure()
    colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA'] # 不同轴的颜色
    
    for i, ind in enumerate(indicators[:4]): # 限制前4个使用独立轴
        axis_key = f"y{i+1}" if i > 0 else "y"
        fig.add_trace(go.Scatter(
            x=slice_data['Date'], y=slice_data[ind],
            name=ind, yaxis=axis_key, line=dict(color=colors[i], width=2)
        ))

    # 配置多轴布局
    layout_args = {
        "title": f"多指标联动分析 ({selected_regime})",
        "xaxis": dict(domain=[0.15, 0.85], title="日期"),
        "yaxis": dict(title=indicators[0], titlefont=dict(color=colors[0]), tickfont=dict(color=colors[0])),
    }

    # 动态添加额外的轴
    for i in range(1, len(indicators[:4])):
        side = 'right' if i == 1 else 'left'
        pos = 1 - (i-1)*0.07 if side == 'right' else 0.15 - i*0.07
        layout_args[f"yaxis{i+1}"] = dict(
            title=indicators[i],
            titlefont=dict(color=colors[i]),
            tickfont=dict(color=colors[i]),
            anchor="free" if i > 1 else ("x" if i==1 else None),
            overlaying="y",
            side=side,
            position=pos
        )

    fig.update_layout(**layout_args, height=700, hovermode="x unified", showlegend=True)
    st.plotly_chart(fig, use_container_width=True)
