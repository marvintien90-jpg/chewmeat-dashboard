"""
utils/settings_store.py — Google Sheets 持久化設定層 v1.0

解決 Render 免費方案每次重啟清空 /tmp（SQLite 消失）的問題。
每次 set_setting() 同步備份到 GSheets；重啟時自動從 GSheets 還原。

使用需求：GCP_SERVICE_ACCOUNT_JSON 環境變數（已設定於 Render）
"""
from __future__ import annotations
import logging, threading
from datetime import datetime

logger = logging.getLogger("kerou.settings_store")

_SPREADSHEET_TITLE = "KeRou_SystemSettings"
_WORKSHEET_NAME    = "Settings"
_lock = threading.Lock()


# ── GSheets 連線 ──────────────────────────────────────────────────

def _get_gcp_json() -> dict:
    """從 os.environ 或 st.secrets 讀取 GCP_SERVICE_ACCOUNT_JSON，回傳 dict"""
    import json as _json, os as _os
    # 1. os.environ（Render 端）
    raw = _os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")
    if raw:
        return _json.loads(raw)
    # 2. st.secrets（Streamlit Cloud 端）
    try:
        import streamlit as st
        raw = st.secrets.get("GCP_SERVICE_ACCOUNT_JSON", "") or ""
        if raw:
            return _json.loads(raw)
        # 也支援 [gcp_service_account] 巢狀格式
        nested = st.secrets.get("gcp_service_account", {})
        if nested:
            return dict(nested)
    except Exception:
        pass
    raise RuntimeError("找不到 GCP_SERVICE_ACCOUNT_JSON")


def _get_client():
    try:
        from google.oauth2.service_account import Credentials
        import gspread
        SCOPES = ["https://spreadsheets.google.com/feeds",
                  "https://www.googleapis.com/auth/drive"]
        info  = _get_gcp_json()
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        logger.warning(f"[settings_store] GCP 連線失敗: {e}")
        return None


def _get_drive_folder_id() -> str:
    """從 st.secrets[google_sheets][drive_folder_id] 或 os.environ 讀取使用者的 Drive 資料夾 ID。
    建立試算表時指定此資料夾，使其佔用使用者的配額而非服務帳號的配額。"""
    import os as _os
    fid = _os.environ.get("DRIVE_FOLDER_ID", "")
    if fid:
        return fid
    try:
        import streamlit as _st
        # 1. 直接 key
        fid = (_st.secrets.get("DRIVE_FOLDER_ID", "") or "").strip()
        if fid:
            return fid
        # 2. 巢狀 [google_sheets] 區塊
        gs = _st.secrets.get("google_sheets", {})
        if gs:
            fid = (gs.get("drive_folder_id", "") or "").strip()
        return fid
    except Exception:
        return ""


def _get_fallback_spreadsheet_id() -> str:
    """取得 fallback 試算表 ID（已知有存取權的現有試算表）"""
    import os as _os
    sid = _os.environ.get("SETTINGS_SPREADSHEET_ID", "")
    if sid:
        return sid
    try:
        import streamlit as _st
        sid = (_st.secrets.get("SETTINGS_SPREADSHEET_ID", "") or "").strip()
        if sid:
            return sid
        # 使用 [google_sheets] spreadsheet_id 作 fallback
        gs = _st.secrets.get("google_sheets", {})
        if gs:
            sid = (gs.get("spreadsheet_id", "") or "").strip()
        return sid
    except Exception:
        return ""


def _get_worksheet(client):
    folder_id = _get_drive_folder_id()

    # 1. 嘗試以標題直接開啟（最快）
    ss = None
    try:
        ss = client.open(_SPREADSHEET_TITLE)
    except Exception:
        pass

    # 2. Fallback：使用已知有存取權的試算表（不需要建立新檔，避免配額問題）
    if ss is None:
        fb_id = _get_fallback_spreadsheet_id()
        if fb_id:
            try:
                ss = client.open_by_key(fb_id)
                logger.info(f"[settings_store] 使用 fallback 試算表 id={fb_id}")
            except Exception as e:
                logger.warning(f"[settings_store] fallback 試算表開啟失敗: {e}")

    # 3. 最後嘗試建立新試算表（指定 folder_id 放進使用者 Drive）
    if ss is None:
        try:
            if folder_id:
                ss = client.create(_SPREADSHEET_TITLE, folder_id=folder_id)
                logger.info(f"[settings_store] 建立新設定試算表 id={ss.id} folder={folder_id}")
            else:
                ss = client.create(_SPREADSHEET_TITLE)
                logger.info(f"[settings_store] 建立新設定試算表 id={ss.id}")
        except Exception as e:
            logger.error(f"[settings_store] 無法建立試算表: {e}")
            raise

    try:
        ws = ss.worksheet(_WORKSHEET_NAME)
    except Exception:
        ws = ss.add_worksheet(_WORKSHEET_NAME, rows=500, cols=3)
        ws.append_row(["key", "value", "updated_at"])
        logger.info("[settings_store] 建立 Settings 工作表")
    return ws


# ── 公開 API ──────────────────────────────────────────────────────

def save(key: str, value: str) -> bool:
    """將單一設定值備份到 GSheets（UPSERT）。執行緒安全。"""
    client = _get_client()
    if not client:
        return False
    try:
        with _lock:
            ws      = _get_worksheet(client)
            records = ws.get_all_records()
            now     = datetime.now().isoformat()
            for i, row in enumerate(records, start=2):
                if row.get("key") == key:
                    ws.update(f"B{i}:C{i}", [[value, now]])
                    return True
            ws.append_row([key, value, now])
        return True
    except Exception as e:
        logger.warning(f"[settings_store] save({key}) 失敗: {e}")
        return False


def load_all() -> dict[str, str]:
    """從 GSheets 讀取所有設定，回傳 {key: value}。"""
    client = _get_client()
    if not client:
        return {}
    try:
        ws      = _get_worksheet(client)
        records = ws.get_all_records()
        return {r["key"]: r["value"] for r in records if r.get("key")}
    except Exception as e:
        logger.warning(f"[settings_store] load_all 失敗: {e}")
        return {}


def restore_to_sqlite() -> int:
    """從 GSheets 還原所有設定到本地 SQLite，回傳還原筆數。"""
    settings = load_all()
    if not settings:
        logger.info("[settings_store] GSheets 無設定資料，略過還原")
        return 0
    try:
        from utils import edge_store
        count = 0
        for key, value in settings.items():
            edge_store._set_setting_local(key, str(value))
            count += 1
        logger.info(f"[settings_store] 已還原 {count} 筆設定 from GSheets")
        return count
    except Exception as e:
        logger.error(f"[settings_store] restore_to_sqlite 失敗: {e}")
        return 0
