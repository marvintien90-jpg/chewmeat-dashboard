"""
2_專案追蹤師.py
跨 6 部門工作追蹤 · AI 督導摘要 · 核准/批示回寫
"""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import date, datetime

# ──────────────────────────────────────────────
# Display helper (used throughout the page)
# ──────────────────────────────────────────────
_BLANK_DISPLAY = {"", "nan", "NaN", "None", "none", "NONE", "NAN", "-", "N/A", "n/a"}


def _disp(v, fallback="—") -> str:
    """Return v as string, or fallback if v is blank/nan/None."""
    s = str(v).strip()
    return s if s not in _BLANK_DISPLAY else fallback

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 專案追蹤師",
    page_icon="🗂️",
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

if "專案追蹤師" not in st.session_state.get("enabled_pages", set()):
    st.error("🔒 本功能尚未開放，請由管理員在總部門禁頁勾選啟用「專案追蹤師」")
    st.page_link("main_portal.py", label="← 返回總部", use_container_width=False)
    st.stop()

# ──────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
    .main .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    [data-testid="stSidebarNav"] {display: none !important;}
    [data-testid="stSidebar"] {background: #FAFAFA;}

    [data-testid="stMetric"] {
        background: #FFFFFF; padding: 14px; border-radius: 10px;
        border: 1.5px solid #F0E8E5;
        box-shadow: 0 1px 4px rgba(230,59,31,0.07);
    }
    [data-testid="stMetricLabel"] {font-size: 0.85rem; color: #888;}
    [data-testid="stMetricValue"] {font-size: 1.5rem; font-weight: 700;}

    .section-hdr {
        background: #E63B1F; color: white;
        padding: 7px 16px; border-radius: 8px;
        margin: 1.2rem 0 0.6rem; font-weight: 700; font-size: 0.95rem;
    }
    .section-hdr-dark {
        background: #2C3E50; color: white;
        padding: 7px 16px; border-radius: 8px;
        margin: 1.2rem 0 0.6rem; font-weight: 700; font-size: 0.95rem;
    }

    /* AI 督導摘要區 */
    .ai-summary-box {
        background: linear-gradient(135deg, #FFF3EE 0%, #FFE8E0 100%);
        border: 2px solid #E63B1F;
        border-radius: 14px;
        padding: 1.4rem 1.8rem;
        margin-bottom: 1.5rem;
    }
    .ai-summary-title {
        font-size: 1.05rem; font-weight: 800; color: #C1320F;
        margin-bottom: 0.8rem; display: flex; align-items: center; gap: 8px;
    }
    .ai-item {
        background: white; border-radius: 10px;
        border-left: 5px solid #E63B1F;
        padding: 0.7rem 1rem; margin-bottom: 0.5rem;
        font-size: 0.88rem;
    }
    .ai-item.yellow { border-left-color: #F59E0B; }
    .ai-item-dept { font-weight: 700; color: #E63B1F; font-size: 0.8rem; }
    .ai-item-task { font-weight: 600; color: #1A1A1A; }
    .ai-item-meta { color: #888; font-size: 0.76rem; margin-top: 2px; }

    /* 任務卡片 */
    .task-card {
        background: #FFFFFF; border: 1.5px solid #E8EEF4;
        border-radius: 12px; padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem; border-left: 5px solid #2C3E50;
        box-shadow: 0 1px 5px rgba(0,0,0,0.04);
    }
    .task-card.red   { border-left-color: #DC2626; }
    .task-card.yellow{ border-left-color: #F59E0B; }
    .task-card.green { border-left-color: #10B981; }
    .task-card.gray  { border-left-color: #9CA3AF; opacity: 0.8; }

    .task-title  { font-size: 0.96rem; font-weight: 700; color: #1A1A1A; }
    .task-meta   { font-size: 0.78rem; color: #888; line-height: 1.8; margin-top: 2px; }
    .task-tag    { display: inline-block; padding: 2px 8px; border-radius: 20px;
                   font-size: 0.71rem; font-weight: 600; margin-right: 4px; }
    .tag-todo    { background: #F3F4F6; color: #6B7280; }
    .tag-doing   { background: #DBEAFE; color: #1D4ED8; }
    .tag-done    { background: #D1FAE5; color: #065F46; }
    .tag-overdue { background: #FEE2E2; color: #DC2626; }

    .prog-bg   { background:#F0F0F0; border-radius:6px; height:6px; margin-top:5px; }
    .prog-fill { height:6px; border-radius:6px;
                 background: linear-gradient(90deg,#E63B1F,#FF6B3D); }
    .prog-fill.done    { background: linear-gradient(90deg,#10B981,#34D399); }
    .prog-fill.overdue { background: linear-gradient(90deg,#F59E0B,#FCD34D); }

    /* 批示面板 */
    .approval-box {
        background: #F8FAFC; border: 1.5px solid #E2E8F0;
        border-radius: 10px; padding: 1rem 1.2rem; margin-top: 0.4rem;
    }

    /* 部門狀態橫幅 */
    .dept-status-ok   { color: #065F46; background: #D1FAE5;
                        padding: 4px 12px; border-radius: 20px;
                        font-size: 0.8rem; font-weight: 600; }
    .dept-status-warn { color: #92400E; background: #FEF3C7;
                        padding: 4px 12px; border-radius: 20px;
                        font-size: 0.8rem; font-weight: 600; }
    .dept-status-err  { color: #991B1B; background: #FEE2E2;
                        padding: 4px 12px; border-radius: 20px;
                        font-size: 0.8rem; font-weight: 600; }
    .dept-status-pending { color: #1E40AF; background: #DBEAFE;
                        padding: 4px 12px; border-radius: 20px;
                        font-size: 0.8rem; font-weight: 600; }
    .error-box {
        background: #FFF3EE; border-left: 4px solid #E63B1F;
        padding: 12px 16px; border-radius: 10px; margin: 0.5rem 0;
        font-size: 0.85rem;
    }

    /* ── 手機響應式：任務卡片改為單欄顯示 ── */
    @media (max-width: 640px) {
        .main .block-container { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
        .task-card { padding: 0.75rem 0.9rem; margin-bottom: 0.5rem; }
        .task-title { font-size: 0.92rem; }
        .task-meta  { font-size: 0.72rem; }
        [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
        .section-hdr, .section-hdr-dark { font-size: 0.85rem; }
    }

    /* ── 進度條全寬修正 ── */
    .prog-bg { width: 100%; }

    /* 高質感版本 */
    .task-card {
        transition: box-shadow 0.2s ease;
    }
    .task-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.10);
    }
    .quality-score-high { color: #27AE60; }
    .quality-score-mid  { color: #F39C12; }
    .quality-score-low  { color: #E74C3C; }
    .source-tab-badge {
        display: inline-block; background: #EBF5FB; color: #1A5276;
        border-radius: 4px; padding: 1px 6px; font-size: 0.7rem; margin-left: 6px;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 資料載入
# ──────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def _cached_load(cache_key: str):
    from utils.data_engine import load_all_dept_tasks
    return load_all_dept_tasks(cache_key=cache_key)


def _daily_key() -> str:
    from datetime import timedelta
    now = datetime.now()
    if now.hour < 8:
        return str(date.today() - timedelta(days=1))
    return str(date.today())


# ──────────────────────────────────────────────
# 側邊欄
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗂️ 專案追蹤師")
    st.caption("跨部門工作進度總覽")
    st.divider()
    st.page_link("main_portal.py", label="🏢 返回總部大門")
    st.page_link("pages/1_數據戰情中心.py", label="📊 數據戰情中心")
    st.page_link("pages/3_決策AI偵察.py",   label="🧠 決策AI偵察")
    st.divider()

    view_mode = st.radio("顯示模式", ["📋 卡片視圖", "📊 統計分析", "✍️ 審核批示"], horizontal=False)
    st.divider()

    dept_opts = ["行銷", "人資", "採購", "行政", "財務", "資訊"]
    dept_filter = st.multiselect("篩選部門", dept_opts, default=[])
    status_filter = st.multiselect("篩選狀態", ["待辦", "進行中", "已完成", "逾期"], default=[])
    light_filter = st.multiselect("燈號篩選", ["🔴 紅燈", "🟡 黃燈", "🟢 綠燈", "⚪ 已完成"], default=[])
    st.divider()

    if st.button("🔄 重新整理資料", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ──────────────────────────────────────────────
# 主體標題
# ──────────────────────────────────────────────
st.markdown("# 🗂️ 專案追蹤師")
st.markdown("**跨 6 部門** 工作進度即時追蹤 · AI 督導摘要 · 紅黃燈預警 · 總指揮批示回寫")
st.divider()

# ──────────────────────────────────────────────
# 載入資料
# ──────────────────────────────────────────────
with st.spinner("🔄 正在從各部門 Google Sheets 讀取最新任務資料…"):
    df_all, errors = _cached_load(_daily_key())

# ── 跑馬燈 & AI 摘要 ──
from utils.ui_helpers import render_marquee, render_ai_summary
_total_tasks = len(df_all)
if not df_all.empty:
    _n_overdue = len(df_all[df_all["處理狀態"] == "逾期"])
    _n_doing = len(df_all[df_all["處理狀態"] == "進行中"])
    _n_done = len(df_all[df_all["處理狀態"] == "已完成"])
    _n_red = len(df_all[df_all["燈號"] == "🔴"]) if "燈號" in df_all.columns else 0
    _avg_p = df_all["目前進度"].mean() if "目前進度" in df_all.columns else 0
else:
    _n_overdue = _n_doing = _n_done = _n_red = 0
    _avg_p = 0
render_marquee([
    f"總任務 {_total_tasks} 筆",
    f"進行中 {_n_doing} 件",
    f"逾期 {_n_overdue} 件" if _n_overdue > 0 else "無逾期任務",
    f"🔴 紅燈 {_n_red} 項" if _n_red > 0 else "紅燈清零",
    f"平均進度 {_avg_p:.1f}%",
])
_summary_bullets = []
if _n_red > 0:
    _summary_bullets.append(f"共 {_n_red} 項紅燈任務需要總指揮立即介入")
if _n_overdue > 0:
    _summary_bullets.append(f"逾期任務 {_n_overdue} 件，建議優先督促相關負責人")
if _n_doing > 0:
    _summary_bullets.append(f"進行中任務 {_n_doing} 件，整體平均進度 {_avg_p:.1f}%")
if not _summary_bullets:
    _summary_bullets = ["目前無紅燈或逾期任務，各部門執行狀況良好"]
render_ai_summary("專案追蹤師 — 督導摘要", _summary_bullets)

# ── 部門授權狀態列 ──
st.markdown('<div class="section-hdr-dark">📡 各部門 Sheet 連線狀態</div>', unsafe_allow_html=True)
dept_cols = st.columns(6)
dept_list = ["行銷", "人資", "採購", "行政", "財務", "資訊"]
for i, dept in enumerate(dept_list):
    with dept_cols[i]:
        if dept in errors:
            err_msg = errors[dept]
            if "等待授權" in err_msg or "未設定" in err_msg:
                st.markdown(f'<div class="dept-status-pending">⏳ {dept}<br><small>等待授權中</small></div>',
                            unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="dept-status-err">❌ {dept}<br><small>連線失敗</small></div>',
                            unsafe_allow_html=True)
        else:
            dept_count = len(df_all[df_all["來源部門"] == dept]) if not df_all.empty else 0
            st.markdown(f'<div class="dept-status-ok">✅ {dept}<br><small>{dept_count} 筆</small></div>',
                        unsafe_allow_html=True)

if errors:
    with st.expander("⚠️ 查看連線失敗部門詳情", expanded=True):
        for dept, msg in errors.items():
            st.markdown(f"""
            <div class="error-box">
            <b>{dept}</b>：{msg[:200]}
            </div>
            """, unsafe_allow_html=True)
        st.info("💡 請前往 [管理] 系統設定 頁面貼入各部門的 Google Sheet 網址（需設定為「知道連結者皆可檢視」）")
        if st.session_state.get("is_admin", False):
            st.page_link("pages/5_系統設定.py", label="⚙️ 前往系統設定配置 Google Sheet 網址", use_container_width=True)

st.divider()

# ── 資料品質診斷 ──────────────────────────────
from utils.data_engine import get_dept_validation_results
_val_results = get_dept_validation_results()

if _val_results:
    _all_problems = []
    for _dept_k, _result_v in _val_results.items():
        _all_problems.extend(_result_v.get("problems", []))

    # Always show the quality panel when we have validation results
    _expander_label = (
        f"🔍 資料品質診斷 — 發現 {len(_all_problems)} 筆需修正項目"
        if _all_problems else
        "✅ 資料品質診斷 — 各部門欄位對應概覽"
    )
    with st.expander(_expander_label, expanded=bool(_all_problems)):
        # ── Quality scores row ─────────────────────────────────
        _q_cols = st.columns(max(1, len(_val_results)))
        for _qi, (_dept_k, _result_v) in enumerate(_val_results.items()):
            _q = _result_v.get("quality", {})
            _score = _q.get("quality_score", 0)
            _tab_title = _result_v.get("tab_title", "")
            _color = "#27AE60" if _score >= 80 else ("#F39C12" if _score >= 60 else "#E74C3C")
            with _q_cols[_qi]:
                st.markdown(f"""<div style="text-align:center;padding:8px;background:#FAFAFA;
                    border-radius:8px;border:1px solid #eee;">
                    <div style="font-size:0.8rem;color:#666;">{_dept_k}</div>
                    <div style="font-size:1.4rem;font-weight:800;color:{_color};">{_score}</div>
                    <div style="font-size:0.65rem;color:#999;">品質分數</div>
                    {f'<div style="font-size:0.65rem;color:#3498DB;margin-top:2px;">📑 {_tab_title}</div>' if _tab_title else ''}
                    </div>""", unsafe_allow_html=True)

        # ── Column mapping summary ──────────────────────────────
        st.markdown("---")
        st.markdown("##### 🗂️ 欄位對應結果（AI 自動偵測）")
        _map_cols = st.columns(max(1, len(_val_results)))
        _STD_ICONS = {
            "任務項目": "📌", "負責人": "👤", "截止日期": "📅",
            "目前進度": "📊", "處理狀態": "🏷️", "最後更新": "🕒"
        }
        for _qi, (_dept_k, _result_v) in enumerate(_val_results.items()):
            _col_map = _result_v.get("column_mapping", {})
            _raw_hdrs = _result_v.get("raw_headers", [])
            with _map_cols[_qi]:
                st.markdown(f"**{_dept_k}**")
                if _col_map:
                    for _std, _orig in _col_map.items():
                        _icon = _STD_ICONS.get(_std, "▸")
                        _mapped_note = (
                            f'<span style="color:#27AE60;">✓</span>'
                            if _std == _orig else
                            f'<span style="color:#3498DB;">↦</span>'
                        )
                        st.markdown(
                            f'<div style="font-size:0.76rem;line-height:1.7;">'
                            f'{_icon} <b>{_std}</b> {_mapped_note} '
                            f'<code style="font-size:0.7rem;">{_orig}</code></div>',
                            unsafe_allow_html=True
                        )
                    # Highlight unmapped important columns
                    for _std in ["任務項目", "負責人", "截止日期", "目前進度"]:
                        if _std not in _col_map:
                            st.markdown(
                                f'<div style="font-size:0.76rem;color:#E74C3C;">'
                                f'{_STD_ICONS.get(_std,"▸")} <b>{_std}</b>'
                                f' <span style="color:#E74C3C;">⚠ 未偵測到</span></div>',
                                unsafe_allow_html=True
                            )
                else:
                    st.caption("（未取得對應資訊）")
                if _raw_hdrs:
                    _unmapped = [h for h in _raw_hdrs if h not in _col_map.values()][:6]
                    if _unmapped:
                        st.markdown(
                            f'<div style="font-size:0.7rem;color:#999;margin-top:4px;">'
                            f'原始欄位: {", ".join(_unmapped[:6])}'
                            f'{"…" if len(_raw_hdrs) > 6 else ""}</div>',
                            unsafe_allow_html=True
                        )

        # ── Problem rows correction form ────────────────────────
        if _all_problems:
            st.markdown("---")
            st.markdown("**⚠️ 可在下方直接修正後同步回 Google Sheet：**")
            from utils.data_engine import write_dept_field
            for _pi, _prob in enumerate(_all_problems[:20]):
                with st.container():
                    _pc1, _pc2, _pc3 = st.columns([3, 3, 2])
                    with _pc1:
                        st.markdown(f"**{_prob.get('dept', '')}** → {str(_prob.get('task',''))[:30]}")
                        st.caption(f"⚠️ {_prob.get('issue_desc', '')}")
                    with _pc2:
                        _fix_key = f"fix_{_pi}_{_prob.get('row_index', 0)}"
                        _fix_val = st.text_input(
                            f"修正 {_prob.get('field_to_fix', '')}",
                            value=_prob.get("current_value", ""),
                            key=_fix_key,
                            placeholder=f"輸入{_prob.get('field_to_fix', '')}…",
                            label_visibility="collapsed",
                        )
                    with _pc3:
                        if st.button("回寫", key=f"wb_{_pi}_{_prob.get('row_index', 0)}"):
                            _ok = write_dept_field(
                                _prob.get("sheet_id", ""),
                                _prob.get("row_index", 0),
                                _prob.get("field_to_fix", ""),
                                _fix_val,
                                gid=_prob.get("gid", "0"),
                            )
                            if _ok:
                                st.success("已回寫，請重新整理")
                            else:
                                _sheet_url = f"https://docs.google.com/spreadsheets/d/{_prob.get('sheet_id','')}/edit"
                                st.warning(f"無法直接回寫（需服務帳號授權），請[手動修正]({_sheet_url})")

st.divider()

# ──────────────────────────────────────────────
# KPI 總覽
# ──────────────────────────────────────────────
total = len(df_all)
if not df_all.empty:
    n_todo     = len(df_all[df_all["處理狀態"] == "待辦"])
    n_doing    = len(df_all[df_all["處理狀態"] == "進行中"])
    n_done     = len(df_all[df_all["處理狀態"] == "已完成"])
    n_overdue  = len(df_all[df_all["處理狀態"] == "逾期"])
    n_red      = len(df_all[df_all.get("燈號", pd.Series()) == "🔴"]) if "燈號" in df_all.columns else 0
    avg_prog   = df_all["目前進度"].mean() if "目前進度" in df_all.columns else 0
else:
    n_todo = n_doing = n_done = n_overdue = n_red = 0
    avg_prog = 0

# ── 第一列：核心 KPIs ──────────────────────────────────────────
kc = st.columns(6)
kc[0].metric("📋 總任務數", total)
kc[1].metric("⏳ 待辦", n_todo)
kc[2].metric("⚡ 進行中", n_doing)
kc[3].metric("✅ 已完成", n_done)
kc[4].metric("⚠️ 逾期", n_overdue,
             delta=f"-{n_overdue} 件" if n_overdue > 0 else None,
             delta_color="inverse")
kc[5].metric("📈 平均進度", f"{avg_prog:.1f}%")

# ── 第二列：最累負責人 Top3 + 各部門完工率 ─────────────────────
if not df_all.empty:
    # 最累負責人：未完成任務最多的人
    active_df = df_all[df_all["處理狀態"] != "已完成"]
    if not active_df.empty and "負責人" in active_df.columns:
        owner_counts = (active_df.groupby("負責人").size()
                        .sort_values(ascending=False).head(3))
        top3_parts = [f"**{n}** ({c}件)" for n, c in owner_counts.items() if str(n).strip()]
        top3_str = "　".join(top3_parts) if top3_parts else "—"
    else:
        top3_str = "—"

    # 各部門完工率
    dept_completion: dict[str, str] = {}
    for dept_name, grp in df_all.groupby("來源部門"):
        done = len(grp[grp["處理狀態"] == "已完成"])
        total_dept = len(grp)
        pct = round(done / total_dept * 100) if total_dept > 0 else 0
        dept_completion[dept_name] = f"{pct}%"
    completion_str = "　".join([f"**{d}** {p}" for d, p in sorted(dept_completion.items())])

    st.markdown(f"""
    <div style="background:#FFFBF9;border:1.5px solid #F0E8E5;border-radius:12px;
                padding:0.9rem 1.2rem;margin:0.8rem 0;display:flex;gap:2rem;flex-wrap:wrap;">
      <div style="flex:1;min-width:200px;">
        <div style="font-size:0.78rem;color:#888;margin-bottom:4px;">🏋️ 最累負責人 Top 3（進行中任務數）</div>
        <div style="font-size:0.92rem;">{top3_str}</div>
      </div>
      <div style="flex:2;min-width:260px;">
        <div style="font-size:0.78rem;color:#888;margin-bottom:4px;">📊 各部門完工率</div>
        <div style="font-size:0.92rem;">{completion_str}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ──────────────────────────────────────────────
# ★ AI 督導摘要（頁面頂部固定顯示）
# ──────────────────────────────────────────────
from utils.data_engine import get_top_red_items

red_items = get_top_red_items(df_all, n=3)

if red_items:
    def _build_reason(item: dict) -> str:
        parts = []
        if item["_overdue"] > 0:
            parts.append(f"已逾期 **{item['_overdue']} 天**")
        if item["_stale"] > 3:
            parts.append(f"失聯 **{item['_stale']} 天**未更新")
        if item["目前進度"] == 0:
            parts.append("進度掛零")
        return "；".join(parts) if parts else "需要關注"

    items_html = ""
    for rank, item in enumerate(red_items, 1):
        light = item["燈號"]
        css_cls = "yellow" if light == "🟡" else ""
        reason = _build_reason(item)
        _dl = _disp(item.get("截止日期", ""))
        deadline_str = f"截止：{_dl}" if _dl != "—" else "無截止日"
        items_html += (
            f'<div class="ai-item {css_cls}">'
            f'<div>'
            f'<span class="ai-item-dept">{light} #{rank} · {item["來源部門"]}部</span>'
            f'<span class="task-tag tag-overdue" style="margin-left:6px;">{item["處理狀態"]}</span>'
            f'</div>'
            f'<div class="ai-item-task">{item["任務項目"]}</div>'
            f'<div class="ai-item-meta">'
            f'👤 {_disp(item.get("負責人", ""))} ｜ {deadline_str} ｜ 進度 {item["目前進度"]}% ｜ {reason}'
            f'</div>'
            f'</div>'
        )

    footer = '<div style="font-size:0.76rem;color:#999;margin-top:0.6rem;">⏱ 資料快取至每日 08:00 更新 · 點擊「審核批示」頁籤可直接批示</div>'
    st.markdown(
        f'<div class="ai-summary-box">'
        f'<div class="ai-summary-title">🤖 AI 督導摘要 — 需要總指揮立即介入的 {len(red_items)} 個紅燈項目</div>'
        f'{items_html}{footer}'
        f'</div>',
        unsafe_allow_html=True,
    )
else:
    st.success("✅ 目前無紅燈任務，各部門工作進展正常")

# ──────────────────────────────────────────────
# 篩選套用
# ──────────────────────────────────────────────
df_view = df_all.copy() if not df_all.empty else pd.DataFrame(columns=list(df_all.columns) if not df_all.empty else [])

if dept_filter and not df_view.empty:
    df_view = df_view[df_view["來源部門"].isin(dept_filter)]
if status_filter and not df_view.empty:
    df_view = df_view[df_view["處理狀態"].isin(status_filter)]
if light_filter and not df_view.empty and "燈號" in df_view.columns:
    light_keys = []
    for lf in light_filter:
        if "🔴" in lf: light_keys.append("🔴")
        elif "🟡" in lf: light_keys.append("🟡")
        elif "🟢" in lf: light_keys.append("🟢")
        elif "⚪" in lf: light_keys.append("⚪")
    if light_keys:
        df_view = df_view[df_view["燈號"].isin(light_keys)]

# ──────────────────────────────────────────────
# 視圖一：卡片視圖
# ──────────────────────────────────────────────
STATUS_TAG = {
    "待辦":   '<span class="task-tag tag-todo">待辦</span>',
    "進行中": '<span class="task-tag tag-doing">進行中</span>',
    "已完成": '<span class="task-tag tag-done">✅ 完成</span>',
    "逾期":   '<span class="task-tag tag-overdue">⚠️ 逾期</span>',
}

LIGHT_TO_CARD = {"🔴": "red", "🟡": "yellow", "🟢": "green", "⚪": "gray"}
PROG_CLASS    = {"已完成": "done", "逾期": "overdue"}

if view_mode == "📋 卡片視圖":
    st.markdown(f'<div class="section-hdr">📋 任務清單（顯示 {len(df_view)} 筆）</div>',
                unsafe_allow_html=True)

    if df_view.empty:
        st.info("目前沒有符合篩選條件的任務。")
    else:
        sort_order = {"🔴": 0, "🟡": 1, "🟢": 2, "⚪": 3}
        df_sorted = df_view.copy()
        if "燈號" in df_sorted.columns:
            df_sorted["_sort"] = df_sorted["燈號"].map(sort_order).fillna(4)
            df_sorted = df_sorted.sort_values("_sort")

        for _, row in df_sorted.iterrows():
            light  = row.get("燈號", "🟢")
            status = row.get("處理狀態", "待辦")
            prog   = int(row.get("目前進度", 0))
            card_cls = LIGHT_TO_CARD.get(light, "")
            prog_cls = PROG_CLASS.get(status, "")
            tag_html = STATUS_TAG.get(status, "")

            deadline  = _disp(row.get("截止日期", ""))
            owner     = _disp(row.get("負責人",   ""))
            dept      = str(row.get("來源部門", "")) or "—"
            task      = str(row.get("任務項目", "（無標題）"))
            tab_title = str(row.get("_tab_title", "")) if "_tab_title" in row else ""
            tab_badge = (f'<span class="source-tab-badge">📑 {tab_title}</span>'
                         if tab_title else "")

            st.markdown(
                f'<div class="task-card {card_cls}">'
                f'<div class="task-title">{light} {task}</div>'
                f'<div class="task-meta">{tag_html} 🏢 {dept}{tab_badge} ｜ 👤 {owner} ｜ 📅 {deadline}</div>'
                f'<div class="prog-bg"><div class="prog-fill {prog_cls}" style="width:{min(prog,100)}%;"></div></div>'
                f'<div class="task-meta" style="text-align:right;margin-top:2px;">{prog}%</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ──────────────────────────────────────────────
# 視圖二：統計分析
# ──────────────────────────────────────────────
elif view_mode == "📊 統計分析":
    import plotly.express as px
    import plotly.graph_objects as go

    st.markdown('<div class="section-hdr">📊 各部門工作統計</div>', unsafe_allow_html=True)

    if df_all.empty:
        st.info("尚無資料可供統計。")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            status_cnt = df_all["處理狀態"].value_counts().reset_index()
            status_cnt.columns = ["狀態", "數量"]
            cmap = {"待辦": "#9CA3AF", "進行中": "#3B82F6", "已完成": "#10B981", "逾期": "#EF4444"}
            fig1 = px.pie(status_cnt, names="狀態", values="數量",
                          color="狀態", color_discrete_map=cmap, title="全部門狀態分佈")
            fig1.update_layout(paper_bgcolor="white", font_family="sans-serif", height=300)
            st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

        with col_b:
            dept_cnt = df_all.groupby("來源部門").size().reset_index(name="任務數").sort_values("任務數")
            fig2 = px.bar(dept_cnt, x="任務數", y="來源部門", orientation="h",
                          title="各部門任務數", color_discrete_sequence=["#E63B1F"])
            fig2.update_layout(paper_bgcolor="white", font_family="sans-serif", height=300)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        # 燈號矩陣
        if "燈號" in df_all.columns:
            st.markdown('<div class="section-hdr-dark">🚦 部門×燈號矩陣</div>', unsafe_allow_html=True)
            light_matrix = df_all.groupby(["來源部門", "燈號"]).size().unstack(fill_value=0).reset_index()
            st.dataframe(light_matrix, use_container_width=True, hide_index=True)

        # 部門平均進度
        dept_prog = df_all.groupby("來源部門")["目前進度"].mean().reset_index()
        dept_prog.columns = ["部門", "平均進度"]
        dept_prog = dept_prog.sort_values("平均進度")
        fig3 = go.Figure()
        fig3.add_bar(x=dept_prog["平均進度"], y=dept_prog["部門"], orientation="h",
                     marker_color="#E63B1F",
                     text=dept_prog["平均進度"].apply(lambda v: f"{v:.1f}%"),
                     textposition="outside")
        fig3.update_layout(xaxis=dict(range=[0, 115]), title="各部門平均任務進度",
                           paper_bgcolor="white", font_family="sans-serif", height=280)
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

        # 完整表格
        st.markdown('<div class="section-hdr-dark">📋 完整任務清單</div>', unsafe_allow_html=True)
        show_cols = ["燈號", "來源部門", "負責人", "任務項目", "截止日期", "目前進度", "處理狀態"]
        avail = [c for c in show_cols if c in df_view.columns]
        st.dataframe(df_view[avail], use_container_width=True, hide_index=True)

# ──────────────────────────────────────────────
# 視圖三：審核批示
# ──────────────────────────────────────────────
else:
    from utils.data_engine import write_dept_approval

    st.markdown('<div class="section-hdr">✍️ 總指揮審核批示</div>', unsafe_allow_html=True)
    st.caption("選擇任務後點擊「核准」或輸入批示意見，系統將即時寫回原始 Google Sheet")

    if df_view.empty:
        st.info("目前無任務可審核。請調整篩選條件。")
    else:
        # 優先顯示紅燈任務
        sort_order = {"🔴": 0, "🟡": 1, "🟢": 2, "⚪": 3}
        df_approval = df_view.copy()
        if "燈號" in df_approval.columns:
            df_approval["_s"] = df_approval["燈號"].map(sort_order).fillna(4)
            df_approval = df_approval.sort_values("_s")

        for idx, (_, row) in enumerate(df_approval.iterrows()):
            light  = row.get("燈號", "🟢")
            status = row.get("處理狀態", "待辦")
            task   = str(row.get("任務項目", "（無標題）"))
            dept   = str(row.get("來源部門", "—"))
            owner  = _disp(row.get("負責人",   ""))
            deadline = _disp(row.get("截止日期", ""))
            prog   = int(row.get("目前進度",  0))
            sheet_id  = str(row.get("_sheet_id",  ""))
            row_index = int(row.get("_row_index", 0))
            card_cls  = LIGHT_TO_CARD.get(light, "")
            tag_html  = STATUS_TAG.get(status, "")

            with st.container():
                st.markdown(
                    f'<div class="task-card {card_cls}">'
                    f'<div class="task-title">{light} {task}</div>'
                    f'<div class="task-meta">{tag_html} 🏢 {dept} ｜ 👤 {owner} ｜ 📅 {deadline} ｜ {prog}%</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if sheet_id and row_index > 0:
                    with st.expander("📝 展開批示面板", expanded=False):
                        st.markdown('<div class="approval-box">', unsafe_allow_html=True)
                        col_ap, col_cm = st.columns([1, 2])
                        with col_ap:
                            if st.button("✅ 核准", key=f"approve_{idx}_{row_index}",
                                         use_container_width=True):
                                ok = write_dept_approval(sheet_id, row_index, "核准", "")
                                if ok:
                                    st.success("✅ 已核准，寫回成功")
                                    st.cache_data.clear()
                                else:
                                    st.error("❌ 寫回失敗，請確認 Sheet 權限")
                        with col_cm:
                            comment_key = f"comment_{idx}_{row_index}"
                            comment = st.text_input("批示意見（按 Enter 送出）",
                                                    placeholder="輸入指示…",
                                                    key=comment_key,
                                                    label_visibility="collapsed")
                            if st.button("📨 送出批示", key=f"submit_{idx}_{row_index}",
                                         use_container_width=True) and comment:
                                ok = write_dept_approval(sheet_id, row_index, "批示", comment)
                                if ok:
                                    st.success(f"✅ 批示已送出：「{comment}」")
                                    st.cache_data.clear()
                                else:
                                    st.error("❌ 寫回失敗，請確認 Sheet 權限")
                        st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.caption("⚠️ 此任務無法回寫（未設定 Sheet ID）")
