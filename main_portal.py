import streamlit as st

ACCESS_KEY = "admin888"

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
    .module-card-brain {{
        background: linear-gradient(145deg, #6C3483 0%, #9B59B6 100%);
        box-shadow: 0 6px 24px rgba(108,52,131,0.28);
    }}
    .module-card-mkt {{
        background: linear-gradient(145deg, #117A65 0%, #1ABC9C 100%);
        box-shadow: 0 6px 24px rgba(17,122,101,0.28);
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
                st.session_state["is_admin"] = True
                if "enabled_pages" not in st.session_state:
                    st.session_state["enabled_pages"] = {
                        "數據戰情中心", "專案追蹤師", "決策AI偵察", "品牌數位資產"
                    }
                st.rerun()
            elif key_input:
                st.error("❌ 密鑰錯誤，請重新輸入")
        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# 分頁權限設定（管理員勾選）
# ============================================================
ALL_PAGES = {
    "數據戰情中心": ("pages/1_數據戰情中心.py", "📊", "營收儀表板・門店排行・達標追蹤<br>商圈分析・AI 數據洞察"),
    "專案追蹤師":   ("pages/2_專案追蹤師.py",   "🗂️", "6 部門跨部門工作進度・審核批示<br>AI 督導摘要・紅黃燈預警"),
    "決策AI偵察":   ("pages/3_決策AI偵察.py",   "🧠", "跨部門連動診斷・偏差警示<br>逾期任務追蹤・白話報告"),
    "品牌數位資產": ("pages/4_品牌數位資產.py", "🎨", "活動成效追蹤・ROI 分析<br>社群觸及・營收增長對照"),
}

CARD_CLASSES = {
    "數據戰情中心": "",
    "專案追蹤師":   "module-card-ops",
    "決策AI偵察":   "module-card-brain",
    "品牌數位資產": "module-card-mkt",
}


# ============================================================
# 已驗證：門戶主頁
# ============================================================
def show_portal():
    enabled = st.session_state.get("enabled_pages", set(ALL_PAGES.keys()))

    with st.sidebar:
        st.markdown("## 🏢 嗑肉數位總部")
        st.caption("管理員指揮中心")
        st.divider()

        # 管理員分頁勾選
        st.markdown("### ⚙️ 本次開放功能")
        new_enabled: set[str] = set()
        for page_name in ALL_PAGES:
            checked = st.checkbox(
                page_name,
                value=(page_name in enabled),
                key=f"chk_{page_name}",
            )
            if checked:
                new_enabled.add(page_name)
        st.session_state["enabled_pages"] = new_enabled

        st.divider()
        st.markdown("### 🚪 快速進入")
        for page_name, (path, icon, _) in ALL_PAGES.items():
            if page_name in new_enabled:
                st.page_link(path, label=f"{icon} {page_name}")
            else:
                st.caption(f"🔒 {page_name}（已關閉）")
        st.divider()
        if st.button("🔒 登出", use_container_width=True):
            for k in ("authenticated", "is_admin", "enabled_pages"):
                st.session_state.pop(k, None)
            st.rerun()

    # 主體
    st.markdown('<div class="hq-title">🏢 嗑肉數位總部</div>', unsafe_allow_html=True)
    st.markdown('<div class="hq-subtitle">管理員指揮中心 ｜ 功能別模組導航</div>', unsafe_allow_html=True)
    st.markdown('<div class="welcome-bar">✅ 管理員已驗證，歡迎回到總部 — 請在左側勾選本次開放的功能分頁</div>',
                unsafe_allow_html=True)

    enabled_now = st.session_state.get("enabled_pages", set())

    cols = st.columns(2, gap="large")
    page_items = list(ALL_PAGES.items())
    for i, (page_name, (path, icon, desc)) in enumerate(page_items):
        col = cols[i % 2]
        extra_class = CARD_CLASSES.get(page_name, "")
        locked = page_name not in enabled_now
        with col:
            lock_badge = '<span style="position:absolute;top:12px;right:16px;font-size:1.4rem;">🔒</span>' if locked else ''
            opacity = '0.5' if locked else '1'
            card_html = (
                f'<div class="module-card {extra_class}" style="position:relative;opacity:{opacity};">'
                f'{lock_badge}'
                f'<span class="icon">{icon}</span>'
                f'<h2>{page_name}</h2>'
                f'<p>{desc}</p>'
                f'</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)
            if not locked:
                st.page_link(path, label=f"→ 進入 {page_name}", use_container_width=True)
            else:
                st.caption("🔒 尚未開放，請在左側勾選啟用")


# ============================================================
# 主程式
# ============================================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if st.session_state["authenticated"]:
    show_portal()
else:
    show_login()
