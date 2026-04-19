"""
utils/sheet_validator.py
多階段 Google Sheet 智能驗證引擎
"""
from __future__ import annotations
import io
import re
import requests
import pandas as pd
from typing import Optional


# ──────────────────────────────────────────────
# 欄位別名對照（與 data_engine.COL_ALIASES 保持一致）
# ──────────────────────────────────────────────
_DEFAULT_COL_ALIASES: dict[str, list[str]] = {
    "task":     ["任務項目", "任務名稱", "工作事項", "項目名稱", "工作項目",
                 "任務", "工作", "項目目標", "項目", "Task", "事項", "待辦事項"],
    "owner":    ["負責人", "承辦人", "執行人", "姓名", "人員", "Owner", "Assignee",
                 "立案單位", "負責單位", "申請單位", "負責部門"],
    "deadline": ["截止日期", "完成日期", "到期日", "期限", "截止", "完成期限",
                 "(預計)完成日", "預計完成日", "完成日", "Due Date", "Deadline"],
    "progress": ["目前進度", "進度", "完成度", "完成率", "Progress", "進展",
                 "進度比", "進度比較", "進度比例"],
    "status":   ["處理狀態", "狀態", "執行狀態", "Status", "任務狀態"],
}


def _find_col_by_aliases(headers: list[str], aliases: list[str]) -> Optional[str]:
    """Return the first header that matches any alias (case-insensitive)."""
    h_lower = [h.strip().lower() for h in headers]
    for alias in aliases:
        if alias.strip().lower() in h_lower:
            return headers[h_lower.index(alias.strip().lower())]
    return None


def get_sheet_tabs(sheet_id: str) -> list[dict]:
    """
    Enumerate all worksheets in a public Google Sheet.
    Returns [{"title": "工作表1", "gid": "0"}, ...]
    Falls back to [{"title": "工作表1", "gid": "0"}] on failure.
    """
    try:
        url = (
            f"https://spreadsheets.google.com/feeds/worksheets"
            f"/{sheet_id}/public/basic?alt=json"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        entries = data.get("feed", {}).get("entry", [])
        tabs = []
        for entry in entries:
            title = entry.get("title", {}).get("$t", "工作表1")
            gid = "0"
            for link in entry.get("link", []):
                href = link.get("href", "")
                m = re.search(r"gid=(\d+)", href)
                if m:
                    gid = m.group(1)
                    break
            tabs.append({"title": title, "gid": gid})
        return tabs if tabs else [{"title": "工作表1", "gid": "0"}]
    except Exception:
        return [{"title": "工作表1", "gid": "0"}]


def load_sheet_by_gid(sheet_id: str, gid: str) -> pd.DataFrame:
    """
    Fetch a specific tab as CSV.
    Tries with &gid= first; falls back to no-gid URL (loads the first/default tab).
    Returns empty DataFrame (with _error attribute) on failure.
    """
    urls_to_try = [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}",
        # Fallback: no gid — loads the default/first sheet (works when the GID is unknown)
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv",
    ]
    last_error = ""
    for url in urls_to_try:
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            df = pd.read_csv(io.BytesIO(resp.content)).dropna(how="all")
            if not df.empty:
                return df
        except Exception as e:
            last_error = str(e)
            continue
    empty = pd.DataFrame()
    empty._error = last_error  # type: ignore[attr-defined]
    return empty


