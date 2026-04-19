import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import warnings
import re
import calendar
import io
import os
import requests

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 數據戰情中心",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 門禁驗證
# ============================================================
if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("app.py", label="← 返回數位總部大門", use_container_width=False)
    st.stop()

if "數據戰情中心" not in st.session_state.get("enabled_pages", set()):
    st.error("🔒 本功能尚未開放，請由管理員在總部門禁頁勾選啟用「數據戰情中心」")
    st.page_link("app.py", label="← 返回總部", use_container_width=False)
    st.stop()

# ============================================================
# 基本設定
# ============================================================
SHEET_ID = "1NZQEJgL-HkB08JSW6zsVHRSyl_XgwLc5etUqSF0O9ow"

SHEET_GIDS = {
    "2025-01": "672482866", "2025-02": "1943981506", "2025-03": "847955849",
    "2025-04": "591730250", "2025-05": "695013616", "2025-06": "897256004",
    "2025-07": "593028448", "2025-08": "836455215", "2025-09": "1728608975",
    "2025-10": "2043079442", "2025-11": "1307429413", "2025-12": "1838876978",
    "2026-01": "872131612", "2026-02": "162899314", "2026-03": "1575135129",
    "2026-04": "1702412906", "2026-05": "1499115222", "2026-06": "467088033",
}

WEEKDAY_MAP = {0: "週一", 1: "週二", 2: "週三", 3: "週四", 4: "週五", 5: "週六", 6: "週日"}
QUARTER_MAP = {1: "Q1", 2: "Q1", 3: "Q1", 4: "Q2", 5: "Q2", 6: "Q2",
               7: "Q3", 8: "Q3", 9: "Q3", 10: "Q4", 11: "Q4", 12: "Q4"}

CLOSED_STORES = {"北屯軍福店", "犝犝楠梓店", "高雄大順店", "高雄自由店", "高雄鼎強店", "鳳山文中店"}

PAGE_LIST = [
    "📊 總覽", "🏪 門店排行", "💪 綜合戰力分析", "🔄 店對店比較",
    "📅 週循環分析", "📅 月循環比較", "📅 季循環分析", "📅 年循環比較",
    "🏙️ 商圈分析", "🎯 達標追蹤", "🔍 單店下鑽", "⚠️ 異常警示", "🤖 AI 數據分析",
]

MOBILE_CHART_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "displaylogo": False,
    "staticPlot": False,
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d", "zoomIn2d", "zoomOut2d",
        "autoScale2d", "resetScale2d", "hoverClosestCartesian",
        "hoverCompareCartesian", "toggleSpikelines", "toImage",
    ],
}

# ============================================================
# 圖 B 風格 CSS（扁平化・橘紅白配色・全中文）
# ============================================================
st.markdown("""
<style>
    .main .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}

    /* KPI 卡片 — 扁平白底 */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        padding: 14px;
        border-radius: 10px;
        border: 1.5px solid #F0E8E5;
        box-shadow: 0 1px 4px rgba(230,59,31,0.07);
    }
    [data-testid="stMetricLabel"] {font-size: 0.85rem; color: #888;}
    [data-testid="stMetricValue"] {font-size: 1.5rem; font-weight: 700; color: #1A1A1A;}
    [data-testid="stMetricDelta"] {font-size: 0.78rem;}

    /* 側邊欄 */
    [data-testid="stSidebar"] {background: #FAFAFA;}
    [data-testid="stSidebar"] button {width: 100%; font-size: 0.85rem;}

    /* Plotly 手機鎖定 */
    .js-plotly-plot, .plotly, .plot-container {
        touch-action: pan-y !important;
        -ms-touch-action: pan-y !important;
    }
    .js-plotly-plot .dragcover {display: none !important;}

    /* 手機優化 */
    @media (max-width: 768px) {
        .main .block-container {padding: 0.8rem;}
        [data-testid="stMetricValue"] {font-size: 1.1rem;}
        [data-testid="stMetric"] {padding: 10px;}
        .js-plotly-plot {touch-action: pan-y !important;}
    }

    /* 區塊標題 — SVG 圖示 + 底線 */
    .section-header {
        display: flex; align-items: center; gap: 8px;
        font-size: 1.0rem; font-weight: 800; color: #1A1A1A;
        padding: 0.4rem 0; margin: 1.2rem 0 0.6rem;
        border-bottom: 2px solid #F0F0F0;
    }
    .section-header svg { flex-shrink: 0; }

    /* AI 觀察小方塊 */
    .ai-box {
        background: #FFF3EE;
        border-left: 4px solid #E63B1F;
        padding: 10px 14px;
        border-radius: 8px;
        margin: 0.5rem 0;
        font-size: 0.85rem;
    }

    /* 概況區 */
    .overview-item {font-size: 0.75rem; padding: 2px 0;}

    /* 隱藏 Streamlit 預設頁面導覽（portal 統一管理） */
    [data-testid="stSidebarNav"] {display: none !important;}
</style>
""", unsafe_allow_html=True)


# ── UI helpers — module 層級 import（供各頁面函式直接呼叫）──────
from utils.ui_helpers import render_section_header, inject_global_css, render_marquee

# ============================================================
# 資料讀取
# ============================================================
@st.cache_data(ttl=3600)
def load_sheet(year_month, gid):
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
        if s == "nan" or s == "合計":
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
        if metric not in ["業績合計", "人數合計", "平均客單"]:
            continue
        if not cur_store:
            continue

        vals = []
        for val in row.iloc[7:]:
            s = str(val).strip().replace(",", "").replace(" ", "")
            if s in ["nan", "", "#DIV/0!", "\\#DIV/0\\!", "#DIV/0!"]:
                vals.append(None)
            else:
                try:
                    vals.append(float(s))
                except ValueError:
                    vals.append(None)

        day_vals = []
        for idx in range(0, len(vals), 2):
            if idx // 2 < len(dates):
                day_vals.append(vals[idx])

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
        index=["日期", "區域", "門店"],
        columns="指標", values="數值", aggfunc="first",
        dropna=False,
    ).reset_index()
    pivot.columns.name = None

    meta = df[["門店", "本月目標", "達成率"]].drop_duplicates("門店").set_index("門店")
    pivot["本月目標"] = pivot["門店"].map(meta["本月目標"].to_dict())
    pivot["達成率"] = pivot["門店"].map(meta["達成率"].to_dict())

    ren = {}
    if "業績合計" in pivot.columns: ren["業績合計"] = "營業額"
    if "人數合計" in pivot.columns: ren["人數合計"] = "來客數"
    if "平均客單" in pivot.columns: ren["平均客單"] = "客單價"
    pivot = pivot.rename(columns=ren)

    for col in ["營業額", "來客數", "客單價"]:
        if col not in pivot.columns:
            pivot[col] = None
    return pivot


@st.cache_data(ttl=3600)
def load_all_data():
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


# ============================================================
# 工具函數
# ============================================================
def fmt_num(x):
    if pd.isna(x) or x == 0:
        return "—"
    return f"{x:,.0f}"


def plotly_chart(fig, key=None, height=None):
    if height:
        fig.update_layout(height=height)
    fig.update_layout(
        dragmode=False,
        hoverlabel=dict(bgcolor="rgba(30,30,30,0.88)", bordercolor="#E63B1F",
                        font=dict(size=12, color="white")),
    )
    st.plotly_chart(fig, use_container_width=True, config=MOBILE_CHART_CONFIG, key=key)


def get_filter_expander(data, key_prefix, include_closed=False):
    with st.expander("🔍 篩選條件", expanded=False):
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        min_date = data["日期"].min().date()
        max_date = data["日期"].max().date()

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
        with c3:
            show_closed = st.checkbox("含已結村店", value=include_closed, key=f"{key_prefix}_closed")
        with c4:
            pool = data[data["區域"].isin(sel_regions)]
            if not show_closed:
                pool = pool[~pool["門店"].isin(CLOSED_STORES)]
            stores = sorted(pool["門店"].dropna().unique().tolist())
            sel_stores = st.multiselect(
                "門店", stores, default=stores,
                key=f"{key_prefix}_store",
            )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
    else:
        start_d, end_d = min_date, max_date

    mask = (
        (data["日期"].dt.date >= start_d) & (data["日期"].dt.date <= end_d)
        & (data["區域"].isin(sel_regions)) & (data["門店"].isin(sel_stores))
    )
    return data[mask].copy(), start_d, end_d, sel_regions, sel_stores, show_closed


def add_median_line(fig, values, label="中位數"):
    if len(values) > 0:
        med = pd.Series(values).median()
        fig.add_hline(y=med, line_dash="dot", line_color="#E63B1F",
                      annotation_text=f"{label} {med:,.0f}",
                      annotation_position="top left")
    return fig


def kpi_card_row(valid, label_prefix=""):
    total = valid["營業額"].sum()
    mean = valid.groupby("日期")["營業額"].sum().mean() if len(valid) else 0
    median = valid.groupby("日期")["營業額"].sum().median() if len(valid) else 0
    return total, mean, median


