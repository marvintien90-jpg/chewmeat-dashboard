"""
嗑肉石鍋 數位總部 — 專案進度
管理跨店、跨部門的任務與行動項目，追蹤截止日與負責人。
"""
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.revenue_data import PORTAL_CSS

# ── 頁面設定 ────────────────────────────────────────────────
st.set_page_config(
    page_title="專案進度 — 嗑肉石鍋",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(PORTAL_CSS, unsafe_allow_html=True)

st.sidebar.markdown("## 📋 專案進度")
st.sidebar.divider()
st.sidebar.caption("管理任務、行動項目與截止日追蹤")

# ── Session State 初始化 ─────────────────────────────────────
if "tasks" not in st.session_state:
    st.session_state.tasks = pd.DataFrame(columns=[
        "任務名稱", "負責人", "所屬門店", "開始日期", "截止日期",
        "優先級", "狀態", "備註", "建立時間",
    ])

STATUS_OPTIONS = ["待開始", "進行中", "已完成", "延遲"]
PRIORITY_OPTIONS = ["高", "中", "低"]
STATUS_COLOR = {"待開始": "#FFD9CC", "進行中": "#FF6B35", "已完成": "#44BB44", "延遲": "#E8431A"}

# ── 標題 ────────────────────────────────────────────────────
st.header("📋 專案進度追蹤")

tabs = st.tabs(["任務看板", "新增任務", "匯入 CSV", "統計總覽"])

# ════════════════════════════════════════════════════════════
# Tab 1：任務看板
# ════════════════════════════════════════════════════════════
with tabs[0]:
    tasks = st.session_state.tasks

    if tasks.empty:
        st.info("目前尚無任務。請至「新增任務」或「匯入 CSV」建立資料。")
    else:
        # 篩選列
        c1, c2, c3 = st.columns(3)
        with c1:
            filter_status = st.multiselect("狀態篩選", STATUS_OPTIONS, default=STATUS_OPTIONS)
        with c2:
            all_stores = ["全部"] + sorted(tasks["所屬門店"].dropna().unique().tolist())
            filter_store = st.selectbox("門店篩選", all_stores)
        with c3:
            filter_priority = st.multiselect("優先級", PRIORITY_OPTIONS, default=PRIORITY_OPTIONS)

        filtered = tasks[tasks["狀態"].isin(filter_status) & tasks["優先級"].isin(filter_priority)]
        if filter_store != "全部":
            filtered = filtered[filtered["所屬門店"] == filter_store]

        # 逾期標記
        today = date.today()
        filtered = filtered.copy()
        filtered["是否逾期"] = filtered.apply(
            lambda r: r["狀態"] not in ("已完成",) and pd.notna(r["截止日期"])
                      and r["截止日期"] < str(today),
            axis=1,
        )

        # 顯示看板（依優先級 + 狀態排序）
        priority_order = {"高": 0, "中": 1, "低": 2}
        status_order = {"延遲": 0, "進行中": 1, "待開始": 2, "已完成": 3}
        filtered["_p"] = filtered["優先級"].map(priority_order)
        filtered["_s"] = filtered["狀態"].map(status_order)
        filtered = filtered.sort_values(["_p", "_s"]).drop(columns=["_p", "_s"])

        st.markdown(f"**共 {len(filtered)} 筆任務**")

        for _, row in filtered.iterrows():
            overdue_tag = "🚨 逾期" if row.get("是否逾期") else ""
            color = STATUS_COLOR.get(row["狀態"], "#FFF5F2")
            st.markdown(f"""
            <div style="background:{color}22; border-left:4px solid {color};
                        border-radius:8px; padding:12px 16px; margin-bottom:8px;">
                <div style="font-weight:700; font-size:1rem; color:#2D1A0A;">
                    {row['任務名稱']} {overdue_tag}
                </div>
                <div style="font-size:0.85rem; color:#7A5544; margin-top:4px;">
                    負責人：{row['負責人']} ｜ 門店：{row['所屬門店']}
                    ｜ 優先級：{row['優先級']} ｜ 狀態：{row['狀態']}
                    ｜ 截止：{row['截止日期']}
                </div>
                {f'<div style="font-size:0.8rem; color:#555; margin-top:3px;">備註：{row["備註"]}</div>' if row.get('備註') else ''}
            </div>
            """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# Tab 2：新增任務
# ════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("新增任務")
    with st.form("add_task_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        task_name = c1.text_input("任務名稱 *", placeholder="例：台一店 9 月備料盤點")
        owner = c2.text_input("負責人 *", placeholder="例：王店長")

        c3, c4 = st.columns(2)
        store_name = c3.text_input("所屬門店", placeholder="例：台一店")
        priority = c4.selectbox("優先級", PRIORITY_OPTIONS)

        c5, c6 = st.columns(2)
        start_date = c5.date_input("開始日期", value=date.today())
        end_date = c6.date_input("截止日期", value=date.today())

        status = st.selectbox("初始狀態", STATUS_OPTIONS, index=0)
        note = st.text_area("備註（選填）", placeholder="相關說明、注意事項…")

        submitted = st.form_submit_button("新增任務")
        if submitted:
            if not task_name or not owner:
                st.error("任務名稱與負責人為必填欄位")
            else:
                new_row = {
                    "任務名稱": task_name,
                    "負責人": owner,
                    "所屬門店": store_name or "未指定",
                    "開始日期": str(start_date),
                    "截止日期": str(end_date),
                    "優先級": priority,
                    "狀態": status,
                    "備註": note,
                    "建立時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                new_df = pd.DataFrame([new_row])
                st.session_state.tasks = pd.concat(
                    [st.session_state.tasks, new_df], ignore_index=True
                )
                st.success(f"任務「{task_name}」已新增！")

# ════════════════════════════════════════════════════════════
# Tab 3：匯入 CSV
# ════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("從 CSV 匯入任務清單")
    st.markdown("""
    **CSV 格式規範（欄位順序不限，欄位名稱需符合）：**

    | 欄位名稱 | 說明 | 必填 |
    |---------|------|------|
    | 任務名稱 | 任務標題 | ✅ |
    | 負責人 | 姓名或代稱 | ✅ |
    | 所屬門店 | 門店名稱 | — |
    | 開始日期 | YYYY-MM-DD | — |
    | 截止日期 | YYYY-MM-DD | — |
    | 優先級 | 高 / 中 / 低 | — |
    | 狀態 | 待開始 / 進行中 / 已完成 / 延遲 | — |
    | 備註 | 自由文字 | — |
    """)

    uploaded = st.file_uploader("上傳任務 CSV 檔", type=["csv"])
    if uploaded:
        try:
            df_upload = pd.read_csv(uploaded)
            required_cols = {"任務名稱", "負責人"}
            if not required_cols.issubset(df_upload.columns):
                st.error(f"CSV 缺少必要欄位：{required_cols - set(df_upload.columns)}")
            else:
                # 填補缺少的欄位
                for col, default in [
                    ("所屬門店", "未指定"), ("開始日期", str(date.today())),
                    ("截止日期", str(date.today())), ("優先級", "中"),
                    ("狀態", "待開始"), ("備註", ""),
                ]:
                    if col not in df_upload.columns:
                        df_upload[col] = default
                df_upload["建立時間"] = datetime.now().strftime("%Y-%m-%d %H:%M")

                st.dataframe(df_upload, use_container_width=True, hide_index=True)
                if st.button("確認匯入"):
                    st.session_state.tasks = pd.concat(
                        [st.session_state.tasks, df_upload], ignore_index=True
                    )
                    st.success(f"成功匯入 {len(df_upload)} 筆任務！")
        except Exception as e:
            st.error(f"CSV 解析失敗：{e}")

# ════════════════════════════════════════════════════════════
# Tab 4：統計總覽
# ════════════════════════════════════════════════════════════
with tabs[3]:
    tasks = st.session_state.tasks
    if tasks.empty:
        st.info("尚無資料")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("任務總數", len(tasks))
        c2.metric("進行中", len(tasks[tasks["狀態"] == "進行中"]))
        c3.metric("已完成", len(tasks[tasks["狀態"] == "已完成"]))
        c4.metric("延遲", len(tasks[tasks["狀態"] == "延遲"]))

        col1, col2 = st.columns(2)
        with col1:
            status_count = tasks["狀態"].value_counts().reset_index()
            status_count.columns = ["狀態", "數量"]
            fig = px.pie(status_count, values="數量", names="狀態",
                         title="任務狀態分佈", hole=0.4,
                         color_discrete_sequence=["#FFD9CC", "#FF6B35", "#44BB44", "#E8431A"])
            fig.update_layout(paper_bgcolor="#FFFFFF")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            priority_count = tasks["優先級"].value_counts().reset_index()
            priority_count.columns = ["優先級", "數量"]
            fig2 = px.bar(priority_count, x="優先級", y="數量",
                          color="優先級", title="任務優先級分佈",
                          color_discrete_map={"高": "#E8431A", "中": "#FF6B35", "低": "#FFD9CC"})
            fig2.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("門店任務量排行")
        store_count = tasks.groupby("所屬門店").size().reset_index(name="任務數").sort_values(
            "任務數", ascending=False
        )
        fig3 = px.bar(store_count, x="所屬門店", y="任務數",
                      color="任務數", color_continuous_scale=["#FFE4D6", "#E8431A"],
                      title="各門店任務數量", height=350)
        fig3.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
        st.plotly_chart(fig3, use_container_width=True)
