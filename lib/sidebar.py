"""
共用側邊欄元件 — Google Drive 資料夾切換器
在所有頁面的 sidebar 呼叫 drive_folder_widget() 即可。
"""
from __future__ import annotations
import streamlit as st


def drive_folder_widget() -> str:
    """
    顯示當前連動資料夾並提供切換功能。
    回傳目前生效的資料夾 ID（空字串表示尚未設定）。
    """
    st.markdown("### 📁 Drive 資料夾")

    _cur = st.session_state.get("import_folder_id", "")
    _edit = st.session_state.get("_folder_edit_mode", False)

    if _cur and not _edit:
        _disp = _cur[:20] + "…" if len(_cur) > 20 else _cur
        st.markdown(
            f'<div style="background:#F0FFF4;border:1.5px solid #A9DFBF;border-radius:8px;'
            f'padding:6px 12px;font-size:0.78rem;color:#1E8449;word-break:break-all;margin-bottom:4px;">'
            f'✅ {_disp}</div>',
            unsafe_allow_html=True,
        )
        if st.button("✏️ 切換資料夾", use_container_width=True, key="_drv_edit_btn"):
            st.session_state["_folder_edit_mode"] = True
            st.rerun()
    else:
        _raw = st.text_input(
            "Google Drive 資料夾網址",
            value="",
            placeholder="貼入資料夾網址或 ID…",
            label_visibility="collapsed",
            key="_drv_url_input",
        )
        _fid = _raw.strip()
        if "folders/" in _fid:
            _fid = _fid.split("folders/")[-1].split("?")[0].split("/")[0].strip()

        if _fid:
            if st.button("✅ 套用", type="primary", use_container_width=True, key="_drv_apply_btn"):
                st.session_state["import_folder_id"] = _fid
                st.session_state["_folder_edit_mode"] = False
                for k in [k for k in st.session_state if k.startswith(("_scan", "_parse", "_confirmed"))]:
                    del st.session_state[k]
                st.rerun()
        else:
            st.caption("貼入 Google Drive 資料夾網址後按「套用」")
            if _cur and _edit:
                if st.button("取消", use_container_width=True, key="_drv_cancel_btn"):
                    st.session_state["_folder_edit_mode"] = False
                    st.rerun()

    return st.session_state.get("import_folder_id", "")