# ============================================================
# 規則引擎 AI 分析
# ============================================================
def rule_based_ai_analysis(data):
    insights = {"異常": [], "機會": [], "規範": []}

    if data.empty:
        return insights

    valid = data[data["營業額"].notna() & (data["營業額"] > 0) & (~data["門店"].isin(CLOSED_STORES))]
    if valid.empty:
        return insights

    latest = valid["日期"].max().date()
    last_7 = valid[valid["日期"].dt.date > (latest - timedelta(days=7))]
    prev_7 = valid[(valid["日期"].dt.date <= (latest - timedelta(days=7))) & (valid["日期"].dt.date > (latest - timedelta(days=14)))]

    if "本月目標" in valid.columns:
        cur = valid[(valid["日期"].dt.year == latest.year) & (valid["日期"].dt.month == latest.month)]
        if not cur.empty:
            days_in_mo = calendar.monthrange(latest.year, latest.month)[1]
            for store in cur["門店"].unique():
                sd = cur[cur["門店"] == store].sort_values("日期")
                if sd.empty: continue
                target = sd["本月目標"].iloc[0]
                if pd.isna(target) or target <= 0: continue
                daily_target = target / days_in_mo
                last_3 = sd.tail(3)
                if len(last_3) >= 3 and (last_3["營業額"] < daily_target).all():
                    insights["異常"].append(f"🔴 **{store}** 連續 3 天未達日均目標（{daily_target:,.0f} 元）")

    for store in valid["門店"].unique()[:30]:
        sd = valid[valid["門店"] == store].sort_values("日期").tail(7)
        if len(sd) < 2: continue
        for i in range(1, len(sd)):
            curr, prev = sd.iloc[i]["營業額"], sd.iloc[i-1]["營業額"]
            if prev > 0 and curr < prev * 0.7:
                dt = sd.iloc[i]["日期"].strftime("%m/%d")
                pct = (1 - curr/prev) * 100
                insights["異常"].append(f"🔴 **{store}** {dt} 營收暴跌 {pct:.0f}%")
                break

    if not last_7.empty:
        store_stats = last_7.groupby("門店").agg({
            "營業額": "sum", "來客數": "sum", "客單價": "mean"
        }).reset_index()
        store_stats["日均營收"] = store_stats["營業額"] / 7

        avg_ticket = store_stats["客單價"].median()
        avg_cust = store_stats["來客數"].median()

        for _, r in store_stats.iterrows():
            if r["客單價"] > avg_ticket * 1.15 and r["來客數"] < avg_cust * 0.85:
                insights["機會"].append(f"💡 **{r['門店']}** 客單價高（{r['客單價']:,.0f}）但來客偏低，可推動「分享優惠」提升客流")
            elif r["客單價"] < avg_ticket * 0.85 and r["來客數"] > avg_cust * 1.15:
                insights["機會"].append(f"💡 **{r['門店']}** 來客多但客單偏低，可試推升級套餐或加點策略")

    if not last_7.empty and not prev_7.empty:
        l7 = last_7["營業額"].sum()
        p7 = prev_7["營業額"].sum()
        if p7 > 0:
            delta = (l7 - p7) / p7 * 100
            if delta > 5:
                insights["規範"].append(f"📈 最近 7 天整體營收較前週 **成長 {delta:.1f}%**，可持續觀察增長驅動力")
            elif delta < -5:
                insights["規範"].append(f"📉 最近 7 天整體營收較前週 **下降 {abs(delta):.1f}%**，建議召開區域檢討會議")

        weekend_rev = last_7[last_7["星期"].isin([5, 6])]["營業額"].sum()
        weekday_rev = last_7[~last_7["星期"].isin([5, 6])]["營業額"].sum()
        if weekend_rev > 0 and weekday_rev > 0:
            ratio = weekend_rev / 2 / (weekday_rev / 5)
            if ratio > 1.5:
                insights["規範"].append(f"📅 週末日均營收是平日的 **{ratio:.1f} 倍**，可優化平日促銷方案")

    for k in insights:
        insights[k] = insights[k][:5]
    return insights


# ============================================================
# Feature 2 — Claude AI 分析輔助函數
# ============================================================
def _build_data_summary(data) -> str:
    """將 DataFrame 轉為文字摘要，供 Claude API 分析使用。"""
    valid = data[
        data["營業額"].notna() & (data["營業額"] > 0)
        & (~data["門店"].isin(CLOSED_STORES))
    ]
    if valid.empty:
        return "無資料"

    latest = valid["日期"].max().date()
    yr, mn = latest.year, latest.month

    lines: list = [
        f"資料截至 {latest.strftime('%Y-%m-%d')}，共 {valid['門店'].nunique()} 家門店",
    ]

    # ── 本月各店表現 ──
    cur = valid[(valid["日期"].dt.year == yr) & (valid["日期"].dt.month == mn)]
    if not cur.empty:
        total_rev = cur["營業額"].sum()
        lines.append(f"本月累計營收：{total_rev:,.0f} 元")
        store_sum = cur.groupby("門店").agg(
            營業額=("營業額", "sum"),
            來客數=("來客數", "sum"),
            客單價=("客單價", "mean"),
            本月目標=("本月目標", "first"),
        ).reset_index()
        store_sum["達成率"] = (
            store_sum["營業額"] / store_sum["本月目標"].replace(0, float("nan"))
        ) * 100
        lines.append("\n本月各門店表現：")
        for _, r in store_sum.iterrows():
            ach = f"{r['達成率']:.1f}%" if pd.notna(r.get("達成率")) else "N/A"
            lines.append(
                f"  - {r['門店']}：營收 {r['營業額']:,.0f}元"
                f"，來客 {r['來客數']:.0f}人"
                f"，客單 {r['客單價']:.0f}元，達成率 {ach}"
            )

    # ── 近7天 vs 前7天 ──
    last_7 = valid[valid["日期"].dt.date > (latest - timedelta(days=7))]
    prev_7 = valid[
        (valid["日期"].dt.date <= (latest - timedelta(days=7)))
        & (valid["日期"].dt.date > (latest - timedelta(days=14)))
    ]
    if not last_7.empty:
        l7 = last_7["營業額"].sum()
        p7 = prev_7["營業額"].sum() if not prev_7.empty else 0
        delta = ((l7 - p7) / p7 * 100) if p7 > 0 else 0
        lines.append(
            f"\n近7天合計：{l7:,.0f}元（vs前7天 {delta:+.1f}%）"
        )
        we = last_7[last_7["星期"].isin([5, 6])]["營業額"].sum()
        wd = last_7[~last_7["星期"].isin([5, 6])]["營業額"].sum()
        if we > 0 and wd > 0:
            ratio = (we / 2) / (wd / 5) if wd > 0 else 0
            lines.append(f"週末日均 / 平日日均 = {ratio:.2f}")

    return "\n".join(lines)


@st.cache_data(ttl=1800, show_spinner=False)
def _claude_analysis_cached(data_summary: str, api_key: str) -> dict | None:
    """呼叫 Claude API 分析（快取 30 分鐘）。回傳 dict 或 None（失敗時）。"""
    try:
        import anthropic
        import json

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "你是嗑肉石鍋的數據分析師。以下是近期門店營收摘要：\n\n"
            f"{data_summary}\n\n"
            "請用繁體中文分析，以嚴格 JSON 格式輸出（只輸出 JSON，不要其他文字）：\n"
            "{\n"
            '  "異常": ["項目1（限50字）", "項目2"],\n'
            '  "機會": ["項目1（限50字）", "項目2"],\n'
            '  "規範": ["項目1（限50字）", "項目2"],\n'
            '  "總結": "整體評估（100字內）"\n'
            "}\n"
            "異常：連續下滑、缺失數據、異常偏低門店\n"
            "機會：高客單低來客 or 低客單高來客，給具體建議\n"
            "規範：整體趨勢、週末平日效應、成長方向\n"
            "每類最多5條，每條限50字。"
        )
        resp = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        start, end = text.find("{"), text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return None
    except Exception as exc:
        return {"error": str(exc)}


