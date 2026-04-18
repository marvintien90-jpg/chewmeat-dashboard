"""
嗑肉石鍋 數位總部 — 主入口
提供品牌首頁與快速導覽，引導使用者進入各功能模組。
執行方式：streamlit run main_portal.py
"""
from datetime import datetime

import streamlit as st

from utils.revenue_data import PORTAL_CSS, load_all_data

# ── 頁面設定 ────────────────────────────────────────────────
st.set_page_config(
    page_title="嗑肉石鍋 數位總部",
    page_icon="🍲",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(PORTAL_CSS, unsafe_allow_html=True)

# ── 側邊欄 ──────────────────────────────────────────────────
st.sidebar.markdown("## 🍲 嗑肉石鍋")
st.sidebar.markdown("**數位總部**")
st.sidebar.caption(f"今日：{datetime.now().strftime('%Y-%m-%d')}")
st.sidebar.divider()

st.sidebar.markdown("""
**功能模組**
- 📊 [營收看板](./1_營收看板)
- 📋 [專案進度](./2_專案進度)
- 🤖 [智能戰情室](./3_智能戰情室)
- 📥 [資料匯入中心](./4_資料匯入中心)
""")

st.sidebar.divider()

if st.sidebar.button("🔄 清除快取重新整理"):
    st.cache_data.clear()
    st.rerun()

# ── 首頁主體 ────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 2rem 0 1rem;">
    <h1 style="font-size:2.8rem; color:#E8431A; margin:0;">🍲 嗑肉石鍋</h1>
    <h2 style="font-size:1.4rem; color:#C73A18; margin:0.3rem 0 0;">數 位 總 部</h2>
    <p style="color:#7A5544; margin-top:0.6rem; font-size:1rem;">
        整合營收、專案、智能分析與資料匯入的一站式管理平台
    </p>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── 四大模組卡片 ────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div style="background:#FFF5F2; border:1.5px solid #FFD9CC; border-radius:16px; padding:20px; text-align:center; min-height:160px;">
        <div style="font-size:2.5rem;">📊</div>
        <div style="font-weight:700; color:#E8431A; font-size:1.1rem; margin:8px 0 4px;">營收看板</div>
        <div style="color:#7A5544; font-size:0.85rem;">全店業績總覽、門店排行、達標追蹤、異常警示</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="background:#FFF5F2; border:1.5px solid #FFD9CC; border-radius:16px; padding:20px; text-align:center; min-height:160px;">
        <div style="font-size:2.5rem;">📋</div>
        <div style="font-weight:700; color:#E8431A; font-size:1.1rem; margin:8px 0 4px;">專案進度</div>
        <div style="color:#7A5544; font-size:0.85rem;">任務管理、負責人追蹤、截止日提醒</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div style="background:#FFF5F2; border:1.5px solid #FFD9CC; border-radius:16px; padding:20px; text-align:center; min-height:160px;">
        <div style="font-size:2.5rem;">🤖</div>
        <div style="font-weight:700; color:#E8431A; font-size:1.1rem; margin:8px 0 4px;">智能戰情室</div>
        <div style="color:#7A5544; font-size:0.85rem;">跨域診斷、AI 建議、LINE 自動推播</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div style="background:#FFF5F2; border:1.5px solid #FFD9CC; border-radius:16px; padding:20px; text-align:center; min-height:160px;">
        <div style="font-size:2.5rem;">📥</div>
        <div style="font-weight:700; color:#E8431A; font-size:1.1rem; margin:8px 0 4px;">資料匯入中心</div>
        <div style="color:#7A5544; font-size:0.85rem;">客服評論、市場調查 CSV 手動上傳</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ── 即時概況（快速指標）──────────────────────────────────────
st.subheader("📡 即時概況")

with st.spinner("載入最新資料..."):
    data = load_all_data()

if not data.empty:
    valid = data[data["營業額"].notna() & (data["營業額"] > 0)]
    latest_date = valid["日期"].max()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "最新資料日期",
        latest_date.strftime("%Y-%m-%d"),
    )
    m2.metric(
        "活躍門店數",
        f"{valid[~valid['已結村']]['門店'].nunique()} 家",
    )
    # 本月累計
    yr, mn = latest_date.year, latest_date.month
    this_month = valid[(valid["年份"] == yr) & (valid["月份"] == mn)]
    m3.metric(
        "本月累計營業額",
        f"{this_month['營業額'].sum():,.0f} 元",
    )
    # 昨日/最新一日全店合計
    last_day_data = valid[valid["日期"] == latest_date]
    m4.metric(
        f"{latest_date.strftime('%m/%d')} 全店合計",
        f"{last_day_data['營業額'].sum():,.0f} 元",
    )
else:
    st.warning("目前無法取得資料，請確認網路連線或 Google Sheets 存取權限。")

st.divider()

st.caption("💡 請透過左側選單或上方功能卡片進入各模組。如需重新整理資料，請點選側邊欄的「清除快取重新整理」按鈕。")
