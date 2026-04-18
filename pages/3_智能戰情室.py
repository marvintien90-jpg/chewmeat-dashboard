"""
嗑肉石鍋 數位總部 — 智能戰情室
跨域診斷（營收 × 專案）、AI 建議、證據鏈標註、LINE Notify 自動推播。
"""
import calendar
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.revenue_data import CLOSED_STORES, PORTAL_CSS, load_all_data, plotly_chart
from utils.notifier import check_and_notify, send_line_notify

# ── 頁面設定 ────────────────────────────────────────────────
st.set_page_config(
    page_title="智能戰情室 — 嗑肉石鍋",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(PORTAL_CSS, unsafe_allow_html=True)

st.sidebar.markdown("## 🤖 智能戰情室")
st.sidebar.divider()
st.sidebar.caption("跨域診斷 · AI 建議 · 自動推播")

# ── 頂部核心開關 ─────────────────────────────────────────────
st.header("🤖 智能戰情室")

col_toggle, col_token = st.columns([1, 3])
with col_toggle:
    auto_mode = st.toggle("🤖 自動化小幫手開關", value=False, key="auto_toggle")
with col_token:
    if auto_mode:
        line_token = st.text_input(
            "LINE Notify 金鑰（開啟自動推播必填）",
            type="password", key="line_token",
            placeholder="從 notify-bot.line.me 取得 Token",
        )
    else:
        line_token = ""

if auto_mode:
    st.success("自動化小幫手已啟用 ✅  系統將持續監控異常並在偏差 ≥ 5% 時自動推播 LINE。")
else:
    st.info("小幫手已關閉。開啟後系統將自動診斷並推播警示。")

st.divider()

# ── 載入資料 ────────────────────────────────────────────────
with st.spinner("載入營收資料..."):
    rev_data = load_all_data()

# 取得本次 session 的專案資料（若有匯入）
proj_data: pd.DataFrame = st.session_state.get("tasks", pd.DataFrame())

if rev_data.empty:
    st.error("無法取得營收資料，請確認網路連線。")
    st.stop()

valid_rev = rev_data[rev_data["營業額"].notna() & (rev_data["營業額"] > 0)]
latest_date = valid_rev["日期"].max().date()
yr, mn = latest_date.year, latest_date.month
days_in_month = calendar.monthrange(yr, mn)[1]

# ════════════════════════════════════════════════════════════
# 跨域診斷：整合營收與專案資料
# ════════════════════════════════════════════════════════════
st.subheader("跨域診斷總覽")

# ── 1. 本月各店達成率快照 ────────────────────────────────────
cur_month = valid_rev[
    (valid_rev["日期"].dt.year == yr) & (valid_rev["日期"].dt.month == mn)
    & ~valid_rev["門店"].isin(CLOSED_STORES)
]

store_prog = cur_month.groupby("門店").agg(
    實際營業額=("營業額", "sum"),
    已營業天數=("日期", "nunique"),
    月目標=("本月目標", "first"),
).reset_index()
store_prog["日均實際"] = (store_prog["實際營業額"] / store_prog["已營業天數"]).round(0)
store_prog["日均目標"] = (store_prog["月目標"] / days_in_month).round(0)
store_prog["預估月營收"] = (store_prog["日均實際"] * days_in_month).round(0)
store_prog["預估達成率"] = (store_prog["預估月營收"] / store_prog["月目標"] * 100).round(1)
store_prog["偏差率"] = ((store_prog["日均實際"] - store_prog["日均目標"]) / store_prog["日均目標"] * 100).round(1)
store_prog = store_prog.dropna(subset=["月目標"])

# 彙總指標
total_stores = len(store_prog)
danger_stores = store_prog[store_prog["預估達成率"] < 85]
low_stores = store_prog[(store_prog["預估達成率"] >= 85) & (store_prog["預估達成率"] < 100)]
ok_stores = store_prog[store_prog["預估達成率"] >= 100]

m1, m2, m3, m4 = st.columns(4)
m1.metric("監控門店數", f"{total_stores} 家")
m2.metric("預估可達標", f"{len(ok_stores)} 家")
m3.metric("略低", f"{len(low_stores)} 家")
m4.metric("危險（<85%）", f"{len(danger_stores)} 家")

# ════════════════════════════════════════════════════════════
# 證據鏈 AI 診斷報告
# ════════════════════════════════════════════════════════════
st.subheader("AI 診斷建議（附證據鏈）")
st.caption("每條建議均附有原始資料來源標註，確保可追溯性。")


def evidence_tag(source: str) -> str:
    """產生橘色證據鏈標籤 HTML"""
    return f'<span style="background:#FFE4D6; color:#C73A18; border-radius:6px; padding:2px 8px; font-size:0.78rem; margin-left:8px;">🔗 來源：{source}</span>'


def render_finding(icon: str, title: str, body: str, source: str, level: str = "warning"):
    """渲染單條診斷發現，附證據鏈"""
    bg_map = {"danger": "#FFEAEA", "warning": "#FFF8F0", "ok": "#F0FFF4"}
    border_map = {"danger": "#E8431A", "warning": "#FF6B35", "ok": "#44BB44"}
    bg = bg_map.get(level, "#FFF5F2")
    border = border_map.get(level, "#E8431A")
    st.markdown(f"""
    <div style="background:{bg}; border-left:4px solid {border};
                border-radius:8px; padding:14px 18px; margin-bottom:10px;">
        <div style="font-weight:700; color:#2D1A0A; font-size:0.97rem;">
            {icon} {title} {evidence_tag(source)}
        </div>
        <div style="color:#5A3A2A; font-size:0.88rem; margin-top:6px; line-height:1.6;">
            {body}
        </div>
    </div>
    """, unsafe_allow_html=True)


findings_generated = 0

# ── 診斷 1：危險門店警示 ─────────────────────────────────────
if not danger_stores.empty:
    for _, row in danger_stores.iterrows():
        source_ref = f"營收表-{row['門店']} {yr}年{mn}月"
        gap = row["月目標"] - row["預估月營收"]
        render_finding(
            icon="🚨",
            title=f"【{row['門店']}】預估達成率僅 {row['預估達成率']:.0f}%，需立即介入",
            body=(
                f"目前日均實際 <b>{row['日均實際']:,.0f} 元</b>，"
                f"距月目標 {row['月目標']:,.0f} 元仍差 <b>{gap:,.0f} 元</b>。<br>"
                f"建議：本週加強促銷力度或核查服務問題，避免月底衝刺壓力過大。"
            ),
            source=source_ref,
            level="danger",
        )
        findings_generated += 1

# ── 診斷 2：偏差 ≥ 5% 自動推播 ───────────────────────────────
alert_candidates = store_prog[store_prog["偏差率"].abs() >= 5]
if auto_mode and not alert_candidates.empty and line_token:
    store_actual = dict(zip(store_prog["門店"], store_prog["日均實際"]))
    store_target = dict(zip(store_prog["門店"], store_prog["日均目標"]))
    alerts = check_and_notify(store_actual, store_target, line_token, threshold_pct=5.0)

    if alerts:
        notified_stores = [a["門店"] for a in alerts if a["已推播"]]
        if notified_stores:
            st.success(f"LINE 推播已送出 → {', '.join(notified_stores)}")

# ── 診斷 3：高偏差門店（正向） ───────────────────────────────
high_performers = store_prog[store_prog["偏差率"] >= 10]
if not high_performers.empty:
    for _, row in high_performers.iterrows():
        source_ref = f"營收表-{row['門店']} {yr}年{mn}月"
        render_finding(
            icon="⭐",
            title=f"【{row['門店']}】表現優異，超過日均目標 {row['偏差率']:.1f}%",
            body=(
                f"日均實際 <b>{row['日均實際']:,.0f} 元</b>（目標 {row['日均目標']:,.0f} 元）。<br>"
                f"建議：記錄本店本月成功因素，提取複製到其他門店。"
            ),
            source=source_ref,
            level="ok",
        )
        findings_generated += 1

# ── 診斷 4：跨域 — 有未完成任務的門店 vs 業績下滑 ────────────
if not proj_data.empty and "所屬門店" in proj_data.columns:
    overdue_tasks = proj_data[
        (proj_data["狀態"].isin(["延遲", "進行中"])) &
        (proj_data.get("截止日期", "").apply(
            lambda x: pd.notna(x) and str(x) < str(date.today())
        ) if "截止日期" in proj_data.columns else False)
    ]

    if not overdue_tasks.empty:
        for store, group in overdue_tasks.groupby("所屬門店"):
            rev_row = store_prog[store_prog["門店"] == store]
            if rev_row.empty:
                continue
            rate = rev_row.iloc[0]["預估達成率"]
            if rate < 95:
                source_ref = f"營收表-{store} {yr}年{mn}月 ＋ 專案進度表"
                render_finding(
                    icon="⚠️",
                    title=f"【{store}】有 {len(group)} 筆逾期任務，且業績達成率僅 {rate:.0f}%",
                    body=(
                        f"逾期任務：{', '.join(group['任務名稱'].tolist())}。<br>"
                        f"建議：優先釐清任務延遲是否影響門店運作，安排緊急支援。"
                    ),
                    source=source_ref,
                    level="danger",
                )
                findings_generated += 1

if findings_generated == 0:
    st.success("✅ 目前所有門店運作正常，未偵測到需要立即關注的異常。")

st.divider()

# ════════════════════════════════════════════════════════════
# 本月各店預估達成率視覺化
# ════════════════════════════════════════════════════════════
st.subheader(f"{yr}年{mn}月 各門店預估達成率")
st.caption(f"資料來源：Google Sheets 營收表 {yr}年{mn}月，基準日 {latest_date.strftime('%m/%d')}")

if not store_prog.empty:
    store_sorted = store_prog.sort_values("預估達成率", ascending=False)
    colors = [
        "#44BB44" if r >= 100 else ("#FFaa00" if r >= 85 else "#E8431A")
        for r in store_sorted["預估達成率"]
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=store_sorted["門店"], y=store_sorted["預估達成率"],
        marker_color=colors,
        text=[f"{r:.0f}%" for r in store_sorted["預估達成率"]],
        textposition="outside",
        hovertemplate="%{x}<br>預估達成率：%{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=100, line_dash="dash", line_color="#C73A18", annotation_text="目標 100%")
    fig.update_layout(height=420, xaxis_tickangle=-45,
                      paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    plotly_chart(fig, key="war_target")

# ════════════════════════════════════════════════════════════
# 偏差率熱力圖（各店日均偏差）
# ════════════════════════════════════════════════════════════
st.subheader("日均偏差率分佈")
st.caption(f"資料來源：Google Sheets 營收表 {yr}年{mn}月 — 偏差 = (日均實際 - 日均目標) ÷ 日均目標 × 100%")

if not store_prog.empty and "偏差率" in store_prog.columns:
    fig2 = px.bar(
        store_prog.sort_values("偏差率"),
        x="門店", y="偏差率",
        color="偏差率",
        color_continuous_scale=["#E8431A", "#FFFFFF", "#44BB44"],
        color_continuous_midpoint=0,
        title="各門店日均偏差率（正=超標、負=低於目標）",
        height=380,
    )
    fig2.add_hline(y=0, line_dash="dash", line_color="#999")
    fig2.add_hline(y=5, line_dash="dot", line_color="#44BB44",
                   annotation_text="+5% 優良門檻")
    fig2.add_hline(y=-5, line_dash="dot", line_color="#E8431A",
                   annotation_text="-5% 預警門檻")
    fig2.update_layout(xaxis_tickangle=-45, paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    plotly_chart(fig2, key="war_deviation")

# ════════════════════════════════════════════════════════════
# LINE Notify 手動測試（開關開啟時顯示）
# ════════════════════════════════════════════════════════════
if auto_mode:
    st.divider()
    st.subheader("LINE Notify 手動推播測試")
    test_msg = st.text_area(
        "推播訊息內容（可自訂）",
        value=f"【嗑肉石鍋 測試推播】\n日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n目前系統正常運作中。",
        height=100,
    )
    if st.button("發送測試推播"):
        if not line_token:
            st.warning("請先填入 LINE Notify 金鑰")
        else:
            ok = send_line_notify(line_token, test_msg)
            if ok:
                st.success("推播成功！請確認 LINE 通知。")
            else:
                st.error("推播失敗，請確認金鑰是否正確。")
