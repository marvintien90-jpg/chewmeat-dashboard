"""
歷史歷程 — 任務完成趨勢、進度歷史時間軸
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 歷史歷程",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("app.py", label="← 返回數位總部大門", use_container_width=False)
    st.stop()

st.markdown("""
<style>
    .main .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    [data-testid="stSidebarNav"] {display: none !important;}
    [data-testid="stSidebar"] {background: #FAFAFA;}
    .section-header {
        background: #2C3E50; color: white;
        padding: 7px 16px; border-radius: 8px;
        margin: 1rem 0 0.5rem 0; font-weight: 700; font-size: 0.95rem;
    }
    [data-testid="stMetric"] {
        background: #FFFFFF; padding: 14px; border-radius: 10px;
        border: 1.5px solid #E8EEF4;
        box-shadow: 0 1px 4px rgba(44,62,80,0.07);
    }
    .timeline-item {
        border-left: 3px solid #E63B1F;
        padding: 0.5rem 0 0.5rem 1rem;
        margin-bottom: 0.7rem;
        position: relative;
    }
    .timeline-dot {
        width: 10px; height: 10px; border-radius: 50%;
        background: #E63B1F; display: inline-block;
        margin-left: -1.4rem; margin-right: 0.5rem;
        vertical-align: middle;
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 📊 歷史歷程")
    st.caption("任務完成趨勢 · 進度時間軸")
    st.divider()
    st.page_link("app.py",               label="🏢 返回總部大門")
    st.page_link("pages/2_專案進度.py",   label="🗂️ 專案進度")
    st.page_link("pages/4_匯入管理.py",   label="📥 匯入管理")
    st.page_link("pages/7_系統設定.py",   label="⚙️ 系統設定")
    st.divider()
    lookback = st.selectbox("顯示最近", [7, 14, 30, 60, 90], index=2, format_func=lambda x: f"{x} 天")
    if st.button("🔄 重新整理", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("# 📊 歷史歷程")
st.markdown("任務完成趨勢 · 逾期分析 · 每日進度變化")
st.divider()


@st.cache_data(ttl=300, show_spinner=False)
def _load_all() -> tuple[list[dict], list[dict]]:
    from lib.sheets_db import load_tasks, load_history
    return load_tasks(), load_history()


with st.spinner("載入歷史資料…"):
    try:
        tasks, history = _load_all()
    except Exception as e:
        st.error(f"❌ 無法連線 Google Sheets：{e}")
        st.stop()

today = date.today()
cutoff = today - timedelta(days=lookback)

# ── 當前快照 KPI ──────────────────────────────────────────────
total     = len(tasks)
completed = sum(1 for t in tasks if int(t.get("progress", 0)) >= 100)
overdue   = 0
for t in tasks:
    end_str = str(t.get("when_end", "")).strip()
    prog    = int(t.get("progress", 0))
    if end_str and prog < 100:
        try:
            if datetime.strptime(end_str, "%Y-%m-%d").date() < today:
                overdue += 1
        except ValueError:
            pass

avg_prog  = (sum(int(t.get("progress", 0)) for t in tasks) / total) if total else 0
comp_rate = (completed / total * 100) if total else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("📋 總任務數",  total)
c2.metric("✅ 已完成",    completed, delta=f"{comp_rate:.1f}%")
c3.metric("⚠️ 逾期中",    overdue)
c4.metric("📈 平均進度",  f"{avg_prog:.1f}%")

st.divider()

# ── Progress History 圖表 ─────────────────────────────────────
st.markdown('<div class="section-header">📈 進度歷史趨勢（progress_history 表）</div>', unsafe_allow_html=True)

if history:
    df_h = pd.DataFrame(history)
    df_h["date"] = pd.to_datetime(df_h["date"], errors="coerce")
    df_h = df_h.dropna(subset=["date"]).sort_values("date")
    df_h = df_h[df_h["date"].dt.date >= cutoff]

    if not df_h.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_h["date"], y=df_h["completion_rate"].astype(float) * 100,
            name="完成率 (%)", mode="lines+markers",
            line=dict(color="#27AE60", width=2.5),
            hovertemplate="%{x|%m/%d}<br>完成率 %{y:.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df_h["date"], y=df_h["avg_progress"].astype(float),
            name="平均進度 (%)", mode="lines+markers",
            line=dict(color="#E63B1F", width=2, dash="dot"),
            hovertemplate="%{x|%m/%d}<br>平均進度 %{y:.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=df_h["date"], y=df_h["total"].astype(int),
            name="任務總數", opacity=0.25,
            marker_color="#2C3E50", yaxis="y2",
            hovertemplate="%{x|%m/%d}<br>總數 %{y}<extra></extra>",
        ))
        fig.update_layout(
            title="任務進度歷史",
            hovermode="x unified",
            yaxis=dict(title="百分比 (%)", range=[0, 105]),
            yaxis2=dict(title="任務數", overlaying="y", side="right", showgrid=False),
            plot_bgcolor="white", paper_bgcolor="white",
            font_family="sans-serif", height=380,
            legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        disp = df_h[["date", "total", "completed", "avg_progress", "completion_rate"]].copy()
        disp["date"] = disp["date"].dt.strftime("%Y-%m-%d")
        disp["completion_rate"] = disp["completion_rate"].astype(float).apply(lambda x: f"{x*100:.1f}%")
        disp["avg_progress"]    = disp["avg_progress"].astype(float).apply(lambda x: f"{x:.1f}%")
        disp = disp.rename(columns={"date": "日期", "total": "總數", "completed": "完成", "avg_progress": "平均進度", "completion_rate": "完成率"})
        st.dataframe(disp.sort_values("日期", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info(f"最近 {lookback} 天無歷史紀錄。")
else:
    st.info("progress_history 表目前沒有資料。每次「總部專案追蹤助理」執行時會自動記錄每日快照。")

st.divider()

# ── 任務匯入時間軸 ────────────────────────────────────────────
st.markdown('<div class="section-header">🕐 任務匯入時間軸</div>', unsafe_allow_html=True)

import_events: list[dict] = []
for t in tasks:
    ia = str(t.get("imported_at", "")).strip()
    if ia:
        try:
            dt_ia = datetime.strptime(ia, "%Y-%m-%d %H:%M")
            if dt_ia.date() >= cutoff:
                import_events.append({"時間": dt_ia, "任務": t.get("what", "?")[:50], "部門": t.get("who_dept", "—")})
        except ValueError:
            pass

if import_events:
    df_ev = pd.DataFrame(import_events).sort_values("時間", ascending=False)
    df_ev["日期"] = df_ev["時間"].dt.strftime("%Y-%m-%d %H:%M")

    # Group by date for bar chart
    df_ev["日期_only"] = df_ev["時間"].dt.date.astype(str)
    daily_counts = df_ev.groupby("日期_only").size().reset_index(name="匯入數")
    fig2 = px.bar(daily_counts, x="日期_only", y="匯入數",
                  title=f"每日新增任務數（最近 {lookback} 天）",
                  color="匯入數", color_continuous_scale="Oranges", height=300)
    fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                       font_family="sans-serif", coloraxis_showscale=False,
                       xaxis_title="日期", yaxis_title="新增任務數")
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    st.markdown(f"**最近 {lookback} 天共新增 {len(df_ev)} 筆任務：**")
    st.dataframe(df_ev[["日期", "任務", "部門"]], use_container_width=True, hide_index=True)
else:
    st.info(f"最近 {lookback} 天無新增匯入記錄。")

st.divider()

# ── 逾期任務分析 ──────────────────────────────────────────────
st.markdown('<div class="section-header">⚠️ 逾期任務分析</div>', unsafe_allow_html=True)

overdue_list = []
for t in tasks:
    end_str = str(t.get("when_end", "")).strip()
    prog    = int(t.get("progress", 0))
    if end_str and prog < 100:
        try:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            if end_date < today:
                overdue_list.append({
                    "任務":    t.get("what", "?")[:45],
                    "部門":    t.get("who_dept", "—"),
                    "負責人":  t.get("who_person", "—"),
                    "截止日":  end_str,
                    "進度":    prog,
                    "逾期天數": (today - end_date).days,
                })
        except ValueError:
            pass

if overdue_list:
    df_od = pd.DataFrame(overdue_list).sort_values("逾期天數", ascending=False)
    fig3 = px.bar(df_od.head(15), x="逾期天數", y="任務", orientation="h",
                  color="逾期天數", color_continuous_scale="Reds",
                  title="逾期任務排行（天數越多越緊急）", height=max(300, len(df_od.head(15)) * 32))
    fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                       font_family="sans-serif", coloraxis_showscale=False)
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
    st.dataframe(df_od[["任務", "部門", "負責人", "截止日", "進度", "逾期天數"]],
                 use_container_width=True, hide_index=True)
else:
    st.success("✅ 目前沒有逾期任務，執行狀況良好！")

# ── 寫入今日快照 ──────────────────────────────────────────────
st.divider()
with st.expander("📸 寫入今日進度快照（手動觸發）"):
    st.caption("通常由「總部專案追蹤助理」自動記錄。若需手動補錄可點擊下方按鈕。")
    if st.button("📸 記錄今日快照", use_container_width=False):
        try:
            from lib.sheets_db import upsert_history
            entry = {
                "date":            str(today),
                "total":           total,
                "completed":       completed,
                "avg_progress":    round(avg_prog, 2),
                "completion_rate": round(comp_rate / 100, 4),
            }
            upsert_history(entry)
            st.success(f"✅ 已記錄 {today} 快照：完成率 {comp_rate:.1f}%")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"寫入失敗：{e}")
