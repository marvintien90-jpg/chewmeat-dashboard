import streamlit as st

ACCESS_KEY = "kerou888"

st.set_page_config(
    page_title="嗑肉數位總部",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* 隱藏側邊欄頁面導覽 */
    [data-testid="stSidebarNav"] {display: none !important;}
    [data-testid="collapsedControl"] {display: none !important;}

    /* 全域重置 */
    .main .block-container {
        padding-top: 4rem;
        padding-bottom: 3rem;
        max-width: 860px;
        margin: 0 auto;
    }

    /* 總部標題 */
    .hq-title {
        font-size: 2.6rem;
        font-weight: 900;
        color: #E63B1F;
        text-align: center;
        letter-spacing: -0.5px;
        margin-bottom: 0.4rem;
    }
    .hq-subtitle {
        font-size: 1.05rem;
        color: #999;
        text-align: center;
        margin-bottom: 3rem;
    }

    /* 登入卡片 */
    .login-card {
        background: #FFFFFF;
        border: 2px solid #F0E8E5;
        border-radius: 16px;
        padding: 2.5rem 2rem;
        box-shadow: 0 4px 24px rgba(230, 59, 31, 0.08);
    }

    /* 模組卡片 */
    .module-card {
        background: linear-gradient(145deg, #E63B1F 0%, #FF6B3D 100%);
        color: white;
        padding: 2.2rem 1.5rem;
        border-radius: 18px;
        text-align: center;
        box-shadow: 0 6px 24px rgba(230, 59, 31, 0.28);
        margin-bottom: 0.5rem;
    }
    .module-card-ops {
        background: linear-gradient(145deg, #2C3E50 0%, #3D5A80 100%);
        box-shadow: 0 6px 24px rgba(44, 62, 80, 0.28);
    }
    .module-card .icon { font-size: 3rem; display: block; margin-bottom: 0.6rem; }
    .module-card h2 { font-size: 1.7rem; margin: 0.3rem 0; font-weight: 800; }
    .module-card p { font-size: 0.88rem; opacity: 0.88; line-height: 1.6; margin: 0; }

    /* 歡迎橫幅 */
    .welcome-bar {
        background: #FFF3EE;
        border: 1.5px solid #FFCBB8;
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        margin-bottom: 2.5rem;
        display: flex;
        align-items: center;
        gap: 0.8rem;
        font-size: 0.95rem;
        color: #C1320F;
        font-weight: 600;
    }

    /* Streamlit 按鈕覆寫 */
    .stButton > button[kind="primary"] {
        background-color: #E63B1F !important;
        border-color: #E63B1F !important;
        color: white !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        padding: 0.6rem 1.5rem !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #C1320F !important;
        border-color: #C1320F !important;
    }
    /* page_link 按鈕樣式 */
    a[data-testid="stPageLink"] {
        background: rgba(255,255,255,0.15) !important;
        border: 2px solid rgba(255,255,255,0.5) !important;
        color: white !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        transition: all 0.15s !important;
    }
</style>
""", unsafe_allow_html=True)


def show_login():
    st.markdown('<div class="hq-title">🏢 嗑肉數位總部</div>', unsafe_allow_html=True)
    st.markdown('<div class="hq-subtitle">指揮中心 ｜ 請輸入存取密鑰以進入</div>', unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown("#### 🔑 身份驗證")
        key_input = st.text_input(
            "存取密鑰",
            type="password",
            placeholder="請輸入密鑰...",
            label_visibility="collapsed",
            key="key_input",
        )
        enter_clicked = st.button("進入總部", type="primary", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if enter_clicked:
            if key_input == ACCESS_KEY:
                st.session_state["authenticated"] = True
                st.rerun()
            elif key_input:
                st.error("❌ 密鑰錯誤，請重新輸入")


def show_portal():
    st.markdown('<div class="hq-title">🏢 嗑肉數位總部</div>', unsafe_allow_html=True)
    st.markdown('<div class="hq-subtitle">指揮中心 ｜ 選擇部門進入功能模組</div>', unsafe_allow_html=True)

    st.markdown('<div class="welcome-bar">✅ 已驗證身份，歡迎回到總部</div>', unsafe_allow_html=True)

    col_logout = st.columns([6, 1])
    with col_logout[1]:
        if st.button("登出", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown("""
        <div class="module-card">
            <span class="icon">📊</span>
            <h2>財務部</h2>
            <p>營收儀表板・門店排行・達標追蹤<br>商圈分析・AI 數據洞察</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/1_營收看板.py", label="→ 進入財務部（營收看板）", use_container_width=True)

    with c2:
        st.markdown("""
        <div class="module-card module-card-ops">
            <span class="icon">🗂️</span>
            <h2>營運部</h2>
            <p>專案進度追蹤・任務看板<br>待辦管理・專案狀態總覽</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/2_專案進度.py", label="→ 進入營運部（專案進度）", use_container_width=True)


# ============================================================
# 主程式
# ============================================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if st.session_state["authenticated"]:
    show_portal()
else:
    show_login()