# ============================================================
# Feature 3 — 異常警示通知列資料生成
# ============================================================
def _generate_alert_items(data) -> list:
    """根據資料產生即時警示清單，供跑馬燈使用。"""
    items: list = []
    valid = data[
        data["營業額"].notna() & (data["營業額"] > 0)
        & (~data["門店"].isin(CLOSED_STORES))
    ]
    if valid.empty:
        return ["✅ 目前無異常警示"]

    latest = valid["日期"].max().date()
    all_stores = set(valid["門店"].unique())

    # 1. 今日缺資料
    today_stores = set(valid[valid["日期"].dt.date == latest]["門店"].unique())
    missing_today = all_stores - today_stores
    if missing_today:
        items.append(
            f"⚠️ {latest.strftime('%m/%d')} 缺少數據門店：{', '.join(sorted(missing_today))}"
        )

    # 2. 本週缺資料（以最新日期往回推至本週一）
    dow = latest.weekday()          # 0=Mon
    week_start = latest - timedelta(days=dow)
    week_stores = set(valid[valid["日期"].dt.date >= week_start]["門店"].unique())
    missing_week = all_stores - week_stores
    if missing_week:
        items.append(
            f"📋 本週數據尚缺門店：{', '.join(sorted(missing_week))}"
        )

    # 3. 今日異常偏高／偏低（±2σ）
    store_stats = (
        valid.groupby("門店")["營業額"]
        .agg(["mean", "std"])
        .reset_index()
        .rename(columns={"mean": "均值", "std": "標準差"})
    )
    latest_day = valid[valid["日期"].dt.date == latest]
    for _, r in latest_day.iterrows():
        store = r["門店"]
        rev = r["營業額"]
        stat = store_stats[store_stats["門店"] == store]
        if stat.empty:
            continue
        mu, sigma = stat.iloc[0]["均值"], stat.iloc[0]["標準差"]
        if sigma > 0:
            if rev > mu + 2 * sigma:
                items.append(
                    f"🚀 {store} 今日 {rev:,.0f}元 — 異常偏高（超均值+2σ）"
                )
            elif rev < mu - 2 * sigma:
                items.append(
                    f"🔴 {store} 今日 {rev:,.0f}元 — 異常偏低（低於均值-2σ）"
                )

    # 4. 連續 3 天未達日均目標
    yr, mn = latest.year, latest.month
    cur = valid[(valid["日期"].dt.year == yr) & (valid["日期"].dt.month == mn)]
    if not cur.empty and "本月目標" in cur.columns:
        days_in_mo = calendar.monthrange(yr, mn)[1]
        for store in cur["門店"].unique():
            sd = cur[cur["門店"] == store].sort_values("日期")
            tgt = sd["本月目標"].iloc[0] if not sd.empty else None
            if pd.isna(tgt) or tgt <= 0:
                continue
            daily_tgt = tgt / days_in_mo
            last3 = sd.tail(3)
            if len(last3) >= 3 and (last3["營業額"] < daily_tgt).all():
                items.append(
                    f"🔴 {store} 連續3天未達日均目標（目標 {daily_tgt:,.0f}元）"
                )

    if not items:
        items = ["✅ 所有門店數據正常，無異常警示"]
    return items


# ============================================================
# 側邊欄概況
# ============================================================
def sidebar_overview(data):
    valid = data[data["營業額"].notna() & (data["營業額"] > 0) & (~data["門店"].isin(CLOSED_STORES))]
    latest = valid["日期"].max()
    latest_month = valid[valid["年月"] == valid["年月"].max()]

    if latest_month.empty:
        return

    st.sidebar.markdown("### 📊 本月概況")
    st.sidebar.caption(f"{latest.strftime('%Y-%m')}")

    dim = st.sidebar.selectbox("維度", ["營收", "達成率", "來客數", "客單價"], key="ov_dim")

    store_sum = latest_month.groupby("門店").agg({
        "營業額": "sum", "來客數": "sum",
        "客單價": "mean", "本月目標": "first",
    }).reset_index()
    store_sum["達成率"] = store_sum["營業額"] / store_sum["本月目標"]

    if dim == "營收":
        col, unit = "營業額", "元"
    elif dim == "達成率":
        col, unit = "達成率", "%"
    elif dim == "來客數":
        col, unit = "來客數", "人"
    else:
        col, unit = "客單價", "元"

    valid_stats = store_sum[store_sum[col].notna()].sort_values(col, ascending=False)

    st.sidebar.markdown(f"**🏆 {dim} TOP5**")
    for i, r in valid_stats.head(5).iterrows():
        v = r[col]
        txt = f"{v*100:.1f}%" if col == "達成率" else f"{v:,.0f} {unit}"
        st.sidebar.markdown(f"<div class='overview-item'>• {r['門店']}: <b>{txt}</b></div>", unsafe_allow_html=True)

    st.sidebar.markdown(f"**⚠️ {dim} BOTTOM5**")
    for i, r in valid_stats.tail(5).iterrows():
        v = r[col]
        txt = f"{v*100:.1f}%" if col == "達成率" else f"{v:,.0f} {unit}"
        st.sidebar.markdown(f"<div class='overview-item'>• {r['門店']}: <b>{txt}</b></div>", unsafe_allow_html=True)


# ============================================================
# 分頁函數
# ============================================================
def page_overview(data):
    st.header("📊 總覽")
    filtered, _, _, _, _, _ = get_filter_expander(data, "ov")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]
    if valid.empty:
        st.warning("篩選後無資料"); return

    today = valid["日期"].max().date()
    yr, mn = today.year, today.month

    render_section_header("chart-bar", "四大累計分析（含中位數）")

    def calc_period(start, end):
        d = data[(data["日期"].dt.date >= start) & (data["日期"].dt.date <= end)]
        d = d[d["營業額"].notna() & (d["營業額"] > 0) & (~d["門店"].isin(CLOSED_STORES))]
        total = d["營業額"].sum()
        daily = d.groupby("日期")["營業額"].sum()
        mean = daily.mean() if len(daily) else 0
        median = daily.median() if len(daily) else 0
        store_med = d.groupby("門店")["營業額"].sum().median() if len(d) else 0
        return total, mean, median, store_med

    yoy_t, yoy_m, yoy_med, yoy_sm = calc_period(data["日期"].min().date(), today)

    y_start = date(yr, 1, 1)
    y_ly_start = date(yr - 1, 1, 1)
    try:
        y_ly_end = date(yr - 1, today.month, today.day)
    except ValueError:
        y_ly_end = date(yr - 1, today.month, calendar.monthrange(yr-1, today.month)[1])
    y_t, y_m, y_med, y_sm = calc_period(y_start, today)
    y_ly_t, _, _, _ = calc_period(y_ly_start, y_ly_end)
    y_delta = ((y_t - y_ly_t) / y_ly_t * 100) if y_ly_t > 0 else None

    q_start_m = ((mn - 1) // 3) * 3 + 1
    q_start = date(yr, q_start_m, 1)
    q_t, q_m, q_med, q_sm = calc_period(q_start, today)
    try:
        q_ly_start = date(yr - 1, q_start_m, 1)
        q_ly_end = date(yr - 1, mn, min(today.day, calendar.monthrange(yr-1, mn)[1]))
        q_ly_t, _, _, _ = calc_period(q_ly_start, q_ly_end)
        q_delta = ((q_t - q_ly_t) / q_ly_t * 100) if q_ly_t > 0 else None
    except ValueError:
        q_delta = None

    m_start = date(yr, mn, 1)
    m_t, m_m, m_med, m_sm = calc_period(m_start, today)
    cur_month_tgt = data[(data["日期"].dt.year == yr) & (data["日期"].dt.month == mn)].groupby("門店")["本月目標"].first().sum()
    m_rate = (m_t / cur_month_tgt * 100) if cur_month_tgt > 0 else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📚 曆年累計", f"{yoy_t:,.0f} 元", delta=f"日均 {yoy_m:,.0f} / 中位 {yoy_med:,.0f}")
    c2.metric("🗓️ 今年累計", f"{y_t:,.0f} 元",
              delta=f"{y_delta:+.1f}% vs 去年" if y_delta else f"中位 {y_med:,.0f}")
    c3.metric("🎯 本季累計", f"{q_t:,.0f} 元",
              delta=f"{q_delta:+.1f}% vs 去年" if q_delta else f"中位 {q_med:,.0f}")
    c4.metric("📅 本月累計", f"{m_t:,.0f} 元",
              delta=f"達成 {m_rate:.1f}%" if m_rate else f"中位 {m_med:,.0f}")

    st.caption(f"✨ 日均 = 全店當日合計的平均｜中位 = 全店當日合計的中位數｜門店中位（曆年）= {yoy_sm:,.0f} 元")
    st.divider()

    render_section_header("chart-line", "每日營收趨勢")
    daily = valid.groupby("日期").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    daily["客單價"] = (daily["營業額"] / daily["來客數"]).round(0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["日期"], y=daily["營業額"], name="營業額",
        marker_color="#E63B1F",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f} 元<extra></extra>",
    ))
    if not daily.empty:
        peak = daily.loc[daily["營業額"].idxmax()]
        fig.add_annotation(x=peak["日期"], y=peak["營業額"],
                           text=f"峰值 {peak['營業額']:,.0f}",
                           showarrow=True, arrowhead=2, bgcolor="#FFF3EE")
    add_median_line(fig, daily["營業額"].values)
    fig.update_layout(title="全店每日營業額", height=400, hovermode="x unified",
                      xaxis_title="日期", yaxis_title="營業額（元）")
    plotly_chart(fig, key="ov_bar")

    # ── Feature 4：來客數 / 客單價 勾選顯示 ─────────────────────────
    ck1, ck2 = st.columns(2)
    with ck1:
        show_guests = st.checkbox("📊 顯示來客數", value=True, key="ov_show_guests")
    with ck2:
        show_ticket = st.checkbox("💴 顯示客單價", value=True, key="ov_show_ticket")

    if show_guests or show_ticket:
        dual_axis = show_guests and show_ticket
        fig2 = go.Figure()
        if show_guests:
            fig2.add_trace(go.Bar(
                x=daily["日期"], y=daily["來客數"], name="來客數",
                marker_color="#FF7043",
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f} 人<extra></extra>",
            ))
        if show_ticket:
            fig2.add_trace(go.Scatter(
                x=daily["日期"], y=daily["客單價"], name="客單價",
                mode="lines+markers", line=dict(color="#2C3E50", width=2),
                yaxis="y2" if dual_axis else "y",
                hovertemplate="客單：%{y:,.0f} 元<extra></extra>",
            ))
        layout_kw: dict = dict(
            title="來客數 與 客單價", height=400,
            hovermode="x unified", xaxis_title="日期",
        )
        if dual_axis:
            layout_kw["yaxis"]  = dict(title="來客數（人）", side="left")
            layout_kw["yaxis2"] = dict(title="客單價（元）", side="right", overlaying="y")
        elif show_guests:
            layout_kw["yaxis"] = dict(title="來客數（人）")
        else:
            layout_kw["yaxis"] = dict(title="客單價（元）")
        fig2.update_layout(**layout_kw)
        plotly_chart(fig2, key="ov_dual")
    else:
        st.info("💡 請至少勾選「來客數」或「客單價」以顯示圖表")

    render_section_header("chart-bar", "中位數 vs 平均數 分佈")
    col_a, col_b = st.columns(2)

    with col_a:
        store_daily = valid.groupby("門店")["營業額"].agg(["sum", "mean", "median"]).reset_index()
        fig_box = go.Figure()
        fig_box.add_trace(go.Bar(x=store_daily["門店"], y=store_daily["mean"], name="平均",
                                  marker_color="#E63B1F",
                                  hovertemplate="%{x}<br>平均 %{y:,.0f}<extra></extra>"))
        fig_box.add_trace(go.Bar(x=store_daily["門店"], y=store_daily["median"], name="中位數",
                                  marker_color="#FF7043",
                                  hovertemplate="%{x}<br>中位 %{y:,.0f}<extra></extra>"))
        fig_box.update_layout(title="各門店：平均 vs 中位數", height=400,
                              xaxis_tickangle=-45, barmode="group")
        plotly_chart(fig_box, key="ov_box")

    with col_b:
        sb_data = valid.groupby(["區域", "門店"])["營業額"].sum().reset_index()
        fig_sb = px.sunburst(sb_data, path=["區域", "門店"], values="營業額",
                             color="營業額", color_continuous_scale="Oranges",
                             title="區域 → 門店 營收佔比")
        fig_sb.update_layout(height=400)
        plotly_chart(fig_sb, key="ov_sb")


