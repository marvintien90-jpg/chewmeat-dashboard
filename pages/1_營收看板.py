"""
嗑肉石鍋 數位總部 — 營收看板
包含：總覽、門店排行、店對店比較、週/月/季/年循環、商圈分析、達標追蹤、單店下鑽、異常警示
"""
import calendar
import io
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.revenue_data import (
    CLOSED_STORES,
    PORTAL_CSS,
    calc_kpi_card,
    get_date_filter,
    load_all_data,
    make_dual_axis,
    make_revenue_bar,
    plotly_chart,
)

# ── 頁面設定 ────────────────────────────────────────────────
st.set_page_config(
    page_title="營收看板 — 嗑肉石鍋",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(PORTAL_CSS, unsafe_allow_html=True)

# ── 側邊欄 ──────────────────────────────────────────────────
st.sidebar.markdown("## 📊 營收看板")
st.sidebar.divider()

sub_pages = {
    "總覽": "overview",
    "門店排行": "store_rank",
    "店對店比較": "store_compare",
    "週循環分析": "week",
    "月循環比較": "month",
    "季循環分析": "quarter",
    "年循環比較": "year",
    "商圈分析": "region",
    "達標追蹤": "target",
    "單店下鑽": "drill",
    "異常警示": "alert",
}
selected = st.sidebar.radio("選擇功能", list(sub_pages.keys()), label_visibility="collapsed")

st.sidebar.divider()
if st.sidebar.button("🔄 重新載入資料"):
    st.cache_data.clear()
    st.rerun()

# ── 載入資料 ────────────────────────────────────────────────
with st.spinner("載入資料中..."):
    data = load_all_data()

if data.empty:
    st.error("無法載入資料，請確認 Google Sheets 連線")
    st.stop()

# Excel 匯出（側邊欄）
valid_all = data[data["營業額"].notna() & (data["營業額"] > 0)]
export_df = valid_all[["日期", "區域", "門店", "營業額", "來客數", "客單價", "本月目標", "達成率"]].copy()
export_df["日期"] = export_df["日期"].dt.strftime("%Y-%m-%d")


def to_excel(df: pd.DataFrame) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="營收資料")
    return out.getvalue()


