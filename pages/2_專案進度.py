import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 專案進度",
    page_icon="🗂️",
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

# ============================================================
# 圖 B 風格 CSS（深藍/橘紅雙主色 × 白底 × 全中文）
# ============================================================
st.markdown("""
<style>
    .main .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}

    /* KPI 卡片 */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        padding: 14px;
        border-radius: 10px;
        border: 1.5px solid #E8EEF4;
        box-shadow: 0 1px 4px rgba(44,62,80,0.07);
    }
    [data-testid="stMetricLabel"] {font-size: 0.85rem; color: #888;}
    [data-testid="stMetricValue"] {font-size: 1.5rem; font-weight: 700; color: #1A1A1A;}

    /* 區塊標題 — 深藍扁平 */
    .section-header {
        background: #2C3E50;
        color: white;
        padding: 7px 16px;
        border-radius: 8px;
        margin: 1rem 0 0.5rem 0;
        font-weight: 700;
        font-size: 0.95rem;
    }
    .section-header-orange {
        background: #E63B1F;
        color: white;
        padding: 7px 16px;
        border-radius: 8px;
        margin: 1rem 0 0.5rem 0;
        font-weight: 700;
        font-size: 0.95rem;
    }

    /* 專案卡片 */
    .proj-card {
        background: #FFFFFF;
        border: 1.5px solid #E8EEF4;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        border-left: 5px solid #2C3E50;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .proj-card.urgent { border-left-color: #E63B1F; }
    .proj-card.done   { border-left-color: #27AE60; opacity: 0.85; }
    .proj-card.hold   { border-left-color: #95A5A6; opacity: 0.75; }

    .proj-title { font-size: 1rem; font-weight: 700; color: #1A1A1A; margin: 0 0 0.3rem 0; }
    .proj-meta  { font-size: 0.78rem; color: #888; line-height: 1.7; }
    .proj-tag   { display: inline-block; padding: 2px 8px; border-radius: 20px;
                  font-size: 0.72rem; font-weight: 600; margin-right: 4px; }
    .tag-executing { background: #EBF5FB; color: #2980B9; }
    .tag-planning  { background: #FFF3CD; color: #856404; }
    .tag-done      { background: #D5F5E3; color: #1E8449; }
    .tag-hold      { background: #F2F3F4; color: #717D7E; }

    /* 進度條容器 */
    .progress-wrap { margin-top: 0.5rem; }
    .progress-bar-bg {
        background: #F0F0F0; border-radius: 6px; height: 8px; width: 100%; margin-top: 3px;
    }
    .progress-bar-fill {
        background: linear-gradient(90deg, #2C3E50, #3D5A80);
        border-radius: 6px; height: 8px;
    }
    .progress-bar-fill.urgent { background: linear-gradient(90deg, #E63B1F, #FF7043); }
    .progress-bar-fill.done   { background: linear-gradient(90deg, #27AE60, #52BE80); }

    /* 側邊欄 */
    [data-testid="stSidebar"] {background: #FAFAFA;}
    [data-testid="stSidebarNav"] {display: none !important;}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 專案資料（示範資料，可替換為 Google Sheets 資料源）
# ============================================================
PROJECTS = [
    {
        "編號": "P-2026-001", "名稱": "2026 Q2 全台門店優化計畫",
        "部門": "營運部", "負責人": "王總監",
        "狀態": "執行中", "優先級": "高",
        "開始日": "2026-04-01", "截止日": "2026-06-30",
        "進度": 35, "標籤": "門店優化",
        "說明": "針對 15 間門店進行服務流程優化，提升翻桌率與客戶滿意度",
    },
    {
        "編號": "P-2026-002", "名稱": "台中逢甲新店開幕準備",
        "部門": "展店部", "負責人": "陳副理",
        "狀態": "執行中", "優先級": "緊急",
        "開始日": "2026-03-15", "截止日": "2026-05-15",
        "進度": 68, "標籤": "展店",
        "說明": "台中逢甲商圈新店裝潢、設備採購、人員招募及試營運規劃",
    },
    {
        "編號": "P-2026-003", "名稱": "POS 系統全台升級",
        "部門": "資訊部", "負責人": "李工程師",
        "狀態": "執行中", "優先級": "高",
        "開始日": "2026-02-01", "截止日": "2026-07-31",
        "進度": 50, "標籤": "資訊系統",
        "說明": "導入新一代 POS 系統，整合線上訂位、外送平台與會員系統",
    },
    {
        "編號": "P-2026-004", "名稱": "2026 五月母親節行銷活動",
        "部門": "行銷部", "負責人": "林行銷長",
        "狀態": "規劃中", "優先級": "高",
        "開始日": "2026-04-20", "截止日": "2026-05-12",
        "進度": 15, "標籤": "行銷活動",
        "說明": "母親節限定套餐設計、社群媒體宣傳、門店佈置與員工培訓",
    },
    {
        "編號": "P-2026-005", "名稱": "菜單 2.0 改版計畫",
        "部門": "研發部", "負責人": "廚藝總監",
        "狀態": "規劃中", "優先級": "中",
        "開始日": "2026-05-01", "截止日": "2026-08-31",
        "進度": 5, "標籤": "產品研發",
        "說明": "引入季節性食材，調整 30% 菜色，強化健康輕食選項",
    },
    {
        "編號": "P-2026-006", "名稱": "Q1 員工教育訓練計畫",
        "部門": "人資部", "負責人": "人資主任",
        "狀態": "已完成", "優先級": "中",
        "開始日": "2026-01-15", "截止日": "2026-03-31",
        "進度": 100, "標籤": "人才培育",
        "說明": "全台員工服務禮儀、食安認證、緊急應變訓練，共 320 人次完訓",
    },
    {
        "編號": "P-2026-007", "名稱": "供應鏈整合與成本優化",
        "部門": "採購部", "負責人": "採購經理",
        "狀態": "執行中", "優先級": "高",
        "開始日": "2026-03-01", "截止日": "2026-09-30",
        "進度": 28, "標籤": "供應鏈",
        "說明": "整合 3 家核心供應商，目標降低食材採購成本 12%",
    },
    {
        "編號": "P-2026-008", "名稱": "會員忠誠度計畫升級",
        "部門": "行銷部", "負責人": "數位行銷師",
        "狀態": "暫緩", "優先級": "低",
        "開始日": "2026-06-01", "截止日": "2026-10-31",
        "進度": 0, "標籤": "會員經營",
        "說明": "等待 POS 系統升級完成後，配合推出積分制會員系統",
    },
    {
        "編號": "P-2026-009", "名稱": "2025 年報與稅務申報",
        "部門": "財務部", "負責人": "財務長",
        "狀態": "已完成", "優先級": "緊急",
        "開始日": "2026-02-01", "截止日": "2026-04-10",
        "進度": 100, "標籤": "財務合規",
        "說明": "2025 全年財務審計、稅務申報及股東報告書編製",
    },
    {
        "編號": "P-2026-010", "名稱": "高雄楠梓新店評估",
        "部門": "展店部", "負責人": "展店副理",
        "狀態": "規劃中", "優先級": "中",
        "開始日": "2026-04-15", "截止日": "2026-06-30",
        "進度": 10, "標籤": "展店",
        "說明": "評估高雄楠梓區商圈可行性，包含市場調查、租金談判及競品分析",
    },
]


@st.cache_data(ttl=300)
def get_projects():
    return pd.DataFrame(PROJECTS)


# ============================================================
# 工具函數
# ============================================================
STATUS_MAP = {
    "執行中": ("tag-executing", "▶"),
    "規劃中": ("tag-planning", "📋"),
    "已完成": ("tag-done", "✅"),
    "暫緩": ("tag-hold", "⏸"),
}

PRIORITY_COLOR = {"緊急": "#E63B1F", "高": "#E67E22", "中": "#2980B9", "低": "#7F8C8D"}

CARD_CLASS = {
    "執行中": "proj-card",
    "規劃中": "proj-card",
    "已完成": "proj-card done",
    "暫緩": "proj-card hold",
}

FILL_CLASS = {
    "執行中": "progress-bar-fill",
    "規劃中": "progress-bar-fill",
    "已完成": "progress-bar-fill done",
    "暫緩": "progress-bar-fill",
}


def priority_badge(p):
    c = PRIORITY_COLOR.get(p, "#888")
    return f'<span style="background:{c};color:white;padding:2px 8px;border-radius:20px;font-size:0.72rem;font-weight:700">{p}</span>'


def render_project_card(row):
    tag_cls, tag_icon = STATUS_MAP.get(row["狀態"], ("tag-planning", "?"))
    card_cls = CARD_CLASS.get(row["狀態"], "proj-card")
    fill_cls = FILL_CLASS.get(row["狀態"], "progress-bar-fill")
    if row["優先級"] == "緊急":
        card_cls += " urgent"
        fill_cls += " urgent"

    progress_pct = min(100, max(0, row["進度"]))
    badge = priority_badge(row["優先級"])

    html = f"""
    <div class="{card_cls}">
        <div class="proj-title">{row['名稱']}</div>
        <div class="proj-meta">
            {badge}
            <span class="proj-tag {tag_cls}">{tag_icon} {row['狀態']}</span>
            <span class="proj-tag" style="background:#F0F0F0;color:#444">{row['標籤']}</span>
            <br>
            📁 {row['部門']} ｜ 👤 {row['負責人']} ｜ 🗓️ {row['截止日']} ｜ #{row['編號']}
            <br>
            <span style="color:#555;font-size:0.8rem">{row['說明']}</span>
        </div>
        <div class="progress-wrap">
            <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#888">
                <span>進度</span><span><b>{progress_pct}%</b></span>
            </div>
            <div class="progress-bar-bg">
                <div class="{fill_cls}" style="width:{progress_pct}%"></div>
            </div>
        </div>
    </div>
    """
    return html


# ============================================================
# 主程式
# ============================================================
def main():
    df = get_projects()

    # 側邊欄
    st.sidebar.markdown("## 🗂️ 嗑肉石鍋 專案進度")
    st.sidebar.caption(f"資料更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.sidebar.page_link("app.py", label="← 返回數位總部大門")
    st.sidebar.divider()

    # 篩選器
    st.sidebar.markdown("### 🔍 篩選")
    all_depts = ["全部"] + sorted(df["部門"].unique().tolist())
    sel_dept = st.sidebar.selectbox("部門", all_depts, key="dept_filter")
    all_status = ["全部", "執行中", "規劃中", "已完成", "暫緩"]
    sel_status = st.sidebar.selectbox("狀態", all_status, key="status_filter")
    all_priority = ["全部", "緊急", "高", "中", "低"]
    sel_priority = st.sidebar.selectbox("優先級", all_priority, key="priority_filter")

    st.sidebar.divider()
    view_mode = st.sidebar.radio("檢視模式", ["看板視圖", "列表視圖", "統計分析"], key="view_mode")

    # 套用篩選
    filtered = df.copy()
    if sel_dept != "全部":
        filtered = filtered[filtered["部門"] == sel_dept]
    if sel_status != "全部":
        filtered = filtered[filtered["狀態"] == sel_status]
    if sel_priority != "全部":
        filtered = filtered[filtered["優先級"] == sel_priority]

    # ========== 頁首 ==========
    st.markdown("## 🗂️ 嗑肉數位總部 ｜ 專案進度追蹤")

    # KPI
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📋 專案總數", f"{len(df)} 件")
    c2.metric("▶ 執行中", f"{len(df[df['狀態']=='執行中'])} 件")
    c3.metric("📋 規劃中", f"{len(df[df['狀態']=='規劃中'])} 件")
    c4.metric("✅ 已完成", f"{len(df[df['狀態']=='已完成'])} 件")
    c5.metric("🔴 緊急", f"{len(df[df['優先級']=='緊急'])} 件")

    st.caption(f"目前篩選：{len(filtered)} 件專案")
    st.divider()

    # ========== 看板視圖 ==========
    if view_mode == "看板視圖":
        st.markdown("<div class='section-header'>🗃️ 專案看板</div>", unsafe_allow_html=True)

        kanban_cols = ["執行中", "規劃中", "已完成", "暫緩"]
        k1, k2, k3, k4 = st.columns(4)
        col_map = {"執行中": k1, "規劃中": k2, "已完成": k3, "暫緩": k4}
        col_label = {
            "執行中": "▶ 執行中",
            "規劃中": "📋 規劃中",
            "已完成": "✅ 已完成",
            "暫緩": "⏸ 暫緩",
        }
        col_color = {
            "執行中": "#2980B9", "規劃中": "#E67E22",
            "已完成": "#27AE60", "暫緩": "#95A5A6",
        }

        for status in kanban_cols:
            with col_map[status]:
                cnt = len(filtered[filtered["狀態"] == status])
                st.markdown(
                    f'<div style="background:{col_color[status]};color:white;padding:6px 12px;'
                    f'border-radius:8px;font-weight:700;margin-bottom:0.8rem">'
                    f'{col_label[status]} ({cnt})</div>',
                    unsafe_allow_html=True
                )
                subset = filtered[filtered["狀態"] == status]
                if subset.empty:
                    st.markdown('<div style="color:#bbb;font-size:0.85rem;padding:0.5rem">（無專案）</div>',
                                unsafe_allow_html=True)
                for _, row in subset.iterrows():
                    st.markdown(render_project_card(row), unsafe_allow_html=True)

    # ========== 列表視圖 ==========
    elif view_mode == "列表視圖":
        st.markdown("<div class='section-header'>📋 專案列表</div>", unsafe_allow_html=True)

        disp = filtered[["編號", "名稱", "部門", "負責人", "狀態", "優先級",
                          "開始日", "截止日", "進度", "標籤"]].copy()
        disp["進度"] = disp["進度"].apply(lambda x: f"{x}%")

        # 狀態排序
        status_order = {"緊急": 0, "高": 1, "中": 2, "低": 3}
        disp_sorted = filtered.copy()
        disp_sorted["_order"] = disp_sorted["優先級"].map(status_order)
        disp_sorted = disp_sorted.sort_values(["_order", "截止日"])

        for _, row in disp_sorted.iterrows():
            with st.expander(f"{'🔴' if row['優先級']=='緊急' else '🟠' if row['優先級']=='高' else '🔵' if row['優先級']=='中' else '⚪'} "
                             f"{row['名稱']}  ─  {row['狀態']} ｜ {row['進度']}%"):
                st.markdown(render_project_card(row), unsafe_allow_html=True)
                cl, cr = st.columns(2)
                with cl:
                    st.write(f"**編號：** {row['編號']}")
                    st.write(f"**部門：** {row['部門']}")
                    st.write(f"**負責人：** {row['負責人']}")
                with cr:
                    st.write(f"**開始日：** {row['開始日']}")
                    st.write(f"**截止日：** {row['截止日']}")
                    st.write(f"**優先級：** {row['優先級']}")

    # ========== 統計分析 ==========
    else:
        st.markdown("<div class='section-header-orange'>📊 專案統計分析</div>", unsafe_allow_html=True)

        ca, cb = st.columns(2)

        with ca:
            # 狀態分佈
            status_cnt = df.groupby("狀態").size().reset_index(name="件數")
            fig1 = px.pie(status_cnt, values="件數", names="狀態",
                          title="各狀態分佈", hole=0.45,
                          color_discrete_sequence=["#2980B9", "#E67E22", "#27AE60", "#95A5A6"])
            fig1.update_layout(height=320)
            st.plotly_chart(fig1, use_container_width=True, key="stat_pie1")

        with cb:
            # 部門工作量
            dept_cnt = df.groupby("部門").size().reset_index(name="件數")
            dept_cnt = dept_cnt.sort_values("件數", ascending=True)
            fig2 = px.bar(dept_cnt, x="件數", y="部門", orientation="h",
                          title="各部門專案數量",
                          color="件數", color_continuous_scale="Blues")
            fig2.update_layout(height=320, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True, key="stat_bar2")

        st.markdown("<div class='section-header'>📈 進度分佈</div>", unsafe_allow_html=True)

        cc, cd = st.columns(2)
        with cc:
            # 進度分佈（執行中專案）
            exec_df = df[df["狀態"] == "執行中"].sort_values("進度", ascending=False)
            fig3 = px.bar(exec_df, x="名稱", y="進度", color="優先級",
                          title="執行中專案進度",
                          color_discrete_map={
                              "緊急": "#E63B1F", "高": "#E67E22", "中": "#2980B9", "低": "#7F8C8D"
                          })
            fig3.add_hline(y=50, line_dash="dot", line_color="#888", annotation_text="50%")
            fig3.update_layout(height=380, xaxis_tickangle=-35, yaxis_title="完成度（%）")
            st.plotly_chart(fig3, use_container_width=True, key="stat_exec")

        with cd:
            # 優先級 × 部門
            pri_dept = df.groupby(["部門", "優先級"]).size().reset_index(name="件數")
            fig4 = px.bar(pri_dept, x="部門", y="件數", color="優先級",
                          title="部門 × 優先級分佈", barmode="stack",
                          color_discrete_map={
                              "緊急": "#E63B1F", "高": "#E67E22", "中": "#2980B9", "低": "#7F8C8D"
                          })
            fig4.update_layout(height=380, xaxis_tickangle=-30)
            st.plotly_chart(fig4, use_container_width=True, key="stat_pri_dept")

        # 甘特圖概覽
        st.markdown("<div class='section-header'>🗓️ 專案時程甘特圖</div>", unsafe_allow_html=True)
        gantt_df = df[df["狀態"] != "暫緩"].copy()
        gantt_df["開始日"] = pd.to_datetime(gantt_df["開始日"])
        gantt_df["截止日"] = pd.to_datetime(gantt_df["截止日"])
        gantt_df = gantt_df.sort_values("截止日")

        fig5 = px.timeline(
            gantt_df, x_start="開始日", x_end="截止日", y="名稱",
            color="狀態",
            color_discrete_map={
                "執行中": "#2980B9", "規劃中": "#E67E22",
                "已完成": "#27AE60", "暫緩": "#95A5A6",
            },
            title="2026 專案時程總覽",
        )
        fig5.update_yaxes(categoryorder="total ascending")
        fig5.add_vline(x=datetime.now(), line_dash="dash", line_color="#E63B1F",
                       annotation_text="今日", annotation_position="top right")
        fig5.update_layout(height=420, xaxis_title="日期", yaxis_title="")
        st.plotly_chart(fig5, use_container_width=True, key="stat_gantt")

        # 完整明細表
        st.markdown("<div class='section-header'>📋 完整明細</div>", unsafe_allow_html=True)
        tbl = df[["編號", "名稱", "部門", "負責人", "狀態", "優先級",
                  "截止日", "進度", "標籤"]].copy()
        tbl["進度"] = tbl["進度"].apply(lambda x: f"{x}%")
        st.dataframe(tbl, use_container_width=True, hide_index=True)


main()