def page_store_rank(data):
    st.header("🏪 門店排行")
    filtered, _, _, _, _, _ = get_filter_expander(data, "rk")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]
    if valid.empty:
        st.warning("篩選後無資料"); return

    store_sum = valid.groupby(["區域", "門店"]).agg({
        "營業額": "sum", "來客數": "sum", "本月目標": "first", "達成率": "first",
    }).reset_index()
    store_sum["客單價"] = (store_sum["營業額"] / store_sum["來客數"]).round(0)
    store_sum = store_sum.sort_values("營業額", ascending=False)

    med = store_sum["營業額"].median()
    mean = store_sum["營業額"].mean()
    c1, c2, c3 = st.columns(3)
    c1.metric("全店合計", f"{store_sum['營業額'].sum():,.0f} 元")
    c2.metric("平均營業額", f"{mean:,.0f} 元")
    c3.metric("中位數", f"{med:,.0f} 元")

    fig = px.bar(store_sum, x="門店", y="營業額", color="區域",
                 title="各門店營業額排行", height=450,
                 color_discrete_sequence=px.colors.qualitative.Set2)
    fig.update_layout(xaxis_tickangle=-45)
    fig.update_traces(hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>")
    add_median_line(fig, store_sum["營業額"].values)
    plotly_chart(fig, key="rk_bar")

    if store_sum["達成率"].notna().any():
        st.subheader("🎯 前六店達成率儀表板")
        top6 = store_sum[store_sum["達成率"].notna()].head(6)
        cols = st.columns(3)
        for i, (_, r) in enumerate(top6.iterrows()):
            with cols[i % 3]:
                fig_g = go.Figure(go.Indicator(
                    mode="gauge+number", value=r["達成率"] * 100,
                    title={"text": r["門店"]}, number={"suffix": "%"},
                    gauge={"axis": {"range": [0, 130]}, "bar": {"color": "#E63B1F"},
                           "steps": [{"range": [0, 50], "color": "#FFD6D6"},
                                     {"range": [50, 80], "color": "#FFF3EE"},
                                     {"range": [80, 130], "color": "#D4EDDA"}],
                           "threshold": {"line": {"color": "red", "width": 4},
                                         "thickness": 0.75, "value": 100}}))
                fig_g.update_layout(height=180, margin=dict(t=30, b=10, l=10, r=10))
                plotly_chart(fig_g, key=f"gg_{i}")

    st.subheader("📋 明細表")
    disp = store_sum[["區域", "門店", "營業額", "來客數", "客單價", "達成率"]].copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["達成率"] = disp["達成率"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_combat(data):
    st.header("💪 門市綜合戰力分析")
    filtered, _, _, _, _, _ = get_filter_expander(data, "cb")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]
    if valid.empty:
        st.warning("篩選後無資料"); return

    sd = valid.groupby(["區域", "門店"]).agg({
        "營業額": "sum", "來客數": "sum",
        "客單價": "mean", "達成率": "first",
    }).reset_index()
    sd["日數"] = valid.groupby("門店")["日期"].nunique().values
    sd["日均營收"] = sd["營業額"] / sd["日數"]

    daily_by_store = valid.groupby(["門店", "日期"])["營業額"].sum().reset_index()
    stab = daily_by_store.groupby("門店")["營業額"].agg(lambda x: 1 - (x.std() / x.mean()) if x.mean() > 0 else 0).to_dict()
    sd["穩定度"] = sd["門店"].map(stab).fillna(0)

    def norm(s):
        if s.max() == s.min():
            return pd.Series([50] * len(s), index=s.index)
        return (s - s.min()) / (s.max() - s.min()) * 100

    sd["營收分"] = norm(sd["營業額"])
    sd["達標分"] = norm(sd["達成率"].fillna(0))
    sd["客單分"] = norm(sd["客單價"])
    sd["來客分"] = norm(sd["來客數"])
    sd["穩定分"] = norm(sd["穩定度"])

    sd["綜合戰力"] = (
        sd["營收分"] * 0.30 + sd["達標分"] * 0.25 +
        sd["客單分"] * 0.20 + sd["來客分"] * 0.15 + sd["穩定分"] * 0.10
    ).round(1)

    def grade(score):
        if score >= 85: return "🟢 S 級"
        if score >= 70: return "🔵 A 級"
        if score >= 50: return "🟡 B 級"
        return "🔴 C 級"
    sd["分級"] = sd["綜合戰力"].apply(grade)
    sd = sd.sort_values("綜合戰力", ascending=False)

    render_section_header("star", "綜合戰力排行榜")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 S 級店", f"{len(sd[sd['分級'].str.contains('S')])} 店")
    c2.metric("🔵 A 級店", f"{len(sd[sd['分級'].str.contains('A')])} 店")
    c3.metric("🟡 B 級店", f"{len(sd[sd['分級'].str.contains('B')])} 店")
    c4.metric("🔴 C 級店", f"{len(sd[sd['分級'].str.contains('C')])} 店")

    colors_map = {"🟢 S 級": "#27AE60", "🔵 A 級": "#2980B9",
                  "🟡 B 級": "#F39C12", "🔴 C 級": "#E74C3C"}
    colors = [colors_map[g] for g in sd["分級"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sd["門店"], y=sd["綜合戰力"], marker_color=colors,
        text=[f"{s:.1f}" for s in sd["綜合戰力"]],
        textposition="outside",
        hovertemplate="%{x}<br>綜合分 %{y:.1f}<br>分級：%{customdata}<extra></extra>",
        customdata=sd["分級"],
    ))
    add_median_line(fig, sd["綜合戰力"].values, "中位")
    fig.update_layout(title="各門店綜合戰力評分（0-100）",
                      height=450, xaxis_tickangle=-45,
                      yaxis_title="綜合戰力分")
    plotly_chart(fig, key="cb_bar")

    render_section_header("adjustments", "三維戰力矩陣（營收 × 達標 × 規模）")
    fig_sc = px.scatter(
        sd, x="達成率", y="日均營收", size="來客數", color="分級",
        color_discrete_map=colors_map, hover_name="門店",
        size_max=40, title="X: 達成率 ／ Y: 日均營收 ／ 點大小: 來客數",
    )
    fig_sc.update_layout(height=500, xaxis_tickformat=".0%")
    fig_sc.update_traces(hovertemplate="<b>%{hovertext}</b><br>達成率：%{x:.1%}<br>日均：%{y:,.0f} 元<br>來客：%{marker.size}<extra></extra>")
    plotly_chart(fig_sc, key="cb_sc")

    render_section_header("chart-radar", "TOP5 綜合戰力雷達")
    top5 = sd.head(5)
    cats = ["營收分", "達標分", "客單分", "來客分", "穩定分"]
    fig_r = go.Figure()
    palette = ["#E63B1F", "#FF7043", "#2C3E50", "#FF9800", "#27AE60"]
    for i, (_, r) in enumerate(top5.iterrows()):
        vals = [r[c] for c in cats] + [r[cats[0]]]
        fig_r.add_trace(go.Scatterpolar(
            r=vals, theta=cats + [cats[0]],
            fill="toself", name=r["門店"],
            line=dict(color=palette[i % 5]),
        ))
    fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                        height=500)
    plotly_chart(fig_r, key="cb_radar")

    render_section_header("clipboard-list", "戰力明細")
    disp = sd[["分級", "區域", "門店", "綜合戰力", "營收分", "達標分", "客單分", "來客分", "穩定分"]].copy()
    for c in ["綜合戰力", "營收分", "達標分", "客單分", "來客分", "穩定分"]:
        disp[c] = disp[c].apply(lambda x: f"{x:.1f}")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_compare(data):
    st.header("🔄 店對店比較")
    filtered, _, _, _, sel_stores, _ = get_filter_expander(data, "cmp")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]
    if valid.empty:
        st.warning("篩選後無資料"); return

    compare_stores = st.multiselect(
        "選 2-4 間比較", sel_stores, default=sel_stores[:min(2, len(sel_stores))],
        max_selections=4, key="cmp_sel")
    if len(compare_stores) < 2:
        st.info("至少選 2 間"); return

    comp = valid[valid["門店"].isin(compare_stores)]
    pivot = comp.pivot_table(index="日期", columns="門店", values="營業額", aggfunc="sum").reset_index()
    fig = go.Figure()
    colors = ["#E63B1F", "#2C3E50", "#FF7043", "#FF9800"]
    for i, s in enumerate(compare_stores):
        if s in pivot.columns:
            fig.add_trace(go.Scatter(x=pivot["日期"], y=pivot[s], mode="lines+markers",
                                      name=s, line=dict(color=colors[i % 4], width=2),
                                      hovertemplate=f"{s}<br>%{{x|%m/%d}}<br>%{{y:,.0f}} 元<extra></extra>"))
    add_median_line(fig, pivot.iloc[:, 1:].values.flatten())
    fig.update_layout(title="每日營業額對比", height=400, hovermode="x unified")
    plotly_chart(fig, key="cmp_line")

    radar = comp.groupby("門店").agg({"營業額": "sum", "來客數": "sum", "客單價": "mean"}).reset_index()
    cats = ["營業額", "來客數", "客單價"]
    fig_r = go.Figure()
    for i, s in enumerate(compare_stores):
        r = radar[radar["門店"] == s]
        if r.empty: continue
        vals = [r[c].values[0] / radar[c].max() * 100 if radar[c].max() > 0 else 0 for c in cats]
        vals.append(vals[0])
        fig_r.add_trace(go.Scatterpolar(r=vals, theta=cats+[cats[0]], fill="toself",
                                         name=s, line=dict(color=colors[i % 4])))
    fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,100])),
                        title="綜合指標雷達", height=450)
    plotly_chart(fig_r, key="cmp_radar")


