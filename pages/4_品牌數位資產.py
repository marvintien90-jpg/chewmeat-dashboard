import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 品牌數位資產",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("main_portal.py", label="← 返回數位總部大門", use_container_width=False)
    st.stop()

if "品牌數位資產" not in st.session_state.get("enabled_pages", set()):
    st.error("🔒 本功能尚未開放，請由管理員在總部門禁頁勾選啟用「品牌數位資產」")
    st.page_link("main_portal.py", label="← 返回總部", use_container_width=False)
    st.stop()

# ──────────────────────────────────────────────
# CSS（橘紅配色・扁平圓角・全中文）
# ──────────────────────────────────────────────
st.markdown("""
<style>
    .main .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    [data-testid="stSidebarNav"] {display: none !important;}
    [data-testid="stSidebar"] {background: #FAFAFA;}
    .section-header {
        background: #E63B1F; color: white;
        padding: 7px 16px; border-radius: 8px;
        margin: 1rem 0 0.5rem 0; font-weight: 700; font-size: 0.95rem;
    }
    [data-testid="stMetric"] {
        background: #FFFFFF; padding: 14px; border-radius: 10px;
        border: 1.5px solid #F0E8E5;
        box-shadow: 0 1px 4px rgba(230,59,31,0.07);
    }
    [data-testid="stMetricLabel"] {font-size: 0.85rem; color: #888;}
    [data-testid="stMetricValue"] {font-size: 1.5rem; font-weight: 700; color: #1A1A1A;}
    .campaign-card {
        background: #FFFFFF; border: 1.5px solid #F0E8E5;
        border-left: 5px solid #E63B1F; border-radius: 12px;
        padding: 1rem 1.2rem; margin-bottom: 0.8rem;
        box-shadow: 0 2px 8px rgba(230,59,31,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 側邊欄
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎨 品牌行銷部")
    st.caption("活動成效 × 營收增長分析")
    st.divider()
    st.page_link("main_portal.py",                    label="🏢 返回總部大門")
    st.page_link("pages/1_數據戰情中心.py",            label="📊 數據戰情中心")
    st.page_link("pages/2_專案追蹤師.py",              label="🗂️ 專案追蹤師")
    st.page_link("pages/3_決策AI偵察.py",              label="🧠 決策AI偵察")

# ──────────────────────────────────────────────
# 標題
# ──────────────────────────────────────────────
st.markdown("# 🎨 品牌行銷部")
st.markdown("**活動成效追蹤 × 營收增長對照** — 衡量每次行銷活動對業績的實質貢獻")
st.divider()

# ──────────────────────────────────────────────
# 活動資料（靜態範例）
# ──────────────────────────────────────────────
campaigns = pd.DataFrame([
    {"活動名稱": "2025春節優惠套餐", "活動類型": "節慶促銷", "開始日": date(2025, 1, 22),
     "結束日": date(2025, 2, 5),  "投入預算(萬)": 8,  "參與門店數": 18,
     "活動期間日均(萬)": 32.4, "活動前日均(萬)": 26.1, "社群觸及(萬人)": 15.2},
    {"活動名稱": "母親節雙人套餐", "活動類型": "節慶促銷", "開始日": date(2025, 5, 5),
     "結束日": date(2025, 5, 12), "投入預算(萬)": 5,  "參與門店數": 18,
     "活動期間日均(萬)": 29.7, "活動前日均(萬)": 25.3, "社群觸及(萬人)": 9.8},
    {"活動名稱": "暑假嗑肉節", "活動類型": "主題活動", "開始日": date(2025, 7, 1),
     "結束日": date(2025, 7, 31), "投入預算(萬)": 12, "參與門店數": 18,
     "活動期間日均(萬)": 35.2, "活動前日均(萬)": 27.8, "社群觸及(萬人)": 22.5},
    {"活動名稱": "中秋烤肉趴體驗", "活動類型": "主題活動", "開始日": date(2025, 9, 25),
     "結束日": date(2025, 10, 6), "投入預算(萬)": 6,  "參與門店數": 15,
     "活動期間日均(萬)": 28.9, "活動前日均(萬)": 24.6, "社群觸及(萬人)": 11.3},
    {"活動名稱": "尾牙感恩回饋", "活動類型": "節慶促銷", "開始日": date(2025, 12, 15),
     "結束日": date(2025, 12, 28), "投入預算(萬)": 7,  "參與門店數": 18,
     "活動期間日均(萬)": 38.6, "活動前日均(萬)": 27.5, "社群觸及(萬人)": 18.7},
    {"活動名稱": "春節限定石鍋套餐", "活動類型": "節慶促銷", "開始日": date(2026, 1, 25),
     "結束日": date(2026, 2, 10), "投入預算(萬)": 9,  "參與門店數": 18,
     "活動期間日均(萬)": 34.1, "活動前日均(萬)": 28.2, "社群觸及(萬人)": 16.9},
    {"活動名稱": "母親節行銷活動（進行中）", "活動類型": "節慶促銷", "開始日": date(2026, 5, 1),
     "結束日": date(2026, 5, 12), "投入預算(萬)": 5,  "參與門店數": 18,
     "活動期間日均(萬)": None, "活動前日均(萬)": 28.5, "社群觸及(萬人)": 6.2},
])

campaigns["增長幅度(%)"] = campaigns.apply(
    lambda r: round((r["活動期間日均(萬)"] - r["活動前日均(萬)"]) / r["活動前日均(萬)"] * 100, 1)
    if pd.notna(r["活動期間日均(萬)"]) else None, axis=1
)
campaigns["ROI(倍)"] = campaigns.apply(
    lambda r: round((r["活動期間日均(萬)"] - r["活動前日均(萬)"]) * (r["結束日"] - r["開始日"]).days / r["投入預算(萬)"], 1)
    if pd.notna(r["活動期間日均(萬)"]) else None, axis=1
)

completed = campaigns[campaigns["活動期間日均(萬)"].notna()].copy()

# ──────────────────────────────────────────────
# KPI 列
# ──────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("🎯 已執行活動", len(completed))
c2.metric("📈 平均業績增長", f"{completed['增長幅度(%)'].mean():.1f}%")
c3.metric("💰 平均 ROI", f"{completed['ROI(倍)'].mean():.1f} 倍")
c4.metric("📣 累計社群觸及", f"{completed['社群觸及(萬人)'].sum():.0f} 萬人")

st.divider()

# ──────────────────────────────────────────────
# 圖一：活動成效 vs 營收增長對照（橫向雙軸）
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">📊 活動成效 × 營收增長對照圖</div>', unsafe_allow_html=True)

fig1 = go.Figure()
x_labels = completed["活動名稱"].str.replace("（進行中）", "", regex=False)

fig1.add_bar(
    name="活動期間日均(萬)",
    x=x_labels, y=completed["活動期間日均(萬)"],
    marker_color="#E63B1F", opacity=0.9,
    text=completed["活動期間日均(萬)"].apply(lambda v: f"{v:.1f}"),
    textposition="outside",
)
fig1.add_bar(
    name="活動前日均(萬)",
    x=x_labels, y=completed["活動前日均(萬)"],
    marker_color="#FFCBB8", opacity=0.85,
)
fig1.add_scatter(
    name="增長幅度(%)",
    x=x_labels, y=completed["增長幅度(%)"],
    mode="lines+markers+text",
    yaxis="y2",
    line=dict(color="#2C3E50", width=2.5, dash="dot"),
    marker=dict(size=9, color="#2C3E50"),
    text=completed["增長幅度(%)"].apply(lambda v: f"+{v}%"),
    textposition="top center",
)
fig1.update_layout(
    barmode="group",
    yaxis=dict(title="日均業績（萬元）", gridcolor="#F5F5F5"),
    yaxis2=dict(title="增長幅度（%）", overlaying="y", side="right",
                showgrid=False, range=[0, 50]),
    plot_bgcolor="white", paper_bgcolor="white",
    font_family="sans-serif", height=420,
    legend=dict(orientation="h", y=1.12),
    xaxis=dict(tickangle=-20),
)
st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

# ──────────────────────────────────────────────
# 圖二：ROI 泡泡圖（預算 × 增長 × 觸及人數）
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">💡 投入預算 × ROI × 社群觸及 泡泡圖</div>', unsafe_allow_html=True)

fig2 = px.scatter(
    completed,
    x="投入預算(萬)", y="ROI(倍)",
    size="社群觸及(萬人)", color="活動類型",
    text="活動名稱",
    color_discrete_sequence=["#E63B1F", "#FF6B3D"],
    labels={"投入預算(萬)": "投入預算（萬元）", "ROI(倍)": "ROI（倍）"},
    size_max=55, height=400,
)
fig2.update_traces(textposition="top center", textfont_size=11)
fig2.update_layout(
    plot_bgcolor="white", paper_bgcolor="white",
    font_family="sans-serif",
    legend=dict(orientation="h", y=1.1),
)
fig2.add_hline(y=completed["ROI(倍)"].mean(), line_dash="dash",
               line_color="#95A5A6", annotation_text="平均 ROI",
               annotation_position="bottom right")
st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

# ──────────────────────────────────────────────
# 圖三：每月累計行銷觸及趨勢
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">📣 社群觸及趨勢（各活動）</div>', unsafe_allow_html=True)

fig3 = go.Figure()
fig3.add_bar(
    x=x_labels, y=completed["社群觸及(萬人)"],
    marker_color="#E63B1F", opacity=0.85,
    text=completed["社群觸及(萬人)"].apply(lambda v: f"{v:.1f}萬"),
    textposition="outside",
)
fig3.update_layout(
    yaxis_title="觸及人數（萬）", xaxis_tickangle=-20,
    plot_bgcolor="white", paper_bgcolor="white",
    font_family="sans-serif", height=340,
)
st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

# ──────────────────────────────────────────────
# 活動明細表
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">📋 歷次活動完整明細</div>', unsafe_allow_html=True)

show_cols = ["活動名稱", "活動類型", "開始日", "結束日", "投入預算(萬)",
             "參與門店數", "活動前日均(萬)", "活動期間日均(萬)", "增長幅度(%)", "ROI(倍)", "社群觸及(萬人)"]
st.dataframe(campaigns[show_cols], use_container_width=True, hide_index=True)
