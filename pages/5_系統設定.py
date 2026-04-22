"""
5_系統設定.py — 系統管理員設定頁
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import json

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 系統設定",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("app.py", label="← 返回數位總部大門")
    st.stop()

if not st.session_state.get("is_admin", False):
    st.error("🔒 此頁面僅限管理員存取")
    st.page_link("app.py", label="← 返回總部")
    st.stop()

# CSS
st.markdown("""
<style>
    .main .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    [data-testid="stSidebarNav"] {display: none !important;}
    .section-header {
        display: flex; align-items: center; gap: 8px;
        font-size: 1.0rem; font-weight: 800; color: #1A1A1A;
        padding: 0.4rem 0; margin: 1.2rem 0 0.6rem;
        border-bottom: 2px solid #F0F0F0;
    }
    .section-header svg { flex-shrink: 0; }
    .help-box {
        background: #FFF8F6; border-left: 4px solid #E63B1F;
        padding: 12px 16px; border-radius: 8px;
        font-size: 0.88rem; line-height: 1.7; margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar nav
with st.sidebar:
    st.markdown("## ⚙️ 系統設定")
    st.caption("管理員專屬")
    st.divider()
    st.page_link("app.py", label="🏢 返回總部大門")
    st.page_link("pages/1_數據戰情中心.py", label="📊 數據戰情中心")
    st.page_link("pages/2_專案追蹤師.py", label="🗂️ 專案追蹤師")
    st.page_link("pages/3_決策AI偵察.py", label="🧠 決策AI偵察")
    st.page_link("pages/4_品牌數位資產.py", label="🎨 品牌數位資產")
    st.page_link("pages/6_Line邊緣代理人.py", label="🔔 Line 邊緣代理人")

st.markdown("# ⚙️ 系統設定")
st.markdown("**管理員專屬** — 設定各部門 Google Sheet 連線與系統參數")
st.divider()

# ── 跑馬燈 & AI 摘要 ──
from utils.ui_helpers import render_marquee, render_ai_summary, render_section_header, inject_global_css
inject_global_css()
import json as _json_sys
_config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
_sheets_cfg_path = os.path.join(_config_dir, "dept_sheets.json")
_dept_keys_sys = ["行銷", "人資", "採購", "行政", "財務", "資訊"]
try:
    with open(_sheets_cfg_path, "r", encoding="utf-8") as _f:
        _sheets_cfg = _json_sys.load(_f)
except Exception:
    _sheets_cfg = {}
_configured_depts = [d for d in _dept_keys_sys if _sheets_cfg.get(d, "").strip()]
_unconfigured_depts = [d for d in _dept_keys_sys if not _sheets_cfg.get(d, "").strip()]
render_marquee([
    f"已設定部門：{len(_configured_depts)}/6",
    f"未設定部門：{', '.join(_unconfigured_depts)}" if _unconfigured_depts else "所有部門已設定完成",
    "管理員專屬系統配置頁面",
    "修改設定後系統快取會自動清除",
])
_sys_bullets = []
if _unconfigured_depts:
    _sys_bullets.append(f"以下部門尚未設定 Google Sheet：{', '.join(_unconfigured_depts)}")
else:
    _sys_bullets.append("所有 6 個部門的 Google Sheet 均已設定完成")
_sys_bullets.append("請確保各部門 Sheet 已設定為「知道連結的人均可檢視」")
render_ai_summary("系統設定 — 配置狀態", _sys_bullets)

# ─── Helper ───────────────────────────────────────
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
SHEETS_CONFIG = os.path.join(CONFIG_DIR, "dept_sheets.json")
DEPT_KEYS = ["行銷", "人資", "採購", "行政", "財務", "資訊"]

def load_sheets_config() -> dict:
    if os.path.exists(SHEETS_CONFIG):
        try:
            with open(SHEETS_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {k: "" for k in DEPT_KEYS}

def extract_sheet_id(url_or_id: str) -> str:
    import re
    s = str(url_or_id).strip()
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9\-_]+)', s)
    return m.group(1) if m else s

# ─── Section 1: Google Sheets 設定 ────────────────
render_section_header("plug", "各部門 Google Sheet 連線設定")

st.markdown("""
<div class="help-box">
<b>設定說明：</b><br>
1. 開啟各部門的 Google Sheet → 點右上角「共用」→ 設定為「知道連結的人均可<b>檢視</b>」<br>
2. 複製 Google Sheet 的完整網址（或只貼 Sheet ID 也可以）<br>
3. 貼入下方對應欄位，點「儲存設定」即生效<br>
<br>
<b>Sheet 格式要求：</b> 第一列為標題列，需包含以下欄位（名稱彈性）：<br>
負責人 / 任務項目 / 截止日期 / 目前進度 / 處理狀態 / 最後更新
</div>
""", unsafe_allow_html=True)

current_config = load_sheets_config()

dept_icons = {"行銷": "📣", "人資": "👥", "採購": "🛒", "行政": "🏢", "財務": "💰", "資訊": "💻"}
new_ids: dict[str, str] = {}

cols = st.columns(2, gap="large")
for i, dept in enumerate(DEPT_KEYS):
    col = cols[i % 2]
    with col:
        icon = dept_icons.get(dept, "📁")
        val = current_config.get(dept, "")
        user_input = st.text_input(
            f"{icon} {dept}部 Google Sheet 網址",
            value=val,
            placeholder="貼上 Google Sheet 網址 或 Sheet ID",
            key=f"sheet_input_{dept}",
        )
        new_ids[dept] = user_input.strip()
        # Show status
        if user_input.strip():
            extracted = extract_sheet_id(user_input.strip())
            st.caption(f"✅ Sheet ID: `{extracted[:20]}...`" if len(extracted) > 20 else f"✅ Sheet ID: `{extracted}`")
        else:
            st.caption("⚠️ 尚未設定")

st.divider()
col_save, col_clear, col_test = st.columns([1, 1, 1])

with col_save:
    if st.button("💾 儲存所有設定", type="primary", use_container_width=True):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        cleaned = {k: extract_sheet_id(v) for k, v in new_ids.items()}
        try:
            with open(SHEETS_CONFIG, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, ensure_ascii=False, indent=2)
            # Clear cache
            st.cache_data.clear()
            st.success("✅ 設定已儲存！資料快取已清除，請返回專案追蹤師頁面重新載入。")
        except Exception as e:
            st.error(f"❌ 儲存失敗：{e}")

with col_clear:
    if st.button("🗑️ 清除所有設定", use_container_width=True):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        empty = {k: "" for k in DEPT_KEYS}
        with open(SHEETS_CONFIG, "w", encoding="utf-8") as f:
            json.dump(empty, f, ensure_ascii=False, indent=2)
        st.cache_data.clear()
        st.rerun()

with col_test:
    if st.button("🔄 清除快取（強制重新讀取）", use_container_width=True):
        st.cache_data.clear()
        st.success("✅ 快取已清除！")

# Show current saved config
st.divider()
render_section_header("chart-bar", "目前設定狀態")

saved = load_sheets_config()
status_cols = st.columns(6)
for i, dept in enumerate(DEPT_KEYS):
    with status_cols[i]:
        sid = saved.get(dept, "")
        if sid:
            st.success(f"**{dept}**\n\n✅ 已設定")
        else:
            st.error(f"**{dept}**\n\n❌ 未設定")