def page_week(data):
    st.header("📅 週循環分析")
    filtered, _, _, _, _, _ = get_filter_expander(data, "wk")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]
    if valid.empty:
        st.warning("篩選後無資料"); return

    weeks = sorted(valid["年週"].unique(), reverse=True)
    sel_wks = st.multiselect("週次（預設最新 3 週）", weeks,
                              default=weeks[:min(3, len(weeks))], key="wk_sel")
    if not sel_wks:
        st.info("請至少選一週"); return

    wd = valid[valid["年週"].isin(sel_wks)]
    wk_sum = wd.groupby("年週").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    wk_sum["客單價"] = (wk_sum["營業額"] / wk_sum["來客數"]).round(0)
    wk_sum["中位數"] = wd.groupby("年週")["營業額"].median().values

    c1, c2, c3 = st.columns(3)
    c1.metric("選定週數", f"{len(sel_wks)} 週")
    c2.metric("平均週營收", f"{wk_sum['營業額'].mean():,.0f} 元")
    c3.metric("中位週營收", f"{wk_sum['營業額'].median():,.0f} 元")

    disp = wk_sum.copy()
    for c in ["營業額", "來客數", "客單價", "中位數"]:
        unit = " 元" if c != "來客數" else " 人"
        disp[c] = disp[c].apply(lambda x: f"{x:,.0f}{unit}")
    st.dataframe(disp, use_container_width=True, hide_index=True)

    wd2 = wd.groupby(["年週", "星期", "星期名"])["營業額"].sum().reset_index().sort_values("星期")
    fig = px.bar(wd2, x="星期名", y="營業額", color="年週", barmode="group", height=400,
                 color_discrete_sequence=["#E63B1F", "#FF7043", "#2C3E50"])
    fig.update_layout(xaxis_title="星期", yaxis_title="營業額（元）")
    add_median_line(fig, wd2["營業額"].values)
    plotly_chart(fig, key="wk_wd")

    render_section_header("calendar", "熱力圖：選定期間各門店每日")
    heat = wd.pivot_table(index="門店", columns="日期", values="營業額", aggfunc="sum")
    if not heat.empty:
        fig_h = px.imshow(heat.values, labels=dict(x="日期", y="門店", color="營業額"),
                          x=[d.strftime("%m/%d") for d in heat.columns],
                          y=heat.index.tolist(),
                          color_continuous_scale="Oranges", aspect="auto")
        fig_h.update_layout(height=max(400, len(heat) * 25))
        plotly_chart(fig_h, key="wk_heat")


