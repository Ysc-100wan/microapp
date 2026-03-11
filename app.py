import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import chardet

# --- 1. 页面配置 ---
st.set_page_config(page_title="高级宏观多轴模型", layout="wide")

# --- 2. 编码识别 ---
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
        st.error(f"解析错误: {e}")
        return None

# --- 3. 界面逻辑 ---
st.sidebar.header("⚙️ 维度设置")
window_choice = st.sidebar.select_slider("选择判定周期 (天)", options=[7, 21, 42, 63, 126], value=21)

uploaded_file = st.sidebar.file_uploader("更新文件", type=['csv', 'xlsx'])
df = load_and_process_data(uploaded_file, window_choice)

if df is None:
    st.warning("等待数据加载...")
    st.stop()

selected_regime = st.sidebar.selectbox("目标象限", ["美元涨 & 黄金涨", "美元涨 & 黄金跌", "美元跌 & 黄金涨", "美元跌 & 黄金跌"])

regime_df = df[df['Regime'] == selected_regime]
slice_summary = regime_df.groupby('Regime_Grp').agg({'Date': ['min', 'max', 'count']}).reset_index()
slice_summary.columns = ['ID', 'Start', 'End', 'Days']
slice_summary = slice_summary[slice_summary['Days'] >= 3].sort_values('Start', ascending=False)

if slice_summary.empty:
    st.info("当前维度无匹配切片。")
    st.stop()

slice_options = slice_summary.apply(lambda x: f"{x['Start'].date()} 至 {x['End'].date()} ({x['Days']}天)", axis=1).tolist()
selected_slice_str = st.sidebar.selectbox("历史切片", slice_options)
slice_data = df[df['Regime_Grp'] == slice_summary.iloc[slice_options.index(selected_slice_str)]['ID']].copy()

# --- 4. 绘图 (兼容新版 Plotly) ---
st.sidebar.subheader("📈 指标配置")
indicators = st.sidebar.multiselect("展示指标 (1-4个)", 
                                    ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper'], 
                                    default=['USD', 'Gold'])

if indicators:
    fig = go.Figure()
    colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA']
    
    # 基础布局：使用新的 API 规范
    fig.update_layout(
        xaxis=dict(domain=[0.15, 0.85], title=dict(text="日期")),
        hovermode="x unified",
        height=700,
        template="plotly_white",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    for i, ind in enumerate(indicators[:4]):
        # 添加数据
        fig.add_trace(go.Scatter(
            x=slice_data['Date'], y=slice_data[ind],
            name=ind, 
            yaxis=f"y{i+1}" if i > 0 else "y",
            line=dict(color=colors[i], width=2)
        ))
        
        # 兼容性设置：将 titlefont 改为 title_font，或者嵌套在 title 中
        axis_config = dict(
            title=dict(text=ind, font=dict(color=colors[i])),
            tickfont=dict(color=colors[i]),
            anchor="x" if i <= 1 else "free",
            overlaying="y" if i > 0 else None,
            side="left" if i % 2 == 0 else "right",
            position=0.05 if i == 2 else (0.95 if i == 3 else None)
        )
        
        if i == 0:
            fig.update_layout(yaxis=axis_config)
        elif i == 1:
            fig.update_layout(yaxis2=axis_config)
        elif i == 2:
            fig.update_layout(yaxis3=axis_config)
        elif i == 3:
            fig.update_layout(yaxis4=axis_config)

    st.plotly_chart(fig, use_container_width=True)