def score_sheet_quality(df: pd.DataFrame, col_aliases: dict) -> dict:
    """
    Analyze data quality of a loaded DataFrame.
    col_aliases keys: task, owner, deadline, progress, status
    """
    issues: list[str] = []

    if df.empty:
        return {
            "total_rows": 0,
            "has_task_col": False,
            "has_deadline_col": False,
            "has_owner_col": False,
            "blank_tasks": 0,
            "blank_deadlines": 0,
            "blank_owners": 0,
            "zero_progress_no_status": 0,
            "quality_score": 0,
            "issues": ["工作表為空或無法解析"],
            "recommended_tab": "",
        }

    headers = df.columns.tolist()

    task_aliases     = col_aliases.get("task", _DEFAULT_COL_ALIASES["task"])
    owner_aliases    = col_aliases.get("owner", _DEFAULT_COL_ALIASES["owner"])
    deadline_aliases = col_aliases.get("deadline", _DEFAULT_COL_ALIASES["deadline"])
    progress_aliases = col_aliases.get("progress", _DEFAULT_COL_ALIASES["progress"])
    status_aliases   = col_aliases.get("status", _DEFAULT_COL_ALIASES["status"])

    task_col     = _find_col_by_aliases(headers, task_aliases)
    owner_col    = _find_col_by_aliases(headers, owner_aliases)
    deadline_col = _find_col_by_aliases(headers, deadline_aliases)
    progress_col = _find_col_by_aliases(headers, progress_aliases)
    status_col   = _find_col_by_aliases(headers, status_aliases)

    has_task     = task_col is not None
    has_deadline = deadline_col is not None
    has_owner    = owner_col is not None

    total_rows = len(df)

    # Count blanks
    def _blank_count(col: Optional[str]) -> int:
        if col is None or col not in df.columns:
            return total_rows
        return int(df[col].apply(lambda v: str(v).strip() in ("", "nan", "NaN", "None")).sum())

    blank_tasks     = _blank_count(task_col)
    blank_deadlines = _blank_count(deadline_col)
    blank_owners    = _blank_count(owner_col)

    # zero_progress_no_status
    zero_prog_no_status = 0
    if progress_col and progress_col in df.columns:
        def _is_zero_prog(v) -> bool:
            s = str(v).strip().replace("%", "").lower()
            try:
                return float(s) == 0.0
            except ValueError:
                return s in ("", "nan", "0", "待辦", "未開始")

        def _is_empty_status(v) -> bool:
            return str(v).strip() in ("", "nan", "NaN", "None")

        for _, row in df.iterrows():
            prog_v = row.get(progress_col, "")
            stat_v = row.get(status_col, "") if status_col else ""
            if _is_zero_prog(prog_v) and _is_empty_status(stat_v):
                zero_prog_no_status += 1

    # Quality score
    score = 100
    if not has_task:
        score -= 30
        issues.append("找不到任務名稱欄位（請確認欄位名稱）")
    if not has_deadline:
        score -= 20
        issues.append("找不到截止日期欄位")
    if not has_owner:
        score -= 15
        issues.append("找不到負責人欄位")

    if total_rows > 0:
        blank_task_ratio = blank_tasks / total_rows
        deduct_task = min(3, int(blank_task_ratio / 0.20)) * 10
        score -= deduct_task
        if deduct_task > 0:
            issues.append(f"任務名稱空白率 {round(blank_task_ratio*100)}%（共 {blank_tasks} 筆）")

        blank_dl_ratio = blank_deadlines / total_rows
        deduct_dl = min(4, int(blank_dl_ratio / 0.20)) * 5
        score -= deduct_dl
        if deduct_dl > 0:
            issues.append(f"截止日期空白率 {round(blank_dl_ratio*100)}%（共 {blank_deadlines} 筆）")

    score = max(0, score)

    return {
        "total_rows": total_rows,
        "has_task_col": has_task,
        "has_deadline_col": has_deadline,
        "has_owner_col": has_owner,
        "blank_tasks": blank_tasks,
        "blank_deadlines": blank_deadlines,
        "blank_owners": blank_owners,
        "zero_progress_no_status": zero_prog_no_status,
        "quality_score": score,
        "issues": issues,
        "recommended_tab": "",  # filled by find_best_tab
    }


def find_best_tab(sheet_id: str, col_aliases: Optional[dict] = None) -> dict:
    """
    Try all tabs and pick the one with the highest quality score.
    Returns {"df": best_df, "tab_title": str, "gid": str, "quality": dict, "all_tabs": list}
    """
    if col_aliases is None:
        col_aliases = _DEFAULT_COL_ALIASES

    tabs = get_sheet_tabs(sheet_id)
    best_df = pd.DataFrame()
    best_tab = tabs[0]["title"] if tabs else "工作表1"
    best_gid = tabs[0]["gid"] if tabs else "0"
    best_quality: dict = {}
    best_score = -1
    all_tabs = []

    for tab in tabs:
        df = load_sheet_by_gid(sheet_id, tab["gid"])
        if hasattr(df, "_error") or df.empty:
            all_tabs.append({
                "title": tab["title"],
                "gid": tab["gid"],
                "quality_score": 0,
                "error": getattr(df, "_error", "empty"),
            })
            continue

        quality = score_sheet_quality(df, col_aliases)
        quality["recommended_tab"] = tab["title"]
        sc = quality["quality_score"]
        all_tabs.append({
            "title": tab["title"],
            "gid": tab["gid"],
            "quality_score": sc,
        })

        if sc > best_score:
            best_score = sc
            best_df = df
            best_tab = tab["title"]
            best_gid = tab["gid"]
            best_quality = quality

    return {
        "df": best_df,
        "tab_title": best_tab,
        "gid": best_gid,
        "quality": best_quality,
        "all_tabs": all_tabs,
    }