def page_month(data):
    st.header("📅 月循環比較")
    filtered, _, _, _, _, _ = get_filter_expander(data, "mo")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]
    if valid.empty:
        st.warning("篩選後無資料"); return

    months = sorted(valid["年月"].unique(), reverse=True)
    sel_ms = st.multiselect("月份", months, default=months[:min(3, len(months))], key="mo_sel")
    if not sel_ms:
        st.info("請至少選一月"); return

    md = valid[valid["年月"].isin(sel_ms)]
    mo = md.groupby("年月").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    mo["客單價"] = (mo["營業額"] / mo["來客數"]).round(0)
    mo["中位數"] = md.groupby("年月")["營業額"].median().values
    mo["成長率"] = mo["營業額"].pct_change() * 100
    mo = mo.sort_values("年月")

    c1, c2 = st.columns(2)
    c1.metric("平均月營收", f"{mo['營業額'].mean():,.0f} 元")
    c2.metric("中位月營收", f"{mo['營業額'].median():,.0f} 元")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=mo["年月"], y=mo["營業額"], name="營業額", marker_color="#E63B1F",
                         hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>"))
    fig.add_trace(go.Scatter(x=mo["年月"], y=mo["客單價"], name="客單價", yaxis="y2",
                              mode="lines+markers", line=dict(color="#2C3E50")))
    add_median_line(fig, mo["營業額"].values)
    fig.update_layout(title="月度趨勢", height=400,
                      yaxis=dict(title="營業額（元）"),
                      yaxis2=dict(title="客單價（元）", side="right", overlaying="y"))
    plotly_chart(fig, key="mo_trend")

    disp = mo.copy()
    for c in ["營業額", "客單價", "中位數"]:
        disp[c] = disp[c].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["成長率"] = disp["成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_quarter(data):
    st.header("📅 季循環分析")
    filtered, _, _, _, _, _ = get_filter_expander(data, "qt")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]
    if valid.empty:
        st.warning("篩選後無資料"); return

    qs = sorted(valid["年季"].unique(), reverse=True)
    sel_qs = st.multiselect("季度", qs, default=qs[:min(4, len(qs))], key="qt_sel")
    if not sel_qs:
        st.info("請至少選一季"); return

    qd = valid[valid["年季"].isin(sel_qs)]
    qo = qd.groupby("年季").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    qo["客單價"] = (qo["營業額"] / qo["來客數"]).round(0)
    qo["中位數"] = qd.groupby("年季")["營業額"].median().values
    qo["成長率"] = qo["營業額"].pct_change() * 100

    c1, c2 = st.columns(2)
    c1.metric("平均季營收", f"{qo['營業額'].mean():,.0f} 元")
    c2.metric("中位季營收", f"{qo['營業額'].median():,.0f} 元")

    fig = px.bar(qo.sort_values("年季"), x="年季", y="營業額",
                 color="營業額", color_continuous_scale="Oranges",
                 title="季度營業額", height=400)
    add_median_line(fig, qo["營業額"].values)
    plotly_chart(fig, key="qt_bar")

    disp = qo.sort_values("年季").copy()
    for c in ["營業額", "客單價", "中位數"]:
        disp[c] = disp[c].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["成長率"] = disp["成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_year(data):
    st.header("📅 年循環比較")
    filtered, _, _, _, _, _ = get_filter_expander(data, "yr")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]
    if valid.empty:
        st.warning("篩選後無資料"); return

    years = sorted(valid["年份"].unique())
    yo = valid.groupby("年份").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    yo["客單價"] = (yo["營業額"] / yo["來客數"]).round(0)
    yo["中位數"] = valid.groupby("年份")["營業額"].median().values
    yo["成長率"] = yo["營業額"].pct_change() * 100

    c1, c2 = st.columns(2)
    c1.metric("平均年營收", f"{yo['營業額'].mean():,.0f} 元")
    c2.metric("中位年營收", f"{yo['營業額'].median():,.0f} 元")

    fig = px.bar(yo, x="年份", y="營業額", color="年份",
                 title="年度營業額",
                 text=yo["營業額"].apply(lambda x: f"{x/10000:,.0f}萬"), height=400,
                 color_discrete_sequence=["#E63B1F", "#2C3E50"])
    fig.update_traces(textposition="outside")
    plotly_chart(fig, key="yr_bar")

    if len(years) > 1:
        st.subheader("年度同月比較")
        ym = valid.groupby(["年份", "月份"])["營業額"].sum().reset_index()
        fig_y = go.Figure()
        ycolors = ["#E63B1F", "#2C3E50", "#FF7043"]
        for i, yr in enumerate(years):
            yd = ym[ym["年份"] == yr].sort_values("月份")
            fig_y.add_trace(go.Bar(x=[f"{m}月" for m in yd["月份"]], y=yd["營業額"],
                                    name=f"{yr}年", marker_color=ycolors[i % 3]))
        fig_y.update_layout(barmode="group", height=400, xaxis_title="月份", yaxis_title="營業額（元）")
        plotly_chart(fig_y, key="yr_yoy")

    disp = yo.copy()
    disp["年份"] = disp["年份"].astype(str) + "年"
    for c in ["營業額", "客單價", "中位數"]:
        disp[c] = disp[c].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["成長率"] = disp["成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_region(data):
    st.header("🏙️ 商圈分析")
    filtered, _, _, _, _, _ = get_filter_expander(data, "rg")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]
    if valid.empty:
        st.warning("篩選後無資料"); return

    rg = valid.groupby("區域").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    rg["客單價"] = (rg["營業額"] / rg["來客數"]).round(0)
    rg["門店數"] = valid.groupby("區域")["門店"].nunique().values
    rg["中位數"] = valid.groupby("區域")["營業額"].median().values
    rg = rg.sort_values("營業額", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(rg, x="區域", y="營業額", color="區域",
                     text=rg["營業額"].apply(lambda x: f"{x/10000:,.0f}萬"),
                     title="各區域營業額", height=350,
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_traces(textposition="outside")
        plotly_chart(fig, key="rg_bar")
    with c2:
        fig_p = px.pie(rg, values="營業額", names="區域", title="區域佔比", hole=0.4,
                       color_discrete_sequence=px.colors.qualitative.Set2)
        fig_p.update_layout(height=350)
        plotly_chart(fig_p, key="rg_pie")

    sel_r = st.selectbox("查看區域內競爭", sorted(valid["區域"].dropna().unique()))
    rs = valid[valid["區域"] == sel_r].groupby("門店").agg({
        "營業額": "sum", "來客數": "sum", "達成率": "first",
    }).reset_index()
    rs["客單價"] = (rs["營業額"] / rs["來客數"]).round(0)
    rs = rs.sort_values("營業額", ascending=False)
    avg = rs["營業額"].mean()
    med = rs["營業額"].median()

    fig = go.Figure()
    cols = ["#27AE60" if r > avg else "#E63B1F" for r in rs["營業額"]]
    fig.add_trace(go.Bar(x=rs["門店"], y=rs["營業額"], marker_color=cols,
                         hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>"))
    fig.add_hline(y=avg, line_dash="dash", line_color="#2C3E50",
                  annotation_text=f"平均 {avg:,.0f}")
    fig.add_hline(y=med, line_dash="dot", line_color="#E63B1F",
                  annotation_text=f"中位 {med:,.0f}")
    fig.update_layout(title=f"【{sel_r}】內部競爭", height=400, xaxis_tickangle=-45)
    plotly_chart(fig, key="rg_inner")


def page_target(data):
    st.header("🎯 本月達標進度追蹤")

    today = data["日期"].max().date()
    yr, mn = today.year, today.month
    dim = calendar.monthrange(yr, mn)[1]
    dom = today.day

    # ── 計算當月 平日(週一~五) / 假日(週六日) 天數分布 ──────────────
    month_days = pd.date_range(start=date(yr, mn, 1), end=date(yr, mn, dim))
    total_wday = sum(1 for d in month_days if d.dayofweek < 5)
    total_wend = sum(1 for d in month_days if d.dayofweek >= 5)
    elapsed_days = pd.date_range(start=date(yr, mn, 1), end=today)
    elapsed_wday = sum(1 for d in elapsed_days if d.dayofweek < 5)
    elapsed_wend = sum(1 for d in elapsed_days if d.dayofweek >= 5)

    st.info(
        f"基準日：{today.strftime('%Y-%m-%d')} ｜ 第 {dom}/{dim} 天 ｜ "
        f"已過平日 {elapsed_wday}/{total_wday} 天、假日 {elapsed_wend}/{total_wend} 天"
    )

    cur = data[(data["日期"].dt.year == yr) & (data["日期"].dt.month == mn)]
    cur = cur[cur["營業額"].notna() & (cur["營業額"] > 0)]
    cur = cur[~cur["門店"].isin(CLOSED_STORES)]
    if cur.empty:
        st.warning("本月無資料"); return

    rows = []
    for (region, store), sg in cur.groupby(["區域", "門店"]):
        target_val = sg["本月目標"].dropna()
        if target_val.empty:
            continue
        target = target_val.iloc[0]
        if pd.isna(target) or target <= 0:
            continue

        sg = sg.copy()
        sg["_dow"] = sg["日期"].dt.dayofweek
        wday_rev = sg[sg["_dow"] < 5]["營業額"].dropna()
        wend_rev = sg[sg["_dow"] >= 5]["營業額"].dropna()
        avg_wday = wday_rev.mean() if len(wday_rev) > 0 else 0
        avg_wend = wend_rev.mean() if len(wend_rev) > 0 else 0
        if avg_wday == 0 and avg_wend == 0:
            avg_wday = avg_wend = 1
        elif avg_wday == 0:
            avg_wday = avg_wend
        elif avg_wend == 0:
            avg_wend = avg_wday

        total_weight = total_wday * avg_wday + total_wend * avg_wend
        expected_rev = target * (elapsed_wday * avg_wday + elapsed_wend * avg_wend) / total_weight if total_weight > 0 else 0
        actual_rev = sg["營業額"].sum()
        vs_exp = (actual_rev / expected_rev * 100) if expected_rev > 0 else 0
        actual_rate = (actual_rev / target * 100)

        if vs_exp >= 95:
            light, status = "🟢", "🟢 達標"
        elif vs_exp >= 90:
            light, status = "🟡", "🟡 注意"
        else:
            light, status = "🔴", "🔴 危險"

        rows.append({
            "燈號": light, "狀態": status, "區域": region, "門店": store,
            "本月目標": target, "目前業績": actual_rev, "應有業績": round(expected_rev),
            "目前達成率": round(actual_rate, 1), "vs應有%": round(vs_exp, 1),
            "差距": round(actual_rev - expected_rev),
            "平日日均": round(avg_wday), "假日日均": round(avg_wend),
        })

    if not rows:
        st.warning("無有效目標資料"); return

    sp = pd.DataFrame(rows).sort_values("vs應有%", ascending=True)

    green  = len(sp[sp["燈號"] == "🟢"])
    yellow = len(sp[sp["燈號"] == "🟡"])
    red    = len(sp[sp["燈號"] == "🔴"])
    ov_exp  = sp["應有業績"].sum() / sp["本月目標"].sum() * 100 if sp["本月目標"].sum() > 0 else 0
    ov_act  = sp["目前業績"].sum() / sp["本月目標"].sum() * 100 if sp["本月目標"].sum() > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🟢 達標", f"{green} 店")
    c2.metric("🟡 注意", f"{yellow} 店")
    c3.metric("🔴 危險", f"{red} 店")
    c4.metric("應有達成率", f"{ov_exp:.1f}%")
    c5.metric("實際達成率", f"{ov_act:.1f}%", delta=f"{ov_act - ov_exp:+.1f}%")

    # ── 儀表盤（最需關注門店，由低到高取前8）────────────────────────
    render_section_header("chart-radar", "達標進度儀表盤（最需關注門店）")
    top8 = sp.head(min(8, len(sp)))
    cols = st.columns(4)
    for i, (_, r) in enumerate(top8.iterrows()):
        color = "#27AE60" if r["燈號"] == "🟢" else ("#FF9800" if r["燈號"] == "🟡" else "#E63B1F")
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=r["vs應有%"],
            delta={"reference": 100, "valueformat": ".1f",
                   "increasing": {"color": "#27AE60"}, "decreasing": {"color": "#E63B1F"}},
            gauge={
                "axis": {"range": [0, 130], "tickwidth": 1},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 90], "color": "rgba(230,59,31,0.12)"},
                    {"range": [90, 95], "color": "rgba(255,152,0,0.12)"},
                    {"range": [95, 130], "color": "rgba(39,174,96,0.10)"},
                ],
                "threshold": {"line": {"color": "#444", "width": 2}, "value": 100},
            },
            title={"text": f"{r['燈號']} {r['門店']}"},
            number={"suffix": "%", "font": {"size": 22}},
        ))
        fig.update_layout(height=210, margin=dict(l=10, r=10, t=38, b=5), font={"size": 11})
        cols[i % 4].plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── 橫向進度條圖 ─────────────────────────────────────────────
    render_section_header("trending-up", "全店 vs 應有達成率（由低到高）")
    colors = ["#27AE60" if r >= 95 else ("#FF9800" if r >= 90 else "#E63B1F") for r in sp["vs應有%"]]
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=sp["門店"], y=sp["vs應有%"], marker_color=colors,
        text=[f"{r:.0f}%" for r in sp["vs應有%"]], textposition="outside",
        hovertemplate="<b>%{x}</b><br>vs應有：%{y:.1f}%<extra></extra>",
    ))
    fig_bar.add_hline(y=100, line_dash="dash", line_color="#333", annotation_text="應有 100%")
    fig_bar.add_hline(y=95, line_dash="dot", line_color="#FF9800", annotation_text="黃燈 95%")
    fig_bar.add_hline(y=90, line_dash="dot", line_color="#E63B1F", annotation_text="紅燈 90%")
    fig_bar.update_layout(
        title=f"{yr}年{mn}月 ｜ 平日/假日加權應有達成率對比",
        height=480, xaxis_tickangle=-45, yaxis_title="vs 應有達成率（%）",
        yaxis_range=[0, max(sp["vs應有%"].max() * 1.12, 115)],
    )
    plotly_chart(fig_bar, key="tg_bar")

    # ── 詳細表格（由低到高）────────────────────────────────────────
    render_section_header("clipboard-list", "門店達標明細（由低到高排序）")
    disp = sp[["狀態", "區域", "門店", "本月目標", "目前業績", "應有業績",
               "目前達成率", "vs應有%", "差距", "平日日均", "假日日均"]].copy()
    for c in ["本月目標", "目前業績", "應有業績", "差距", "平日日均", "假日日均"]:
        disp[c] = disp[c].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
    for c in ["目前達成率", "vs應有%"]:
        disp[c] = disp[c].apply(lambda x: f"{x:.1f}%")
    disp = disp.rename(columns={"vs應有%": "vs應有達成率"})
    st.dataframe(disp, use_container_width=True, hide_index=True)
    st.caption(
        "💡 **計算邏輯**：依本月已過平日/假日天數 × 各店實際平日/假日日均，"
        "估算「應有業績」。實際業績 ÷ 應有業績 ≥ 95% 🟢、90–95% 🟡、< 90% 🔴"
    )


