import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 页面配置
st.set_page_config(page_title="宏观资产联动分析看板", layout="wide")

st.title("📊 宏观资产联动历史切片分析工具")
st.markdown("上传 Excel 数据，根据**美元 & 黄金**的周变动自动筛选历史切片。")

# 1. 文件上传
uploaded_file = st.file_uploader("请上传你的 Excel 数据文件", type=["xlsx", "csv"])

if uploaded_file:
    # 加载数据 (跳过首行说明，根据你文件实际情况调整)
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    
    # 简单清洗：假设第一列是日期，其他是各指标
    df.columns = ['Date', 'USD_Index', 'SP500', 'Treasury_10Y', 'Gold', 'FFR', 'CPI', 'Oil', 'Copper', 'Unemployment']
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')

    # 2. 按周重采样计算变动
    # 取每周一（周初）和周五（周末）的数据
    df_weekly = df.resample('W-FRI', on='Date').last()
    df_weekly_start = df.resample('W-FRI', on='Date').first()

    # 计算周涨跌幅 (周末价 - 周初价)
    df_analysis = pd.DataFrame(index=df_weekly.index)
    df_analysis['USD_Delta'] = df_weekly['USD_Index'] - df_weekly_start['USD_Index']
    df_analysis['Gold_Delta'] = df_weekly['Gold'] - df_weekly_start['Gold']
    
    # 计算其他指标在当周的变化 (Delta)
    target_cols = ['Oil', 'Copper', 'Treasury_10Y', 'CPI', 'Unemployment']
    for col in target_cols:
        df_analysis[f'{col}_Delta'] = df_weekly[col] - df_weekly_start[col]

    # 3. 定义四种组合
    def classify(row):
        if row['USD_Delta'] > 0 and row['Gold_Delta'] > 0: return "美元涨 & 黄金涨"
        elif row['USD_Delta'] > 0 and row['Gold_Delta'] <= 0: return "美元涨 & 黄金跌"
        elif row['USD_Delta'] <= 0 and row['Gold_Delta'] > 0: return "美元跌 & 黄金涨"
        else: return "美元跌 & 黄金跌"

    df_analysis['Scenario'] = df_analysis.apply(classify, axis=1)

    # --- 侧边栏交互 ---
    st.sidebar.header("筛选设置")
    selected_scenario = st.sidebar.selectbox("选择历史切片场景", df_analysis['Scenario'].unique())

    # 筛选数据
    filtered_df = df_analysis[df_analysis['Scenario'] == selected_scenario]

    # --- 主界面展示 ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("样本周数", len(filtered_df))
    col2.metric("平均原油变动", f"{filtered_df['Oil_Delta'].mean():.2f}")
    col3.metric("平均铜价变动", f"{filtered_df['Copper_Delta'].mean():.2f}")
    col4.metric("平均10Y国债变动", f"{filtered_df['Treasury_10Y_Delta'].mean():.4f}")

    st.subheader(f"📍 场景切片：{selected_scenario}")
    
    # 可视化 1：其他指标变动分布
    fig_hist = px.histogram(filtered_df, x='Oil_Delta', title="原油在该场景下的变动分布", 
                            labels={'Oil_Delta': '周涨跌幅'}, marginal="box", nbins=50)
    st.plotly_chart(fig_hist, use_container_width=True)

    # 可视化 2：散点图查看联动
    fig_scatter = px.scatter(df_analysis, x="USD_Delta", y="Gold_Delta", color="Scenario",
                             title="美元 vs 黄金 周变动全景散点图",
                             hover_data=['Oil_Delta'])
    # 添加辅助线
    fig_scatter.add_vline(x=0, line_dash="dash", line_color="gray")
    fig_scatter.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig_scatter, use_container_width=True)

    # 展示原始数据切片
    with st.expander("查看该场景下的具体日期及详细数据"):
        st.write(filtered_df)