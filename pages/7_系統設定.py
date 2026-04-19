"""
系統設定 — 連線狀態、資料夾管理、快取控制、資料匯出
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 系統設定",
    page_icon="⚙️",
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
    .status-ok   { color: #27AE60; font-weight: 700; }
    .status-fail { color: #E63B1F; font-weight: 700; }
    .info-row {
        background: #F8F9FA; border-radius: 8px;
        padding: 0.6rem 1rem; margin: 0.3rem 0; font-size: 0.88rem;
    }
    [data-testid="stMetric"] {
        background: #FFFFFF; padding: 14px; border-radius: 10px;
        border: 1.5px solid #E8EEF4;
        box-shadow: 0 1px 4px rgba(44,62,80,0.07);
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ⚙️ 系統設定")
    st.caption("連線 · 資料夾 · 快取 · 匯出")
    st.divider()
    st.page_link("app.py",               label="🏢 返回總部大門")
    st.page_link("pages/2_專案進度.py",   label="🗂️ 專案進度")
    st.page_link("pages/4_匯入管理.py",   label="📥 匯入管理")
    st.page_link("pages/8_歷史歷程.py",   label="📊 歷史歷程")
    st.divider()
    from lib.sidebar import drive_folder_widget
    drive_folder_widget()

st.markdown("# ⚙️ 系統設定")
st.markdown("連線狀態確認、資料夾設定、快取清理與資料管理")
st.divider()

# ── Google Drive 資料夾設定（最高優先，頂部顯示）─────────────
st.markdown('<div class="section-header">📁 Google Drive 連動資料夾設定</div>', unsafe_allow_html=True)

_default_folder = ""
try:
    from lib.config import get_drive_folder_id
    _default_folder = get_drive_folder_id()
except Exception:
    pass

_current_folder = st.session_state.get("import_folder_id", _default_folder)

col_folder_input, col_folder_status = st.columns([3, 1])
with col_folder_input:
    _raw_folder = st.text_input(
        "Google Drive 資料夾網址或 ID",
        value=_current_folder,
        placeholder="貼入 Google Drive 資料夾的完整網址，或直接輸入資料夾 ID…",
        help="在 Google Drive 開啟目標資料夾，複製網址列完整 URL 貼入此處，系統自動解析 ID",
        label_visibility="collapsed",
    )

# 自動從 URL 解析 ID
_folder_id = _raw_folder.strip()
if "folders/" in _folder_id:
    _folder_id = _folder_id.split("folders/")[-1].split("?")[0].split("/")[0].strip()

with col_folder_status:
    if _folder_id:
        st.session_state["import_folder_id"] = _folder_id
        _display = _folder_id[:16] + "…" if len(_folder_id) > 16 else _folder_id
        st.success(f"✅ `{_display}`")
    else:
        st.warning("尚未設定")

if _folder_id:
    st.caption(f"📂 已連動資料夾 ID：`{_folder_id}`　→　前往 [匯入管理](pages/4_匯入管理.py) 開始掃描")
else:
    st.info("👆 請貼入 Google Drive 資料夾網址（例：`https://drive.google.com/drive/folders/XXXXXX`）")

    with st.expander("📖 如何取得 Google Drive 資料夾網址？"):
        st.markdown("""