def validate_and_load_dept_sheet(dept_name: str, sheet_id: str) -> dict:
    """
    Main entry point for the smart loader.
    Loads the best tab, maps columns, identifies problematic rows.
    """
    try:
        from utils.data_engine import COL_ALIASES as _ENGINE_ALIASES  # type: ignore
        # Map engine aliases to our format
        col_aliases = {
            "task":     _ENGINE_ALIASES.get("任務項目", _DEFAULT_COL_ALIASES["task"]),
            "owner":    _ENGINE_ALIASES.get("負責人",   _DEFAULT_COL_ALIASES["owner"]),
            "deadline": _ENGINE_ALIASES.get("截止日期", _DEFAULT_COL_ALIASES["deadline"]),
            "progress": _ENGINE_ALIASES.get("目前進度", _DEFAULT_COL_ALIASES["progress"]),
            "status":   _ENGINE_ALIASES.get("處理狀態", _DEFAULT_COL_ALIASES["status"]),
        }
    except Exception:
        col_aliases = _DEFAULT_COL_ALIASES

    result: dict = {
        "dept": dept_name,
        "sheet_id": sheet_id,
        "df": pd.DataFrame(),
        "tab_title": "",
        "quality": {},
        "problems": [],
        "success": False,
        "error": None,
        "raw_headers": [],      # original column names from the sheet
        "column_mapping": {},   # {std_col: original_col} for diagnostic display
    }

    try:
        best = find_best_tab(sheet_id, col_aliases)
        df = best["df"]
        tab_title = best["tab_title"]
        gid = best["gid"]
        quality = best["quality"]

        result["tab_title"] = tab_title
        result["quality"] = quality
        result["quality"]["all_tabs"] = best.get("all_tabs", [])

        if df.empty:
            result["error"] = "所有工作表均為空或無法讀取"
            return result

        # Store raw headers before renaming
        result["raw_headers"] = df.columns.tolist()

        # Apply column mapping using engine's _map_dept_columns (with diagnostic output)
        col_map_out: dict = {}
        try:
            from utils.data_engine import _map_dept_columns, _normalize_dept_progress, _derive_dept_status  # type: ignore
            df = _map_dept_columns(df, _col_map_out=col_map_out)
            df["目前進度"] = df["目前進度"].apply(_normalize_dept_progress)
            df["處理狀態"] = df.apply(
                lambda r: _derive_dept_status(r["目前進度"], r.get("截止日期", "")), axis=1
            )
        except Exception:
            pass

        result["column_mapping"] = col_map_out
        df["來源部門"] = dept_name
        df["_sheet_id"] = sheet_id
        df["_row_index"] = range(2, len(df) + 2)
        df["_tab_title"] = tab_title
        df["_gid"] = gid

        # Identify problematic rows
        problems: list[dict] = []
        task_col = "任務項目" if "任務項目" in df.columns else None
        deadline_col = "截止日期" if "截止日期" in df.columns else None
        owner_col = "負責人" if "負責人" in df.columns else None
        progress_col = "目前進度" if "目前進度" in df.columns else None
        status_col = "處理狀態" if "處理狀態" in df.columns else None

        for _, row in df.iterrows():
            row_idx = int(row.get("_row_index", 0))
            task_val = str(row.get(task_col, "") if task_col else "").strip()
            if not task_val or task_val in ("nan", "None", "NaN"):
                task_val = ""

            task_display = task_val if task_val else "(未命名)"

            # blank task
            if not task_val:
                problems.append({
                    "row_index": row_idx,
                    "task": task_display,
                    "dept": dept_name,
                    "issue_type": "blank_task",
                    "issue_desc": "任務名稱為空，無法追蹤",
                    "current_value": "",
                    "field_to_fix": "任務項目",
                    "sheet_id": sheet_id,
                    "gid": gid,
                })
                continue  # skip further checks for unnamed tasks

            # blank deadline
            if deadline_col:
                dl_val = str(row.get(deadline_col, "")).strip()
                if not dl_val or dl_val in ("nan", "None", "NaN"):
                    problems.append({
                        "row_index": row_idx,
                        "task": task_display,
                        "dept": dept_name,
                        "issue_type": "blank_deadline",
                        "issue_desc": f"「{task_display[:20]}」缺少截止日期",
                        "current_value": "",
                        "field_to_fix": "截止日期",
                        "sheet_id": sheet_id,
                        "gid": gid,
                    })

            # blank owner
            if owner_col:
                owner_val = str(row.get(owner_col, "")).strip()
                if not owner_val or owner_val in ("nan", "None", "NaN"):
                    problems.append({
                        "row_index": row_idx,
                        "task": task_display,
                        "dept": dept_name,
                        "issue_type": "blank_owner",
                        "issue_desc": f"「{task_display[:20]}」缺少負責人",
                        "current_value": "",
                        "field_to_fix": "負責人",
                        "sheet_id": sheet_id,
                        "gid": gid,
                    })

            # stuck progress: progress==0 and status is empty
            if progress_col and status_col:
                prog_val = row.get(progress_col, 0)
                stat_val = str(row.get(status_col, "")).strip()
                try:
                    prog_int = int(float(str(prog_val).replace("%", "")))
                except Exception:
                    prog_int = 0
                if prog_int == 0 and (not stat_val or stat_val in ("nan", "None", "NaN")):
                    problems.append({
                        "row_index": row_idx,
                        "task": task_display,
                        "dept": dept_name,
                        "issue_type": "stuck_progress",
                        "issue_desc": f"「{task_display[:20]}」進度為0且狀態空白",
                        "current_value": "",
                        "field_to_fix": "處理狀態",
                        "sheet_id": sheet_id,
                        "gid": gid,
                    })

        result["df"] = df
        result["problems"] = problems
        result["success"] = True
        return result

    except Exception as e:
        result["error"] = str(e)
        return result
