"""集中管理常數與 secrets 讀取（同時支援 Streamlit secrets 與環境變數）。"""
from __future__ import annotations

import json
import os
from typing import Any

# ── 營收 Google Sheets 設定（集中在此，避免多處重複） ──────────────────
REVENUE_SHEET_ID = "1NZQEJgL-HkB08JSW6zsVHRSyl_XgwLc5etUqSF0O9ow"

REVENUE_SHEET_GIDS: dict[str, str] = {
    "2025-01": "672482866",  "2025-02": "1943981506", "2025-03": "847955849",
    "2025-04": "591730250",  "2025-05": "695013616",  "2025-06": "897256004",
    "2025-07": "593028448",  "2025-08": "836455215",  "2025-09": "1728608975",
    "2025-10": "2043079442", "2025-11": "1307429413", "2025-12": "1838876978",
    "2026-01": "872131612",  "2026-02": "162899314",  "2026-03": "1575135129",
    "2026-04": "1702412906", "2026-05": "1499115222", "2026-06": "467088033",
}

CLOSED_STORES: set[str] = {
    "北屯軍福店", "犝犝楠梓店", "高雄大順店", "高雄自由店", "高雄鼎強店", "鳳山文中店",
}

DEPARTMENTS = [
    '董事長室', '營運中心', '研發課', '教育訓練課', '食安課',
    '展店課', '直營部', '財務部', '行銷部', '人資部',
    '採購部', '工程部', '行政部',
]

# Google Drive MIME 類型
DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
DOC_MIME = 'application/msword'
FOLDER_MIME = 'application/vnd.google-apps.folder'
GDOC_MIME = 'application/vnd.google-apps.document'
PDF_MIME = 'application/pdf'

DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
]

# Sheets 分頁名稱（必須跟 Google Sheet 中的分頁名一致）
TASKS_SHEET = 'tasks'
HISTORY_SHEET = 'progress_history'
SCANNED_SHEET = 'scanned_files'

TASK_COLUMNS = [
    'task_id', 'what', 'why', 'who_dept', 'who_person', 'where',
    'when_start', 'when_end', 'how', 'progress',
    'source_file', 'imported_at', 'updated_at',
]
HISTORY_COLUMNS = ['date', 'total', 'completed', 'avg_progress', 'completion_rate']
SCANNED_COLUMNS = ['file_id', 'file_name', 'scanned_at']


def _from_streamlit_secrets() -> dict[str, Any] | None:
    try:
        import streamlit as st  # 只有跑在 Streamlit 內才會 import 成功
        if not st.secrets:
            return None
        return dict(st.secrets)
    except Exception:
        return None


def _from_env() -> dict[str, Any]:
    """GitHub Actions / 本地 CLI 跑時用環境變數。

    需要設定的環境變數：
      - OPENAI_API_KEY
      - GSPREAD_SPREADSHEET_ID
      - DRIVE_FOLDER_ID
      - GCP_SERVICE_ACCOUNT_JSON  （整段 JSON 字串）
    """
    sa_raw = os.getenv('GCP_SERVICE_ACCOUNT_JSON', '')
    sa_dict: dict[str, Any] = {}
    if sa_raw:
        sa_dict = json.loads(sa_raw)
    return {
        'openai_api_key': os.getenv('OPENAI_API_KEY', ''),
        'google_sheets': {
            'spreadsheet_id': os.getenv('GSPREAD_SPREADSHEET_ID', ''),
            'drive_folder_id': os.getenv('DRIVE_FOLDER_ID', ''),
        },
        'gcp_service_account': sa_dict,
    }


def get_config() -> dict[str, Any]:
    """優先讀 Streamlit secrets，沒有就 fallback 到環境變數。"""
    cfg = _from_streamlit_secrets()
    if cfg and (cfg.get('openai_api_key') or cfg.get('gcp_service_account')):
        return cfg
    return _from_env()


def get_service_account_info() -> dict[str, Any]:
    cfg = get_config()
    info = cfg.get('gcp_service_account') or {}
    if not info:
        raise RuntimeError(
            '找不到 Service Account 設定，請檢查 secrets.toml 的 [gcp_service_account] '
            '或環境變數 GCP_SERVICE_ACCOUNT_JSON'
        )
    return dict(info)


def get_spreadsheet_id() -> str:
    cfg = get_config()
    sid = (cfg.get('google_sheets') or {}).get('spreadsheet_id', '')
    if not sid:
        raise RuntimeError('找不到 google_sheets.spreadsheet_id 設定')
    return sid


def get_drive_folder_id() -> str:
    cfg = get_config()
    fid = (cfg.get('google_sheets') or {}).get('drive_folder_id', '')
    if not fid:
        raise RuntimeError('找不到 google_sheets.drive_folder_id 設定')
    return fid


def get_openai_api_key() -> str:
    cfg = get_config()
    key = cfg.get('openai_api_key', '')
    if not key:
        raise RuntimeError('找不到 openai_api_key 設定')
    return key
