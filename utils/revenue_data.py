"""
嗑肉石鍋 數位總部 — 營收資料共用模組
所有需要讀取營收資料的頁面皆從此模組匯入，避免重複定義。
"""
import re
import calendar
import warnings
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

warnings.filterwarnings("ignore")

# ── Google Sheets 設定 ────────────────────────────────────────
SHEET_ID = "1NZQEJgL-HkB08JSW6zsVHRSyl_XgwLc5etUqSF0O9ow"

SHEET_GIDS = {
    "2025-01": "672482866",  "2025-02": "1943981506", "2025-03": "847955849",
    "2025-04": "591730250",  "2025-05": "695013616",  "2025-06": "897256004",
    "2025-07": "593028448",  "2025-08": "836455215",  "2025-09": "1728608975",
    "2025-10": "2043079442", "2025-11": "1307429413", "2025-12": "1838876978",
    "2026-01": "872131612",  "2026-02": "162899314",  "2026-03": "1575135129",
    "2026-04": "1702412906", "2026-05": "1499115222", "2026-06": "467088033",
}

WEEKDAY_MAP = {0: "週一", 1: "週二", 2: "週三", 3: "週四", 4: "週五", 5: "週六", 6: "週日"}
QUARTER_MAP = {1: "Q1", 2: "Q1", 3: "Q1", 4: "Q2", 5: "Q2", 6: "Q2",
               7: "Q3", 8: "Q3", 9: "Q3", 10: "Q4", 11: "Q4", 12: "Q4"}

# 已結村門店（有歷史資料但已停業）
CLOSED_STORES = {"北屯軍福店", "犝犝楠梓店", "高雄大順店", "高雄自由店", "高雄鼎強店", "鳳山文中店"}

# 手機圖表設定：關閉縮放/拖曳，保留 tooltip
MOBILE_CHART_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "displaylogo": False,
    "staticPlot": False,
}

# ── 溫暖橘紅主題 CSS ──────────────────────────────────────────
PORTAL_CSS = """
<style>
    /* 全域背景與字體 */
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

    /* KPI 卡片 — 溫暖圓角風格 */
    [data-testid="stMetric"] {
        background: #FFF5F2;
        border: 1px solid #FFD9CC;
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 2px 6px rgba(232,67,26,0.08);
    }
    [data-testid="stMetricLabel"] { font-size: 0.85rem; color: #7A5544; }
    [data-testid="stMetricValue"] { font-size: 1.55rem; font-weight: 700; color: #E8431A; }
    [data-testid="stMetricDelta"] { font-size: 0.8rem; }

    /* 側邊欄 */
    [data-testid="stSidebar"] {
        background: #FFF5F2;
        border-right: 2px solid #FFD9CC;
    }
    [data-testid="stSidebar"] h2 {
        color: #E8431A;
        font-weight: 800;
    }

    /* 標題色 */
    h1 { color: #E8431A !important; }
    h2 { color: #C73A18 !important; }
    h3 { color: #D94420 !important; }

    /* 按鈕 */
    .stButton > button {
        background: #E8431A;
        color: white;
        border-radius: 10px;
        border: none;
        font-weight: 600;
    }
    .stButton > button:hover {
        background: #C73A18;
        color: white;
    }

    /* 分隔線 */
    hr { border-color: #FFD9CC; }

    /* 手機優化 */
    @media (max-width: 768px) {
        .main .block-container { padding: 0.8rem; }
        [data-testid="stMetricValue"] { font-size: 1.2rem; }
    }
</style>
"""


