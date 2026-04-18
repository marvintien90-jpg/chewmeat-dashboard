"""
嗑肉石鍋 數位總部 — 資料匯入中心
支援手動上傳客服評論 CSV 與市場調查 CSV，
並利用模糊比對自動對齊門店名稱。
"""
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_engine import build_store_alias_table, fuzzy_merge, normalize_store_names
from utils.revenue_data import PORTAL_CSS, load_all_data

# ── 頁面設定 ────────────────────────────────────────────────
st.set_page_config(
    page_title="資料匯入中心 — 嗑肉石鍋",
    page_icon="📥",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(PORTAL_CSS, unsafe_allow_html=True)

st.sidebar.markdown("## 📥 資料匯入中心")
st.sidebar.divider()
st.sidebar.caption("上傳外部資料，與營收資料自動比對融合")

# ── 取得標準店名清單（供模糊比對使用）──────────────────────
@st.cache_data(ttl=3600)
def get_canonical_stores() -> list[str]:
    data = load_all_data()
    if data.empty:
        return []
    return sorted(data["門店"].dropna().unique().tolist())


canonical_stores = get_canonical_stores()

# ── 標題 ────────────────────────────────────────────────────
st.header("📥 資料匯入中心")
st.markdown("上傳外部資料檔（客服評論、市場調查），系統將自動比對門店名稱並整合分析。")

tabs = st.tabs(["客服評論上傳", "市場調查上傳", "店名比對工具", "已匯入資料管理"])

# ════════════════════════════════════════════════════════════
# Tab 1：客服評論上傳
# ════════════════════════════════════════════════════════════
with tabs[0]:
    st.subheader("客服評論 CSV 上傳")
    st.markdown("""
    **建議欄位（欄位名稱需符合）：**

    | 欄位 | 說明 | 必填 |
    |------|------|------|
    | 門店名稱 | 評論來源門店 | ✅ |
    | 評論日期 | YYYY-MM-DD | — |
    | 評分 | 1-5 分 | — |
    | 評論內容 | 文字內容 | — |
    | 評論來源 | 例：Google / 客訴信箱 | — |
    """)

    review_file = st.file_uploader("上傳客服評論 CSV", type=["csv"], key="review_upload")

    if review_file:
        try:
            df_review = pd.read_csv(review_file)
            st.success(f"已讀取 {len(df_review)} 筆評論資料")

            # 自動模糊比對門店名稱
            if "門店名稱" in df_review.columns and canonical_stores:
                with st.spinner("比對門店名稱中..."):
                    df_review = normalize_store_names(
                        df_review, "門店名稱", canonical_stores,
                        score_threshold=70, new_col="標準門店名稱"
                    )
                low_conf = df_review[df_review["比對分數"] < 80]
                if not low_conf.empty:
                    st.warning(f"有 {len(low_conf)} 筆門店名稱比對信心度偏低（<80分），請人工確認：")
                    st.dataframe(
                        low_conf[["門店名稱", "標準門店名稱", "比對分數"]],
                        use_container_width=True, hide_index=True
                    )

            st.subheader("資料預覽")
            st.dataframe(df_review, use_container_width=True, hide_index=True)

            # 評分統計
            if "評分" in df_review.columns and "標準門店名稱" in df_review.columns:
                st.subheader("各門店平均評分")
                store_col = "標準門店名稱"
                avg_score = df_review.groupby(store_col)["評分"].mean().reset_index()
                avg_score.columns = ["門店", "平均評分"]
                avg_score = avg_score.sort_values("平均評分")

                fig = px.bar(avg_score, x="門店", y="平均評分",
                             color="平均評分",
                             color_continuous_scale=["#E8431A", "#FFD9CC", "#44BB44"],
                             color_continuous_midpoint=3,
                             title="各門店客服評論平均評分", height=380)
                fig.add_hline(y=avg_score["平均評分"].mean(), line_dash="dash",
                              line_color="#C73A18",
                              annotation_text=f"全體平均 {avg_score['平均評分'].mean():.2f} 分")
                fig.update_layout(xaxis_tickangle=-45,
                                  paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
                st.plotly_chart(fig, use_container_width=True)

            # 儲存到 session state
            if st.button("確認匯入客服評論", key="confirm_review"):
                st.session_state["review_data"] = df_review
                st.success(f"客服評論資料已匯入（{len(df_review)} 筆）！")

        except Exception as e:
            st.error(f"CSV 解析失敗：{e}")

# ════════════════════════════════════════════════════════════
# Tab 2：市場調查上傳
# ════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("市場調查 CSV 上傳")
    st.markdown("""
    **建議欄位：**

    | 欄位 | 說明 | 必填 |
    |------|------|------|
    | 門店名稱 | 受訪門店 | ✅ |
    | 調查日期 | YYYY-MM-DD | — |
    | 調查項目 | 例：裝潢滿意度 | — |
    | 分數 | 數值型 | — |
    | 受訪人數 | 整數 | — |
    | 備註 | 自由文字 | — |
    """)

    survey_file = st.file_uploader("上傳市場調查 CSV", type=["csv"], key="survey_upload")

    if survey_file:
        try:
            df_survey = pd.read_csv(survey_file)
            st.success(f"已讀取 {len(df_survey)} 筆調查資料")

            if "門店名稱" in df_survey.columns and canonical_stores:
                with st.spinner("比對門店名稱中..."):
                    df_survey = normalize_store_names(
                        df_survey, "門店名稱", canonical_stores,
                        score_threshold=70, new_col="標準門店名稱"
                    )

            st.subheader("資料預覽")
            st.dataframe(df_survey, use_container_width=True, hide_index=True)

            # 若有數值欄位，做基本統計
            numeric_cols = df_survey.select_dtypes(include="number").columns.tolist()
            for col in ["比對分數"]:
                if col in numeric_cols:
                    numeric_cols.remove(col)

            if numeric_cols and "標準門店名稱" in df_survey.columns:
                sel_metric = st.selectbox("選擇要視覺化的指標", numeric_cols)
                grp = df_survey.groupby("標準門店名稱")[sel_metric].mean().reset_index()
                grp.columns = ["門店", sel_metric]
                fig = px.bar(grp.sort_values(sel_metric), x="門店", y=sel_metric,
                             color=sel_metric,
                             color_continuous_scale=["#FFE4D6", "#E8431A"],
                             title=f"各門店 {sel_metric} 平均", height=350)
                fig.update_layout(xaxis_tickangle=-45,
                                  paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
                st.plotly_chart(fig, use_container_width=True)

            if st.button("確認匯入市場調查", key="confirm_survey"):
                st.session_state["survey_data"] = df_survey
                st.success(f"市場調查資料已匯入（{len(df_survey)} 筆）！")

        except Exception as e:
            st.error(f"CSV 解析失敗：{e}")

# ════════════════════════════════════════════════════════════
# Tab 3：店名比對工具
# ════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("門店名稱模糊比對工具")
    st.markdown("""
    貼入非標準門店名稱清單，自動比對出標準名稱。
    比對分數 ≥ 75 視為可信，低於此值建議人工確認。
    """)

    if not canonical_stores:
        st.warning("無法取得標準店名清單（營收資料未載入）")
    else:
        st.info(f"目前標準店名共 **{len(canonical_stores)}** 家：{', '.join(canonical_stores[:10])}{'...' if len(canonical_stores) > 10 else ''}")

        raw_names_input = st.text_area(
            "貼入待比對的門店名稱（每行一個）",
            placeholder="台一\n台一旗艦\n高雄大順\n鳳山文中",
            height=150,
        )
        threshold = st.slider("比對信心門檻（分數低於此值標示為需確認）", 50, 95, 75)

        if st.button("開始比對", key="fuzzy_match_btn"):
            names = [n.strip() for n in raw_names_input.strip().split("\n") if n.strip()]
            if not names:
                st.warning("請輸入至少一個店名")
            else:
                result = build_store_alias_table(names, canonical_stores, threshold)
                st.subheader("比對結果")
                st.dataframe(result, use_container_width=True, hide_index=True)

                low_conf = result[result["需人工確認"]]
                if not low_conf.empty:
                    st.warning(f"有 {len(low_conf)} 筆需要人工確認")
                else:
                    st.success("所有店名均成功比對！")

# ════════════════════════════════════════════════════════════
# Tab 4：已匯入資料管理
# ════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("已匯入資料管理")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**客服評論資料**")
        review_data = st.session_state.get("review_data", None)
        if review_data is not None and not review_data.empty:
            st.success(f"已匯入 {len(review_data)} 筆")
            st.dataframe(review_data.head(20), use_container_width=True, hide_index=True)
            csv_bytes = review_data.to_csv(index=False, encoding="utf-8-sig").encode()
            st.download_button(
                "下載客服評論 CSV",
                data=csv_bytes,
                file_name=f"客服評論_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
            if st.button("清除客服評論資料"):
                del st.session_state["review_data"]
                st.rerun()
        else:
            st.info("尚未匯入客服評論資料")

    with col2:
        st.markdown("**市場調查資料**")
        survey_data = st.session_state.get("survey_data", None)
        if survey_data is not None and not survey_data.empty:
            st.success(f"已匯入 {len(survey_data)} 筆")
            st.dataframe(survey_data.head(20), use_container_width=True, hide_index=True)
            csv_bytes = survey_data.to_csv(index=False, encoding="utf-8-sig").encode()
            st.download_button(
                "下載市場調查 CSV",
                data=csv_bytes,
                file_name=f"市場調查_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
            if st.button("清除市場調查資料"):
                del st.session_state["survey_data"]
                st.rerun()
        else:
            st.info("尚未匯入市場調查資料")
