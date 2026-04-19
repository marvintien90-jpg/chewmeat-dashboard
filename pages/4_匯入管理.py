"""
營運部 — 匯入管理
Google Drive 資料夾自動掃描 → 模糊讀取 → AI 精準辨識 → 去重複核對 → 安全寫入 Sheets
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime
from difflib import SequenceMatcher

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 匯入管理",
    page_icon="📥",
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

    .step-header {
        background: #2C3E50; color: white;
        padding: 8px 18px; border-radius: 8px;
        margin: 1.2rem 0 0.6rem 0; font-weight: 700; font-size: 0.95rem;
    }
    .step-header-active {
        background: #E63B1F; color: white;
        padding: 8px 18px; border-radius: 8px;
        margin: 1.2rem 0 0.6rem 0; font-weight: 700; font-size: 0.95rem;
    }
    [data-testid="stMetric"] {
        background: #FFFFFF; padding: 14px; border-radius: 10px;
        border: 1.5px solid #E8EEF4;
        box-shadow: 0 1px 4px rgba(44,62,80,0.07);
    }
    .file-card {
        background: #FFFFFF; border: 1.5px solid #E8EEF4;
        border-radius: 10px; padding: 0.75rem 1rem;
        margin-bottom: 0.4rem;
    }
    .file-card.new-file  { border-left: 4px solid #E63B1F; }
    .file-card.old-file  { border-left: 4px solid #BDC3C7; opacity: 0.75; }
    .dup-tag {
        display: inline-block; padding: 2px 9px;
        border-radius: 12px; font-size: 0.72rem; font-weight: 700;
    }
    .tag-new  { background: #D5F5E3; color: #1E8449; }
    .tag-dup  { background: #FDEBD0; color: #D35400; }
    .task-row {
        background: #F8F9FA; border-radius: 8px;
        padding: 0.5rem 0.8rem; margin: 0.25rem 0;
        font-size: 0.85rem; line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📥 匯入管理")
    st.caption("Drive 自動掃描 · AI 解析 · 去重複")
    st.divider()
    st.page_link("app.py",               label="🏢 返回總部大門")
    st.page_link("pages/2_專案進度.py",   label="🗂️ 專案進度")
    st.page_link("pages/3_智能戰情室.py", label="🧠 智能戰情室")
    st.divider()

    st.markdown("### 📁 連動資料夾")
    _sid = st.session_state.get("import_folder_id", "")
    if _sid:
        _disp = _sid[:16] + "…" if len(_sid) > 16 else _sid
        st.success(f"✅ `{_disp}`")
        if st.button("✏️ 變更資料夾", use_container_width=True):
            st.session_state.pop("import_folder_id", None)
            st.rerun()
    else:
        st.warning("尚未設定資料夾")
        st.page_link("pages/7_系統設定.py", label="⚙️ 前往系統設定輸入資料夾網址", use_container_width=True)

    st.divider()
    if st.button("🗑️ 清除解析快取", use_container_width=True,
                 help="清除本頁快取，不影響已寫入 Sheets 的資料"):
        for k in [k for k in st.session_state if k.startswith(("_scan", "_parse", "_confirmed"))]:
            del st.session_state[k]
        st.rerun()

# ── Header ───────────────────────────────────────────────────
st.markdown("# 📥 匯入管理")
st.markdown("**Google Drive → 模糊讀取 → AI 精準辨識 → 去重複 → 寫入追蹤表**")
st.divider()

folder_id = st.session_state.get("import_folder_id", "")
if not folder_id:
    st.warning("⚠️ 尚未連動 Google Drive 資料夾，請先在系統設定中設定資料夾網址。")
    st.page_link("pages/7_系統設定.py", label="⚙️ 前往系統設定 — 設定 Google Drive 資料夾網址", use_container_width=False)
    st.stop()

# ─────────────────────────────────────────────────────────────
# 步驟 1：掃描資料夾
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="step-header">🔍 步驟 1：掃描資料夾</div>', unsafe_allow_html=True)

c_btn, c_desc = st.columns([1, 4])
with c_btn:
    do_scan = st.button("🔍 開始掃描", type="primary", use_container_width=True)
with c_desc:
    st.caption("遞迴列出資料夾中所有 .doc / .docx / Google Docs，並比對已掃描記錄。")

if do_scan:
    with st.spinner("連線 Google Drive 中…"):
        try:
            from lib.drive_client import get_drive_service, list_doc_files
            from lib.sheets_db import load_scanned_file_ids
            service = get_drive_service()
            all_files = list_doc_files(service, folder_id)
            scanned_ids = load_scanned_file_ids()
            st.session_state["_scan_all"]       = all_files
            st.session_state["_scan_new"]       = [f for f in all_files if f["id"] not in scanned_ids]
            st.session_state["_scan_old"]       = [f for f in all_files if f["id"] in scanned_ids]
            # Clear downstream state so user re-parses with fresh scan
            for k in [k for k in st.session_state if k.startswith(("_parse", "_confirmed"))]:
                del st.session_state[k]
        except Exception as e:
            st.error(f"❌ 掃描失敗：{e}")
            st.stop()

if "_scan_all" in st.session_state:
    all_files  = st.session_state["_scan_all"]
    new_files  = st.session_state["_scan_new"]
    old_files  = st.session_state["_scan_old"]

    ca, cb, cc = st.columns(3)
    ca.metric("📄 資料夾文件總數", len(all_files))
    cb.metric("🆕 待匯入（新）",    len(new_files))
    cc.metric("✅ 已掃描過",         len(old_files))

    if new_files:
        st.markdown(f"**🆕 發現 {len(new_files)} 個新文件：**")
        for f in new_files:
            ct = f.get("createdTime", "")[:10]
            st.markdown(f'<div class="file-card new-file">📄 <b>{f["name"]}</b>'
                        f'<span style="color:#888;font-size:0.78rem;"> &nbsp;建立：{ct}</span></div>',
                        unsafe_allow_html=True)

    if old_files:
        with st.expander(f"📁 已掃描過的文件（{len(old_files)} 個，不重複解析）"):
            for f in old_files:
                st.markdown(f'<div class="file-card old-file">📄 <span style="color:#999;">{f["name"]}</span></div>',
                            unsafe_allow_html=True)

    if not new_files:
        st.success("✅ 所有文件均已掃描過，無需匯入。")
        st.stop()

    # ─────────────────────────────────────────────────────────
    # 步驟 2：AI 解析
    # ─────────────────────────────────────────────────────────
    st.markdown('<div class="step-header">🤖 步驟 2：模糊讀取 → AI 精準辨識</div>', unsafe_allow_html=True)

    col_parse_btn, col_parse_info = st.columns([1, 4])
    with col_parse_btn:
        already_parsed = "_parse_results" in st.session_state
        do_parse = st.button(
            "🤖 開始解析" if not already_parsed else "✅ 已解析（重新解析請清快取）",
            type="primary", disabled=already_parsed, use_container_width=True,
        )

    with col_parse_info:
        st.caption("**模糊讀取**：提取文件純文字 → **AI 精準辨識**：GPT-4o-mini 解析 5W2H 任務結構")

    if do_parse:
        parse_results: list[dict] = []
        errors: list[str] = []

        prog_bar  = st.progress(0.0)
        status_ph = st.empty()

        try:
            from lib.drive_client import get_drive_service, extract_text
            from lib.ai_parser import parse_meeting
            service = get_drive_service()
        except Exception as e:
            st.error(f"❌ 服務初始化失敗：{e}")
            st.stop()

        for i, f in enumerate(new_files):
            prog_bar.progress(i / len(new_files))
            status_ph.text(f"({i+1}/{len(new_files)}) 解析中：{f['name'][:45]}…")
            try:
                # 步驟 2a：模糊讀取（Raw text extraction）
                raw_text = extract_text(service, f["id"], f["mimeType"], f["name"])
                if not raw_text.strip():
                    errors.append(f"⚠️ {f['name']} — 文件內容為空，略過")
                    continue
                # 步驟 2b：AI 精準辨識
                parsed = parse_meeting(raw_text, f["name"])
                tasks  = parsed.get("tasks", [])
                for t in tasks:
                    t["source_file"] = f["name"]
                parse_results.append({
                    "file":         f,
                    "text_preview": raw_text[:400],
                    "tasks":        tasks,
                    "meeting_date": parsed.get("meeting_date", ""),
                })
            except Exception as e:
                errors.append(f"❌ {f['name']} — 解析失敗：{str(e)[:120]}")

        prog_bar.progress(1.0)
        status_ph.text("✅ 解析完成！")

        st.session_state["_parse_results"] = parse_results
        if errors:
            with st.expander(f"⚠️ 解析錯誤紀錄（{len(errors)} 筆）"):
                for err in errors:
                    st.warning(err)

    # ─────────────────────────────────────────────────────────
    # 步驟 3：去重複核對
    # ─────────────────────────────────────────────────────────
    parse_results = st.session_state.get("_parse_results", [])
    if not parse_results:
        st.stop()

    st.markdown('<div class="step-header">🔎 步驟 3：去重複核對</div>', unsafe_allow_html=True)

    @st.cache_data(ttl=120, show_spinner=False)
    def _existing_tasks() -> list[dict]:
        from lib.sheets_db import load_tasks
        return load_tasks()

    existing = _existing_tasks()

    def _sim(a: str, b: str) -> float:
        return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()

    def _is_dup(name: str) -> tuple[bool, str]:
        n = name.strip().lower()
        for ex in existing:
            en = ex.get("what", "").strip().lower()
            if not en:
                continue
            if _sim(n, en) > 0.72 or n in en or en in n:
                return True, ex.get("what", "")
        return False, ""

    # Flatten and tag
    all_parsed: list[dict] = []
    for pr in parse_results:
        for t in pr["tasks"]:
            is_d, matched = _is_dup(t.get("what", ""))
            all_parsed.append({**t,
                "_dup": is_d, "_matched": matched,
                "_file_id": pr["file"]["id"],
                "_file_name": pr["file"]["name"],
                "_meeting_date": pr["meeting_date"],
            })

    new_items = [t for t in all_parsed if not t["_dup"]]
    dup_items = [t for t in all_parsed if t["_dup"]]

    cd1, cd2, cd3 = st.columns(3)
    cd1.metric("📋 AI 解析任務總數", len(all_parsed))
    cd2.metric("✅ 全新任務（可匯入）", len(new_items))
    cd3.metric("🔄 重複任務（略過）",   len(dup_items))

    if dup_items:
        with st.expander(f"🔄 重複任務明細（{len(dup_items)} 個，已自動略過）"):
            for t in dup_items:
                st.markdown(
                    f'<div class="task-row">'
                    f'<span class="dup-tag tag-dup">重複</span> '
                    f'<b>{t.get("what","")[:60]}</b><br>'
                    f'<span style="color:#999;font-size:0.78rem;">'
                    f'已有：「{t.get("_matched","")[:55]}」</span></div>',
                    unsafe_allow_html=True,
                )

    # ─────────────────────────────────────────────────────────
    # 步驟 4：預覽 & 編輯 & 確認匯入
    # ─────────────────────────────────────────────────────────
    if not new_items:
        st.success("✅ 沒有全新任務需要匯入。")
        st.stop()

    st.markdown('<div class="step-header-active">🚀 步驟 4：確認匯入</div>', unsafe_allow_html=True)
    st.info(f"以下 **{len(new_items)}** 個任務為全新項目，可勾選後匯入。所有欄位均可在此編輯。")

    DEPT_OPTIONS = [
        "董事長室", "營運中心", "研發課", "教育訓練課", "食安課",
        "展店課", "直營部", "財務部", "行銷部", "人資部",
        "採購部", "工程部", "行政部", "待確認",
    ]

    confirmed: list[dict] = []
    for i, t in enumerate(new_items):
        dept_default = t.get("who_dept", "待確認")
        dept_idx = DEPT_OPTIONS.index(dept_default) if dept_default in DEPT_OPTIONS else len(DEPT_OPTIONS) - 1

        with st.expander(
            f"📌 [{i+1}] {t.get('what','（無標題）')[:55]} — {t.get('who_dept','?')}",
            expanded=(i < 2),
        ):
            include = st.checkbox("✅ 納入匯入清單", value=True, key=f"_inc_{i}")

            col1, col2 = st.columns(2)
            with col1:
                w_what   = st.text_input("任務名稱 *",      value=t.get("what", ""),          key=f"_w_{i}")
                w_dept   = st.selectbox("負責部門",          DEPT_OPTIONS, index=dept_idx,     key=f"_dept_{i}")
                w_person = st.text_input("負責人",           value=t.get("who_person", "待確認"), key=f"_person_{i}")
                w_prog   = st.slider("初始進度 (%)", 0, 100, t.get("progress", 0),             key=f"_prog_{i}")
            with col2:
                w_start  = st.text_input("開始日 (YYYY-MM-DD)", value=t.get("when_start", ""), key=f"_start_{i}")
                w_end    = st.text_input("截止日 (YYYY-MM-DD)", value=t.get("when_end", ""),   key=f"_end_{i}")
                w_why    = st.text_input("目的",              value=t.get("why", ""),           key=f"_why_{i}")
                w_where  = st.text_input("執行地點",          value=t.get("where", "總部"),     key=f"_where_{i}")
            w_how = st.text_area("執行說明", value=t.get("how", ""), height=70, key=f"_how_{i}")

            with st.expander("📄 原始文件預覽（前 300 字）"):
                # Find the text preview from parse_results
                for pr in parse_results:
                    if pr["file"]["id"] == t["_file_id"]:
                        st.text(pr["text_preview"])
                        break

            if include and w_what.strip():
                confirmed.append({
                    "what":        w_what.strip(),
                    "why":         w_why.strip(),
                    "who_dept":    w_dept,
                    "who_person":  w_person.strip(),
                    "where":       w_where.strip(),
                    "when_start":  w_start.strip(),
                    "when_end":    w_end.strip(),
                    "how":         w_how.strip(),
                    "progress":    w_prog,
                    "source_file": t.get("source_file", t["_file_name"]),
                    "_file_id":    t["_file_id"],
                    "_file_name":  t["_file_name"],
                })

    st.divider()
    st.markdown(f"**準備匯入：{len(confirmed)} 個任務**")

    if confirmed:
        col_go, col_cancel = st.columns([1, 4])
        with col_go:
            do_import = st.button("🚀 確認匯入", type="primary", use_container_width=True)

        if do_import:
            # ── 資料保護：先寫 Sheets，再清快取，絕不反向 ──
            with st.spinner("寫入 Google Sheets 中（請勿關閉頁面）…"):
                try:
                    from lib.sheets_db import append_tasks, append_scanned_files

                    # 去掉 _ 開頭的內部欄位
                    clean = [{k: v for k, v in t.items() if not k.startswith("_")}
                             for t in confirmed]
                    n_written = append_tasks(clean)

                    # 標記已掃描的檔案（去重）
                    seen: set[str] = set()
                    scanned_entries: list[dict] = []
                    for t in confirmed:
                        fid = t.get("_file_id", "")
                        if fid and fid not in seen:
                            scanned_entries.append({"file_id": fid, "file_name": t["_file_name"]})
                            seen.add(fid)
                    append_scanned_files(scanned_entries)

                    st.success(f"🎉 成功寫入 **{n_written}** 筆任務！已標記 {len(scanned_entries)} 個檔案為已掃描。")

                    # 清除本頁解析快取（不影響已寫入的 Sheets 資料）
                    for k in [k for k in st.session_state if k.startswith(("_parse", "_confirmed", "_scan"))]:
                        del st.session_state[k]
                    # 讓任務列表下次重新從 Sheets 讀取
                    st.cache_data.clear()
                    st.balloons()

                except Exception as e:
                    st.error(f"❌ 寫入失敗：{e}")
                    st.error("⚠️ 資料**尚未**寫入，請重試。不會有資料遺失。")
    else:
        st.warning("請至少勾選一個任務，且任務名稱不可為空。")

else:
    st.info("點擊「開始掃描」以連線 Google Drive 並列出文件。")
