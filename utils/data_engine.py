"""
數據中樞引擎 — 供各分頁調用的全域資料讀取與店名模糊比對工具。
"""
from __future__ import annotations
import re
from typing import Optional, List
import pandas as pd
import streamlit as st

# ──────────────────────────────────────────────
# 常數
# ──────────────────────────────────────────────
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
from lib.config import REVENUE_SHEET_ID as SHEET_ID, REVENUE_SHEET_GIDS as SHEET_GIDS, CLOSED_STORES

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
        raw = pd.read_csv(url, header=None)
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
            start_str = str(t.get("when_start", "")).strip()
            end_str = str(t.get("when_end", "")).strip()
            start_date = None
            end_date = None
            if start_str:
                try:
                    start_date = dt_.strptime(start_str, "%Y-%m-%d").date()
                except ValueError:
                    pass
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
                "開始日":  start_date,
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
