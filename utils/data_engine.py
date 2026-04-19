"""
數據中樞引擎 — 供各分頁調用的全域資料讀取與店名模糊比對工具。
"""
from __future__ import annotations
import re
import io
import requests
import json as _json
from typing import Optional, List
import pandas as pd
import streamlit as st

# Module-level validation cache — populated by load_all_dept_tasks
_dept_validation_cache: dict = {}


def get_dept_validation_results() -> dict:
    """Return a copy of the last dept validation results."""
    return _dept_validation_cache.copy()


def extract_sheet_id(url_or_id: str) -> str:
    """Extract Google Sheet ID from full URL or return as-is if already an ID."""
    s = str(url_or_id).strip()
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9\-_]+)', s)
    return m.group(1) if m else s


def save_dept_sheet_ids(ids: dict[str, str]) -> bool:
    """Persist dept sheet IDs to config/dept_sheets.json."""
    import os as _os
    config_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "config")
    _os.makedirs(config_dir, exist_ok=True)
    path = _os.path.join(config_dir, "dept_sheets.json")
    try:
        cleaned = {k: extract_sheet_id(v) for k, v in ids.items()}
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(cleaned, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

# ──────────────────────────────────────────────
# 常數
# ──────────────────────────────────────────────
SHEET_ID = "1NZQEJgL-HkB08JSW6zsVHRSyl_XgwLc5etUqSF0O9ow"

SHEET_GIDS = {
    "2025-01": "672482866",  "2025-02": "1943981506", "2025-03": "847955849",
    "2025-04": "591730250",  "2025-05": "695013616",  "2025-06": "897256004",
    "2025-07": "593028448",  "2025-08": "836455215",  "2025-09": "1728608975",
    "2025-10": "2043079442", "2025-11": "1307429413", "2025-12": "1838876978",
    "2026-01": "872131612",  "2026-02": "162899314",  "2026-03": "1575135129",
    "2026-04": "1702412906", "2026-05": "1499115222", "2026-06": "467088033",
}

CLOSED_STORES = {"北屯軍福店", "犝犝楠梓店", "高雄大順店", "高雄自由店", "高雄鼎強店", "鳳山文中店"}

from datetime import date


# ──────────────────────────────────────────────
# 店名模糊比對
# ──────────────────────────────────────────────
def _normalize(name: str) -> str:
    """去除常見贅字、空白，便於比對。"""
    name = str(name).strip()
    for token in ["嗑肉石鍋", "嗑肉", "石鍋", "店", " ", "　"]:
        name = name.replace(token, "")
    return name


def fuzzy_match_store(query: str, candidates: List[str]) -> Optional[str]:
    """
    從 candidates 中找出與 query 最接近的店名。
    先做正規化後子字串比對；找不到則回傳 None。
    """
    q_norm = _normalize(query)
    for c in candidates:
        if _normalize(c) == q_norm:
            return c
    # 子字串部分比對
    for c in candidates:
        if q_norm in _normalize(c) or _normalize(c) in q_norm:
            return c
    return None


def align_store_names(df_a: pd.DataFrame, df_b: pd.DataFrame,
                      col_a: str = "店名", col_b: str = "店名") -> pd.DataFrame:
    """
    將 df_b[col_b] 的店名對齊到 df_a[col_a] 的標準命名，
    回傳新增 aligned_store 欄的 df_b 副本。
    """
    candidates = df_a[col_a].unique().tolist()
    df_b = df_b.copy()
    df_b["aligned_store"] = df_b[col_b].apply(
        lambda x: fuzzy_match_store(x, candidates) or x
    )
    return df_b


# ──────────────────────────────────────────────
# 全域營收資料讀取
# ──────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_revenue_sheet(year_month: str, gid: str) -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        raw = pd.read_csv(io.BytesIO(resp.content), header=None)
    except Exception:
        return pd.DataFrame()

    year, month = year_month.split("-")
    year, month = int(year), int(month)

    date_row = raw.iloc[1, 7:]
    dates = []
    for val in date_row:
        s = str(val).strip()
        if s in ("nan", "合計"):
            continue
        m_ = re.match(r"(\d+)/(\d+)", s)
        if m_:
            mo, d = int(m_.group(1)), int(m_.group(2))
            if mo != month:
                continue
            try:
                dates.append(date(year, mo, d))
            except ValueError:
                continue

    if not dates:
        return pd.DataFrame()

    rows = []
    cur_region = cur_store = cur_target = None

    for i in range(2, len(raw)):
        row = raw.iloc[i]
        if pd.notna(row.iloc[0]) and str(row.iloc[0]).strip():
            cur_region = str(row.iloc[0]).strip()
        if pd.notna(row.iloc[1]) and str(row.iloc[1]).strip():
            cur_store = str(row.iloc[1]).strip()
        if pd.notna(row.iloc[2]) and str(row.iloc[2]).strip():
            t = str(row.iloc[2]).replace(",", "").strip()
            try:
                cur_target = float(t)
            except ValueError:
                cur_target = None

        metric = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else ""
        if metric not in ("業績合計", "人數合計", "平均客單"):
            continue
        if not cur_store:
            continue

        vals = []
        for val in row.iloc[7: 7 + len(dates)]:
            s = str(val).strip().replace(",", "").replace(" ", "")
            if s in ("nan", "", "#DIV/0!", "\\#DIV/0\\!"):
                vals.append(None)
            else:
                try:
                    vals.append(float(s))
                except ValueError:
                    vals.append(None)

        for dt, v in zip(dates, vals):
            if v is None:
                continue
            rows.append({
                "日期": dt,
                "年月": year_month,
                "商圈": cur_region,
                "店名": cur_store,
                "月目標": cur_target,
                "指標": metric,
                "數值": v,
            })

    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def load_all_revenue(months: Optional[List[str]] = None) -> pd.DataFrame:
    """
    讀取所有（或指定）月份的營收資料，回傳寬表（已 pivot）。
    欄位：日期, 年月, 商圈, 店名, 月目標, 業績合計, 人數合計, 平均客單
    """
    if months is None:
        months = list(SHEET_GIDS.keys())

    frames = []
    for ym in months:
        gid = SHEET_GIDS.get(ym)
        if not gid:
            continue
        df = load_revenue_sheet(ym, gid)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    long = pd.concat(frames, ignore_index=True)
    long = long[~long["店名"].isin(CLOSED_STORES)]

    pivot = long.pivot_table(
        index=["日期", "年月", "商圈", "店名", "月目標"],
        columns="指標",
        values="數值",
        aggfunc="first",
    ).reset_index()
    pivot.columns.name = None
    for col in ("業績合計", "人數合計", "平均客單"):
        if col not in pivot.columns:
            pivot[col] = None
    return pivot


# ──────────────────────────────────────────────
# 全域專案資料讀取（接 Google Sheets 後端）
# ──────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_projects() -> pd.DataFrame:
    """
    優先從 Google Sheets（總部專案追蹤助理後端）讀取真實任務。
    若無法連線（缺少 secrets），回傳空 DataFrame。
    """
    from datetime import date as d_, datetime as dt_
    try:
        from lib.sheets_db import load_tasks
        tasks = load_tasks()
        if not tasks:
            return pd.DataFrame()

        def _derive_status(t: dict) -> str:
            prog = int(t.get("progress", 0))
            if prog >= 100:
                return "已完成"
            end_str = str(t.get("when_end", "")).strip()
            if end_str:
                try:
                    if dt_.strptime(end_str, "%Y-%m-%d").date() < d_.today():
                        return "逾期"
                except ValueError:
                    pass
            start_str = str(t.get("when_start", "")).strip()
            if start_str:
                try:
                    if dt_.strptime(start_str, "%Y-%m-%d").date() <= d_.today():
                        return "執行中"
                except ValueError:
                    pass
            return "規劃中"

        rows = []
        for t in tasks:
            status = _derive_status(t)
            end_str = str(t.get("when_end", "")).strip()
            end_date = None
            if end_str:
                try:
                    end_date = dt_.strptime(end_str, "%Y-%m-%d").date()
                except ValueError:
                    pass
            rows.append({
                "編號":   t.get("task_id", "")[:8],
                "名稱":   t.get("what", "（無標題）"),
                "部門":   t.get("who_dept", "—"),
                "負責人":  t.get("who_person", "—"),
                "狀態":   status,
                "優先級":  "高",
                "開始日":  end_date,
                "截止日":  end_date,
                "進度":   int(t.get("progress", 0)),
                "標籤":   t.get("who_dept", ""),
                "說明":   t.get("how", "") or t.get("why", ""),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


# ──────────────────────────────────────────────
# 快速診斷摘要（供戰情室調用）
# ──────────────────────────────────────────────
def get_revenue_anomalies(df_all: pd.DataFrame, lookback_months: int = 2) -> list[dict]:
    """
    從全量營收資料中找出近 N 個月月均業績下滑 ≥10% 的門店，
    回傳結構化清單 [{store, prev_avg, curr_avg, drop_pct, source_note}]
    """
    if df_all.empty or "業績合計" not in df_all.columns:
        return []

    df = df_all.dropna(subset=["業績合計"]).copy()
    df["年月"] = df["年月"].astype(str)
    all_months = sorted(df["年月"].unique())
    if len(all_months) < lookback_months + 1:
        return []

    curr_months = all_months[-lookback_months:]
    prev_months = all_months[-2 * lookback_months: -lookback_months]

    curr_avg = (df[df["年月"].isin(curr_months)]
                .groupby("店名")["業績合計"].mean())
    prev_avg = (df[df["年月"].isin(prev_months)]
                .groupby("店名")["業績合計"].mean())

    anomalies = []
    for store in curr_avg.index:
        if store not in prev_avg.index:
            continue
        c, p = curr_avg[store], prev_avg[store]
        if p == 0:
            continue
        drop = (p - c) / p
        if drop >= 0.10:
            anomalies.append({
                "店名": store,
                "前期均值": round(p),
                "近期均值": round(c),
                "下滑幅度": round(drop * 100, 1),
                "數據來源": f"[來源：營收表-{curr_months[0]}~{curr_months[-1]}]",
            })
    return sorted(anomalies, key=lambda x: -x["下滑幅度"])


def get_overdue_projects(df_projects: pd.DataFrame) -> list[dict]:
    """
    找出截止日已過且進度未達 100% 的逾期任務。
    """
    today = date.today()
    overdue = []
    for _, row in df_projects.iterrows():
        if row["狀態"] == "已完成":
            continue
        deadline = row["截止日"]
        if isinstance(deadline, date) and deadline < today and row["進度"] < 100:
            overdue.append({
                "編號": row["編號"],
                "名稱": row["名稱"],
                "部門": row["部門"],
                "負責人": row["負責人"],
                "截止日": str(deadline),
                "進度": row["進度"],
                "逾期天數": (today - deadline).days,
                "數據來源": f"[來源：專案表-{row['編號']}]",
            })
    return sorted(overdue, key=lambda x: -x["逾期天數"])


# ══════════════════════════════════════════════════════════════════
# ★ 6 部門 Google Sheets ETL 引擎（跨部門工作追蹤）
# ══════════════════════════════════════════════════════════════════
import sys as _sys
import os as _os
from functools import lru_cache as _lru_cache
from datetime import datetime as _datetime, timedelta as _timedelta

DEPT_KEYS = ["行銷", "人資", "採購", "行政", "財務", "資訊"]

COL_ALIASES: dict[str, list[str]] = {
    "負責人":   ["負責人", "承辦人", "執行人", "姓名", "人員", "Owner", "Assignee",
                "立案單位", "負責單位", "申請單位", "負責部門"],
    "任務項目": ["任務項目", "任務名稱", "工作事項", "項目名稱", "工作項目",
                "任務", "工作", "項目目標", "項目", "Task", "事項", "待辦事項"],
    "截止日期": ["截止日期", "完成日期", "到期日", "期限", "截止", "完成期限",
                "(預計)完成日", "預計完成日", "完成日", "Due Date", "Deadline"],
    "目前進度": ["目前進度", "進度", "完成度", "完成率", "Progress", "進展",
                "進度比", "進度比較", "進度比例"],
    "處理狀態": ["處理狀態", "狀態", "執行狀態", "Status", "任務狀態"],
    "最後更新": ["最後更新", "最後更新日", "更新日期", "更新時間", "updated_at",
                "Last Updated", "立案日"],
}

DEPT_STANDARD_COLS = [
    "來源部門", "負責人", "任務項目", "截止日期",
    "目前進度", "處理狀態", "最後更新", "_sheet_id", "_row_index",
]


def _daily_cache_key() -> str:
    now = _datetime.now()
    if now.hour < 8:
        return str(date.today() - _timedelta(days=1))
    return str(date.today())


@_lru_cache(maxsize=1)
def _get_dept_gspread_client():
    from lib.config import get_service_account_info, DRIVE_SCOPES
    from google.oauth2.service_account import Credentials
    import gspread
    info = get_service_account_info()
    creds = Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)
    return gspread.authorize(creds)


def _get_dept_sheet_ids() -> dict[str, str]:
    """Read dept sheet IDs from config file first, fallback to st.secrets."""
    config_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "config", "dept_sheets.json")
    if _os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
                ids = {k: str(v).strip() for k, v in data.items() if v and str(v).strip()}
                if ids:
                    return ids
        except Exception:
            pass
    try:
        return {k: v for k, v in dict(st.secrets.get("dept_sheets", {})).items() if v}
    except Exception:
        return {}


_BLANK_VALS = frozenset({"", "nan", "NaN", "None", "NONE", "none", "-", "—", "N/A", "n/a"})


def _find_col_alias(headers: list[str], aliases: list[str]) -> str | None:
    h_lower = [h.strip().lower() for h in headers]
    for alias in aliases:
        if alias.strip().lower() in h_lower:
            return headers[h_lower.index(alias.strip().lower())]
    return None


def _col_task_quality(df: pd.DataFrame, col: str) -> float:
    """
    Score how likely `col` is to contain real task descriptions (0.0–1.0).
    Good task columns: longer avg string, high uniqueness.
    Bad (categorical/scope columns): very short values, many repeats.
    """
    if col not in df.columns:
        return 0.0
    vals = df[col].astype(str).str.strip()
    vals = vals[~vals.isin(_BLANK_VALS)]
    if len(vals) == 0:
        return 0.0
    avg_len = float(vals.str.len().mean())
    unique_ratio = vals.nunique() / len(vals)
    # Normalize: avg_len 8+ chars → full score
    len_score = min(1.0, avg_len / 8.0)
    return 0.6 * len_score + 0.4 * unique_ratio


# Column names that look like scope/category/target, not task descriptions
_NON_TASK_KEYWORDS = frozenset({
    "對象", "類別", "分類", "月份", "年月", "年份", "門店", "店別", "店名",
    "金額", "數量", "費用", "單價", "備註", "note", "remark", "月", "季",
    "商圈", "區域", "地區", "range", "region",
    # Columns whose name contains these are progress/date/unit — not task names
    "進度", "日期", "立案",
})

_TASK_COL_QUALITY_THRESHOLD = 0.22
# Bonus given to alias-matched column to favour explicitly-named task columns
_TASK_COL_ALIAS_BONUS = 0.10


def _smart_find_task_col(df: pd.DataFrame, aliases: list[str]) -> str | None:
    """
    Find the best column to use as the task-name column.

    Strategy:
    1. Find the alias-matched candidate (if any) and score its content quality.
    2. Scan ALL other eligible columns for content quality.
    3. Give the alias candidate a small naming-bonus so it wins ties.
    4. But if a non-alias column clearly outscores it (real task descriptions
       are long and unique), use that instead.
    """
    headers = df.columns.tolist()

    # Step 1 – alias candidate
    alias_candidate = _find_col_alias(headers, aliases)
    alias_score = _col_task_quality(df, alias_candidate) if alias_candidate else 0.0
    # Effective score includes a small bonus for having the right name
    effective_alias_score = (alias_score + _TASK_COL_ALIAS_BONUS) if alias_candidate else 0.0

    # Step 2 – collect columns already claimed by other standard fields
    already_claimed: set[str] = set()
    for std_col, als in COL_ALIASES.items():
        if std_col == "任務項目":
            continue
        found = _find_col_alias(headers, als)
        if found:
            already_claimed.add(found)

    # Step 3 – find best content-quality column among all eligible columns
    best_content_col: str | None = None
    best_content_score: float = 0.0

    for col in headers:
        if col in already_claimed:
            continue
        col_lower = col.strip().lower()
        # Skip obviously non-task columns by keyword
        if any(kw.lower() in col_lower for kw in _NON_TASK_KEYWORDS):
            continue
        q = _col_task_quality(df, col)
        if q > best_content_score:
            best_content_score = q
            best_content_col = col

    # Step 4 – choose the better of alias-candidate vs. content-winner
    # Content winner takes over only if it clearly surpasses the alias candidate
    if best_content_col and best_content_score > effective_alias_score:
        return best_content_col

    # Alias candidate (or None if nothing found anywhere)
    return alias_candidate if alias_candidate else best_content_col


def _map_dept_columns(df: pd.DataFrame, _col_map_out: dict | None = None) -> pd.DataFrame:
    """
    Map raw sheet columns to standardised names.
    If `_col_map_out` dict is supplied, it will be populated with
    {std_col: original_col_name} for diagnostic display.
    """
    headers = df.columns.tolist()
    rename_map: dict[str, str] = {}

    # Task column: smart content-quality-aware detection
    task_col = _smart_find_task_col(df, COL_ALIASES["任務項目"])
    if task_col:
        rename_map[task_col] = "任務項目"
        if _col_map_out is not None:
            _col_map_out["任務項目"] = task_col

    # All other columns: regular alias matching
    for std_col, aliases in COL_ALIASES.items():
        if std_col == "任務項目":
            continue
        found = _find_col_alias(headers, aliases)
        if found and found not in rename_map:
            rename_map[found] = std_col
            if _col_map_out is not None:
                _col_map_out[std_col] = found

    df = df.rename(columns=rename_map)
    for col in ["負責人", "任務項目", "截止日期", "目前進度", "處理狀態", "最後更新"]:
        if col not in df.columns:
            df[col] = ""
    # Normalize blank-equivalent strings ("nan", "NaN", "None", etc.) → "" in text columns
    for col in ["負責人", "截止日期", "處理狀態", "最後更新"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(_BLANK_VALS), col] = ""
    return df


_PROGRESS_KW: dict[str, int] = {
    "待辦": 0, "未開始": 0, "進行中": 50, "執行中": 50,
    "進行": 50, "已完成": 100, "完成": 100, "done": 100,
}


def _normalize_dept_progress(val) -> int:
    if val is None or str(val).strip() == "":
        return 0
    s = str(val).strip().lower().replace("%", "")
    try:
        return max(0, min(100, round(float(s))))
    except ValueError:
        pass
    for kw, pct in _PROGRESS_KW.items():
        if kw.lower() in s:
            return pct
    return 0


def _parse_dept_date(s) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%Y年%m月%d日"):
        try:
            return _datetime.strptime(str(s).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _derive_dept_status(progress: int, deadline_str: str) -> str:
    if progress >= 100:
        return "已完成"
    if deadline_str:
        d = _parse_dept_date(deadline_str)
        if d and d < date.today():
            return "逾期"
    if progress > 0:
        return "進行中"
    return "待辦"


def get_dept_traffic_light(row: dict) -> str:
    if row.get("處理狀態") == "已完成":
        return "⚪"
    today = date.today()
    deadline = _parse_dept_date(row.get("截止日期", ""))
    last_upd = _parse_dept_date(row.get("最後更新", ""))
    if deadline and deadline < today:
        return "🔴"
    if last_upd and (today - last_upd).days > 3:
        return "🔴"
    if deadline and 0 <= (deadline - today).days <= 2:
        return "🟡"
    return "🟢"


def _load_one_dept_sheet(dept_name: str, sheet_id: str) -> pd.DataFrame:
    """Load dept sheet via public CSV export. Sheet must be 'anyone with link can view'."""
    try:
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        df = pd.read_csv(io.BytesIO(resp.content))
        if df.empty:
            return pd.DataFrame()
        df = df.dropna(how="all")
        df = _map_dept_columns(df)
        df["目前進度"] = df["目前進度"].apply(_normalize_dept_progress)
        df["處理狀態"] = df.apply(
            lambda r: _derive_dept_status(r["目前進度"], r.get("截止日期", "")), axis=1
        )
        df["來源部門"] = dept_name
        df["_sheet_id"] = sheet_id
        df["_row_index"] = range(2, len(df) + 2)
        # Filter blank/NaN task names
        df = df[~df["任務項目"].astype(str).str.strip().isin(_BLANK_VALS)]
        return df[DEPT_STANDARD_COLS].reset_index(drop=True)
    except Exception as e:
        return pd.DataFrame({"_error": [str(e)], "來源部門": [dept_name]})


def load_all_dept_tasks(cache_key: str = "") -> tuple[pd.DataFrame, dict[str, str]]:
    global _dept_validation_cache
    sheet_ids = _get_dept_sheet_ids()
    frames: list[pd.DataFrame] = []
    errors: dict[str, str] = {}
    validation_results: dict = {}

    for dept_name in DEPT_KEYS:
        sid = sheet_ids.get(dept_name, "")
        if not sid:
            errors[dept_name] = "⚙️ 尚未設定 Google Sheet 網址（請至系統設定頁配置）"
            continue

        # Try smart loader first
        loaded_via_smart = False
        try:
            from utils.sheet_validator import validate_and_load_dept_sheet
            result = validate_and_load_dept_sheet(dept_name, sid)
            if result["success"] and not result["df"].empty:
                df = result["df"]
                # Ensure standard columns are present
                for col in ["負責人", "任務項目", "截止日期", "目前進度", "處理狀態", "最後更新"]:
                    if col not in df.columns:
                        df[col] = ""
                # Re-apply progress normalisation and status derivation
                df["目前進度"] = df["目前進度"].apply(_normalize_dept_progress)
                df["處理狀態"] = df.apply(
                    lambda r: _derive_dept_status(r["目前進度"], r.get("截止日期", "")), axis=1
                )
                df["來源部門"] = dept_name
                df["_sheet_id"] = sid
                if "_row_index" not in df.columns:
                    df["_row_index"] = range(2, len(df) + 2)
                # Filter blank/NaN task rows
                df = df[~df["任務項目"].astype(str).str.strip().isin(_BLANK_VALS)]
                # Keep only standard columns (plus any extras already there)
                keep = [c for c in DEPT_STANDARD_COLS if c in df.columns]
                df = df[keep].reset_index(drop=True)
                if not df.empty:
                    frames.append(df)
                validation_results[dept_name] = result
                loaded_via_smart = True
        except Exception:
            pass

        if not loaded_via_smart:
            # Fallback to old loader
            df = _load_one_dept_sheet(dept_name, sid)
            if "_error" in df.columns:
                errors[dept_name] = df["_error"].iloc[0] if not df.empty else "未知錯誤"
                continue
            if not df.empty:
                frames.append(df)

    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=DEPT_STANDARD_COLS)
    if not merged.empty:
        merged["燈號"] = merged.apply(lambda r: get_dept_traffic_light(r.to_dict()), axis=1)
    else:
        merged["燈號"] = pd.Series(dtype=str)

    # Persist validation results for page access
    _dept_validation_cache.update(validation_results)

    return merged, errors


def load_all_dept_tasks_cached() -> tuple[pd.DataFrame, dict[str, str]]:
    try:
        import streamlit as st

        @st.cache_data(ttl=86400, show_spinner=False)
        def _inner(key: str):
            return load_all_dept_tasks(cache_key=key)

        return _inner(_daily_cache_key())
    except Exception:
        return load_all_dept_tasks()


def write_dept_approval(sheet_id: str, row_index: int, approval: str, comment: str) -> bool:
    try:
        client = _get_dept_gspread_client()
        sh = client.open_by_key(sheet_id)
        ws = None
        for tab in ["任務", "Tasks", "工作清單", "Sheet1", "工作項目", "task", "tasks"]:
            try:
                ws = sh.worksheet(tab)
                break
            except Exception:
                continue
        if ws is None:
            ws = sh.get_worksheet(0)
        if ws is None:
            return False
        headers = ws.row_values(1)

        def _ensure_col(name: str) -> int:
            if name in headers:
                return headers.index(name) + 1
            idx = len(headers) + 1
            ws.update_cell(1, idx, name)
            headers.append(name)
            return idx

        ac = _ensure_col("總指揮批示")
        cc = _ensure_col("批示意見")
        tc = _ensure_col("批示時間")
        now_str = _datetime.now().strftime("%Y-%m-%d %H:%M")
        ws.update_cell(row_index, ac, approval)
        ws.update_cell(row_index, cc, comment)
        ws.update_cell(row_index, tc, now_str)
        return True
    except Exception:
        return False


def write_dept_field(sheet_id: str, row_index: int, field_name: str, value: str, gid: str = "0") -> bool:
    """Write a single field value back to the sheet."""
    try:
        client = _get_dept_gspread_client()
        sh = client.open_by_key(sheet_id)
        ws = sh.get_worksheet_by_id(int(gid)) if gid != "0" else sh.get_worksheet(0)
        if ws is None:
            return False
        headers = ws.row_values(1)
        col_idx = None
        # Direct match first
        for i, h in enumerate(headers):
            if h.strip() == field_name:
                col_idx = i + 1
                break
        # Then try aliases
        if col_idx is None:
            aliases = COL_ALIASES.get(field_name, [field_name])
            for alias in aliases:
                for i, h in enumerate(headers):
                    if h.strip() == alias:
                        col_idx = i + 1
                        break
                if col_idx is not None:
                    break
        if col_idx is None:
            return False
        ws.update_cell(row_index, col_idx, value)
        return True
    except Exception:
        return False


def get_top_red_items(df: pd.DataFrame, n: int = 3) -> list[dict]:
    if df.empty:
        return []
    today = date.today()
    red_rows = []
    for _, row in df.iterrows():
        light = row.get("燈號", "")
        if light not in ("🔴", "🟡"):
            continue
        deadline = _parse_dept_date(row.get("截止日期", ""))
        overdue_days = (today - deadline).days if deadline and deadline < today else 0
        last_upd = _parse_dept_date(row.get("最後更新", ""))
        stale_days = (today - last_upd).days if last_upd else 0
        red_rows.append({
            "來源部門":  row.get("來源部門", ""),
            "負責人":    row.get("負責人", ""),
            "任務項目":  row.get("任務項目", ""),
            "截止日期":  row.get("截止日期", ""),
            "目前進度":  row.get("目前進度", 0),
            "處理狀態":  row.get("處理狀態", ""),
            "燈號":      light,
            "_overdue":  overdue_days,
            "_stale":    stale_days,
            "_sheet_id": row.get("_sheet_id", ""),
            "_row_index": int(row.get("_row_index", 0)),
        })
    red_rows.sort(key=lambda x: (-x["_overdue"], -x["_stale"]))
    return red_rows[:n]
