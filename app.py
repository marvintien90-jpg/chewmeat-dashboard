import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import warnings
import re

warnings.filterwarnings("ignore")

# ============================================================
# 基本設定
# ============================================================
SHEET_ID = "1NZQEJgL-HkB08JSW6zsVHRSyl_XgwLc5etUqSF0O9ow"

# 所有工作表的 gid（月份 -> gid 對應）
# 用門店數量區分同月份不同年度
SHEET_GIDS = {
    "2025-01": "672482866",
    "2025-02": "1943981506",
    "2025-03": "847955849",
    "2025-12": "1838876978",
    "2026-01": "872131612",
    "2026-02": "162899314",
    "2026-03": "1575135129",
    "2026-04": "1702412906",
    "2026-05": "1499115222",
    "2026-06": "467088033",
}

st.set_page_config(
    page_title="嗑肉石鍋 營收儀表板",
    page_icon="🍲",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 資料讀取與解析
# ============================================================
@st.cache_data(ttl=3600)  # 快取 1 小時
def load_sheet(year_month, gid):
    """從 Google Sheets 讀取單月資料並解析成扁平表格"""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    try:
        raw = pd.read_csv(url, header=None)
    except Exception:
        return pd.DataFrame()

    year, month = year_month.split("-")
    year = int(year)
    month = int(month)

    # 找出日期列（第 2 行，從第 8 欄開始）
    date_row = raw.iloc[1, 7:]
    dates = []
    for val in date_row:
        s = str(val).strip()
        if s == "nan" or s == "合計":
            continue
        # 格式為 "M/D"
        match = re.match(r"(\d+)/(\d+)", s)
        if match:
            m, d = int(match.group(1)), int(match.group(2))
            if m != month:
                continue  # 跳過不屬於本月的日期
            try:
                dates.append(date(year, m, d))
            except ValueError:
                continue

    if not dates:
        return pd.DataFrame()

    # 找出每間門店的資料（每店佔 6 行）
    rows = []
    current_region = None
    current_store = None
    current_target = None
    current_rate = None

    for i in range(2, len(raw)):
        row = raw.iloc[i]

        # 更新區域、門店資訊（只在有值的行更新）
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

        # 讀取每天的數值（從第 8 欄開始，每隔 2 欄一個值）
        data_cols = row.iloc[7:]
        values = []
        col_idx = 0
        for val in data_cols:
            s = str(val).strip().replace(",", "").replace(" ", "")
            if s in ["nan", "", "#DIV/0!", "\\#DIV/0\\!", "#DIV/0!"]:
                values.append(None)
            else:
                try:
                    values.append(float(s))
                except ValueError:
                    values.append(None)
            col_idx += 1

        # 每個日期對應一個值（偶數索引位置）
        day_values = []
        for idx in range(0, len(values), 2):
            if idx // 2 < len(dates):
                day_values.append(values[idx] if idx < len(values) else None)

        for day_idx, dt in enumerate(dates):
            val = day_values[day_idx] if day_idx < len(day_values) else None
            rows.append(
                {
                    "日期": dt,
                    "區域": current_region,
                    "門店": current_store,
                    "本月目標": current_target,
                    "達成率": current_rate,
                    "指標": metric,
                    "數值": val,
                }
            )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # 樞紐轉換：把「業績合計」「人數合計」「平均客單」變成欄位
    pivot = df.pivot_table(
        index=["日期", "區域", "門店", "本月目標", "達成率"],
        columns="指標",
        values="數值",
        aggfunc="first",
    ).reset_index()

    pivot.columns.name = None

    # 重命名
    rename_map = {}
    if "業績合計" in pivot.columns:
        rename_map["業績合計"] = "營業額"
    if "人數合計" in pivot.columns:
        rename_map["人數合計"] = "來客數"
    if "平均客單" in pivot.columns:
        rename_map["平均客單"] = "客單價"
    pivot = pivot.rename(columns=rename_map)

    # 確保欄位存在
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


# ============================================================
# 主程式
# ============================================================
def main():
    st.title("🍲 嗑肉石鍋 — 營收數位儀表板")
    st.caption(f"資料更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 載入資料
    with st.spinner("正在從 Google 試算表載入資料，請稍候..."):
        data = load_all_data()

    if data.empty:
        st.error("無法載入資料，請確認 Google 試算表已設為公開檢視。")
        return

    # 轉換日期格式
    data["日期"] = pd.to_datetime(data["日期"])

    # --------------------------------------------------------
    # 側邊欄：篩選器
    # --------------------------------------------------------
    st.sidebar.header("📊 篩選條件")

    # 日期範圍
    min_date = data["日期"].min().date()
    max_date = data["日期"].max().date()
    date_range = st.sidebar.date_input(
        "選擇日期範圍",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    # 區域篩選
    regions = sorted(data["區域"].dropna().unique().tolist())
    selected_regions = st.sidebar.multiselect("選擇區域", regions, default=regions)

    # 門店篩選
    available_stores = sorted(
        data[data["區域"].isin(selected_regions)]["門店"].dropna().unique().tolist()
    )
    selected_stores = st.sidebar.multiselect(
        "選擇門店", available_stores, default=available_stores
    )

    # 篩選資料
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

    # 刷新按鈕
    if st.sidebar.button("🔄 重新載入資料"):
        st.cache_data.clear()
        st.rerun()

    # --------------------------------------------------------
    # 頂部 KPI 卡片
    # --------------------------------------------------------
    # 只計算有實際數據的日期（營業額 > 0）
    valid_data = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    total_revenue = valid_data["營業額"].sum()
    total_customers = valid_data["來客數"].sum()
    avg_ticket = total_revenue / total_customers if total_customers > 0 else 0
    active_days = valid_data["日期"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 總營業額", f"${total_revenue:,.0f}")
    with col2:
        st.metric("👥 總來客數", f"{total_customers:,.0f} 人")
    with col3:
        st.metric("🧾 平均客單價", f"${avg_ticket:,.0f}")
    with col4:
        st.metric("📅 有效營業天數", f"{active_days} 天")

    st.divider()

    # --------------------------------------------------------
    # Tab 1: 營收趨勢
    # --------------------------------------------------------
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 營收趨勢", "🏪 門店比較", "🔍 下鑽分析", "⚠️ 異常警示"]
    )

    with tab1:
        st.subheader("每日營收趨勢")

        # 每日總營收
        daily = (
            valid_data.groupby("日期")
            .agg({"營業額": "sum", "來客數": "sum"})
            .reset_index()
        )
        daily["客單價"] = daily["營業額"] / daily["來客數"]
        daily["客單價"] = daily["客單價"].round(0)

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=daily["日期"],
                y=daily["營業額"],
                name="營業額",
                marker_color="#4ECDC4",
            )
        )
        fig.update_layout(
            title="全店每日營業額",
            xaxis_title="日期",
            yaxis_title="營業額 (元)",
            height=400,
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        # 來客數與客單價雙軸圖
        fig2 = go.Figure()
        fig2.add_trace(
            go.Bar(
                x=daily["日期"],
                y=daily["來客數"],
                name="來客數",
                marker_color="#45B7D1",
                yaxis="y",
            )
        )
        fig2.add_trace(
            go.Scatter(
                x=daily["日期"],
                y=daily["客單價"],
                name="客單價",
                mode="lines+markers",
                line=dict(color="#FF6B6B", width=2),
                yaxis="y2",
            )
        )
        fig2.update_layout(
            title="來客數 vs 客單價",
            xaxis_title="日期",
            yaxis=dict(title="來客數 (人)", side="left"),
            yaxis2=dict(title="客單價 (元)", side="right", overlaying="y"),
            height=400,
            hovermode="x unified",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # --------------------------------------------------------
    # Tab 2: 門店比較
    # --------------------------------------------------------
    with tab2:
        st.subheader("門店業績排行")

        store_summary = (
            valid_data.groupby(["區域", "門店"])
            .agg(
                {
                    "營業額": "sum",
                    "來客數": "sum",
                    "本月目標": "first",
                    "達成率": "first",
                }
            )
            .reset_index()
        )
        store_summary["客單價"] = (
            store_summary["營業額"] / store_summary["來客數"]
        ).round(0)
        store_summary = store_summary.sort_values("營業額", ascending=False)

        # 營業額排行圖
        fig3 = px.bar(
            store_summary,
            x="門店",
            y="營業額",
            color="區域",
            title="各門店營業額排行",
            height=450,
        )
        fig3.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig3, use_container_width=True)

        # 目標達成率
        if store_summary["達成率"].notna().any():
            st.subheader("目標達成率")
            rate_data = store_summary[store_summary["達成率"].notna()].copy()
            rate_data["達成率_pct"] = rate_data["達成率"] * 100

            fig4 = go.Figure()
            colors = [
                "#FF4444" if r < 50 else ("#FFaa00" if r < 80 else "#44BB44")
                for r in rate_data["達成率_pct"]
            ]
            fig4.add_trace(
                go.Bar(
                    x=rate_data["門店"],
                    y=rate_data["達成率_pct"],
                    marker_color=colors,
                    text=[f"{r:.1f}%" for r in rate_data["達成率_pct"]],
                    textposition="outside",
                )
            )
            fig4.add_hline(
                y=100, line_dash="dash", line_color="red", annotation_text="目標 100%"
            )
            fig4.update_layout(
                title="各門店目標達成率",
                xaxis_title="門店",
                yaxis_title="達成率 (%)",
                height=450,
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig4, use_container_width=True)

        # 門店明細表
        st.subheader("門店明細表")
        display_df = store_summary[
            ["區域", "門店", "營業額", "來客數", "客單價", "達成率"]
        ].copy()
        display_df["營業額"] = display_df["營業額"].apply(lambda x: f"${x:,.0f}")
        display_df["來客數"] = display_df["來客數"].apply(lambda x: f"{x:,.0f}")
        display_df["客單價"] = display_df["客單價"].apply(lambda x: f"${x:,.0f}")
        display_df["達成率"] = display_df["達成率"].apply(
            lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A"
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    # --------------------------------------------------------
    # Tab 3: 下鑽分析
    # --------------------------------------------------------
    with tab3:
        st.subheader("單店下鑽分析")

        drill_store = st.selectbox("選擇要分析的門店", selected_stores)

        store_data = valid_data[valid_data["門店"] == drill_store].sort_values("日期")

        if store_data.empty:
            st.warning("此門店在選定期間無資料。")
        else:
            # KPI
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("門店營業額", f"${store_data['營業額'].sum():,.0f}")
            with c2:
                st.metric("門店來客數", f"{store_data['來客數'].sum():,.0f} 人")
            with c3:
                avg = (
                    store_data["營業額"].sum() / store_data["來客數"].sum()
                    if store_data["來客數"].sum() > 0
                    else 0
                )
                st.metric("門店客單價", f"${avg:,.0f}")

            # 每日營收走勢
            fig5 = go.Figure()
            fig5.add_trace(
                go.Scatter(
                    x=store_data["日期"],
                    y=store_data["營業額"],
                    mode="lines+markers",
                    name="營業額",
                    line=dict(color="#4ECDC4", width=2),
                    fill="tozeroy",
                )
            )
            fig5.update_layout(
                title=f"{drill_store} — 每日營業額走勢",
                xaxis_title="日期",
                yaxis_title="營業額 (元)",
                height=350,
            )
            st.plotly_chart(fig5, use_container_width=True)

            # 來客數與客單價
            col_a, col_b = st.columns(2)
            with col_a:
                fig6 = px.bar(
                    store_data,
                    x="日期",
                    y="來客數",
                    title=f"{drill_store} — 每日來客數",
                    color_discrete_sequence=["#45B7D1"],
                )
                fig6.update_layout(height=300)
                st.plotly_chart(fig6, use_container_width=True)

            with col_b:
                fig7 = px.line(
                    store_data,
                    x="日期",
                    y="客單價",
                    title=f"{drill_store} — 每日客單價",
                    markers=True,
                    color_discrete_sequence=["#FF6B6B"],
                )
                fig7.update_layout(height=300)
                st.plotly_chart(fig7, use_container_width=True)

            # 星期幾分析
            store_data["星期"] = store_data["日期"].dt.dayofweek
            weekday_map = {
                0: "一",
                1: "二",
                2: "三",
                3: "四",
                4: "五",
                5: "六",
                6: "日",
            }
            store_data["星期名"] = store_data["星期"].map(weekday_map)
            weekday_avg = (
                store_data.groupby(["星期", "星期名"])
                .agg({"營業額": "mean", "來客數": "mean"})
                .reset_index()
                .sort_values("星期")
            )

            fig8 = px.bar(
                weekday_avg,
                x="星期名",
                y="營業額",
                title=f"{drill_store} — 平均每日營業額（按星期）",
                color_discrete_sequence=["#96CEB4"],
            )
            fig8.update_layout(height=300, xaxis_title="星期")
            st.plotly_chart(fig8, use_container_width=True)

    # --------------------------------------------------------
    # Tab 4: 異常警示
    # --------------------------------------------------------
    with tab4:
        st.subheader("⚠️ 異常警示面板")

        alerts = []

        for store in selected_stores:
            store_df = (
                filtered[filtered["門店"] == store].sort_values("日期").copy()
            )

            if store_df.empty:
                continue

            for i in range(1, len(store_df)):
                curr = store_df.iloc[i]
                prev = store_df.iloc[i - 1]
                curr_rev = curr["營業額"]
                prev_rev = prev["營業額"]
                curr_date = curr["日期"]
                store_name = curr["門店"]
                region = curr["區域"]

                # 警示1：沒有數據（黃色）
                if pd.isna(curr_rev) or curr_rev == 0:
                    alerts.append(
                        {
                            "日期": curr_date,
                            "區域": region,
                            "門店": store_name,
                            "類型": "🟡 無數據",
                            "說明": "當天無營收資料，可能尚未輸入",
                            "嚴重度": 1,
                        }
                    )
                    continue

                # 警示2：營業額下跌超過 10%（紅色）
                if (
                    pd.notna(prev_rev)
                    and prev_rev > 0
                    and curr_rev < prev_rev * 0.9
                ):
                    drop_pct = (1 - curr_rev / prev_rev) * 100
                    alerts.append(
                        {
                            "日期": curr_date,
                            "區域": region,
                            "門店": store_name,
                            "類型": "🔴 營收下跌",
                            "說明": f"較前日下跌 {drop_pct:.1f}%（${prev_rev:,.0f} → ${curr_rev:,.0f}）",
                            "嚴重度": 2,
                        }
                    )

        if alerts:
            alert_df = pd.DataFrame(alerts)
            alert_df = alert_df.sort_values(
                ["嚴重度", "日期"], ascending=[False, False]
            )

            # 統計
            red_count = len(alert_df[alert_df["嚴重度"] == 2])
            yellow_count = len(alert_df[alert_df["嚴重度"] == 1])

            c1, c2 = st.columns(2)
            with c1:
                st.metric("🔴 營收下跌警示", f"{red_count} 筆")
            with c2:
                st.metric("🟡 無數據警示", f"{yellow_count} 筆")

            # 顯示最近的警示
            st.subheader("最近警示明細")

            # 紅色警示
            red_alerts = alert_df[alert_df["嚴重度"] == 2].head(30)
            if not red_alerts.empty:
                st.markdown("#### 🔴 營收下跌（跌幅 > 10%）")
                display_red = red_alerts[
                    ["日期", "區域", "門店", "說明"]
                ].copy()
                display_red["日期"] = display_red["日期"].dt.strftime("%Y-%m-%d")
                st.dataframe(
                    display_red,
                    use_container_width=True,
                    hide_index=True,
                )

            # 黃色警示
            yellow_alerts = alert_df[alert_df["嚴重度"] == 1].head(30)
            if not yellow_alerts.empty:
                st.markdown("#### 🟡 無數據警示")
                display_yellow = yellow_alerts[
                    ["日期", "區域", "門店", "說明"]
                ].copy()
                display_yellow["日期"] = display_yellow["日期"].dt.strftime(
                    "%Y-%m-%d"
                )
                st.dataframe(
                    display_yellow,
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.success("目前沒有異常警示！一切正常 ✅")


if __name__ == "__main__":
    main()