# ── 資料讀取 ─────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_sheet(year_month: str, gid: str) -> pd.DataFrame:
    """從 Google Sheets 載入單月資料，失敗時回傳空 DataFrame"""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    try:
        raw = pd.read_csv(url, header=None)
    except Exception:
        return pd.DataFrame()

    year, month = year_month.split("-")
    year, month = int(year), int(month)

    # ── 解析日期列（第二列，從第 8 欄起）────────────────────
    date_row = raw.iloc[1, 7:]
    dates = []
    for val in date_row:
        s = str(val).strip()
        if s in ("nan", "合計"):
            continue
        m_ = re.match(r"(\d+)/(\d+)", s)
        if m_:
            m, d = int(m_.group(1)), int(m_.group(2))
            if m != month:
                continue
            try:
                dates.append(date(year, m, d))
            except ValueError:
                continue

    if not dates:
        return pd.DataFrame()

    rows = []
    cur_region = cur_store = cur_target = cur_rate = None

    for i in range(2, len(raw)):
        row = raw.iloc[i]

        # 逐欄解析區域 / 門店 / 目標 / 達成率（跨列繼承）
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
        if pd.notna(row.iloc[3]) and str(row.iloc[3]).strip():
            r = str(row.iloc[3]).replace("%", "").strip()
            try:
                cur_rate = float(r) / 100
            except ValueError:
                cur_rate = None

        metric = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else ""
        if metric not in ("業績合計", "人數合計", "平均客單"):
            continue
        if not cur_store:
            continue

        # 解析每日數值（每日佔兩欄：本日值 + 累計值，取單數欄位）
        vals = []
        for val in row.iloc[7:]:
            s = str(val).strip().replace(",", "").replace(" ", "")
            if s in ("nan", "", "#DIV/0!", "\\#DIV/0\\!"):
                vals.append(None)
            else:
                try:
                    vals.append(float(s))
                except ValueError:
                    vals.append(None)

        # 每隔一欄取一個日期值
        day_vals = [vals[idx] for idx in range(0, len(vals), 2) if idx // 2 < len(dates)]

        for di, dt in enumerate(dates):
            v = day_vals[di] if di < len(day_vals) else None
            rows.append({
                "日期": dt, "區域": cur_region, "門店": cur_store,
                "本月目標": cur_target, "達成率": cur_rate,
                "指標": metric, "數值": v,
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    pivot = df.pivot_table(
        index=["日期", "區域", "門店", "本月目標", "達成率"],
        columns="指標", values="數值", aggfunc="first",
    ).reset_index()
    pivot.columns.name = None

    ren = {}
    if "業績合計" in pivot.columns: ren["業績合計"] = "營業額"
    if "人數合計" in pivot.columns: ren["人數合計"] = "來客數"
    if "平均客單" in pivot.columns: ren["平均客單"] = "客單價"
    pivot = pivot.rename(columns=ren)

    for col in ("營業額", "來客數", "客單價"):
        if col not in pivot.columns:
            pivot[col] = None
    return pivot


@st.cache_data(ttl=3600)
def load_all_data() -> pd.DataFrame:
    """匯總所有月份資料，加入時間維度欄位"""
    dfs = []
    for ym, gid in SHEET_GIDS.items():
        df = load_sheet(ym, gid)
        if not df.empty:
            dfs.append(df)
    if not dfs:
        return pd.DataFrame()

    data = pd.concat(dfs, ignore_index=True)
    data["日期"] = pd.to_datetime(data["日期"])
    data["年份"] = data["日期"].dt.year
    data["月份"] = data["日期"].dt.month
    data["年月"] = data["日期"].dt.to_period("M").astype(str)
    data["季"] = data["月份"].map(QUARTER_MAP)
    data["年季"] = data["年份"].astype(str) + " " + data["季"]
    data["週次"] = data["日期"].dt.isocalendar().week.astype(int)
    data["年週"] = data["日期"].dt.strftime("%G-W%V")
    data["星期"] = data["日期"].dt.dayofweek
    data["星期名"] = data["星期"].map(WEEKDAY_MAP)
    data["已結村"] = data["門店"].isin(CLOSED_STORES)
    return data


# ── 工具函數 ──────────────────────────────────────────────────
def fmt_num(x) -> str:
    if pd.isna(x) or x == 0:
        return "—"
    return f"{x:,.0f}"


def fmt_pct(x) -> str:
    if pd.isna(x):
        return "—"
    return f"{x:+.1f}%"


def plotly_chart(fig, key=None):
    """統一 Plotly 渲染（禁用縮放，適合手機）"""
    st.plotly_chart(fig, use_container_width=True, config=MOBILE_CHART_CONFIG, key=key)


def get_date_filter(data: pd.DataFrame, key_prefix: str = "", active_stores=None):
    """
    共用篩選器 Widget（日期範圍 / 區域 / 門店）
    修正：先計算 sel_regions 再動態更新門店清單，避免跨頁 session key 衝突。
    """
    with st.expander("🔍 篩選條件", expanded=False):
        min_date = data["日期"].min().date()
        max_date = data["日期"].max().date()

        c1, c2 = st.columns([3, 2])
        with c1:
            date_range = st.date_input(
                "日期範圍", value=(min_date, max_date),
                min_value=min_date, max_value=max_date,
                key=f"{key_prefix}_date",
            )
        with c2:
            regions = sorted(data["區域"].dropna().unique().tolist())
            sel_regions = st.multiselect(
                "區域", regions, default=regions,
                key=f"{key_prefix}_region",
            )

        # 門店清單依區域動態更新
        if active_stores:
            store_pool = active_stores
        else:
            region_mask = data["區域"].isin(sel_regions) if sel_regions else pd.Series([True] * len(data))
            store_pool = sorted(data[region_mask]["門店"].dropna().unique().tolist())

        sel_stores = st.multiselect(
            "門店", store_pool, default=store_pool,
            key=f"{key_prefix}_store",
        )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
    else:
        start_d, end_d = min_date, max_date

    # 避免 sel_regions / sel_stores 為空時過濾掉所有資料
    if not sel_regions:
        sel_regions = data["區域"].dropna().unique().tolist()
    if not sel_stores:
        sel_stores = store_pool

    mask = (
        (data["日期"].dt.date >= start_d) & (data["日期"].dt.date <= end_d)
        & (data["區域"].isin(sel_regions)) & (data["門店"].isin(sel_stores))
    )
    return data[mask].copy(), start_d, end_d, sel_regions, sel_stores


def calc_kpi_card(data: pd.DataFrame, period_label: str,
                  start_d, end_d, compare_start=None, compare_end=None):
    """計算本期金額與同期年增率"""
    period_data = data[(data["日期"].dt.date >= start_d) & (data["日期"].dt.date <= end_d)]
    period_data = period_data[period_data["營業額"].notna() & (period_data["營業額"] > 0)]
    total = period_data["營業額"].sum()

    delta = None
    if compare_start and compare_end:
        cmp = data[(data["日期"].dt.date >= compare_start) & (data["日期"].dt.date <= compare_end)]
        cmp = cmp[cmp["營業額"].notna() & (cmp["營業額"] > 0)]
        cmp_total = cmp["營業額"].sum()
        if cmp_total > 0:
            delta = (total - cmp_total) / cmp_total * 100
    return total, delta


# ── 共用圖表 ──────────────────────────────────────────────────
def make_revenue_bar(daily: pd.DataFrame) -> go.Figure:
    """全店每日營業額長條圖，標記峰值"""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["日期"], y=daily["營業額"],
        name="營業額",
        marker_color="#E8431A",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f} 元<extra></extra>",
    ))
    if not daily.empty:
        peak_idx = daily["營業額"].idxmax()
        peak = daily.loc[peak_idx]
        fig.add_annotation(
            x=peak["日期"], y=peak["營業額"],
            text=f"峰值 {peak['營業額']:,.0f}",
            showarrow=True, arrowhead=2,
            bgcolor="#FFF5F2", bordercolor="#E8431A",
        )
    fig.update_layout(
        title="全店每日營業額",
        height=400, hovermode="x unified",
        xaxis_title="日期", yaxis_title="營業額（元）",
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
    )
    return fig


def make_dual_axis(daily: pd.DataFrame) -> go.Figure:
    """來客數（長條）+ 客單價（折線）雙軸圖"""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["日期"], y=daily["來客數"],
        name="來客數", marker_color="#FF6B35",
        hovertemplate="%{x|%Y-%m-%d}<br>來客數：%{y:,.0f} 人<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=daily["日期"], y=daily["客單價"],
        name="客單價", mode="lines+markers",
        line=dict(color="#C73A18", width=2), yaxis="y2",
        hovertemplate="客單價：%{y:,.0f} 元<extra></extra>",
    ))
    fig.update_layout(
        title="來客數 與 客單價",
        height=400, hovermode="x unified",
        xaxis_title="日期",
        yaxis=dict(title="來客數（人）"),
        yaxis2=dict(title="客單價（元）", side="right", overlaying="y"),
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
    )
    return fig