def page_drill(data):
    st.header("🔍 單店下鑽")
    filtered, _, _, _, sel_stores, _ = get_filter_expander(data, "dr")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]
    if not sel_stores:
        st.warning("請選至少 1 店"); return

    store = st.selectbox("選擇門店", sel_stores, key="dr_drill_store")
    sd = valid[valid["門店"] == store].sort_values("日期")
    if sd.empty:
        st.warning("此門店無資料"); return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總營業額", f"{sd['營業額'].sum():,.0f} 元")
    c2.metric("平均日營收", f"{sd['營業額'].mean():,.0f} 元")
    c3.metric("中位日營收", f"{sd['營業額'].median():,.0f} 元")
    c4.metric("營業天數", f"{len(sd)} 天")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sd["日期"], y=sd["營業額"], mode="lines+markers",
                              line=dict(color="#E63B1F", width=2), fill="tozeroy",
                              fillcolor="rgba(230,59,31,0.08)",
                              hovertemplate="%{x|%m/%d}<br>%{y:,.0f} 元<extra></extra>"))
    add_median_line(fig, sd["營業額"].values)
    fig.update_layout(title=f"{store} — 每日走勢", height=350,
                      xaxis_title="日期", yaxis_title="營業額（元）")
    plotly_chart(fig, key="dr_line")

    wd = sd.groupby(["星期", "星期名"])["營業額"].mean().reset_index().sort_values("星期")
    fig_w = px.bar(wd, x="星期名", y="營業額", color="營業額",
                   color_continuous_scale="Oranges", height=300,
                   title=f"{store} — 星期平均")
    add_median_line(fig_w, wd["營業額"].values)
    plotly_chart(fig_w, key="dr_wd")


