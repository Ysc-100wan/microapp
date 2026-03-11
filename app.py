import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="宏观资产象限分析模型",
    page_icon="📈",
    layout="wide"
)

# --- 2. 数据加载函数 (优化版) ---
@st.cache_data
def load_and_process_data(uploaded_file=None):
    # 设定默认文件名 (建议您在GitHub中将Excel/CSV改名为此名称)
    default_filename = 'macro_data.csv'
    
    try:
        # 逻辑：如果有手动上传则用上传的，否则看目录下有没有默认文件
        if uploaded_file is not None:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, header=1)
            else:
                df = pd.read_excel(uploaded_file, header=1)
        elif os.path.exists(default_filename):
            df = pd.read_csv(default_filename, header=1)
        else:
            return None

        # 统一列名映射
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
        
        # 计算1个月(21日)变化率
        window = 21
        df['USD_Ret'] = df['USD'].pct_change(periods=window)
        df['Gold_Ret'] = df['Gold'].pct_change(periods=window)
        
        def get_regime(row):
            if pd.isna(row['USD_Ret']) or pd.isna(row['Gold_Ret']):
                return "初始化中"
            u = "美元涨" if row['USD_Ret'] > 0 else "美元跌"
            g = "黄金涨" if row['Gold_Ret'] > 0 else "黄金跌"
            return f"{u} & {g}"

        df['Regime'] = df.apply(get_regime, axis=1)
        df['Regime_Grp'] = (df['Regime'] != df['Regime'].shift(1)).cumsum()
        return df
    except Exception as e:
        st.error(f"数据处理出错: {e}")
        return None

# --- 3. 侧边栏 ---
st.sidebar.header("🛠️ 数据控制面板")

# 既可以自动读，也可以手动更新
uploaded_file = st.sidebar.file_uploader("更新数据文件 (可选)", type=['csv', 'xlsx'])
df = load_and_process_data(uploaded_file)

if df is None:
    st.warning("⚠️ 未找到数据文件。请确保 GitHub 仓库中有名为 `macro_data.csv` 的文件，或在此处上传。")
    st.stop()

# --- 4. 筛选逻辑 ---
st.sidebar.subheader("🔍 切片筛选")
regime_list = ["美元涨 & 黄金涨", "美元涨 & 黄金跌", "美元跌 & 黄金涨", "美元跌 & 黄金跌"]
selected_regime = st.sidebar.selectbox("选择目标象限", regime_list)

# 提取切片
regime_df = df[df['Regime'] == selected_regime]
slice_summary = regime_df.groupby('Regime_Grp').agg({'Date': ['min', 'max', 'count']}).reset_index()
slice_summary.columns = ['ID', 'Start', 'End', 'Days']
slice_summary = slice_summary[slice_summary['Days'] >= 3].sort_values('Start', ascending=False)

if slice_summary.empty:
    st.error(f"在历史数据中未找到符合 '{selected_regime}' 的切片。")
    st.stop()

slice_options = slice_summary.apply(lambda x: f"{x['Start'].date()} 至 {x['End'].date()} ({x['Days']}天)", axis=1).tolist()
selected_slice_str = st.sidebar.selectbox("选择具体历史切片", slice_options)

slice_idx = slice_options.index(selected_slice_str)
target_id = slice_summary.iloc[slice_idx]['ID']
current_slice_data = df[df['Regime_Grp'] == target_id].copy()

# --- 5. 图表展示 ---
show_indicators = st.sidebar.multiselect("选择展示指标", 
                                        ['USD', 'Gold', 'SP500', 'UST_10Y', 'Oil', 'Copper', 'Fed_Funds', 'CPI_YoY', 'Unemployment'], 
                                        default=['USD', 'Gold', 'Oil'])
use_norm = st.sidebar.checkbox("归一化显示 (起点=100)", value=True)

st.title(f"市场象限: {selected_regime}")
st.caption(f"当前时间切片: {selected_slice_str}")

fig = go.Figure()
for ind in show_indicators:
    y_data = current_slice_data[ind]
    if use_norm:
        y_data = (y_data / y_data.iloc[0]) * 100
    fig.add_trace(go.Scatter(x=current_slice_data['Date'], y=y_data, name=ind, mode='lines'))

fig.update_layout(hovermode="x unified", height=600)
st.plotly_chart(fig, use_container_width=True)

# --- 6. 统计摘要 ---
st.subheader("📊 区间涨跌统计")
summary_list = []
for ind in show_indicators:
    s, e = current_slice_data[ind].iloc[0], current_slice_data[ind].iloc[-1]
    summary_list.append({"指标": ind, "涨跌幅": f"{((e-s)/s*100):.2f}%", "均值": round(current_slice_data[ind].mean(), 2)})
st.table(pd.DataFrame(summary_list))
