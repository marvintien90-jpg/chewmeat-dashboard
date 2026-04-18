import streamlit as st

ACCESS_KEY = "kerou888"

# 讀 session_state 不觸發任何 Streamlit 輸出，可在 set_page_config 之前安全使用
_authenticated = st.session_state.get("authenticated", False)

st.set_page_config(
    page_title="嗑肉數位總部",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded" if _authenticated else "collapsed",
)

# ============================================================
# CSS：圖 B 風格（扁平橘紅、白底、圓角、全中文）
# ============================================================
_hide_collapse = "" if _authenticated else """
    [data-testid="collapsedControl"] {display: none !important;}
"""

st.markdown(f"""
<style>
    /* 隱藏 Streamlit 預設頁面清單（由大門統一管理） */
    [data-testid="stSidebarNav"] {{display: none !important;}}
    {_hide_collapse}

    /* 主體留白 */
    .main .block-container {{
        padding-top: 4rem;
        padding-bottom: 3rem;
        max-width: 860px;
        margin: 0 auto;
    }}

    /* 總部標題 */
    .hq-title {{
        font-size: 2.6rem;
        font-weight: 900;
        color: #E63B1F;
        text-align: center;
        letter-spacing: -0.5px;
        margin-bottom: 0.4rem;
    }}
    .hq-subtitle {{
        font-size: 1.05rem;
        color: #999;
        text-align: center;
        margin-bottom: 3rem;
    }}

    /* 登入卡片 */
    .login-card {{
        background: #FFFFFF;
        border: 2px solid #F0E8E5;
        border-radius: 16px;
        padding: 2.5rem 2rem;
        box-shadow: 0 4px 24px rgba(230,59,31,0.08);
    }}

    /* 模組卡片 */
    .module-card {{
        background: linear-gradient(145deg, #E63B1F 0%, #FF6B3D 100%);
        color: white;
        padding: 2.2rem 1.5rem;
        border-radius: 18px;
        text-align: center;
        box-shadow: 0 6px 24px rgba(230,59,31,0.28);
        margin-bottom: 0.5rem;
    }}
    .module-card-ops {{
        background: linear-gradient(145deg, #2C3E50 0%, #3D5A80 100%);
        box-shadow: 0 6px 24px rgba(44,62,80,0.28);
    }}
    .module-card .icon {{ font-size: 3rem; display: block; margin-bottom: 0.6rem; }}
    .module-card h2 {{ font-size: 1.7rem; margin: 0.3rem 0; font-weight: 800; }}
    .module-card p  {{ font-size: 0.88rem; opacity: 0.88; line-height: 1.6; margin: 0; }}

    /* 已驗證橫幅 */
    .welcome-bar {{
        background: #FFF3EE;
        border: 1.5px solid #FFCBB8;
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        margin-bottom: 2.5rem;
        font-size: 0.95rem;
        color: #C1320F;
        font-weight: 600;
    }}

    /* 按鈕覆寫 */
    .stButton > button[kind="primary"] {{
        background-color: #E63B1F !important;
        border-color: #E63B1F !important;
        color: white !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: #C1320F !important;
        border-color: #C1320F !important;
    }}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 登入畫面
# ============================================================
def show_login():
    st.markdown('<div class="hq-title">🏢 嗑肉數位總部</div>', unsafe_allow_html=True)
    st.markdown('<div class="hq-subtitle">指揮中心 ｜ 請輸入存取密鑰以進入</div>', unsafe_allow_html=True)

    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown("#### 🔑 身份驗證")
        key_input = st.text_input(
            "存取密鑰",
            type="password",
            placeholder="請輸入密鑰…",
            label_visibility="collapsed",
            key="key_input",
        )
        if st.button("進入總部", type="primary", use_container_width=True):
            if key_input == ACCESS_KEY:
                st.session_state["authenticated"] = True
                st.rerun()
            elif key_input:
                st.error("❌ 密鑰錯誤，請重新輸入")
        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# 已驗證：門戶主頁
# ============================================================
def show_portal():
    # 側邊欄：登出按鈕 + 快速導航
    with st.sidebar:
        st.markdown("## 🏢 嗑肉數位總部")
        st.caption("指揮中心")
        st.divider()
        st.markdown("### 🚪 快速進入")
        st.page_link("pages/1_營收看板.py", label="📊 財務部 — 營收看板")
        st.page_link("pages/2_專案進度.py", label="🗂️ 營運部 — 專案進度")
        st.divider()
        if st.button("🔒 登出", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    # 主體
    st.markdown('<div class="hq-title">🏢 嗑肉數位總部</div>', unsafe_allow_html=True)
    st.markdown('<div class="hq-subtitle">指揮中心 ｜ 選擇部門進入功能模組</div>', unsafe_allow_html=True)
    st.markdown('<div class="welcome-bar">✅ 身份已驗證，歡迎回到總部</div>', unsafe_allow_html=True)

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
