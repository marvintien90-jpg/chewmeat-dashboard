"""
營運部 — 專案進度
資料來源：Google Sheets（與總部專案追蹤助理相同後端）
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 專案進度",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# 門禁驗證
# ──────────────────────────────────────────────
if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("app.py", label="← 返回數位總部大門", use_container_width=False)
    st.stop()

# ──────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
    .main .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    [data-testid="stSidebarNav"] {display: none !important;}
    [data-testid="stSidebar"] {background: #FAFAFA;}

    [data-testid="stMetric"] {
        background: #FFFFFF; padding: 14px; border-radius: 10px;
        border: 1.5px solid #E8EEF4;
        box-shadow: 0 1px 4px rgba(44,62,80,0.07);
    }
    [data-testid="stMetricLabel"] {font-size: 0.85rem; color: #888;}
    [data-testid="stMetricValue"] {font-size: 1.5rem; font-weight: 700; color: #1A1A1A;}

    .section-header {
        background: #2C3E50; color: white;
        padding: 7px 16px; border-radius: 8px;
        margin: 1rem 0 0.5rem 0; font-weight: 700; font-size: 0.95rem;
    }
    .section-header-orange {
        background: #E63B1F; color: white;
        padding: 7px 16px; border-radius: 8px;
        margin: 1rem 0 0.5rem 0; font-weight: 700; font-size: 0.95rem;
    }

    .proj-card {
        background: #FFFFFF; border: 1.5px solid #E8EEF4;
        border-radius: 12px; padding: 1rem 1.2rem;
        margin-bottom: 0.8rem; border-left: 5px solid #2C3E50;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .proj-card.urgent { border-left-color: #E63B1F; }
    .proj-card.done   { border-left-color: #27AE60; opacity: 0.85; }
    .proj-card.overdue{ border-left-color: #F39C12; }

    .proj-title { font-size: 1rem; font-weight: 700; color: #1A1A1A; margin: 0 0 0.3rem 0; }
    .proj-meta  { font-size: 0.78rem; color: #888; line-height: 1.7; }
    .proj-tag   { display: inline-block; padding: 2px 8px; border-radius: 20px;
                  font-size: 0.72rem; font-weight: 600; margin-right: 4px; }
    .tag-executing { background: #EBF5FB; color: #2980B9; }
    .tag-planning  { background: #FFF3CD; color: #856404; }
    .tag-done      { background: #D5F5E3; color: #1E8449; }
    .tag-overdue   { background: #FDEBD0; color: #D35400; }

    .progress-bar-bg {
        background: #F0F0F0; border-radius: 6px; height: 8px;
        width: 100%; margin-top: 4px;
    }
    .progress-bar-fill {
        background: linear-gradient(90deg, #2C3E50, #3D5A80);
        border-radius: 6px; height: 8px;
    }
    .progress-bar-fill.done { background: linear-gradient(90deg, #27AE60, #52BE80); }
    .progress-bar-fill.overdue { background: linear-gradient(90deg, #F39C12, #F8C471); }

    .error-box {
        background: #FFF3EE; border-left: 4px solid #E63B1F;
        padding: 14px 18px; border-radius: 10px; margin: 1rem 0;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 資料載入（接 Google Sheets 後端）
# ──────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_tasks_from_sheets():
    try:
        from lib.sheets_db import load_tasks
        return load_tasks(), None
    except Exception as e:
        return [], str(e)


def derive_status(row: dict, today: date) -> str:
    prog = int(row.get("progress", 0))
    if prog >= 100:
        return "已完成"
    end_str = str(row.get("when_end", "")).strip()
    if end_str:
        try:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            if end_date < today:
                return "逾期"
        except ValueError:
            pass
    start_str = str(row.get("when_start", "")).strip()
    if start_str:
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            if start_date <= today:
                return "執行中"
        except ValueError:
            pass
    return "規劃中"


def tasks_to_df(tasks: list[dict]) -> pd.DataFrame:
    today = date.today()
    rows = []
    for t in tasks:
        status = derive_status(t, today)
        rows.append({
            "編號":   t.get("task_id", "")[:8],
            "名稱":   t.get("what", "（無標題）"),
            "目標":   t.get("why", ""),
            "部門":   t.get("who_dept", "—"),
            "負責人":  t.get("who_person", "—"),
            "開始日":  t.get("when_start", ""),
            "截止日":  t.get("when_end", ""),
            "進度":   int(t.get("progress", 0)),
            "狀態":   status,
            "說明":   t.get("how", ""),
            "來源檔": t.get("source_file", ""),
            "_task_id": t.get("task_id", ""),
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
# 側邊欄
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗂️ 營運部")
    st.caption("專案進度追蹤")
    st.divider()
    st.page_link("app.py",               label="🏢 返回總部大門")
    st.page_link("pages/1_營收看板.py",   label="📊 財務部 — 營收看板")
    st.page_link("pages/3_智能戰情室.py", label="🧠 智能戰情室")
    st.divider()

    view = st.radio("顯示模式", ["📋 列表視圖", "📊 統計分析"], horizontal=True)
    st.divider()

    dept_filter = st.multiselect("篩選部門", options=[], key="dept_filter_placeholder")
    status_filter = st.multiselect("篩選狀態", ["執行中", "規劃中", "已完成", "逾期"], default=[])

    st.divider()
    if st.button("🔄 重新整理", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ──────────────────────────────────────────────
# 主體
# ──────────────────────────────────────────────
st.markdown("# 🗂️ 營運部 — 專案進度")
st.markdown("**即時同步** 總部專案追蹤助理資料庫 · Google Sheets 後端")
st.divider()

# 載入資料
with st.spinner("🔄 正在從 Google Sheets 讀取最新專案資料…"):
    raw_tasks, err = load_tasks_from_sheets()

if err:
    st.markdown(f"""
    <div class="error-box">
    ⚠️ <b>無法連線 Google Sheets</b><br><br>
    錯誤訊息：<code>{err[:300]}</code><br><br>
    <b>請確認：</b><br>
    1. Streamlit Cloud Secrets 已設定 <code>[gcp_service_account]</code><br>
    2. <code>google_sheets.spreadsheet_id</code> 已填寫<br>
    3. 服務帳戶 email 已加入 Google Sheet 為編輯者
    </div>
    """, unsafe_allow_html=True)

    st.info("💡 前往 **Streamlit Cloud → 你的 App → Settings → Secrets**，"
            "貼上與「總部專案追蹤助理」相同的 secrets.toml 內容即可連動。")
    st.stop()

if not raw_tasks:
    st.warning("⚠️ Google Sheets 中目前沒有任何專案資料，請先在「總部專案追蹤助理」App 匯入任務。")
    st.stop()

df = tasks_to_df(raw_tasks)

# 更新側邊欄部門選項
all_depts = sorted(df["部門"].unique().tolist())
dept_selection = st.sidebar.multiselect("篩選部門", options=all_depts, default=[], key="dept_filter_real")

# 套用篩選
df_view = df.copy()
if dept_selection:
    df_view = df_view[df_view["部門"].isin(dept_selection)]
if status_filter:
    df_view = df_view[df_view["狀態"].isin(status_filter)]

# ──────────────────────────────────────────────
# KPI 列
# ──────────────────────────────────────────────
today = date.today()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📋 總專案數", len(df))
c2.metric("⚡ 執行中", len(df[df["狀態"] == "執行中"]))
c3.metric("✅ 已完成", len(df[df["狀態"] == "已完成"]))
c4.metric("⚠️ 逾期", len(df[df["狀態"] == "逾期"]))
avg_prog = df["進度"].mean() if not df.empty else 0
c5.metric("📈 平均進度", f"{avg_prog:.1f}%")

st.divider()

# ──────────────────────────────────────────────
# 列表視圖
# ──────────────────────────────────────────────
STATUS_TAG = {
    "執行中": '<span class="proj-tag tag-executing">執行中</span>',
    "規劃中": '<span class="proj-tag tag-planning">規劃中</span>',
    "已完成": '<span class="proj-tag tag-done">已完成</span>',
    "逾期":   '<span class="proj-tag tag-overdue">⚠️逾期</span>',
}

def card_class(status):
    return {"已完成": "done", "逾期": "overdue", "執行中": "urgent"}.get(status, "")

def progress_class(status):
    return {"已完成": "done", "逾期": "overdue"}.get(status, "")


if view == "📋 列表視圖":
    st.markdown(f'<div class="section-header">📋 專案列表（顯示 {len(df_view)} 筆）</div>', unsafe_allow_html=True)

    if df_view.empty:
        st.info("目前沒有符合篩選條件的專案。")
    else:
        df_sorted = df_view.sort_values(["狀態", "截止日"], ascending=[True, True])
        for _, row in df_sorted.iterrows():
            tag = STATUS_TAG.get(row["狀態"], "")
            cc  = card_class(row["狀態"])
            pc  = progress_class(row["狀態"])
            prog = row["進度"]

            desc = row["說明"] or row["目標"] or ""
            if len(desc) > 80:
                desc = desc[:80] + "…"

            card_html = f"""
            <div class="proj-card {cc}">
              <div class="proj-title">{row['名稱']}</div>
              <div class="proj-meta">
                {tag}
                🏢 {row['部門']} ｜ 👤 {row['負責人']} ｜
                📅 {row['截止日'] or '—'}
                {'｜ 📁 ' + row['來源檔'][:20] if row['來源檔'] else ''}
              </div>
              {f'<div class="proj-meta" style="margin-top:4px;color:#555;">{desc}</div>' if desc else ''}
              <div class="progress-bar-bg">
                <div class="progress-bar-fill {pc}" style="width:{min(prog,100)}%;"></div>
              </div>
              <div class="proj-meta" style="text-align:right;margin-top:2px;">{prog}%</div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