def page_alert(data):
    st.header("⚠️ 異常警示")

    # ── Feature 3：即時警示通知列（跑馬燈）────────────────────────
    st.markdown("#### 📢 即時警示公告欄")
    with st.spinner("分析資料中..."):
        alert_items = _generate_alert_items(data)
    render_marquee(alert_items)

    st.divider()
    st.subheader("📊 各門店未達日均目標分析")
    filtered, _, _, _, _, _ = get_filter_expander(data, "al")
    ad = filtered.copy()
    ad["當月天數"] = ad["日期"].apply(lambda x: calendar.monthrange(x.year, x.month)[1])
    ad["日均目標"] = ad["本月目標"] / ad["當月天數"]
    hs = ad[ad["日均目標"].notna() & (ad["日均目標"] > 0) & ad["營業額"].notna()].copy()
    if hs.empty:
        st.warning("無足夠資料"); return

    hs["未達標"] = hs["營業額"] < hs["日均目標"]
    hs["差額"] = hs["日均目標"] - hs["營業額"]
    hs.loc[~hs["未達標"], "差額"] = 0

    sa = hs.groupby(["區域", "門店"]).agg(
        有效天數=("營業額", "count"),
        未達標次數=("未達標", "sum"),
        損失營業額=("差額", "sum"),
        日均目標=("日均目標", "mean"),
        實際日均=("營業額", "mean"),
    ).reset_index()
    sa["未達標率"] = (sa["未達標次數"] / sa["有效天數"] * 100).round(1)
    sa = sa.sort_values("損失營業額", ascending=False)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 總未達次數", f"{int(sa['未達標次數'].sum())} 次")
    c2.metric("💸 累計損失", f"{sa['損失營業額'].sum():,.0f} 元")
    c3.metric("平均損失", f"{sa['損失營業額'].mean():,.0f} 元")
    c4.metric("中位損失", f"{sa['損失營業額'].median():,.0f} 元")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=sa["門店"], y=sa["損失營業額"],
                         marker_color=["#E63B1F" if r > 50 else "#FF9800" for r in sa["未達標率"]]))
    add_median_line(fig, sa["損失營業額"].values)
    fig.update_layout(title="各門店累計損失", height=400, xaxis_tickangle=-45,
                      yaxis_title="損失（元）")
    plotly_chart(fig, key="al_bar")

    disp = sa[["區域", "門店", "有效天數", "未達標次數", "未達標率", "日均目標", "實際日均", "損失營業額"]].copy()
    for c in ["日均目標", "實際日均", "損失營業額"]:
        disp[c] = disp[c].apply(lambda x: f"{x:,.0f} 元")
    disp["未達標次數"] = disp["未達標次數"].astype(int).astype(str) + " 次"
    disp["未達標率"] = disp["未達標率"].apply(lambda x: f"{x:.1f}%")
    disp["有效天數"] = disp["有效天數"].astype(int).astype(str) + " 天"
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_ai(data):
    st.header("🤖 AI 數據分析")

    # ── 偵測 API Key ──────────────────────────────────────────────
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    try:
        api_key = api_key or st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass

    use_claude = bool(api_key)

    if use_claude:
        st.success(
            "✅ **Claude AI 模式** — 偵測到 Anthropic API Key，使用真實 AI 分析（快取 30 分鐘）"
        )
    else:
        st.info(
            "💡 **規則引擎模式** — 設定 `ANTHROPIC_API_KEY` 後自動升級為 Claude 真 AI 分析"
        )

    # ── 規則引擎分析（永遠執行，作為基準與交叉驗證）─────────────
    rule_insights = rule_based_ai_analysis(data)

    # ── Claude 分析（僅在有 API Key 時執行）─────────────────────
    claude_insights: dict | None = None
    if use_claude:
        with st.spinner("🤖 Claude 分析中（首次約需 10-20 秒）..."):
            summary = _build_data_summary(data)
            claude_insights = _claude_analysis_cached(summary, api_key)

        if claude_insights and "error" in claude_insights:
            st.error(f"Claude API 呼叫失敗：{claude_insights['error']}")
            st.warning("自動降級至規則引擎分析結果")
            claude_insights = None

    # ── 顯示分析結果 ───────────────────────────────────────────────
    if use_claude and claude_insights:
        # ── Claude 總結橫幅 ──
        summary_text = claude_insights.get("總結", "")
        if summary_text:
            st.markdown(f"""
<div style="background:linear-gradient(135deg,#FFF8F6,#FFE8DC);
            border:1.5px solid #FFCBB8;border-left:5px solid #E63B1F;
            border-radius:12px;padding:1rem 1.4rem;margin-bottom:1rem;">
  <b style="color:#C1320F;font-size:0.95rem;">🤖 Claude 整體評估</b><br>
  <span style="color:#333;font-size:0.9rem;">{summary_text}</span>
</div>""", unsafe_allow_html=True)

        # ── Claude 三欄分析 ──
        render_section_header("sparkles", "Claude AI 深度分析", badge="真AI")
        col1, col2, col3 = st.columns(3)
        categories = [
            ("異常", col1, "bell", "🚨 異常偵測"),
            ("機會", col2, "light-bulb", "💡 機會點"),
            ("規範", col3, "chart-pie", "📐 規範分析"),
        ]
        for cat, col, icon, label in categories:
            with col:
                render_section_header(icon, label)
                items = claude_insights.get(cat, [])
                if items:
                    for item in items[:5]:
                        st.markdown(
                            f"<div class='ai-box'>{item}</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.success(f"✅ 無{cat}項目")

        # ── 交叉驗證 ──
        st.divider()
        render_section_header("check-circle", "規則引擎交叉驗證", badge="對照")
        st.caption(
            "以下為規則引擎同步分析結果，可與 Claude 結果相互印證。"
            "若兩者一致，代表該訊號可信度較高。"
        )
        rv1, rv2, rv3 = st.columns(3)
        for cat, col, label in [
            ("異常", rv1, "🚨 異常"),
            ("機會", rv2, "💡 機會"),
            ("規範", rv3, "📐 規範"),
        ]:
            with col:
                items = rule_insights.get(cat, [])
                if items:
                    for item in items[:3]:
                        clean = item.replace("**", "")
                        st.markdown(
                            f"<div class='ai-box' style='font-size:0.78rem;'>{clean}</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.success(f"✅ 規則引擎無{cat}項目")
    else:
        # ── 純規則引擎模式 ──
        render_section_header("cpu-chip", "規則引擎分析結果")
        col1, col2, col3 = st.columns(3)
        with col1:
            render_section_header("bell", "異常偵測")
            if rule_insights["異常"]:
                for item in rule_insights["異常"]:
                    st.markdown(f"<div class='ai-box'>{item}</div>", unsafe_allow_html=True)
            else:
                st.success("✅ 未發現異常")
        with col2:
            render_section_header("light-bulb", "機會點")
            if rule_insights["機會"]:
                for item in rule_insights["機會"]:
                    st.markdown(f"<div class='ai-box'>{item}</div>", unsafe_allow_html=True)
            else:
                st.info("暫無特殊機會點")
        with col3:
            render_section_header("chart-pie", "規範分析")
            if rule_insights["規範"]:
                for item in rule_insights["規範"]:
                    st.markdown(f"<div class='ai-box'>{item}</div>", unsafe_allow_html=True)
            else:
                st.info("暫無特殊模式")

    st.divider()
    st.markdown("### 🎓 AI 觀察準則")
    st.markdown("""
    - **異常偵測**：連續 3 天未達日均目標、單日營收暴跌 >30%
    - **機會點**：高客單低來客（推分享活動）、低客單高來客（推套餐）
    - **規範分析**：週期性對比、週末平日效應、成長趨勢判讀
    - **Claude AI**：自動閱讀所有門店摘要，提供更細緻的文字洞察與建議
    """)


# ============================================================
# 主程式
# ============================================================
def main():
    from utils.ui_helpers import render_ai_summary
    inject_global_css()

    with st.spinner("載入資料中..."):
        data = load_all_data()

    if data.empty:
        st.error("無法載入資料"); return

    # 側邊欄
    st.sidebar.markdown("## 📊 嗑肉石鍋 營收看板")
    st.sidebar.caption(f"資料更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.sidebar.page_link("app.py", label="← 返回數位總部大門")
    st.sidebar.divider()

    # ── 跑馬燈 & AI 摘要（頂部） ──
    valid_all_mq = data[data["營業額"].notna() & (data["營業額"] > 0)]
    if not valid_all_mq.empty:
        latest_ym = valid_all_mq["年月"].max()
        latest_month_df = valid_all_mq[valid_all_mq["年月"] == latest_ym]
        total_rev = latest_month_df["營業額"].sum()
        store_cnt = latest_month_df["門店"].nunique()
        avg_daily = valid_all_mq.groupby("日期")["營業額"].sum().mean()
        insights_mq = rule_based_ai_analysis(data)
        anomaly_cnt = len(insights_mq.get("異常", []))
        marquee_items = [
            f"本月累計營收 {total_rev:,.0f} 元",
            f"監控門店 {store_cnt} 家",
            f"全店日均 {avg_daily:,.0f} 元",
            f"異常偵測 {anomaly_cnt} 項" if anomaly_cnt > 0 else "系統運行正常",
            f"資料更新：{datetime.now().strftime('%m/%d %H:%M')}",
        ]
        ai_bullets = []
        for cat in ["異常", "機會", "規範"]:
            for item in insights_mq.get(cat, [])[:2]:
                clean = item.replace("**", "")
                ai_bullets.append(clean)
        if not ai_bullets:
            ai_bullets = ["各門店運營狀況正常，持續監控中"]
        render_marquee(marquee_items)
        render_ai_summary("數據戰情中心 — 即時洞察", ai_bullets[:5])

    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = PAGE_LIST[0]

    curr_idx = PAGE_LIST.index(st.session_state["nav_page"])

    def _go_prev():
        i = PAGE_LIST.index(st.session_state["nav_page"])
        st.session_state["nav_page"] = PAGE_LIST[max(0, i - 1)]

    def _go_next():
        i = PAGE_LIST.index(st.session_state["nav_page"])
        st.session_state["nav_page"] = PAGE_LIST[min(len(PAGE_LIST) - 1, i + 1)]

    def _on_select():
        st.session_state["nav_page"] = st.session_state["_nav_select"]

    nc1, nc2 = st.sidebar.columns(2)
    with nc1:
        st.button("◀ 上一頁", use_container_width=True, disabled=(curr_idx == 0),
                  key="btn_prev", on_click=_go_prev)
    with nc2:
        st.button("下一頁 ▶", use_container_width=True, disabled=(curr_idx == len(PAGE_LIST) - 1),
                  key="btn_next", on_click=_go_next)

    sel_page = st.sidebar.selectbox(
        "⚡ 快速跳轉", PAGE_LIST,
        index=curr_idx,
        key="_nav_select",
        on_change=_on_select,
    )

    st.sidebar.divider()
    sidebar_overview(data)
    st.sidebar.divider()

    with st.sidebar.expander("🤖 AI 重點觀察", expanded=False):
        insights = rule_based_ai_analysis(data)
        total_items = sum(len(v) for v in insights.values())
        if total_items == 0:
            st.caption("一切正常 ✅")
        else:
            if insights["異常"]:
                st.markdown("**🚨 異常**")
                for i in insights["異常"][:3]:
                    st.caption(f"• {i[:60]}")
            if insights["機會"]:
                st.markdown("**💡 機會**")
                for i in insights["機會"][:2]:
                    st.caption(f"• {i[:60]}")

    st.sidebar.divider()

    if st.sidebar.button("🔄 重新載入資料", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    valid_all = data[data["營業額"].notna() & (data["營業額"] > 0)]
    ed = valid_all[["日期", "區域", "門店", "營業額", "來客數", "客單價", "本月目標", "達成率"]].copy()
    ed["日期"] = ed["日期"].dt.strftime("%Y-%m-%d")

    def to_excel(df):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="營收資料")
        return out.getvalue()

    st.sidebar.download_button(
        "📥 匯出 Excel", data=to_excel(ed),
        file_name=f"嗑肉石鍋_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    # 分頁 router
    page_map = {
        "📊 總覽": page_overview,
        "🏪 門店排行": page_store_rank,
        "💪 綜合戰力分析": page_combat,
        "🔄 店對店比較": page_compare,
        "📅 週循環分析": page_week,
        "📅 月循環比較": page_month,
        "📅 季循環分析": page_quarter,
        "📅 年循環比較": page_year,
        "🏙️ 商圈分析": page_region,
        "🎯 達標追蹤": page_target,
        "🔍 單店下鑽": page_drill,
        "⚠️ 異常警示": page_alert,
        "🤖 AI 數據分析": page_ai,
    }
    page_map[sel_page](data)


main()
