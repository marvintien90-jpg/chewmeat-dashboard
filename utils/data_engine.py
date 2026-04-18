"""
數據中樞引擎 — 供各分頁調用的全域資料讀取與店名模糊比對工具。
"""
import re
import pandas as pd
import streamlit as st

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


def fuzzy_match_store(query: str, candidates: list[str]) -> str | None:
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
def load_all_revenue(months: list[str] | None = None) -> pd.DataFrame:
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
# 全域專案資料讀取（靜態範例，可日後接 Google Sheets）
# ──────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_projects() -> pd.DataFrame:
    from datetime import date as d_
    projects = [
        {"編號": "P-2026-001", "名稱": "門店效能優化計畫", "部門": "營運部", "負責人": "陳小明",
         "狀態": "執行中", "優先級": "高", "開始日": d_(2026, 1, 15), "截止日": d_(2026, 4, 30),
         "進度": 35, "標籤": "效能", "說明": "針對業績墊底門店進行人力、菜單、服務流程全面優化"},
        {"編號": "P-2026-002", "名稱": "台中新店展店計畫", "部門": "展店部", "負責人": "林佳慧",
         "狀態": "執行中", "優先級": "緊急", "開始日": d_(2026, 2, 1), "截止日": d_(2026, 5, 15),
         "進度": 68, "標籤": "展店", "說明": "台中市區第三家門店選址、裝修、人員招募"},
        {"編號": "P-2026-003", "名稱": "POS 系統升級", "部門": "資訊部", "負責人": "王大衛",
         "狀態": "執行中", "優先級": "高", "開始日": d_(2026, 1, 20), "截止日": d_(2026, 3, 31),
         "進度": 50, "標籤": "系統", "說明": "全門店 POS 系統版本升級，加入庫存預測模組"},
        {"編號": "P-2026-004", "名稱": "母親節行銷活動", "部門": "行銷部", "負責人": "張雅婷",
         "狀態": "執行中", "優先級": "高", "開始日": d_(2026, 3, 1), "截止日": d_(2026, 5, 12),
         "進度": 15, "標籤": "活動", "說明": "母親節限定套餐設計、社群媒體推廣、門店佈置"},
        {"編號": "P-2026-005", "名稱": "菜單 2.0 改版", "部門": "研發部", "負責人": "劉主廚",
         "狀態": "執行中", "優先級": "中", "開始日": d_(2026, 3, 15), "截止日": d_(2026, 6, 30),
         "進度": 5, "標籤": "菜單", "說明": "新增 8 道新品、調整定價策略、淘汰低點餐率品項"},
        {"編號": "P-2026-006", "名稱": "Q1 全員教育訓練", "部門": "人資部", "負責人": "吳淑芬",
         "狀態": "已完成", "優先級": "高", "開始日": d_(2026, 1, 3), "截止日": d_(2026, 1, 31),
         "進度": 100, "標籤": "培訓", "說明": "全台門店服務標準、食安法規、新菜單說明訓練"},
        {"編號": "P-2026-007", "名稱": "供應鏈優化專案", "部門": "採購部", "負責人": "黃建國",
         "狀態": "執行中", "優先級": "高", "開始日": d_(2026, 2, 15), "截止日": d_(2026, 5, 31),
         "進度": 28, "標籤": "供應鏈", "說明": "重新議價前三大食材供應商、縮短交期"},
        {"編號": "P-2026-008", "名稱": "會員忠誠計畫", "部門": "行銷部", "負責人": "張雅婷",
         "狀態": "暫緩", "優先級": "低", "開始日": d_(2026, 4, 1), "截止日": d_(2026, 8, 31),
         "進度": 0, "標籤": "會員", "說明": "APP 會員積點、生日優惠、等級制度建立"},
        {"編號": "P-2026-009", "名稱": "2025 稅務申報", "部門": "財務部", "負責人": "周會計",
         "狀態": "已完成", "優先級": "高", "開始日": d_(2026, 1, 2), "截止日": d_(2026, 2, 28),
         "進度": 100, "標籤": "財務", "說明": "2025 年度營利事業所得稅申報"},
        {"編號": "P-2026-010", "名稱": "高雄展店評估", "部門": "展店部", "負責人": "林佳慧",
         "狀態": "規劃中", "優先級": "中", "開始日": d_(2026, 4, 1), "截止日": d_(2026, 7, 31),
         "進度": 10, "標籤": "展店", "說明": "高雄市三民區商圈評估、人流調查"},
    ]
    return pd.DataFrame(projects)


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