else:
    # ──────────────────────────────────────────────
    # 統計分析
    # ──────────────────────────────────────────────
    st.markdown('<div class="section-header">📊 統計分析</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)

    with col_a:
        # 狀態分佈
        status_counts = df["狀態"].value_counts().reset_index()
        status_counts.columns = ["狀態", "數量"]
        color_map = {"執行中": "#3498DB", "規劃中": "#F39C12", "已完成": "#27AE60", "逾期": "#E63B1F"}
        fig1 = px.pie(status_counts, names="狀態", values="數量",
                      color="狀態", color_discrete_map=color_map,
                      title="專案狀態分佈")
        fig1.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                           font_family="sans-serif", height=320)
        st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

    with col_b:
        # 部門工作量
        dept_counts = df.groupby("部門").size().reset_index(name="專案數").sort_values("專案數")
        fig2 = px.bar(dept_counts, x="專案數", y="部門", orientation="h",
                      title="各部門專案數", color_discrete_sequence=["#2C3E50"])
        fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                           font_family="sans-serif", height=320)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # 執行中進度條
    executing = df[df["狀態"] == "執行中"].sort_values("進度", ascending=False)
    if not executing.empty:
        st.markdown('<div class="section-header">⚡ 執行中專案進度</div>', unsafe_allow_html=True)
        fig3 = go.Figure()
        fig3.add_bar(x=executing["進度"], y=executing["名稱"].str[:20],
                     orientation="h", marker_color="#3498DB",
                     text=executing["進度"].apply(lambda v: f"{v}%"),
                     textposition="outside")
        fig3.add_vline(x=50, line_dash="dash", line_color="#E63B1F",
                       annotation_text="50% 基準", annotation_position="top")
        fig3.update_layout(xaxis=dict(range=[0, 110]), plot_bgcolor="white",
                           paper_bgcolor="white", font_family="sans-serif", height=max(300, len(executing)*36))
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    # 甘特圖
    gantt_df = df[df["開始日"].str.len() > 0].copy() if "開始日" in df.columns else pd.DataFrame()
    if not gantt_df.empty and "截止日" in gantt_df.columns:
        gantt_df = gantt_df[gantt_df["截止日"].str.len() > 0].copy()
    if not gantt_df.empty:
        st.markdown('<div class="section-header">📅 甘特圖時程</div>', unsafe_allow_html=True)
        gantt_df = gantt_df.rename(columns={"名稱": "Task", "開始日": "Start", "截止日": "Finish", "部門": "Resource"})
        fig4 = px.timeline(gantt_df.head(20), x_start="Start", x_end="Finish",
                           y="Task", color="Resource",
                           color_discrete_sequence=px.colors.qualitative.Set2)
        fig4.add_vline(x=str(today), line_dash="dash", line_color="#E63B1F",
                       annotation_text="今天")
        fig4.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                           font_family="sans-serif", height=max(300, len(gantt_df.head(20))*32))
        st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})

    # 完整資料表
    st.markdown('<div class="section-header">📋 完整專案清單</div>', unsafe_allow_html=True)
    show_cols = ["名稱", "部門", "負責人", "狀態", "進度", "開始日", "截止日", "說明"]
    st.dataframe(df_view[show_cols], use_container_width=True, hide_index=True)
