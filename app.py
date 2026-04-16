import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import warnings
import re
import numpy as np

warnings.filterwarnings("ignore")

# ============================================================
# 基本設定
# ============================================================
SHEET_ID = "1NZQEJgL-HkB08JSW6zsVHRSyl_XgwLc5etUqSF0O9ow"

SHEET_GIDS = {
    "2025-01": "672482866",
    "2025-02": "1943981506",
    "2025-03": "847955849",
    "2025-04": "591730250",
    "2025-05": "695013616",
    "2025-06": "897256004",
    "2025-07": "593028448",
    "2025-08": "836455215",
    "2025-09": "1728608975",
    "2025-10": "2043079442",
    "2025-11": "1307429413",
    "2025-12": "1838876978",
    "2026-01": "872131612",
    "2026-02": "162899314",
    "2026-03": "1575135129",
    "2026-04": "1702412906",
    "2026-05": "1499115222",
    "2026-06": "467088033",
}

WEEKDAY_MAP = {0: "週一", 1: "週二", 2: "週三", 3: "週四", 4: "週五", 5: "週六", 6: "週日"}

st.set_page_config(
    page_title="嗑肉石鍋 營收儀表板",
    page_icon="🍲",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 資料讀取與解析
# ============================================================
@st.cache_data(ttl=3600)
def load_sheet(year_month, gid):
    """從 Google 試算表讀取單月資料並解析成扁平表格"""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    try:
        raw = pd.read_csv(url, header=None)
    except Exception:
        return pd.DataFrame()

    year, month = year_month.split("-")
    year = int(year)
    month = int(month)

    date_row = raw.iloc[1, 7:]
    dates = []
    for val in date_row:
        s = str(val).strip()
        if s == "nan" or s == "合計":
            continue
        match = re.match(r"(\d+)/(\d+)", s)
        if match:
            m, d = int(match.group(1)), int(match.group(2))
            if m != month:
                continue
            try:
                dates.append(date(year, m, d))
            except ValueError:
                continue

    if not dates:
        return pd.DataFrame()

    rows = []
    current_region = None
    current_store = None
    current_target = None
    current_rate = None

    for i in range(2, len(raw)):
        row = raw.iloc[i]

        if pd.notna(row.iloc[0]) and str(row.iloc[0]).strip():
            current_region = str(row.iloc[0]).strip()
        if pd.notna(row.iloc[1]) and str(row.iloc[1]).strip():
            current_store = str(row.iloc[1]).strip()
        if pd.notna(row.iloc[2]) and str(row.iloc[2]).strip():
            raw_target = str(row.iloc[2]).replace(",", "").strip()
            try:
                current_target = float(raw_target)
            except ValueError:
                current_target = None
        if pd.notna(row.iloc[3]) and str(row.iloc[3]).strip():
            raw_rate = str(row.iloc[3]).replace("%", "").strip()
            try:
                current_rate = float(raw_rate) / 100
            except ValueError:
                current_rate = None

        metric = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else ""
        if metric not in ["業績合計", "人數合計", "平均客單"]:
            continue
        if not current_store:
            continue

        data_cols = row.iloc[7:]
        values = []
        for val in data_cols:
            s = str(val).strip().replace(",", "").replace(" ", "")
            if s in ["nan", "", "#DIV/0!", "\\#DIV/0\\!", "#DIV/0!"]:
                values.append(None)
            else:
                try:
                    values.append(float(s))
                except ValueError:
                    values.append(None)

        day_values = []
        for idx in range(0, len(values), 2):
            if idx // 2 < len(dates):
                day_values.append(values[idx] if idx < len(values) else None)

        for day_idx, dt in enumerate(dates):
            val = day_values[day_idx] if day_idx < len(day_values) else None
            rows.append({
                "日期": dt, "區域": current_region, "門店": current_store,
                "本月目標": current_target, "達成率": current_rate,
                "指標": metric, "數值": val,
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    pivot = df.pivot_table(
        index=["日期", "區域", "門店", "本月目標", "達成率"],
        columns="指標", values="數值", aggfunc="first",
    ).reset_index()
    pivot.columns.name = None

    rename_map = {}
    if "業績合計" in pivot.columns:
        rename_map["業績合計"] = "營業額"
    if "人數合計" in pivot.columns:
        rename_map["人數合計"] = "來客數"
    if "平均客單" in pivot.columns:
        rename_map["平均客單"] = "客單價"
    pivot = pivot.rename(columns=rename_map)

    for col in ["營業額", "來客數", "客單價"]:
        if col not in pivot.columns:
            pivot[col] = None

    return pivot


@st.cache_data(ttl=3600)
def load_all_data():
    """載入所有月份資料"""
    all_dfs = []
    for ym, gid in SHEET_GIDS.items():
        df = load_sheet(ym, gid)
        if not df.empty:
            all_dfs.append(df)
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()


def fmt_num(x):
    """格式化數字：加千分位"""
    if pd.isna(x) or x == 0:
        return "—"
    return f"{x:,.0f}"


def fmt_pct(x):
    """格式化百分比"""
    if pd.isna(x):
        return "—"
    return f"{x:.1f}%"


# ============================================================
# 主程式
# ============================================================
def main():
    st.title("🍲 嗑肉石鍋 — 營收數位儀表板")
    st.caption(f"資料更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with st.spinner("正在從 Google 試算表載入資料，請稍候..."):
        data = load_all_data()

    if data.empty:
        st.error("無法載入資料，請確認 Google 試算表已設為公開檢視。")
        return

    data["日期"] = pd.to_datetime(data["日期"])

    # 新增時間維度欄位
    data["年份"] = data["日期"].dt.year
    data["月份"] = data["日期"].dt.month
    data["年月"] = data["日期"].dt.to_period("M").astype(str)
    data["週次"] = data["日期"].dt.isocalendar().week.astype(int)
    data["年週"] = data["日期"].dt.strftime("%G-W%V")
    data["星期"] = data["日期"].dt.dayofweek
    data["星期名"] = data["星期"].map(WEEKDAY_MAP)

    # --------------------------------------------------------
    # 側邊欄：篩選器
    # --------------------------------------------------------
    st.sidebar.header("📊 篩選條件")

    min_date = data["日期"].min().date()
    max_date = data["日期"].max().date()
    date_range = st.sidebar.date_input(
        "選擇日期範圍",
        value=(min_date, max_date),
        min_value=min_date, max_value=max_date,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    regions = sorted(data["區域"].dropna().unique().tolist())
    selected_regions = st.sidebar.multiselect("選擇區域", regions, default=regions)

    available_stores = sorted(
        data[data["區域"].isin(selected_regions)]["門店"].dropna().unique().tolist()
    )
    selected_stores = st.sidebar.multiselect("選擇門店", available_stores, default=available_stores)

    mask = (
        (data["日期"].dt.date >= start_date)
        & (data["日期"].dt.date <= end_date)
        & (data["區域"].isin(selected_regions))
        & (data["門店"].isin(selected_stores))
    )
    filtered = data[mask].copy()

    if filtered.empty:
        st.warning("篩選後無資料，請調整篩選條件。")
        return

    if st.sidebar.button("🔄 重新載入資料"):
        st.cache_data.clear()
        st.rerun()

    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    # --------------------------------------------------------
    # 頂部 KPI
    # --------------------------------------------------------
    total_rev = valid["營業額"].sum()
    total_cust = valid["來客數"].sum()
    avg_ticket = total_rev / total_cust if total_cust > 0 else 0
    active_days = valid["日期"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 總營業額", f"{fmt_num(total_rev)} 元")
    c2.metric("👥 總來客數", f"{fmt_num(total_cust)} 人")
    c3.metric("🧾 平均客單價", f"{fmt_num(avg_ticket)} 元")
    c4.metric("📅 有效營業天數", f"{active_days} 天")

    st.divider()

    # --------------------------------------------------------
    # 分頁
    # --------------------------------------------------------
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📈 總覽", "🏪 門店排行", "🔄 店對店比較",
        "📅 週循環分析", "📊 月循環比較", "🔍 單店下鑽", "⚠️ 異常警示",
    ])

    # ==========================================================
    # 分頁 1：總覽
    # ==========================================================
    with tab1:
        st.subheader("每日營收趨勢")

        daily = valid.groupby("日期").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
        daily["客單價"] = (daily["營業額"] / daily["來客數"]).round(0)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily["日期"], y=daily["營業額"], name="營業額",
            marker_color="#4ECDC4",
            hovertemplate="日期：%{x|%Y-%m-%d}<br>營業額：%{y:,.0f} 元<extra></extra>",
        ))
        fig.update_layout(
            title="全店每日營業額", xaxis_title="日期", yaxis_title="營業額（元）",
            height=400, hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=daily["日期"], y=daily["來客數"], name="來客數",
            marker_color="#45B7D1", yaxis="y",
            hovertemplate="來客數：%{y:,.0f} 人<extra></extra>",
        ))
        fig2.add_trace(go.Scatter(
            x=daily["日期"], y=daily["客單價"], name="客單價",
            mode="lines+markers", line=dict(color="#FF6B6B", width=2), yaxis="y2",
            hovertemplate="客單價：%{y:,.0f} 元<extra></extra>",
        ))
        fig2.update_layout(
            title="來客數 與 客單價", xaxis_title="日期",
            yaxis=dict(title="來客數（人）", side="left"),
            yaxis2=dict(title="客單價（元）", side="right", overlaying="y"),
            height=400, hovermode="x unified",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ==========================================================
    # 分頁 2：門店排行
    # ==========================================================
    with tab2:
        st.subheader("門店業績排行")

        store_sum = valid.groupby(["區域", "門店"]).agg({
            "營業額": "sum", "來客數": "sum", "本月目標": "first", "達成率": "first",
        }).reset_index()
        store_sum["客單價"] = (store_sum["營業額"] / store_sum["來客數"]).round(0)
        store_sum = store_sum.sort_values("營業額", ascending=False)

        fig3 = px.bar(
            store_sum, x="門店", y="營業額", color="區域",
            title="各門店營業額排行", height=450,
        )
        fig3.update_layout(xaxis_tickangle=-45)
        fig3.update_traces(hovertemplate="門店：%{x}<br>營業額：%{y:,.0f} 元<extra></extra>")
        st.plotly_chart(fig3, use_container_width=True)

        if store_sum["達成率"].notna().any():
            st.subheader("目標達成率")
            rate_data = store_sum[store_sum["達成率"].notna()].copy()
            rate_data["達成率百分比"] = rate_data["達成率"] * 100

            fig4 = go.Figure()
            colors = [
                "#FF4444" if r < 50 else ("#FFaa00" if r < 80 else "#44BB44")
                for r in rate_data["達成率百分比"]
            ]
            fig4.add_trace(go.Bar(
                x=rate_data["門店"], y=rate_data["達成率百分比"],
                marker_color=colors,
                text=[f"{r:.1f}%" for r in rate_data["達成率百分比"]],
                textposition="outside",
                hovertemplate="門店：%{x}<br>達成率：%{text}<extra></extra>",
            ))
            fig4.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="目標 100%")
            fig4.update_layout(
                title="各門店目標達成率", xaxis_title="門店", yaxis_title="達成率（%）",
                height=450, xaxis_tickangle=-45,
            )
            st.plotly_chart(fig4, use_container_width=True)

        st.subheader("門店明細表")
        disp = store_sum[["區域", "門店", "營業額", "來客數", "客單價", "達成率"]].copy()
        disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
        disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
        disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
        disp["達成率"] = disp["達成率"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
        st.dataframe(disp, use_container_width=True, hide_index=True)

    # ==========================================================
    # 分頁 3：店對店比較 ⭐ 新增
    # ==========================================================
    with tab3:
        st.subheader("店對店比較")

        compare_stores = st.multiselect(
            "選擇 2～4 間門店進行比較", selected_stores,
            default=selected_stores[:min(2, len(selected_stores))],
            max_selections=4,
        )

        if len(compare_stores) < 2:
            st.info("請至少選擇 2 間門店進行比較。")
        else:
            comp_data = valid[valid["門店"].isin(compare_stores)]

            # 每日營業額對比
            pivot_rev = comp_data.pivot_table(
                index="日期", columns="門店", values="營業額", aggfunc="sum",
            ).reset_index()

            fig_comp = go.Figure()
            colors = ["#4ECDC4", "#FF6B6B", "#45B7D1", "#FFA726"]
            for i, store in enumerate(compare_stores):
                if store in pivot_rev.columns:
                    fig_comp.add_trace(go.Scatter(
                        x=pivot_rev["日期"], y=pivot_rev[store],
                        mode="lines+markers", name=store,
                        line=dict(color=colors[i % 4], width=2),
                        hovertemplate=f"{store}<br>日期：%{{x|%m/%d}}<br>營業額：%{{y:,.0f}} 元<extra></extra>",
                    ))
            fig_comp.update_layout(
                title="各店每日營業額對比", xaxis_title="日期", yaxis_title="營業額（元）",
                height=400, hovermode="x unified",
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            # 來客數對比
            pivot_cust = comp_data.pivot_table(
                index="日期", columns="門店", values="來客數", aggfunc="sum",
            ).reset_index()

            fig_cust = go.Figure()
            for i, store in enumerate(compare_stores):
                if store in pivot_cust.columns:
                    fig_cust.add_trace(go.Scatter(
                        x=pivot_cust["日期"], y=pivot_cust[store],
                        mode="lines+markers", name=store,
                        line=dict(color=colors[i % 4], width=2),
                        hovertemplate=f"{store}<br>來客數：%{{y:,.0f}} 人<extra></extra>",
                    ))
            fig_cust.update_layout(
                title="各店每日來客數對比", xaxis_title="日期", yaxis_title="來客數（人）",
                height=400, hovermode="x unified",
            )
            st.plotly_chart(fig_cust, use_container_width=True)

            # 雷達圖：多指標綜合對比
            st.subheader("綜合指標雷達圖")
            radar_data = comp_data.groupby("門店").agg({
                "營業額": "sum", "來客數": "sum", "客單價": "mean",
            }).reset_index()

            categories = ["營業額", "來客數", "客單價"]
            fig_radar = go.Figure()
            for i, store in enumerate(compare_stores):
                row = radar_data[radar_data["門店"] == store]
                if row.empty:
                    continue
                vals = []
                for cat in categories:
                    col_max = radar_data[cat].max()
                    vals.append(row[cat].values[0] / col_max * 100 if col_max > 0 else 0)
                vals.append(vals[0])
                fig_radar.add_trace(go.Scatterpolar(
                    r=vals, theta=categories + [categories[0]],
                    fill="toself", name=store,
                    line=dict(color=colors[i % 4]),
                ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                title="門店綜合指標對比（標準化百分比）", height=450,
            )
            st.plotly_chart(fig_radar, use_container_width=True)

    # ==========================================================
    # 分頁 4：週循環分析 ⭐ 新增
    # ==========================================================
    with tab4:
        st.subheader("週循環分析")

        # 取得所有可用的年週
        available_weeks = sorted(valid["年週"].unique(), reverse=True)
        if len(available_weeks) < 1:
            st.warning("資料不足，無法進行週循環分析。")
        else:
            # 本週 vs 上週 vs 上上週
            selected_week = st.selectbox("選擇要分析的週次", available_weeks[:20], index=0)
            week_idx = available_weeks.index(selected_week)

            weeks_to_compare = []
            labels = ["本週", "上週", "前兩週"]
            for i in range(3):
                if week_idx + i < len(available_weeks):
                    weeks_to_compare.append(available_weeks[week_idx + i])

            if weeks_to_compare:
                st.subheader("週營業額對比")
                week_data = valid[valid["年週"].isin(weeks_to_compare)]

                week_summary = week_data.groupby("年週").agg({
                    "營業額": "sum", "來客數": "sum",
                }).reset_index()
                week_summary["客單價"] = (week_summary["營業額"] / week_summary["來客數"]).round(0)
                week_summary = week_summary.sort_values("年週", ascending=False)

                # 週對比表格
                week_disp = week_summary.copy()
                label_map = {}
                for i, w in enumerate(weeks_to_compare):
                    if i < len(labels):
                        label_map[w] = f"{labels[i]}（{w}）"
                week_disp["週次"] = week_disp["年週"].map(label_map)
                week_disp["營業額"] = week_disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
                week_disp["來客數"] = week_disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
                week_disp["客單價"] = week_disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
                st.dataframe(
                    week_disp[["週次", "營業額", "來客數", "客單價"]],
                    use_container_width=True, hide_index=True,
                )

                # 週循環：各天對比
                st.subheader("各日營業額對比（按星期）")
                week_daily = week_data.copy()
                week_daily["週標籤"] = week_daily["年週"].map(label_map)

                wd_pivot = week_daily.groupby(["星期名", "星期", "週標籤"]).agg({
                    "營業額": "sum"
                }).reset_index().sort_values("星期")

                fig_week = px.bar(
                    wd_pivot, x="星期名", y="營業額", color="週標籤",
                    barmode="group", title="各日營業額對比（按星期）",
                    height=400,
                )
                fig_week.update_layout(xaxis_title="星期", yaxis_title="營業額（元）")
                fig_week.update_traces(hovertemplate="%{x}<br>營業額：%{y:,.0f} 元<extra></extra>")
                st.plotly_chart(fig_week, use_container_width=True)

            # 週幾效應熱力圖
            st.subheader("門店「週幾效應」熱力圖")
            st.caption("顏色越深 = 該日營業額越高")

            heatmap_data = valid.groupby(["門店", "星期名", "星期"]).agg({
                "營業額": "mean"
            }).reset_index().sort_values("星期")

            heatmap_pivot = heatmap_data.pivot_table(
                index="門店", columns="星期名", values="營業額",
            )
            weekday_order = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
            heatmap_pivot = heatmap_pivot.reindex(columns=[w for w in weekday_order if w in heatmap_pivot.columns])

            fig_heat = px.imshow(
                heatmap_pivot.values,
                labels=dict(x="星期", y="門店", color="平均營業額"),
                x=heatmap_pivot.columns.tolist(),
                y=heatmap_pivot.index.tolist(),
                color_continuous_scale="YlOrRd",
                aspect="auto",
                title="各門店平均每日營業額（按星期）",
            )
            fig_heat.update_layout(height=max(400, len(heatmap_pivot) * 25))
            st.plotly_chart(fig_heat, use_container_width=True)

    # ==========================================================
    # 分頁 5：月循環比較 ⭐ 新增
    # ==========================================================
    with tab5:
        st.subheader("月循環比較")

        # 月度趨勢
        monthly = valid.groupby("年月").agg({
            "營業額": "sum", "來客數": "sum",
        }).reset_index()
        monthly["客單價"] = (monthly["營業額"] / monthly["來客數"]).round(0)
        monthly = monthly.sort_values("年月")

        fig_monthly = go.Figure()
        fig_monthly.add_trace(go.Bar(
            x=monthly["年月"], y=monthly["營業額"], name="營業額",
            marker_color="#4ECDC4",
            hovertemplate="月份：%{x}<br>營業額：%{y:,.0f} 元<extra></extra>",
        ))
        fig_monthly.add_trace(go.Scatter(
            x=monthly["年月"], y=monthly["客單價"], name="客單價",
            mode="lines+markers", line=dict(color="#FF6B6B", width=2),
            yaxis="y2",
            hovertemplate="客單價：%{y:,.0f} 元<extra></extra>",
        ))
        fig_monthly.update_layout(
            title="每月營業額趨勢", xaxis_title="月份", yaxis_title="營業額（元）",
            yaxis2=dict(title="客單價（元）", side="right", overlaying="y"),
            height=400, hovermode="x unified",
        )
        st.plotly_chart(fig_monthly, use_container_width=True)

        # 月度成長率
        st.subheader("月度成長率")
        monthly_growth = monthly.copy()
        monthly_growth["營業額成長率"] = monthly_growth["營業額"].pct_change() * 100
        monthly_growth["來客數成長率"] = monthly_growth["來客數"].pct_change() * 100

        growth_disp = monthly_growth.copy()
        growth_disp["營業額"] = growth_disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
        growth_disp["來客數"] = growth_disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
        growth_disp["客單價"] = growth_disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
        growth_disp["營業額成長率"] = growth_disp["營業額成長率"].apply(
            lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
        )
        growth_disp["來客數成長率"] = growth_disp["來客數成長率"].apply(
            lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
        )
        growth_disp = growth_disp.rename(columns={"年月": "月份"})
        st.dataframe(
            growth_disp[["月份", "營業額", "來客數", "客單價", "營業額成長率", "來客數成長率"]],
            use_container_width=True, hide_index=True,
        )

        # 年同期比較（如果有跨年資料）
        years = sorted(valid["年份"].unique())
        if len(years) > 1:
            st.subheader("年度同期比較")
            year_month_data = valid.groupby(["年份", "月份"]).agg({
                "營業額": "sum",
            }).reset_index()

            fig_yoy = go.Figure()
            year_colors = ["#4ECDC4", "#FF6B6B", "#45B7D1"]
            for i, yr in enumerate(years):
                yr_data = year_month_data[year_month_data["年份"] == yr].sort_values("月份")
                month_labels = [f"{m}月" for m in yr_data["月份"]]
                fig_yoy.add_trace(go.Bar(
                    x=month_labels, y=yr_data["營業額"], name=f"{yr}年",
                    marker_color=year_colors[i % 3],
                    hovertemplate=f"{yr}年<br>%{{x}}<br>營業額：%{{y:,.0f}} 元<extra></extra>",
                ))
            fig_yoy.update_layout(
                title="年度同月營業額比較", xaxis_title="月份", yaxis_title="營業額（元）",
                barmode="group", height=400,
            )
            st.plotly_chart(fig_yoy, use_container_width=True)

    # ==========================================================
    # 分頁 6：單店下鑽
    # ==========================================================
    with tab6:
        st.subheader("單店下鑽分析")

        drill_store = st.selectbox("選擇要分析的門店", selected_stores)
        store_data = valid[valid["門店"] == drill_store].sort_values("日期")

        if store_data.empty:
            st.warning("此門店在選定期間無資料。")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("門店營業額", f"{fmt_num(store_data['營業額'].sum())} 元")
            c2.metric("門店來客數", f"{fmt_num(store_data['來客數'].sum())} 人")
            avg = store_data["營業額"].sum() / store_data["來客數"].sum() if store_data["來客數"].sum() > 0 else 0
            c3.metric("門店客單價", f"{fmt_num(avg)} 元")

            fig5 = go.Figure()
            fig5.add_trace(go.Scatter(
                x=store_data["日期"], y=store_data["營業額"],
                mode="lines+markers", name="營業額",
                line=dict(color="#4ECDC4", width=2), fill="tozeroy",
                hovertemplate="日期：%{x|%m/%d}<br>營業額：%{y:,.0f} 元<extra></extra>",
            ))
            fig5.update_layout(
                title=f"{drill_store} — 每日營業額走勢",
                xaxis_title="日期", yaxis_title="營業額（元）", height=350,
            )
            st.plotly_chart(fig5, use_container_width=True)

            col_a, col_b = st.columns(2)
            with col_a:
                fig6 = px.bar(store_data, x="日期", y="來客數",
                              title=f"{drill_store} — 每日來客數",
                              color_discrete_sequence=["#45B7D1"])
                fig6.update_layout(height=300, xaxis_title="日期", yaxis_title="來客數（人）")
                fig6.update_traces(hovertemplate="日期：%{x|%m/%d}<br>來客數：%{y:,.0f} 人<extra></extra>")
                st.plotly_chart(fig6, use_container_width=True)

            with col_b:
                fig7 = px.line(store_data, x="日期", y="客單價",
                               title=f"{drill_store} — 每日客單價",
                               markers=True, color_discrete_sequence=["#FF6B6B"])
                fig7.update_layout(height=300, xaxis_title="日期", yaxis_title="客單價（元）")
                fig7.update_traces(hovertemplate="日期：%{x|%m/%d}<br>客單價：%{y:,.0f} 元<extra></extra>")
                st.plotly_chart(fig7, use_container_width=True)

            weekday_avg = (
                store_data.groupby(["星期", "星期名"])
                .agg({"營業額": "mean", "來客數": "mean"})
                .reset_index().sort_values("星期")
            )

            fig8 = px.bar(weekday_avg, x="星期名", y="營業額",
                          title=f"{drill_store} — 平均每日營業額（按星期）",
                          color_discrete_sequence=["#96CEB4"])
            fig8.update_layout(height=300, xaxis_title="星期", yaxis_title="營業額（元）")
            fig8.update_traces(hovertemplate="%{x}<br>平均營業額：%{y:,.0f} 元<extra></extra>")
            st.plotly_chart(fig8, use_container_width=True)

    # ==========================================================
    # 分頁 7：異常警示（未達日均目標）
    # ==========================================================
    with tab7:
        st.subheader("⚠️ 未達日均營收目標警示")
        st.caption("日均目標 = 本月營業目標 ÷ 當月天數。每天營業額低於此目標即計為「未達標」。")

        # 計算每筆資料的日均目標
        alert_data = filtered.copy()
        import calendar
        alert_data["當月天數"] = alert_data["日期"].apply(
            lambda x: calendar.monthrange(x.year, x.month)[1]
        )
        alert_data["日均目標"] = alert_data["本月目標"] / alert_data["當月天數"]

        # 篩選有目標且有營業額的資料
        has_target = alert_data[
            alert_data["日均目標"].notna()
            & (alert_data["日均目標"] > 0)
            & alert_data["營業額"].notna()
        ].copy()

        if has_target.empty:
            st.warning("篩選期間內無足夠資料進行目標達成分析。")
        else:
            # 判斷每天是否未達標
            has_target["未達標"] = has_target["營業額"] < has_target["日均目標"]
            has_target["差額"] = has_target["日均目標"] - has_target["營業額"]
            has_target.loc[~has_target["未達標"], "差額"] = 0

            # 按門店彙總
            store_alert = has_target.groupby(["區域", "門店"]).agg(
                有效天數=("營業額", "count"),
                未達標次數=("未達標", "sum"),
                損失營業額=("差額", "sum"),
                日均目標=("日均目標", "mean"),
                實際日均=("營業額", "mean"),
            ).reset_index()
            store_alert["未達標率"] = (store_alert["未達標次數"] / store_alert["有效天數"] * 100).round(1)
            store_alert = store_alert.sort_values("損失營業額", ascending=False)

            # KPI 卡片
            total_miss = int(store_alert["未達標次數"].sum())
            total_loss = store_alert["損失營業額"].sum()
            worst_store = store_alert.iloc[0]["門店"] if not store_alert.empty else "—"

            c1, c2, c3 = st.columns(3)
            c1.metric("🔴 全店未達標總次數", f"{total_miss} 次")
            c2.metric("💸 累計損失營業額", f"{fmt_num(total_loss)} 元")
            c3.metric("⚠️ 損失最多門店", worst_store)

            # 損失營業額排行圖
            st.subheader("各門店損失營業額排行")
            fig_loss = go.Figure()
            fig_loss.add_trace(go.Bar(
                x=store_alert["門店"], y=store_alert["損失營業額"],
                marker_color=["#FF4444" if r > 50 else "#FFaa00" for r in store_alert["未達標率"]],
                hovertemplate="門店：%{x}<br>損失營業額：%{y:,.0f} 元<extra></extra>",
            ))
            fig_loss.update_layout(
                title="各門店累計損失營業額（未達日均目標的差額合計）",
                xaxis_title="門店", yaxis_title="損失營業額（元）",
                height=450, xaxis_tickangle=-45,
            )
            st.plotly_chart(fig_loss, use_container_width=True)

            # 未達標次數排行圖
            st.subheader("各門店未達標次數")
            store_alert_sorted = store_alert.sort_values("未達標次數", ascending=False)
            fig_miss = go.Figure()
            fig_miss.add_trace(go.Bar(
                x=store_alert_sorted["門店"], y=store_alert_sorted["未達標次數"],
                marker_color="#FF6B6B",
                text=[f"{n:.0f}次" for n in store_alert_sorted["未達標次數"]],
                textposition="outside",
                hovertemplate="門店：%{x}<br>未達標次數：%{y:.0f} 次<extra></extra>",
            ))
            fig_miss.update_layout(
                title="各門店未達日均目標次數",
                xaxis_title="門店", yaxis_title="未達標次數",
                height=450, xaxis_tickangle=-45,
            )
            st.plotly_chart(fig_miss, use_container_width=True)

            # 明細表
            st.subheader("門店未達標明細表")
            disp_alert = store_alert[[
                "區域", "門店", "有效天數", "未達標次數", "未達標率", "日均目標", "實際日均", "損失營業額"
            ]].copy()
            disp_alert["日均目標"] = disp_alert["日均目標"].apply(lambda x: f"{x:,.0f} 元")
            disp_alert["實際日均"] = disp_alert["實際日均"].apply(lambda x: f"{x:,.0f} 元")
            disp_alert["損失營業額"] = disp_alert["損失營業額"].apply(lambda x: f"{x:,.0f} 元")
            disp_alert["未達標次數"] = disp_alert["未達標次數"].astype(int).astype(str) + " 次"
            disp_alert["未達標率"] = disp_alert["未達標率"].apply(lambda x: f"{x:.1f}%")
            disp_alert["有效天數"] = disp_alert["有效天數"].astype(int).astype(str) + " 天"
            st.dataframe(disp_alert, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