1. 開啟 [Google Drive](https://drive.google.com)
2. 找到要連動的資料夾，點選進入
3. 複製瀏覽器網址列中的完整 URL
4. 貼入上方輸入框，系統自動解析資料夾 ID

**支援格式：**
- `https://drive.google.com/drive/folders/1ABC...XYZ`
- `https://drive.google.com/drive/u/0/folders/1ABC...XYZ`
- 或直接輸入資料夾 ID（英數字串）

**連動後可掃描的文件類型：**
- Google 文件（Docs）
- Word 文件（.docx / .doc）
- 遞迴掃描所有子資料夾
        """)

st.divider()

# ── 連線狀態 ─────────────────────────────────────────────────
st.markdown('<div class="section-header">🔌 連線狀態診斷</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

# Google Sheets 連線
with col1:
    with st.spinner("測試 Google Sheets…"):
        try:
            from lib.sheets_db import load_tasks
            tasks = load_tasks()
            st.metric("📊 Google Sheets", f"{len(tasks)} 筆任務")
            st.markdown('<span class="status-ok">✅ 連線正常</span>', unsafe_allow_html=True)
        except Exception as e:
            st.metric("📊 Google Sheets", "—")
            st.markdown(f'<span class="status-fail">❌ 連線失敗</span>', unsafe_allow_html=True)
            st.caption(str(e)[:80])

# Google Drive 連線
with col2:
    with st.spinner("測試 Google Drive…"):
        try:
            from lib.drive_client import get_drive_service
            svc = get_drive_service()
            about = svc.about().get(fields="user").execute()
            email = about.get("user", {}).get("emailAddress", "未知")
            st.metric("📁 Google Drive", "已授權")
            st.markdown('<span class="status-ok">✅ 連線正常</span>', unsafe_allow_html=True)
            st.caption(f"服務帳號：{email}")
        except Exception as e:
            st.metric("📁 Google Drive", "—")
            st.markdown('<span class="status-fail">❌ 連線失敗</span>', unsafe_allow_html=True)
            st.caption(str(e)[:80])

# AI 解析服務
with col3:
    try:
        from lib.config import get_openai_api_key
        key = get_openai_api_key()
        masked = key[:4] + "…" + key[-4:] if len(key) > 8 else "***"
        st.metric("🤖 AI 解析 (OpenAI)", "已設定")
        st.markdown('<span class="status-ok">✅ API Key 存在</span>', unsafe_allow_html=True)
        st.caption(f"Key: {masked}")
    except Exception as e:
        st.metric("🤖 AI 解析 (OpenAI)", "未設定")
        st.markdown('<span class="status-fail">⚠️ 需要設定 API Key</span>', unsafe_allow_html=True)
        st.caption("請在 Streamlit Secrets 中加入 openai_api_key")

st.divider()

# ── 設定資訊 ─────────────────────────────────────────────────
st.markdown('<div class="section-header">📋 目前設定值</div>', unsafe_allow_html=True)

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("**Sheets 設定**")
    try:
        from lib.config import get_spreadsheet_id
        sid = get_spreadsheet_id()
        st.markdown(f'<div class="info-row">📊 Spreadsheet ID：<code>{sid[:20]}…</code></div>', unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f'<div class="info-row">❌ 無法讀取 Spreadsheet ID：{e}</div>', unsafe_allow_html=True)

    st.markdown("**Access Key**")
    try:
        ak = st.secrets.get("access_key", None)
        if ak:
            masked_ak = ak[:2] + "*" * (len(ak) - 4) + ak[-2:]
            st.markdown(f'<div class="info-row">🔑 已從 Secrets 讀取：<code>{masked_ak}</code></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="info-row">🔑 使用預設密鑰（建議設定 secrets.access_key）</div>', unsafe_allow_html=True)
    except Exception:
        st.markdown('<div class="info-row">🔑 使用預設密鑰</div>', unsafe_allow_html=True)

with col_b:
    st.markdown("**Drive 資料夾**")
    session_folder = st.session_state.get("import_folder_id", "")
    if session_folder:
        st.markdown(f'<div class="info-row">📂 已連動資料夾：<code>{session_folder[:22]}…</code></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-row">📁 尚未設定（請至頁面頂部輸入資料夾網址）</div>', unsafe_allow_html=True)

st.divider()

# ── 快取管理 ─────────────────────────────────────────────────
st.markdown('<div class="section-header">🗑️ 快取管理</div>', unsafe_allow_html=True)
st.info("清除快取只會讓系統重新從 Google Sheets 讀取資料，**不會刪除或覆蓋任何已儲存的任務**。")

col_c1, col_c2, col_c3 = st.columns(3)
with col_c1:
    if st.button("🔄 清除資料快取", use_container_width=True, help="重新從 Sheets 讀取所有資料"):
        st.cache_data.clear()
        from lib.sheets_db import clear_caches
        clear_caches()
        st.success("✅ 資料快取已清除")

with col_c2:
    if st.button("🗑️ 清除匯入快取", use_container_width=True, help="清除匯入管理頁的掃描與解析結果"):
        for k in [k for k in st.session_state if k.startswith(("_scan", "_parse", "_confirmed", "import_"))]:
            del st.session_state[k]
        st.success("✅ 匯入快取已清除")

with col_c3:
    if st.button("🔁 重新連線", use_container_width=True, help="重置 Google API 連線"):
        from lib.sheets_db import clear_caches
        clear_caches()
        st.cache_data.clear()
        st.success("✅ 連線已重置，下次操作將重新建立連線")

st.divider()

# ── 資料匯出 ─────────────────────────────────────────────────
st.markdown('<div class="section-header">📥 資料匯出</div>', unsafe_allow_html=True)

col_e1, col_e2 = st.columns(2)

with col_e1:
    st.markdown("**匯出任務清單**")
    if st.button("📋 載入任務資料", use_container_width=True):
        try:
            from lib.sheets_db import load_tasks
            tasks = load_tasks()
            df = pd.DataFrame(tasks)
            st.session_state["_export_tasks_df"] = df
        except Exception as e:
            st.error(f"載入失敗：{e}")

    if "_export_tasks_df" in st.session_state:
        df_exp = st.session_state["_export_tasks_df"]
        import io
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df_exp.to_excel(w, index=False, sheet_name="任務清單")
        st.download_button(
            "📥 下載 Excel",
            data=out.getvalue(),
            file_name=f"嗑肉_任務清單_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.caption(f"共 {len(df_exp)} 筆任務")

with col_e2:
    st.markdown("**匯出已掃描檔案記錄**")
    if st.button("📁 載入掃描記錄", use_container_width=True):
        try:
            from lib.sheets_db import _get_or_create_worksheet, _read_all
            from lib.config import SCANNED_SHEET, SCANNED_COLUMNS
            ws = _get_or_create_worksheet(SCANNED_SHEET, SCANNED_COLUMNS)
            rows = _read_all(ws, SCANNED_COLUMNS)
            st.session_state["_export_scanned_df"] = pd.DataFrame(rows)
        except Exception as e:
            st.error(f"載入失敗：{e}")

    if "_export_scanned_df" in st.session_state:
        df_sc = st.session_state["_export_scanned_df"]
        import io
        out2 = io.BytesIO()
        with pd.ExcelWriter(out2, engine="openpyxl") as w:
            df_sc.to_excel(w, index=False, sheet_name="掃描記錄")
        st.download_button(
            "📥 下載 Excel",
            data=out2.getvalue(),
            file_name=f"嗑肉_掃描記錄_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.caption(f"共 {len(df_sc)} 個已掃描檔案")

st.divider()

# ── 系統資訊 ─────────────────────────────────────────────────
st.markdown('<div class="section-header">ℹ️ 系統資訊</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="info-row">🕐 目前時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
<div class="info-row">🐍 Python 版本：{sys.version.split()[0]}</div>
<div class="info-row">📦 App 版本：嗑肉數位總部 v2.0</div>
""", unsafe_allow_html=True)