st.sidebar.download_button(
    label="📥 匯出 Excel",
    data=to_excel(export_df),
    file_name=f"嗑肉石鍋_營收_{datetime.now().strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)


# ════════════════════════════════════════════════════════════
# 各功能頁面
# ════════════════════════════════════════════════════════════

def page_overview(data: pd.DataFrame):
    st.header("📊 總覽")
    filtered, start_d, end_d, _, _ = get_date_filter(data, "ov")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    today = valid["日期"].max().date()
    yr, mn = today.year, today.month

    st.subheader("四大累計指標")
    yoy_total = data[data["營業額"].notna() & (data["營業額"] > 0)]["營業額"].sum()

    y_start = date(yr, 1, 1)
    y_ly_start = date(yr - 1, 1, 1)
    y_ly_end = date(yr - 1, today.month, today.day)
    y_total, y_delta = calc_kpi_card(data, "今年", y_start, today, y_ly_start, y_ly_end)

    q_start_month = ((mn - 1) // 3) * 3 + 1
    q_start = date(yr, q_start_month, 1)
    q_ly_start = date(yr - 1, q_start_month, 1)
    q_ly_end = date(yr - 1, mn, min(today.day, calendar.monthrange(yr - 1, mn)[1]))
    q_total, q_delta = calc_kpi_card(data, "本季", q_start, today, q_ly_start, q_ly_end)

    m_start = date(yr, mn, 1)
    try:
        m_ly_start = date(yr - 1, mn, 1)
        m_ly_end = date(yr - 1, mn, min(today.day, calendar.monthrange(yr - 1, mn)[1]))
    except ValueError:
        m_ly_start = m_ly_end = None
    m_total, m_delta = calc_kpi_card(data, "本月", m_start, today, m_ly_start, m_ly_end)

    cur_month_target = (
        data[(data["日期"].dt.year == yr) & (data["日期"].dt.month == mn)]
        .groupby("門店")["本月目標"].first().sum()
    )
    m_rate = (m_total / cur_month_target * 100) if cur_month_target > 0 else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("曆年累計", f"{yoy_total:,.0f} 元")
    c2.metric("今年累計", f"{y_total:,.0f} 元",
              delta=f"{y_delta:+.1f}% vs 去年" if y_delta is not None else None)
    c3.metric("本季累計", f"{q_total:,.0f} 元",
              delta=f"{q_delta:+.1f}% vs 去年" if q_delta is not None else None)
    c4.metric("本月累計", f"{m_total:,.0f} 元",
              delta=f"達成 {m_rate:.1f}%" if m_rate else None)

    st.divider()

    st.subheader("每日營業額趨勢")
    daily = valid.groupby("日期").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    daily["客單價"] = (daily["營業額"] / daily["來客數"]).round(0)
    plotly_chart(make_revenue_bar(daily), key="ov_daily")
    plotly_chart(make_dual_axis(daily), key="ov_dual")

    st.subheader("區域 / 門店 營收結構")
    sunburst = valid.groupby(["區域", "門店"])["營業額"].sum().reset_index()
    fig_sb = px.sunburst(
        sunburst, path=["區域", "門店"], values="營業額",
        color="營業額", color_continuous_scale=["#FFE4D6", "#E8431A"],
        title="區域 → 門店 佔比",
    )
    fig_sb.update_layout(height=500, paper_bgcolor="#FFFFFF")
    plotly_chart(fig_sb, key="ov_sunburst")


def page_store_rank(data: pd.DataFrame):
    st.header("門店排行")
    filtered, _, _, _, sel_stores = get_date_filter(data, "rk")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    store_sum = valid.groupby(["區域", "門店"]).agg(
        {"營業額": "sum", "來客數": "sum", "本月目標": "first", "達成率": "first"}
    ).reset_index()
    store_sum["客單價"] = (store_sum["營業額"] / store_sum["來客數"]).round(0)
    store_sum = store_sum.sort_values("營業額", ascending=False)

    fig = px.bar(
        store_sum, x="門店", y="營業額", color="區域",
        title="各門店營業額排行", height=450,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(xaxis_tickangle=-45, paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    fig.update_traces(hovertemplate="%{x}<br>營業額：%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="rk_bar")

    if store_sum["達成率"].notna().any():
        st.subheader("前六店達成率儀表板")
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
                        "bar": {"color": "#E8431A"},
                        "steps": [
                            {"range": [0, 50],  "color": "#FFE4D6"},
                            {"range": [50, 80], "color": "#FFD9CC"},
                            {"range": [80, 130], "color": "#FFF5F2"},
                        ],
                        "threshold": {"line": {"color": "#C73A18", "width": 4},
                                      "thickness": 0.75, "value": 100},
                    },
                ))
                fig_g.update_layout(height=200, margin=dict(t=30, b=10, l=10, r=10),
                                    paper_bgcolor="#FFFFFF")
                plotly_chart(fig_g, key=f"gauge_{i}")

    st.subheader("明細表")
    disp = store_sum[["區域", "門店", "營業額", "來客數", "客單價", "達成率"]].copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["達成率"] = disp["達成率"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_store_compare(data: pd.DataFrame):
    st.header("店對店比較")
    filtered, _, _, _, sel_stores = get_date_filter(data, "cmp")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    compare_stores = st.multiselect(
        "選擇 2～4 間門店比較", sel_stores,
        default=sel_stores[:min(2, len(sel_stores))],
        max_selections=4, key="cmp_select",
    )
    if len(compare_stores) < 2:
        st.info("請至少選擇 2 間門店")
        return

    comp = valid[valid["門店"].isin(compare_stores)]
    pivot = comp.pivot_table(index="日期", columns="門店", values="營業額", aggfunc="sum").reset_index()

    colors = ["#E8431A", "#FF6B35", "#45B7D1", "#FFA726"]
    fig = go.Figure()
    for i, s in enumerate(compare_stores):
        if s in pivot.columns:
            fig.add_trace(go.Scatter(
                x=pivot["日期"], y=pivot[s], mode="lines+markers", name=s,
                line=dict(color=colors[i % 4], width=2),
                hovertemplate=f"{s}<br>%{{x|%m/%d}}<br>%{{y:,.0f}} 元<extra></extra>",
            ))
    fig.update_layout(title="每日營業額對比", height=400, hovermode="x unified",
                      paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    plotly_chart(fig, key="cmp_line")

    radar = comp.groupby("門店").agg({"營業額": "sum", "來客數": "sum", "客單價": "mean"}).reset_index()
    cats = ["營業額", "來客數", "客單價"]
    fig_r = go.Figure()
    for i, s in enumerate(compare_stores):
        row = radar[radar["門店"] == s]
        if row.empty:
            continue
        vals = [row[c].values[0] / radar[c].max() * 100 if radar[c].max() > 0 else 0 for c in cats]
        vals.append(vals[0])
        fig_r.add_trace(go.Scatterpolar(
            r=vals, theta=cats + [cats[0]], fill="toself", name=s,
            line=dict(color=colors[i % 4]),
        ))
    fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                        title="綜合指標雷達圖（標準化%）", height=450,
                        paper_bgcolor="#FFFFFF")
    plotly_chart(fig_r, key="cmp_radar")


def page_cycle_week(data: pd.DataFrame):
    st.header("週循環分析")
    filtered, _, _, _, _ = get_date_filter(data, "wk")
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
    wk_sum = wk_data.groupby("年週").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    wk_sum["客單價"] = (wk_sum["營業額"] / wk_sum["來客數"]).round(0)
    wk_sum = wk_sum.sort_values("年週")

    st.subheader("週摘要")
    disp = wk_sum.copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    st.dataframe(disp, use_container_width=True, hide_index=True)

    wd = wk_data.groupby(["年週", "星期", "星期名"])["營業額"].sum().reset_index().sort_values("星期")
    fig = px.bar(wd, x="星期名", y="營業額", color="年週", barmode="group", height=400,
                 color_discrete_sequence=["#E8431A", "#FF6B35", "#FFA07A"])
    fig.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    fig.update_traces(hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="wk_weekday")

    st.subheader("熱力圖：各門店每日營業額")
    heat = wk_data.pivot_table(index="門店", columns="日期", values="營業額", aggfunc="sum")
    if not heat.empty:
        fig_h = px.imshow(
            heat.values,
            labels=dict(x="日期", y="門店", color="營業額"),
            x=[d.strftime("%m/%d") for d in heat.columns],
            y=heat.index.tolist(),
            color_continuous_scale=["#FFF5F2", "#E8431A"], aspect="auto",
        )
        fig_h.update_layout(height=max(400, len(heat) * 25), paper_bgcolor="#FFFFFF")
        plotly_chart(fig_h, key="wk_heat")


def page_cycle_month(data: pd.DataFrame):
    st.header("月循環比較")
    filtered, _, _, _, _ = get_date_filter(data, "mo")
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
    monthly = mo_data.groupby("年月").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    monthly["客單價"] = (monthly["營業額"] / monthly["來客數"]).round(0)
    monthly["成長率"] = monthly["營業額"].pct_change() * 100
    monthly = monthly.sort_values("年月")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=monthly["年月"], y=monthly["營業額"], name="營業額",
                         marker_color="#E8431A",
                         hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>"))
    fig.add_trace(go.Scatter(x=monthly["年月"], y=monthly["客單價"], name="客單價",
                              mode="lines+markers", line=dict(color="#C73A18", width=2),
                              yaxis="y2",
                              hovertemplate="客單價：%{y:,.0f} 元<extra></extra>"))
    fig.update_layout(title="月度趨勢", height=400, hovermode="x unified",
                      yaxis=dict(title="營業額（元）"),
                      yaxis2=dict(title="客單價（元）", side="right", overlaying="y"),
                      paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    plotly_chart(fig, key="mo_trend")

    disp = monthly.copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["成長率"] = disp["成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    disp = disp.rename(columns={"年月": "月份"})
    st.dataframe(disp[["月份", "營業額", "來客數", "客單價", "成長率"]],
                 use_container_width=True, hide_index=True)


def page_cycle_quarter(data: pd.DataFrame):
    st.header("季循環分析")
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
                 color="營業額", color_continuous_scale=["#FFE4D6", "#E8431A"],
                 title="季度營業額", height=400)
    fig.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    fig.update_traces(hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="qt_bar")

    disp = q_sum.sort_values("年季").copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["成長率"] = disp["成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_cycle_year(data: pd.DataFrame):
    st.header("年循環比較")
    filtered, _, _, _, _ = get_date_filter(data, "yr")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    years = sorted(valid["年份"].unique())
    yr_sum = valid.groupby("年份").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    yr_sum["客單價"] = (yr_sum["營業額"] / yr_sum["來客數"]).round(0)
    yr_sum["成長率"] = yr_sum["營業額"].pct_change() * 100

    fig = px.bar(yr_sum, x="年份", y="營業額",
                 text=yr_sum["營業額"].apply(lambda x: f"{x/10000:,.0f}萬"),
                 color="年份", title="年度營業額", height=400,
                 color_discrete_sequence=["#E8431A", "#FF6B35", "#FFA07A"])
    fig.update_traces(textposition="outside",
                      hovertemplate="%{x}年<br>%{y:,.0f} 元<extra></extra>")
    fig.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    plotly_chart(fig, key="yr_bar")

    if len(years) > 1:
        st.subheader("年度同月營業額對比")
        ym = valid.groupby(["年份", "月份"]).agg({"營業額": "sum"}).reset_index()
        fig_y = go.Figure()
        year_colors = ["#E8431A", "#FF6B35", "#FFA07A"]
        for i, y in enumerate(years):
            yd = ym[ym["年份"] == y].sort_values("月份")
            fig_y.add_trace(go.Bar(
                x=[f"{m}月" for m in yd["月份"]], y=yd["營業額"],
                name=f"{y}年", marker_color=year_colors[i % 3],
                hovertemplate=f"{y}年 %{{x}}<br>%{{y:,.0f}} 元<extra></extra>",
            ))
        fig_y.update_layout(barmode="group", height=400,
                             paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
        plotly_chart(fig_y, key="yr_yoy")

    disp = yr_sum.copy()
    disp["年份"] = disp["年份"].astype(str) + "年"
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["成長率"] = disp["成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_region(data: pd.DataFrame):
    st.header("商圈 / 區域競爭分析")
    filtered, _, _, _, _ = get_date_filter(data, "rg")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    rg_sum = valid.groupby("區域").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    rg_sum["客單價"] = (rg_sum["營業額"] / rg_sum["來客數"]).round(0)
    rg_sum = rg_sum.sort_values("營業額", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(rg_sum, x="區域", y="營業額", color="區域",
                     text=rg_sum["營業額"].apply(lambda x: f"{x/10000:,.0f}萬"),
                     title="各區域總營業額", height=350,
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_traces(textposition="outside",
                          hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>")
        fig.update_layout(showlegend=False, paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
        plotly_chart(fig, key="rg_bar")
    with c2:
        fig_pie = px.pie(rg_sum, values="營業額", names="區域", title="區域營收佔比", hole=0.4,
                         color_discrete_sequence=["#E8431A", "#FF6B35", "#FFA07A",
                                                  "#FFD9CC", "#C73A18", "#45B7D1"])
        fig_pie.update_traces(hovertemplate="%{label}<br>%{value:,.0f} 元<br>%{percent}<extra></extra>")
        fig_pie.update_layout(height=350, paper_bgcolor="#FFFFFF")
        plotly_chart(fig_pie, key="rg_pie")

    sel_region = st.selectbox("選擇區域查看內部競爭", sorted(valid["區域"].dropna().unique()))
    rg_stores = valid[valid["區域"] == sel_region].groupby("門店").agg(
        {"營業額": "sum", "來客數": "sum", "達成率": "first"}
    ).reset_index()
    rg_stores["客單價"] = (rg_stores["營業額"] / rg_stores["來客數"]).round(0)
    rg_stores = rg_stores.sort_values("營業額", ascending=False)
    avg_rev = rg_stores["營業額"].mean()

    colors = ["#44BB44" if r > avg_rev else "#E8431A" for r in rg_stores["營業額"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=rg_stores["門店"], y=rg_stores["營業額"], marker_color=colors,
                         hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>"))
    fig.add_hline(y=avg_rev, line_dash="dash", line_color="#C73A18",
                  annotation_text=f"區域平均 {avg_rev:,.0f} 元")
    fig.update_layout(title=f"【{sel_region}】門店營業額（綠=高於平均）",
                      height=350, xaxis_tickangle=-45,
                      paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    plotly_chart(fig, key="rg_inner")

    disp = rg_stores.copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["達成率"] = disp["達成率"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_target(data: pd.DataFrame):
    st.header("本月達標進度追蹤")
    today = data["日期"].max().date()
    yr, mn = today.year, today.month
    days_in_month = calendar.monthrange(yr, mn)[1]
    day_of_month = today.day

    st.info(f"基準日：{today.strftime('%Y-%m-%d')} ｜ 進度 {day_of_month}/{days_in_month} 天（{day_of_month/days_in_month*100:.0f}%）")

    cur = data[(data["日期"].dt.year == yr) & (data["日期"].dt.month == mn)]
    cur = cur[cur["營業額"].notna() & (cur["營業額"] > 0) & ~cur["門店"].isin(CLOSED_STORES)]

    if cur.empty:
        st.warning("本月尚無資料")
        return

    prog = cur.groupby(["區域", "門店"]).agg(
        {"營業額": "sum", "來客數": "sum", "本月目標": "first"}
    ).reset_index()
    prog["已營業天數"] = cur.groupby("門店")["日期"].nunique().values
    prog["日均實際"] = (prog["營業額"] / prog["已營業天數"]).round(0)
    prog["預估月營收"] = (prog["日均實際"] * days_in_month).round(0)
    prog["預估達成率"] = (prog["預估月營收"] / prog["本月目標"] * 100).round(1)
    prog["目前達成率"] = (prog["營業額"] / prog["本月目標"] * 100).round(1)
    prog["狀態"] = prog["預估達成率"].apply(
        lambda x: "可達標" if x >= 100 else ("略低" if x >= 85 else "危險")
    )
    prog = prog.sort_values("預估達成率", ascending=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("預估可達標", f"{len(prog[prog['預估達成率'] >= 100])} 店")
    c2.metric("預估危險", f"{len(prog[prog['預估達成率'] < 85])} 店")
    c3.metric("本月剩餘天數", f"{days_in_month - day_of_month} 天")

    colors = [
        "#44BB44" if r >= 100 else ("#FFaa00" if r >= 85 else "#E8431A")
        for r in prog["預估達成率"]
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=prog["門店"], y=prog["預估達成率"],
        marker_color=colors,
        text=[f"{r:.0f}%" for r in prog["預估達成率"]],
        textposition="outside",
        hovertemplate="%{x}<br>預估達成率：%{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=100, line_dash="dash", line_color="#C73A18", annotation_text="目標 100%")
    fig.update_layout(title=f"{yr}年{mn}月 各門店預估達成率",
                      height=450, xaxis_tickangle=-45,
                      paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    plotly_chart(fig, key="tg_bar")

    disp = prog[["區域", "門店", "營業額", "本月目標", "目前達成率",
                 "日均實際", "預估月營收", "預估達成率", "狀態"]].copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["本月目標"] = disp["本月目標"].apply(lambda x: f"{x:,.0f} 元" if pd.notna(x) else "—")
    disp["日均實際"] = disp["日均實際"].apply(lambda x: f"{x:,.0f} 元")
    disp["預估月營收"] = disp["預估月營收"].apply(lambda x: f"{x:,.0f} 元")
    disp["目前達成率"] = disp["目前達成率"].apply(lambda x: f"{x:.1f}%")
    disp["預估達成率"] = disp["預估達成率"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_drill(data: pd.DataFrame):
    st.header("單店下鑽分析")
    filtered, _, _, _, sel_stores = get_date_filter(data, "dr")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if not sel_stores:
        st.warning("請在篩選條件中至少選擇 1 間門店")
        return

    store = st.selectbox("選擇門店", sel_stores, key="dr_store")
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
                              line=dict(color="#E8431A", width=2), fill="tozeroy",
                              hovertemplate="%{x|%m/%d}<br>%{y:,.0f} 元<extra></extra>"))
    fig.update_layout(title=f"{store} — 每日營業額走勢", height=350,
                      paper_bgcolor="#FFFFFF", plot_bgcolor="#FFF5F2")
    plotly_chart(fig, key="dr_line")

    wd = sd.groupby(["星期", "星期名"]).agg({"營業額": "mean"}).reset_index().sort_values("星期")
    fig_w = px.bar(wd, x="星期名", y="營業額",
                   color="營業額", color_continuous_scale=["#FFE4D6", "#E8431A"],
                   title=f"{store} — 平均營業額（按星期）", height=300)
    fig_w.update_traces(hovertemplate="%{x}<br>平均 %{y:,.0f} 元<extra></extra>")
    fig_w.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    plotly_chart(fig_w, key="dr_weekday")


def page_alert(data: pd.DataFrame):
    st.header("未達日均目標警示")
    filtered, _, _, _, _ = get_date_filter(data, "al")
    alert_data = filtered.copy()
    alert_data["當月天數"] = alert_data["日期"].apply(
        lambda x: calendar.monthrange(x.year, x.month)[1]
    )
    alert_data["日均目標"] = alert_data["本月目標"] / alert_data["當月天數"]
    hs = alert_data[
        alert_data["日均目標"].notna() & (alert_data["日均目標"] > 0)
        & alert_data["營業額"].notna()
    ].copy()

    if hs.empty:
        st.warning("無足夠資料")
        return

    hs["未達標"] = hs["營業額"] < hs["日均目標"]
    hs["差額"] = (hs["日均目標"] - hs["營業額"]).clip(lower=0)

    sa = hs.groupby(["區域", "門店"]).agg(
        有效天數=("營業額", "count"),
        未達標次數=("未達標", "sum"),
        損失營業額=("差額", "sum"),
        日均目標=("日均目標", "mean"),
        實際日均=("營業額", "mean"),
    ).reset_index()
    sa["未達標率"] = (sa["未達標次數"] / sa["有效天數"] * 100).round(1)
    sa = sa.sort_values("損失營業額", ascending=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("全店未達標次數", f"{int(sa['未達標次數'].sum())} 次")
    c2.metric("累計損失營業額", f"{sa['損失營業額'].sum():,.0f} 元")
    c3.metric("損失最多門店", sa.iloc[0]["門店"] if len(sa) else "—")

    colors = ["#E8431A" if r > 50 else "#FFaa00" for r in sa["未達標率"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sa["門店"], y=sa["損失營業額"],
        marker_color=colors,
        hovertemplate="%{x}<br>損失：%{y:,.0f} 元<extra></extra>",
    ))
    fig.update_layout(title="各門店累計損失營業額", height=400, xaxis_tickangle=-45,
                      paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    plotly_chart(fig, key="al_loss")

    disp = sa[["區域", "門店", "有效天數", "未達標次數", "未達標率", "日均目標", "實際日均", "損失營業額"]].copy()
    disp["日均目標"] = disp["日均目標"].apply(lambda x: f"{x:,.0f} 元")
    disp["實際日均"] = disp["實際日均"].apply(lambda x: f"{x:,.0f} 元")
    disp["損失營業額"] = disp["損失營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["未達標次數"] = disp["未達標次數"].astype(int).astype(str) + " 次"
    disp["未達標率"] = disp["未達標率"].apply(lambda x: f"{x:.1f}%")
    disp["有效天數"] = disp["有效天數"].astype(int).astype(str) + " 天"
    st.dataframe(disp, use_container_width=True, hide_index=True)


# ── 路由 ─────────────────────────────────────────────────────
route = sub_pages[selected]
{
    "overview":     page_overview,
    "store_rank":   page_store_rank,
    "store_compare": page_store_compare,
    "week":         page_cycle_week,
    "month":        page_cycle_month,
    "quarter":      page_cycle_quarter,
    "year":         page_cycle_year,
    "region":       page_region,
    "target":       page_target,
    "drill":        page_drill,
    "alert":        page_alert,
}[route](data)
