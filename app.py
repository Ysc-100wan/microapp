import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import chardet

# --- 1. 页面配置 ---
st.set_page_config(page_title="宏观区间分析模型", layout="wide")

# --- 2. 稳健数据加载 ---
def smart_read_csv(file_path):
    with open(file_path, 'rb') as f:
        rawdata = f.read(20000)
        result = chardet.detect(rawdata)
        encoding = result['encoding'] or 'utf-8'
    if 'gb' in encoding.lower() or 'ansi' in encoding.lower():
        encoding = 'gbk'
    return pd.read_csv(file_path, header=1, encoding=encoding)

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
        
        for col in ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # --- 核心逻辑：区间分段判定 (Chunking Logic) ---
        # 根据 window 将数据分成固定长度的组
        df['Group_ID'] = df.index // window
        
        def get_group_regime(group):
            if len(group) < 2: return "数据不足"
            # 只比较区间终点和起点
            u_ret = (group['USD'].iloc[-1] - group['USD'].iloc[0])
            g_ret = (group['Gold'].iloc[-1] - group['Gold'].iloc[0])
            u_label = "美元涨" if u_ret > 0 else "美元跌"
            g_label = "黄金涨" if g_ret > 0 else "黄金跌"
            return f"{u_label} & {g_label}"

        # 为每一组计算标签
        regime_map = df.groupby('Group_ID').apply(get_group_regime).to_dict()
        df['Regime'] = df['Group_ID'].map(regime_map)
        
        return df
    except Exception as e:
        st.error(f"数据处理错误: {e}")
        return None

# --- 3. 侧边栏 ---
st.sidebar.header("⚙️ 维度设置")
window_choice = st.sidebar.select_slider("选择判定周期 (天)", options=[7, 21, 42, 63, 126], value=21)

uploaded_file = st.sidebar.file_uploader("更新数据文件", type=['csv', 'xlsx'])
df = load_and_process_data(uploaded_file, window_choice)

if df is None:
    st.info("👋 请在侧边栏上传或确认 macro_data.csv 文件存在。")
    st.stop()

selected_regime = st.sidebar.selectbox("目标象限", ["美元涨 & 黄金涨", "美元涨 & 黄金跌", "美元跌 & 黄金涨", "美元跌 & 黄金跌"])

# 筛选属于该象限的切片 (现在每个切片都是 window 长度)
slice_summary = df[df['Regime'] == selected_regime].groupby('Group_ID').agg({
    'Date': ['min', 'max', 'count']
}).reset_index()
slice_summary.columns = ['Group_ID', 'Start', 'End', 'Days']
slice_summary = slice_summary.sort_values('Start', ascending=False)

if slice_summary.empty:
    st.warning(f"当前 {window_choice}天 维度下没有匹配的区间。")
    st.stop()

slice_options = slice_summary.apply(lambda x: f"{x['Start'].date()} 至 {x['End'].date()} ({x['Days']}天)", axis=1).tolist()
selected_slice_str = st.sidebar.selectbox("选择历史切片", slice_options)

# 获取选定切片的数据
target_group_id = slice_summary.iloc[slice_options.index(selected_slice_str)]['Group_ID']
slice_data = df[df['Group_ID'] == target_group_id].copy()

# --- 4. 绘图 (修复多轴与报错) ---
st.sidebar.subheader("📈 指标配置")
indicators = st.sidebar.multiselect("选择展示指标 (最多4个)", 
                                    ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds'], 
                                    default=['USD', 'Gold'])

if indicators:
    fig = go.Figure()
    colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA']
    
    # 基础布局
    fig.update_layout(
        xaxis=dict(domain=[0.15, 0.85], title=dict(text="日期")),
        hovermode="x unified",
        height=700,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
    )

    for i, ind in enumerate(indicators[:4]):
        # 添加数据曲线
        fig.add_trace(go.Scatter(
            x=slice_data['Date'], y=slice_data[ind],
            name=ind, 
            yaxis=f"y{i+1}" if i > 0 else "y",
            line=dict(color=colors[i], width=2.5)
        ))
        
        # 坐标轴配置 (采用最新 API 避免 titlefont 报错)
        axis_config = dict(
            title=dict(text=ind, font=dict(color=colors[i])),
            tickfont=dict(color=colors[i]),
            showgrid=True if i == 0 else False,
            anchor="x" if i <= 1 else "free",
            overlaying="y" if i > 0 else None,
            side="left" if i % 2 == 0 else "right",
            position=0.05 if i == 2 else (0.95 if i == 3 else None)
        )
        
        if i == 0: fig.update_layout(yaxis=axis_config)
        elif i == 1: fig.update_layout(yaxis2=axis_config)
        elif i == 2: fig.update_layout(yaxis3=axis_config)
        elif i == 3: fig.update_layout(yaxis4=axis_config)

    st.plotly_chart(fig, use_container_width=True)

    # 底部展示区间涨跌
    st.subheader("📊 区间净涨跌确认")
    summary = []
    for ind in indicators:
        start_v = slice_data[ind].iloc[0]
        end_v = slice_data[ind].iloc[-1]
        summary.append({
            "指标": ind,
            "起点价格": f"{start_v:.2f}",
            "终点价格": f"{end_v:.2f}",
            "净涨跌": f"{end_v - start_v:.2f}",
            "幅度": f"{((end_v-start_v)/start_v*100):.2f}%"
        })
    st.table(pd.DataFrame(summary))
