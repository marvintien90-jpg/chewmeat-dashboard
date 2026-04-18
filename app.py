import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import warnings
import re
import calendar
import io

warnings.filterwarnings("ignore")

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

# 已結村門店清單（有歷史資料但已不在營業）
CLOSED_STORES = {"北屯軍福店", "犝犝楠梓店", "高雄大順店", "高雄自由店", "高雄鼎強店", "鳳山文中店"}

# 手機 RWD：圖表設定（禁用縮放、拖曳；保留 tooltip）
MOBILE_CHART_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "displaylogo": False,
    "staticPlot": False,  # 保留 hover/tooltip
}

st.set_page_config(
    page_title="嗑肉石鍋 營收儀表板",
    page_icon="🍲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 自訂 CSS（優化 Mac + iPhone）
# ============================================================
st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<style>
    /* 全局 */
    .main .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    /* KPI 卡片 */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        border: 1px solid #e0e4e8;
    }
    [data-testid="stMetricLabel"] {font-size: 0.9rem; color: #666;}
    [data-testid="stMetricValue"] {font-size: 1.6rem; font-weight: 700; color: #1a1a2e;}
    /* 側邊欄 */
    [data-testid="stSidebar"] {background: #fafbfc;}
    /* 手機優化 */
    @media (max-width: 768px) {
        .main .block-container {padding: 1rem;}
        [data-testid="stMetricValue"] {font-size: 1.2rem;}
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 資料讀取
# ============================================================
@st.cache_data(ttl=3600)
def load_sheet(year_month, gid):
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
        index=["日期", "區域", "門店", "本月目標", "達成率"],
        columns="指標", values="數值", aggfunc="first",
    ).reset_index()
    pivot.columns.name = None

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
    # 資料清洗：犝犝楠梓店保留為獨立門店（已結村）
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


def fmt_pct(x):
    if pd.isna(x):
        return "—"
    return f"{x:+.1f}%"


def plotly_chart(fig, key=None):
    """統一 Plotly 圖表渲染：禁用縮放拖曳、保留 tooltip"""
    st.plotly_chart(fig, use_container_width=True, config=MOBILE_CHART_CONFIG, key=key)


def bsh(icon, text, level=2):
    tag = f"h{level}"
    st.markdown(
        f'<{tag} style="display:flex;align-items:center;gap:.4rem">'
        f'<i class="bi {icon}"></i> {text}</{tag}>',
        unsafe_allow_html=True,
    )


def get_date_filter(data, key_prefix="", active_stores=None):
    """展開式篩選器 - 每頁通用"""
    with st.expander("篩選條件", expanded=False):
        c1, c2, c3 = st.columns([2, 1, 1])
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
            store_pool = active_stores if active_stores else sorted(
                data[data["區域"].isin(sel_regions)]["門店"].dropna().unique().tolist()
            )
            sel_stores = st.multiselect(
                "門店", store_pool, default=store_pool,
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
    return data[mask].copy(), start_d, end_d, sel_regions, sel_stores


def calc_kpi_card(data, period_label, start_d, end_d, compare_start=None, compare_end=None):
    """計算累計卡片的三合一指標：本期金額、同期比、達成率"""
    period_data = data[(data["日期"].dt.date >= start_d) & (data["日期"].dt.date <= end_d)]
    period_data = period_data[period_data["營業額"].notna() & (period_data["營業額"] > 0)]
    total = period_data["營業額"].sum()

    delta = None
    if compare_start and compare_end:
        cmp_data = data[(data["日期"].dt.date >= compare_start) & (data["日期"].dt.date <= compare_end)]
        cmp_data = cmp_data[cmp_data["營業額"].notna() & (cmp_data["營業額"] > 0)]
        cmp_total = cmp_data["營業額"].sum()
        if cmp_total > 0:
            delta = (total - cmp_total) / cmp_total * 100

    return total, delta


# ============================================================
# 分頁函數
# ============================================================
def page_overview(data):
    """總覽（四大累計）"""
    bsh("bi-bar-chart-line", "總覽", level=2)

    filtered, start_d, end_d, sel_regions, sel_stores = get_date_filter(data, "ov")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    # 計算基準日（資料最新一天）
    today = valid["日期"].max().date()
    yr, mn = today.year, today.month

    # ========== 四大累計卡片 ==========
    bsh("bi-gem", "四大累計分析", level=3)

    # 曆年累計（所有歷史資料至最新日）
    yoy_total = data[data["營業額"].notna() & (data["營業額"] > 0)]["營業額"].sum()

    # 今年累計
    y_start = date(yr, 1, 1)
    y_ly_start = date(yr - 1, 1, 1)
    y_ly_end = date(yr - 1, today.month, today.day) if today.month <= 12 else date(yr - 1, 12, 31)
    y_total, y_delta = calc_kpi_card(data, "今年", y_start, today, y_ly_start, y_ly_end)

    # 本季累計
    q_start_month = ((mn - 1) // 3) * 3 + 1
    q_start = date(yr, q_start_month, 1)
    q_ly_start = date(yr - 1, q_start_month, 1)
    q_ly_end = date(yr - 1, mn, today.day) if today.day <= calendar.monthrange(yr - 1, mn)[1] else date(yr - 1, mn, calendar.monthrange(yr - 1, mn)[1])
    q_total, q_delta = calc_kpi_card(data, "本季", q_start, today, q_ly_start, q_ly_end)

    # 本月累計
    m_start = date(yr, mn, 1)
    try:
        m_ly_start = date(yr - 1, mn, 1)
        ly_last_day = calendar.monthrange(yr - 1, mn)[1]
        m_ly_end = date(yr - 1, mn, min(today.day, ly_last_day))
    except ValueError:
        m_ly_start = m_ly_end = None
    m_total, m_delta = calc_kpi_card(data, "本月", m_start, today, m_ly_start, m_ly_end)

    # 本月目標達成率
    cur_month_target = data[
        (data["日期"].dt.year == yr) & (data["日期"].dt.month == mn)
    ].groupby("門店")["本月目標"].first().sum()
    m_rate = (m_total / cur_month_target * 100) if cur_month_target > 0 else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("曆年累計", f"{yoy_total:,.0f} 元")
    c2.metric("今年累計", f"{y_total:,.0f} 元",
              delta=f"{y_delta:+.1f}% vs 去年同期" if y_delta is not None else None)
    c3.metric("本季累計", f"{q_total:,.0f} 元",
              delta=f"{q_delta:+.1f}% vs 去年同期" if q_delta is not None else None)
    c4.metric("本月累計", f"{m_total:,.0f} 元",
              delta=f"達成 {m_rate:.1f}%" if m_rate else None)

    st.divider()

    # ========== 每日營收趨勢 ==========
    bsh("bi-graph-up-arrow", "每日營收趨勢", level=3)
    daily = valid.groupby("日期").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    daily["客單價"] = (daily["營業額"] / daily["來客數"]).round(0)

    fig = make_revenue_bar(daily)
    plotly_chart(fig, key="ov_daily")

    # 來客數 + 客單價雙軸
    fig2 = make_dual_axis(daily)
    plotly_chart(fig2, key="ov_dual")

    # ========== 區域營收佔比 Sunburst ==========
    bsh("bi-pie-chart", "區域 / 門店營收結構", level=3)
    sunburst_data = valid.groupby(["區域", "門店"])["營業額"].sum().reset_index()
    fig_sb = px.sunburst(
        sunburst_data, path=["區域", "門店"], values="營業額",
        color="營業額", color_continuous_scale="RdYlGn",
        title="區域 → 門店 營收佔比",
    )
    fig_sb.update_layout(height=500)
    plotly_chart(fig_sb, key="ov_sunburst")


def page_store_rank(data):
    """門店排行"""
    bsh("bi-shop", "門店排行")
    filtered, _, _, _, sel_stores = get_date_filter(data, "rk")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    store_sum = valid.groupby(["區域", "門店"]).agg({
        "營業額": "sum", "來客數": "sum",
        "本月目標": "first", "達成率": "first",
    }).reset_index()
    store_sum["客單價"] = (store_sum["營業額"] / store_sum["來客數"]).round(0)
    store_sum = store_sum.sort_values("營業額", ascending=False)

    # 排行圖
    fig = px.bar(
        store_sum, x="門店", y="營業額", color="區域",
        title="各門店營業額排行", height=450,
    )
    fig.update_layout(xaxis_tickangle=-45)
    fig.update_traces(hovertemplate="%{x}<br>營業額：%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="rk_bar")

    # 達成率儀表板（選前 6 名）
    if store_sum["達成率"].notna().any():
        bsh("bi-bullseye", "前六店達成率儀表板", level=3)
        top6 = store_sum[store_sum["達成率"].notna()].head(6)
        cols = st.columns(3)
        for i, (_, row) in enumerate(top6.iterrows()):
            with cols[i % 3]:
                fig_g = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=row["達成率"] * 100,
                    title={"text": row["門店"]},
                    number={"suffix": "%"},
                    gauge={
                        "axis": {"range": [0, 130]},
                        "bar": {"color": "#4ECDC4"},
                        "steps": [
                            {"range": [0, 50], "color": "#FFD6D6"},
                            {"range": [50, 80], "color": "#FFF3C4"},
                            {"range": [80, 130], "color": "#C4F0C4"},
                        ],
                        "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 100},
                    },
                ))
                fig_g.update_layout(height=200, margin=dict(t=30, b=10, l=10, r=10))
                plotly_chart(fig_g, key=f"gauge_{i}")

    # 明細表
    bsh("bi-table", "明細表", level=3)
    disp = store_sum[["區域", "門店", "營業額", "來客數", "客單價", "達成率"]].copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["達成率"] = disp["達成率"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_store_compare(data):
    """店對店比較"""
    bsh("bi-arrow-left-right", "店對店比較")
    filtered, _, _, _, sel_stores = get_date_filter(data, "cmp")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    compare_stores = st.multiselect(
        "選擇 2～4 間門店比較", sel_stores,
        default=sel_stores[:min(2, len(sel_stores))],
        max_selections=4,
        key="cmp_select",
    )
    if len(compare_stores) < 2:
        st.info("請至少選擇 2 間門店")
        return

    comp = valid[valid["門店"].isin(compare_stores)]

    # 每日營業額對比
    pivot = comp.pivot_table(index="日期", columns="門店", values="營業額", aggfunc="sum").reset_index()
    fig = go.Figure()
    colors = ["#4ECDC4", "#FF6B6B", "#45B7D1", "#FFA726"]
    for i, s in enumerate(compare_stores):
        if s in pivot.columns:
            fig.add_trace(go.Scatter(
                x=pivot["日期"], y=pivot[s], mode="lines+markers", name=s,
                line=dict(color=colors[i % 4], width=2),
                hovertemplate=f"{s}<br>%{{x|%m/%d}}<br>%{{y:,.0f}} 元<extra></extra>",
            ))
    fig.update_layout(title="每日營業額對比", height=400, hovermode="x unified",
                      xaxis_title="日期", yaxis_title="營業額（元）")
    plotly_chart(fig, key="cmp_line")

    # 雷達圖
    radar = comp.groupby("門店").agg({"營業額": "sum", "來客數": "sum", "客單價": "mean"}).reset_index()
    cats = ["營業額", "來客數", "客單價"]
    fig_r = go.Figure()
    for i, s in enumerate(compare_stores):
        row = radar[radar["門店"] == s]
        if row.empty: continue
        vals = [row[c].values[0] / radar[c].max() * 100 if radar[c].max() > 0 else 0 for c in cats]
        vals.append(vals[0])
        fig_r.add_trace(go.Scatterpolar(
            r=vals, theta=cats + [cats[0]], fill="toself", name=s,
            line=dict(color=colors[i % 4]),
        ))
    fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                        title="綜合指標雷達圖（標準化%）", height=450)
    plotly_chart(fig_r, key="cmp_radar")


def page_cycle_week(data):
    """週循環分析"""
    bsh("bi-calendar-week", "週循環分析")
    filtered, _, _, _, sel_stores = get_date_filter(data, "wk")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    weeks = sorted(valid["年週"].unique(), reverse=True)
    sel_weeks = st.multiselect(
        "選擇要比較的週次（預設最新 3 週）",
        weeks, default=weeks[:min(3, len(weeks))], key="wk_sel",
    )
    if not sel_weeks:
        st.info("請至少選擇一週")
        return

    wk_data = valid[valid["年週"].isin(sel_weeks)]

    # 週彙總
    wk_sum = wk_data.groupby("年週").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    wk_sum["客單價"] = (wk_sum["營業額"] / wk_sum["來客數"]).round(0)
    wk_sum = wk_sum.sort_values("年週")

    st.subheader("週摘要")
    disp = wk_sum.copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    st.dataframe(disp, use_container_width=True, hide_index=True)

    # 週內日別對比
    st.subheader("各週 × 星期 營業額")
    wd = wk_data.groupby(["年週", "星期", "星期名"])["營業額"].sum().reset_index().sort_values("星期")
    fig = px.bar(wd, x="星期名", y="營業額", color="年週", barmode="group", height=400)
    fig.update_layout(xaxis_title="星期", yaxis_title="營業額（元）")
    fig.update_traces(hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="wk_weekday")

    # 熱力圖：日 × 門店
    bsh("bi-fire", "熱力圖：選定期間各門店每日營業額", level=3)
    heat = wk_data.pivot_table(index="門店", columns="日期", values="營業額", aggfunc="sum")
    if not heat.empty:
        fig_h = px.imshow(
            heat.values,
            labels=dict(x="日期", y="門店", color="營業額"),
            x=[d.strftime("%m/%d") for d in heat.columns],
            y=heat.index.tolist(),
            color_continuous_scale="YlOrRd", aspect="auto",
        )
        fig_h.update_layout(height=max(400, len(heat) * 25))
        plotly_chart(fig_h, key="wk_heat")


def page_cycle_month(data):
    """月循環比較"""
    bsh("bi-calendar-month", "月循環比較")
    filtered, _, _, _, sel_stores = get_date_filter(data, "mo")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    months = sorted(valid["年月"].unique(), reverse=True)
    sel_months = st.multiselect(
        "選擇要比較的月份（預設最新 3 個月）",
        months, default=months[:min(3, len(months))], key="mo_sel",
    )
    if not sel_months:
        st.info("請至少選擇一個月")
        return

    mo_data = valid[valid["年月"].isin(sel_months)]

    # 月度趨勢
    monthly = mo_data.groupby("年月").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    monthly["客單價"] = (monthly["營業額"] / monthly["來客數"]).round(0)
    monthly["營業額成長率"] = monthly["營業額"].pct_change() * 100
    monthly = monthly.sort_values("年月")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=monthly["年月"], y=monthly["營業額"], name="營業額",
                        marker_color="#4ECDC4",
                        hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>"))
    fig.add_trace(go.Scatter(x=monthly["年月"], y=monthly["客單價"], name="客單價",
                             mode="lines+markers", line=dict(color="#FF6B6B", width=2),
                             yaxis="y2",
                             hovertemplate="客單價：%{y:,.0f} 元<extra></extra>"))
    fig.update_layout(title="月度趨勢", height=400, hovermode="x unified",
                      yaxis=dict(title="營業額（元）"),
                      yaxis2=dict(title="客單價（元）", side="right", overlaying="y"))
    plotly_chart(fig, key="mo_trend")

    # 成長率表格
    st.subheader("月度成長率")
    disp = monthly.copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["營業額成長率"] = disp["營業額成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    disp = disp.rename(columns={"年月": "月份"})
    st.dataframe(disp[["月份", "營業額", "來客數", "客單價", "營業額成長率"]],
                 use_container_width=True, hide_index=True)


def page_cycle_quarter(data):
    """季循環分析"""
    bsh("bi-calendar3-range", "季循環分析")
    filtered, _, _, _, _ = get_date_filter(data, "qt")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    quarters = sorted(valid["年季"].unique(), reverse=True)
    sel_q = st.multiselect(
        "選擇要比較的季度（預設最新 4 季）",
        quarters, default=quarters[:min(4, len(quarters))], key="qt_sel",
    )
    if not sel_q:
        st.info("請至少選擇一季")
        return

    q_data = valid[valid["年季"].isin(sel_q)]
    q_sum = q_data.groupby("年季").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    q_sum["客單價"] = (q_sum["營業額"] / q_sum["來客數"]).round(0)
    q_sum["成長率"] = q_sum["營業額"].pct_change() * 100

    fig = px.bar(q_sum.sort_values("年季"), x="年季", y="營業額",
                 color="營業額", color_continuous_scale="Blues",
                 title="季度營業額", height=400)
    fig.update_traces(hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="qt_bar")

    disp = q_sum.sort_values("年季").copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["成長率"] = disp["成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_cycle_year(data):
    """年循環比較"""
    bsh("bi-calendar3", "年循環比較")
    filtered, _, _, _, _ = get_date_filter(data, "yr")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    years = sorted(valid["年份"].unique())
    if len(years) < 1:
        st.info("資料年份不足")
        return

    # 年度彙總
    yr_sum = valid.groupby("年份").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    yr_sum["客單價"] = (yr_sum["營業額"] / yr_sum["來客數"]).round(0)
    yr_sum["成長率"] = yr_sum["營業額"].pct_change() * 100

    fig = px.bar(yr_sum, x="年份", y="營業額", text=yr_sum["營業額"].apply(lambda x: f"{x/10000:,.0f}萬"),
                 color="年份", title="年度營業額", height=400)
    fig.update_traces(textposition="outside", hovertemplate="%{x}年<br>%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="yr_bar")

    # 年度同月對比
    if len(years) > 1:
        st.subheader("年度同月營業額對比")
        ym = valid.groupby(["年份", "月份"]).agg({"營業額": "sum"}).reset_index()
        fig_y = go.Figure()
        year_colors = ["#4ECDC4", "#FF6B6B", "#45B7D1"]
        for i, yr in enumerate(years):
            yd = ym[ym["年份"] == yr].sort_values("月份")
            fig_y.add_trace(go.Bar(
                x=[f"{m}月" for m in yd["月份"]], y=yd["營業額"],
                name=f"{yr}年", marker_color=year_colors[i % 3],
                hovertemplate=f"{yr}年 %{{x}}<br>%{{y:,.0f}} 元<extra></extra>",
            ))
        fig_y.update_layout(barmode="group", height=400, xaxis_title="月份", yaxis_title="營業額（元）")
        plotly_chart(fig_y, key="yr_yoy")

    # 明細
    disp = yr_sum.copy()
    disp["年份"] = disp["年份"].astype(str) + "年"
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["成長率"] = disp["成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_region(data):
    """商圈分析"""
    bsh("bi-buildings", "商圈 / 區域競爭分析")
    filtered, _, _, _, _ = get_date_filter(data, "rg")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    # 區域總覽
    rg_sum = valid.groupby("區域").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    rg_sum["客單價"] = (rg_sum["營業額"] / rg_sum["來客數"]).round(0)
    rg_sum["門店數"] = valid.groupby("區域")["門店"].nunique().values
    rg_sum = rg_sum.sort_values("營業額", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(rg_sum, x="區域", y="營業額", color="區域",
                     text=rg_sum["營業額"].apply(lambda x: f"{x/10000:,.0f}萬"),
                     title="各區域總營業額", height=350)
        fig.update_traces(textposition="outside", hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>")
        fig.update_layout(showlegend=False)
        plotly_chart(fig, key="rg_bar")

    with c2:
        fig_pie = px.pie(rg_sum, values="營業額", names="區域", title="區域營收佔比", hole=0.4)
        fig_pie.update_traces(hovertemplate="%{label}<br>%{value:,.0f} 元<br>%{percent}<extra></extra>")
        fig_pie.update_layout(height=350)
        plotly_chart(fig_pie, key="rg_pie")

    # 選區域看內部
    sel_region = st.selectbox("選擇區域查看內部競爭", sorted(valid["區域"].dropna().unique()))
    rg_stores = valid[valid["區域"] == sel_region].groupby("門店").agg({
        "營業額": "sum", "來客數": "sum", "達成率": "first",
    }).reset_index()
    rg_stores["客單價"] = (rg_stores["營業額"] / rg_stores["來客數"]).round(0)
    rg_stores = rg_stores.sort_values("營業額", ascending=False)
    avg_rev = rg_stores["營業額"].mean()

    fig = go.Figure()
    colors = ["#44BB44" if r > avg_rev else "#FF6B6B" for r in rg_stores["營業額"]]
    fig.add_trace(go.Bar(x=rg_stores["門店"], y=rg_stores["營業額"], marker_color=colors,
                        hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>"))
    fig.add_hline(y=avg_rev, line_dash="dash", line_color="blue",
                  annotation_text=f"區域平均 {avg_rev:,.0f} 元")
    fig.update_layout(title=f"【{sel_region}】門店營業額（綠=高於平均）",
                      height=350, xaxis_tickangle=-45)
    plotly_chart(fig, key="rg_inner")

    # 明細
    disp = rg_stores.copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["達成率"] = disp["達成率"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_target(data):
    """達標追蹤"""
    bsh("bi-bullseye", "本月達標進度追蹤")

    today = data["日期"].max().date()
    yr, mn = today.year, today.month
    days_in_month = calendar.monthrange(yr, mn)[1]
    day_of_month = today.day

    st.info(f"基準日：{today.strftime('%Y-%m-%d')}（資料最新日） ｜ 進度 {day_of_month}/{days_in_month} 天（{day_of_month/days_in_month*100:.0f}%）")

    cur = data[(data["日期"].dt.year == yr) & (data["日期"].dt.month == mn)]
    cur = cur[cur["營業額"].notna() & (cur["營業額"] > 0)]
    # 排除已結村門店
    cur = cur[~cur["門店"].isin(CLOSED_STORES)]

    if cur.empty:
        st.warning("本月尚無資料")
        return

    store_progress = cur.groupby(["區域", "門店"]).agg({
        "營業額": "sum", "來客數": "sum", "本月目標": "first",
    }).reset_index()
    store_progress["已營業天數"] = cur.groupby("門店")["日期"].nunique().values
    store_progress["日均實際"] = (store_progress["營業額"] / store_progress["已營業天數"]).round(0)
    store_progress["預估月營收"] = (store_progress["日均實際"] * days_in_month).round(0)
    store_progress["預估達成率"] = (store_progress["預估月營收"] / store_progress["本月目標"] * 100).round(1)
    store_progress["目前達成率"] = (store_progress["營業額"] / store_progress["本月目標"] * 100).round(1)
    store_progress["狀態"] = store_progress["預估達成率"].apply(
        lambda x: "可達標" if x >= 100 else ("略低" if x >= 85 else "危險")
    )
    store_progress = store_progress.sort_values("預估達成率", ascending=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("預估可達標", f"{len(store_progress[store_progress['預估達成率'] >= 100])} 店")
    c2.metric("預估危險", f"{len(store_progress[store_progress['預估達成率'] < 85])} 店")
    c3.metric("本月剩餘天數", f"{days_in_month - day_of_month} 天")

    # 達成率儀表板 bar chart
    fig = go.Figure()
    colors = [
        "#44BB44" if r >= 100 else ("#FFaa00" if r >= 85 else "#FF4444")
        for r in store_progress["預估達成率"]
    ]
    fig.add_trace(go.Bar(
        x=store_progress["門店"], y=store_progress["預估達成率"],
        marker_color=colors,
        text=[f"{r:.0f}%" for r in store_progress["預估達成率"]],
        textposition="outside",
        hovertemplate="%{x}<br>預估達成率：%{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="目標 100%")
    fig.update_layout(title=f"{yr}年{mn}月 各門店預估達成率",
                      height=450, xaxis_tickangle=-45,
                      yaxis_title="預估達成率（%）")
    plotly_chart(fig, key="tg_bar")

    disp = store_progress[["區域", "門店", "營業額", "本月目標", "目前達成率",
                            "日均實際", "預估月營收", "預估達成率", "狀態"]].copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["本月目標"] = disp["本月目標"].apply(lambda x: f"{x:,.0f} 元" if pd.notna(x) else "—")
    disp["日均實際"] = disp["日均實際"].apply(lambda x: f"{x:,.0f} 元")
    disp["預估月營收"] = disp["預估月營收"].apply(lambda x: f"{x:,.0f} 元")
    disp["目前達成率"] = disp["目前達成率"].apply(lambda x: f"{x:.1f}%")
    disp["預估達成率"] = disp["預估達成率"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_drill(data):
    """單店下鑽"""
    bsh("bi-search", "單店下鑽分析")
    filtered, _, _, _, sel_stores = get_date_filter(data, "dr")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if not sel_stores:
        st.warning("請在篩選條件中至少選擇 1 間門店")
        return

    store = st.selectbox("選擇門店", sel_stores, key="dr_drill_store")
    sd = valid[valid["門店"] == store].sort_values("日期")

    if sd.empty:
        st.warning("此門店在選定期間無資料")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("總營業額", f"{sd['營業額'].sum():,.0f} 元")
    c2.metric("總來客數", f"{sd['來客數'].sum():,.0f} 人")
    avg = sd["營業額"].sum() / sd["來客數"].sum() if sd["來客數"].sum() > 0 else 0
    c3.metric("平均客單價", f"{avg:,.0f} 元")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sd["日期"], y=sd["營業額"], mode="lines+markers",
                              line=dict(color="#4ECDC4", width=2), fill="tozeroy",
                              hovertemplate="%{x|%m/%d}<br>%{y:,.0f} 元<extra></extra>"))
    fig.update_layout(title=f"{store} — 每日營業額走勢", height=350,
                      xaxis_title="日期", yaxis_title="營業額（元）")
    plotly_chart(fig, key="dr_line")

    # 星期分析
    wd = sd.groupby(["星期", "星期名"]).agg({"營業額": "mean"}).reset_index().sort_values("星期")
    fig_w = px.bar(wd, x="星期名", y="營業額", color="營業額",
                   color_continuous_scale="Viridis",
                   title=f"{store} — 平均營業額（按星期）", height=300)
    fig_w.update_traces(hovertemplate="%{x}<br>平均 %{y:,.0f} 元<extra></extra>")
    plotly_chart(fig_w, key="dr_weekday")


def page_alert(data):
    """異常警示"""
    bsh("bi-exclamation-triangle", "未達日均目標警示")
    filtered, _, _, _, _ = get_date_filter(data, "al")
    alert_data = filtered.copy()
    alert_data["當月天數"] = alert_data["日期"].apply(
        lambda x: calendar.monthrange(x.year, x.month)[1]
    )
    alert_data["日均目標"] = alert_data["本月目標"] / alert_data["當月天數"]
    hs = alert_data[alert_data["日均目標"].notna() & (alert_data["日均目標"] > 0)
                    & alert_data["營業額"].notna()].copy()

    if hs.empty:
        st.warning("無足夠資料")
        return

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

    total_miss = int(sa["未達標次數"].sum())
    total_loss = sa["損失營業額"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("全店未達標次數", f"{total_miss} 次")
    c2.metric("累計損失營業額", f"{total_loss:,.0f} 元")
    c3.metric("損失最多門店", sa.iloc[0]["門店"] if len(sa) else "—")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sa["門店"], y=sa["損失營業額"],
        marker_color=["#FF4444" if r > 50 else "#FFaa00" for r in sa["未達標率"]],
        hovertemplate="%{x}<br>損失：%{y:,.0f} 元<extra></extra>",
    ))
    fig.update_layout(title="各門店累計損失營業額", height=400, xaxis_tickangle=-45,
                      yaxis_title="損失營業額（元）")
    plotly_chart(fig, key="al_loss")

    disp = sa[["區域", "門店", "有效天數", "未達標次數", "未達標率", "日均目標", "實際日均", "損失營業額"]].copy()
    disp["日均目標"] = disp["日均目標"].apply(lambda x: f"{x:,.0f} 元")
    disp["實際日均"] = disp["實際日均"].apply(lambda x: f"{x:,.0f} 元")
    disp["損失營業額"] = disp["損失營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["未達標次數"] = disp["未達標次數"].astype(int).astype(str) + " 次"
    disp["未達標率"] = disp["未達標率"].apply(lambda x: f"{x:.1f}%")
    disp["有效天數"] = disp["有效天數"].astype(int).astype(str) + " 天"
    st.dataframe(disp, use_container_width=True, hide_index=True)


# ============================================================
# 共用圖表函數
# ============================================================
def make_revenue_bar(daily):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["日期"], y=daily["營業額"], name="營業額",
        marker_color="#4ECDC4",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f} 元<extra></extra>",
    ))
    # 標記峰值
    if not daily.empty:
        peak_idx = daily["營業額"].idxmax()
        peak = daily.loc[peak_idx]
        fig.add_annotation(
            x=peak["日期"], y=peak["營業額"],
            text=f"峰值 {peak['營業額']:,.0f}",
            showarrow=True, arrowhead=2, bgcolor="#FFF3C4",
        )
    fig.update_layout(title="全店每日營業額", height=400, hovermode="x unified",
                      xaxis_title="日期", yaxis_title="營業額（元）")
    return fig


def make_dual_axis(daily):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["日期"], y=daily["來客數"], name="來客數", marker_color="#45B7D1",
        hovertemplate="%{x|%Y-%m-%d}<br>來客數：%{y:,.0f} 人<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=daily["日期"], y=daily["客單價"], name="客單價",
        mode="lines+markers", line=dict(color="#FF6B6B", width=2), yaxis="y2",
        hovertemplate="客單價：%{y:,.0f} 元<extra></extra>",
    ))
    fig.update_layout(
        title="來客數 與 客單價", height=400, hovermode="x unified",
        xaxis_title="日期",
        yaxis=dict(title="來客數（人）", side="left"),
        yaxis2=dict(title="客單價（元）", side="right", overlaying="y"),
    )
    return fig


# ============================================================
# 主程式
# ============================================================
def main():
    # 載入資料
    with st.spinner("載入資料中..."):
        data = load_all_data()

    if data.empty:
        st.error("無法載入資料")
        return

    # 側邊欄：垂直分頁選單
    st.sidebar.markdown(
        '<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.25rem">'
        '<i class="bi bi-cup-hot" style="font-size:1.4rem;color:#FF6B6B"></i>'
        '<span style="font-size:1.15rem;font-weight:700">嗑肉石鍋</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"資料更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.sidebar.divider()

    pages = {
        "總覽": page_overview,
        "門店排行": page_store_rank,
        "店對店比較": page_store_compare,
        "週循環分析": page_cycle_week,
        "月循環比較": page_cycle_month,
        "季循環分析": page_cycle_quarter,
        "年循環比較": page_cycle_year,
        "商圈分析": page_region,
        "達標追蹤": page_target,
        "單店下鑽": page_drill,
        "異常警示": page_alert,
    }

    selected = st.sidebar.radio("功能選單", list(pages.keys()), label_visibility="collapsed")

    st.sidebar.divider()

    # 匯出
    if st.sidebar.button("重新載入資料"):
        st.cache_data.clear()
        st.rerun()

    valid_all = data[data["營業額"].notna() & (data["營業額"] > 0)]
    export_df = valid_all[["日期", "區域", "門店", "營業額", "來客數", "客單價", "本月目標", "達成率"]].copy()
    export_df["日期"] = export_df["日期"].dt.strftime("%Y-%m-%d")

    def to_excel(df):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="營收資料")
        return out.getvalue()

    st.sidebar.download_button(
        label="匯出 Excel",
        data=to_excel(export_df),
        file_name=f"嗑肉石鍋_營收_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # 執行選中的分頁
    pages[selected](data)


if __name__ == "__main__":
    main()
