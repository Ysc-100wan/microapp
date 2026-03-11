import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import chardet

# --- 1. 页面配置 ---
st.set_page_config(page_title="宏观资产分析模型", layout="wide")

# --- 2. 自动检测编码的读取函数 ---
def smart_read_csv(file_path):
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read(10000))
        encoding = result['encoding']
    # 如果检测到的是 GB2312/GBK，统一用 gbk 读取
    if encoding and ('gb' in encoding.lower() or 'ansi' in encoding.lower()):
        encoding = 'gbk'
    else:
        encoding = 'utf-8'
    return pd.read_csv(file_path, header=1, encoding=encoding)

@st.cache_data
def load_and_process_data(uploaded_file=None):
    try:
        if uploaded_file is not None:
            if uploaded_file.name.endswith('.csv'):
                # 对上传的文件也进行编码检测
                content = uploaded_file.getvalue()
                encoding = chardet.detect(content)['encoding'] or 'utf-8'
                df = pd.read_csv(uploaded_file, header=1, encoding=encoding)
            else:
                df = pd.read_excel(uploaded_file, header=1)
        else:
            # 自动搜索目录下包含 'macro' 的 csv 文件，防止文件名有误
            files = [f for f in os.listdir('.') if 'macro' in f.lower() and f.endswith('.csv')]
            if files:
                df = smart_read_csv(files[0])
            else:
                return None

        # 统一列名映射
        column_mapping = {
            'Unnamed: 0': 'Date', '美元指数': 'USD', '标准普尔500指数': 'SP500',
            '美国:国债收益率:10年': 'UST_10Y', '伦敦市场黄金下午定盘价:按美元': 'Gold',
            '美国:联邦基金利率': 'Fed_Funds', 'CPI:所有项目:同比:美国': 'CPI_YoY',
            '原油': 'Oil', '铜': 'Copper', '美国失业率': 'Unemployment'
        }
        df = df.rename(columns=column_mapping)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True)
        
        # 转换数值列
        num_cols = ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds', 'CPI_YoY', 'Unemployment']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 计算1个月(21日)变化率
        df['USD_Ret'] = df['USD'].pct_change(periods=21)
        df['Gold_Ret'] = df['Gold'].pct_change(periods=21)
        
        def get_regime(row):
            if pd.isna(row['USD_Ret']) or pd.isna(row['Gold_Ret']): return "数据加载中"
            u = "美元涨" if row['USD_Ret'] > 0 else "美元跌"
            g = "黄金涨" if row['Gold_Ret'] > 0 else "黄金跌"
            return f"{u} & {g}"

        df['Regime'] = df.apply(get_regime, axis=1)
        df['Regime_Grp'] = (df['Regime'] != df['Regime'].shift(1)).cumsum()
        return df
    except Exception as e:
        st.error(f"❌ 解析数据出错: {e}")
        return None

# --- 3. 界面逻辑 ---
uploaded_file = st.sidebar.file_uploader("更新数据文件", type=['csv', 'xlsx'])
df = load_and_process_data(uploaded_file)

if df is None:
    st.warning("⚠️ 没找到数据文件。请确认目录下有 macro_data.csv，或在左侧手动上传。")
    st.stop()

# --- 4. 筛选与展示 ---
st.sidebar.subheader("🔍 切片筛选")
regime_list = ["美元涨 & 黄金涨", "美元涨 & 黄金跌", "美元跌 & 黄金涨", "美元跌 & 黄金跌"]
selected_regime = st.sidebar.selectbox("选择目标象限", regime_list)

regime_df = df[df['Regime'] == selected_regime]
slice_summary = regime_df.groupby('Regime_Grp').agg({'Date': ['min', 'max', 'count']}).reset_index()
slice_summary.columns = ['ID', 'Start', 'End', 'Days']
slice_summary = slice_summary[slice_summary['Days'] >= 3].sort_values('Start', ascending=False)

if not slice_summary.empty:
    slice_options = slice_summary.apply(lambda x: f"{x['Start'].date()} 至 {x['End'].date()} ({x['Days']}天)", axis=1).tolist()
    selected_slice_str = st.sidebar.selectbox("选择历史具体切片", slice_options)
    
    target_id = slice_summary.iloc[slice_options.index(selected_slice_str)]['ID']
    slice_data = df[df['Regime_Grp'] == target_id].copy()
    
    # 绘图
    indicators = st.sidebar.multiselect("选择展示指标", ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper'], default=['USD', 'Gold'])
    use_norm = st.sidebar.checkbox("归一化显示", value=True)
    
    fig = go.Figure()
    for ind in indicators:
        y = slice_data[ind]
        if use_norm: y = (y / y.iloc[0]) * 100
        fig.add_trace(go.Scatter(x=slice_data['Date'], y=y, name=ind))
    
    st.title(f"象限: {selected_regime}")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("该象限在历史数据中没有超过3天的记录。")
