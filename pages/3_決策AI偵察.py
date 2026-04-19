import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 決策AI偵察",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# 門禁驗證
# ──────────────────────────────────────────────
if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("main_portal.py", label="← 返回數位總部大門", use_container_width=False)
    st.stop()

if "決策AI偵察" not in st.session_state.get("enabled_pages", set()):
    st.error("🔒 本功能尚未開放，請由管理員在總部門禁頁勾選啟用「決策AI偵察」")
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
    .war-card {
        background: #FFFFFF; border: 1.5px solid #F0E8E5;
        border-radius: 12px; padding: 1.2rem 1.4rem;
        margin-bottom: 1rem; box-shadow: 0 2px 10px rgba(230,59,31,0.06);
    }
    .war-card.urgent { border-left: 5px solid #E63B1F; }
    .war-card.warn   { border-left: 5px solid #F39C12; }
    .war-card.ok     { border-left: 5px solid #27AE60; }

    .diagnosis-box {
        background: #FFF8F6; border-left: 4px solid #E63B1F;
        padding: 14px 18px; border-radius: 10px;
        margin-bottom: 0.8rem; font-size: 0.9rem; line-height: 1.8;
    }
    .source-tag {
        display: inline-block; background: #F0E8E5; color: #C1320F;
        font-size: 0.72rem; padding: 2px 8px; border-radius: 20px;
        margin-left: 6px; font-weight: 600;
    }
    .kpi-chip {
        display: inline-block; padding: 4px 14px;
        border-radius: 20px; font-size: 0.8rem; font-weight: 700;
        margin: 3px 4px;
    }
    .chip-red   { background: #FDECEC; color: #C0392B; }
    .chip-orange{ background: #FEF5E7; color: #D35400; }
    .chip-green { background: #E9F7EF; color: #1E8449; }

    [data-testid="stMetric"] {
        background: #FFFFFF; padding: 14px; border-radius: 10px;
        border: 1.5px solid #F0E8E5;
        box-shadow: 0 1px 4px rgba(230,59,31,0.07);
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 側邊欄
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 決策AI偵察")
    st.caption("跨部門連動診斷中樞")
    st.divider()
    st.page_link("main_portal.py",                    label="🏢 返回總部大門")
    st.page_link("pages/1_數據戰情中心.py",            label="📊 數據戰情中心")
    st.page_link("pages/2_專案追蹤師.py",              label="🗂️ 專案追蹤師")
    st.page_link("pages/4_品牌數位資產.py",            label="🎨 品牌數位資產")
    st.divider()
    lookback = st.selectbox("比對區間", [1, 2, 3], index=1, format_func=lambda x: f"近 {x} 個月")
    if st.button("🔄 重新診斷", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ──────────────────────────────────────────────
# 標題
# ──────────────────────────────────────────────
st.markdown("# 🧠 決策AI偵察")
st.markdown("**跨部門連動診斷** — 自動偵測營收偏差與逾期任務，產出白話診斷報告")
st.divider()

# ──────────────────────────────────────────────
# 資料載入
# ──────────────────────────────────────────────
from utils.data_engine import (
    load_all_revenue, load_projects,
    get_revenue_anomalies, get_overdue_projects,
    align_store_names,
)

with st.spinner("🔄 正在從各部門資料庫抓取最新數據…"):
    df_rev  = load_all_revenue()
    df_proj = load_projects()

anomalies = get_revenue_anomalies(df_rev, lookback_months=lookback)
overdue   = get_overdue_projects(df_proj)

# ──────────────────────────────────────────────
# KPI 總覽列
# ──────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("⚠️ 營收異常門店", len(anomalies), delta=None)
col2.metric("📋 逾期任務數", len(overdue), delta=None)
col3.metric("✅ 執行中專案", len(df_proj[df_proj["狀態"] == "執行中"]) if "狀態" in df_proj.columns else 0)
total_stores = df_rev["店名"].nunique() if not df_rev.empty else "—"
col4.metric("🏪 監控門店數", total_stores)

st.divider()

# ──────────────────────────────────────────────
# 白話診斷報告
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">🩺 Agent 診斷報告（全中文白話）</div>', unsafe_allow_html=True)

def build_diagnosis(anomalies, overdue, df_proj):
    """產出跨部門連動白話診斷文字。"""
    lines = []
    today_str = date.today().strftime("%Y 年 %m 月 %d 日")
    lines.append(f"**診斷日期：{today_str}**\n")

    # 1. 營收異常
    if anomalies:
        lines.append("### 📉 營收下滑警示")
        for a in anomalies[:5]:
            store  = a["店名"]
            drop   = a["下滑幅度"]
            curr   = a["近期均值"]
            prev   = a["前期均值"]
            src    = a["數據來源"]

            # 嘗試找關聯逾期專案
            related = [p for p in overdue if store in p.get("說明", "") or store in p.get("名稱", "")]
            related_proj_names = [p["名稱"] for p in related]

            msg = (f"**{store}** 近期日均營收約 **{curr:,}** 元，"
                   f"較前期 {prev:,} 元下滑 **{drop}%**。")
            if related_proj_names:
                msg += f"疑因相關專案「{'、'.join(related_proj_names)}」進度落後，尚未改善服務流程所致。"
            else:
                msg += "目前無直接關聯逾期專案，建議現場主管深入查核人力與客流。"
            lines.append(f'<div class="diagnosis-box">{msg}<span class="source-tag">{src}</span></div>')
    else:
        lines.append('<div class="diagnosis-box war-card ok">✅ 近期所有門店營收表現正常，無重大下滑警示。</div>')

    # 2. 逾期任務
    if overdue:
        lines.append("\n### 📋 逾期任務連動分析")
        for p in overdue[:5]:
            src = p["數據來源"]
            msg = (f"專案「**{p['名稱']}**」（{p['部門']}・負責人：{p['負責人']}）"
                   f"已逾期 **{p['逾期天數']} 天**，目前進度僅 {p['進度']}%。"
                   f"此任務若持續延誤，將影響相關門店的服務品質與展店時程。")
            lines.append(f'<div class="diagnosis-box">{msg}<span class="source-tag">{src}</span></div>')
    else:
        lines.append('<div class="diagnosis-box">✅ 目前無逾期任務，各部門執行進度正常。</div>')

    # 3. 綜合研判
    lines.append("\n### 🔍 綜合研判")
    if anomalies and overdue:
        lines.append(
            '<div class="diagnosis-box">'
            "系統偵測到 <b>同時存在</b> 營收下滑與逾期任務的高風險狀態。"
            "建議總指揮召開跨部門緊急會議，優先排除逾期專案障礙，"
            "同時追蹤下滑門店的當周業績走勢，若連續三日仍低於月均值 15% 以上，"
            "應立即啟動門店應急方案。"
            "</div>"
        )
    elif anomalies:
        lines.append(
            '<div class="diagnosis-box">'
            "目前任務執行整體正常，但有門店營收出現下滑訊號。"
            "建議行銷部配合推出短期促銷活動，並由營運部進行現場稽核。"
            "</div>"
        )
    elif overdue:
        lines.append(
            '<div class="diagnosis-box">'
            "目前門店營收穩定，但有專案逾期風險。"
            "建議各部門主管每週更新進度，避免任務堆積影響下季度展店計畫。"
            "</div>"
        )
    else:
        lines.append(
            '<div class="diagnosis-box ok">'
            "✅ 總體狀況良好。各門店營收平穩，所有專案均在時程內推進。"
            "建議持續監控並於月底進行例行回顧。"
            "</div>"
        )

    return "\n".join(lines)


diagnosis_html = build_diagnosis(anomalies, overdue, df_proj)
st.markdown(diagnosis_html, unsafe_allow_html=True)

st.divider()

# ──────────────────────────────────────────────
# 營收偏差明細表
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">📉 營收偏差明細（來源：營收看板）</div>', unsafe_allow_html=True)

if anomalies:
    df_anom = pd.DataFrame(anomalies)
    df_anom = df_anom.rename(columns={
        "店名": "門店", "前期均值": "前期日均(元)", "近期均值": "近期日均(元)",
        "下滑幅度": "下滑幅度(%)", "數據來源": "來源標註",
    })
    st.dataframe(
        df_anom.style.background_gradient(subset=["下滑幅度(%)"], cmap="Reds"),
        use_container_width=True, hide_index=True,
    )

    fig = go.Figure()
    stores = [a["店名"] for a in anomalies[:8]]
    fig.add_bar(name="前期日均", x=stores, y=[a["前期均值"] for a in anomalies[:8]],
                marker_color="#2C3E50")
    fig.add_bar(name="近期日均", x=stores, y=[a["近期均值"] for a in anomalies[:8]],
                marker_color="#E63B1F")
    fig.update_layout(
        barmode="group", title="偏差門店前後期日均業績對比",
        xaxis_title="門店", yaxis_title="日均業績（元）",
        plot_bgcolor="white", paper_bgcolor="white",
        font_family="sans-serif", height=360,
        legend=dict(orientation="h", y=1.12),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.info("✅ 近期無營收下滑超過 10% 的門店。")

# ──────────────────────────────────────────────
# 逾期任務明細表
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">📋 逾期任務明細（來源：專案進度）</div>', unsafe_allow_html=True)

if overdue:
    df_od = pd.DataFrame(overdue)
    df_od = df_od[["編號", "名稱", "部門", "負責人", "截止日", "進度", "逾期天數", "數據來源"]]
    df_od = df_od.rename(columns={"逾期天數": "逾期天數(天)", "數據來源": "來源標註"})
    st.dataframe(
        df_od.style.background_gradient(subset=["逾期天數(天)"], cmap="Oranges"),
        use_container_width=True, hide_index=True,
    )
else:
    st.success("✅ 目前所有任務均在截止日期內。")
