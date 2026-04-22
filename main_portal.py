import streamlit as st
import json
import os
from utils.icons import card_icon_html
from utils.ui_helpers import inject_global_css

# 密碼優先讀 st.secrets，本地開發則 fallback 至預設值
try:
    ACCESS_KEY = st.secrets.get("admin_password", "admin888")
except Exception:
    ACCESS_KEY = "admin888"

# Config paths
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCESS_CONTROL_PATH = os.path.join(_BASE_DIR, "config", "access_control.json")

# Default admin config
_DEFAULT_ACCESS = {
    ACCESS_KEY: {
        "role": "admin",
        "display_name": "總指揮",
        "allowed_pages": ["數據戰情中心", "專案追蹤師", "決策AI偵察", "品牌數位資產", "Line智能邊緣代理人", "系統設定"],
    }
}

def _load_access_control() -> dict:
    """Load access control config from JSON file."""
    if os.path.exists(ACCESS_CONTROL_PATH):
        try:
            with open(ACCESS_CONTROL_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    return data
        except Exception:
            pass
    return _DEFAULT_ACCESS.copy()

def _save_access_control(data: dict) -> bool:
    """Save access control config to JSON file."""
    os.makedirs(os.path.dirname(ACCESS_CONTROL_PATH), exist_ok=True)
    try:
        with open(ACCESS_CONTROL_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

# ── 功能模組命名映射（顯示名稱 ↔ 內部鍵）──────────────────────────
DISPLAY_NAMES: dict[str, str] = {
    "數據戰情中心":       "[核心] 數位戰情室",
    "專案追蹤師":         "[核心] 跨部追蹤督導",
    "決策AI偵察":         "[決策] 智能 AI 偵察",
    "品牌數位資產":       "[品牌] 數位資產管理",
    "Line智能邊緣代理人": "[指揮] Line 邊緣代理人",
    "系統設定":           "[管理] 系統設定",
}
REVERSE_NAMES: dict[str, str] = {v: k for k, v in DISPLAY_NAMES.items()}

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
    .module-card-admin {{
        background: linear-gradient(145deg, #7D3C98 0%, #A569BD 100%);
        box-shadow: 0 6px 24px rgba(125,60,152,0.28);
    }}
    .module-card .icon-wrap {{ display: flex; align-items: center; justify-content: center; margin-bottom: 0.7rem; }}
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
            if key_input:
                access_db = _load_access_control()
                if key_input in access_db:
                    user_cfg = access_db[key_input]
                    st.session_state["authenticated"] = True
                    st.session_state["is_admin"] = (user_cfg.get("role") == "admin")
                    st.session_state["user_display_name"] = user_cfg.get("display_name", "使用者")
                    allowed = set(user_cfg.get("allowed_pages", []))
                    st.session_state["enabled_pages"] = allowed
                    if user_cfg.get("role") == "admin":
                        allowed.add("系統設定")
                        st.session_state["enabled_pages"] = allowed
                    st.session_state["user_role"] = user_cfg.get("role", "viewer")
                    st.rerun()
                else:
                    st.error("❌ 密鑰錯誤，請重新輸入")
        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# 分頁權限設定（管理員勾選）
# ============================================================
ALL_PAGES = {
    "數據戰情中心":       ("pages/1_數據戰情中心.py",   "chart-bar",      "營收儀表板・門店排行・達標追蹤<br>商圈分析・AI 數據洞察"),
    "專案追蹤師":         ("pages/2_專案追蹤師.py",     "clipboard-list", "6 部門跨部門工作進度・審核批示<br>AI 督導摘要・紅黃燈預警"),
    "決策AI偵察":         ("pages/3_決策AI偵察.py",     "light-bulb",     "跨部門連動診斷・偏差警示<br>逾期任務追蹤・白話報告"),
    "品牌數位資產":       ("pages/4_品牌數位資產.py",   "sparkles",       "活動成效追蹤・ROI 分析<br>社群觸及・營收增長對照"),
    "Line智能邊緣代理人": ("pages/6_Line邊緣代理人.py", "bell",           "Line群組掃描・三色分級預警<br>分身決策沙盒・全景戰報推播"),
    "系統設定":           ("pages/5_系統設定.py",       "cog",            "部門 Sheet 連線・密碼管理<br>系統參數設定"),
}

CARD_CLASSES = {
    "數據戰情中心":       "",
    "專案追蹤師":         "module-card-ops",
    "決策AI偵察":         "module-card-brain",
    "品牌數位資產":       "module-card-mkt",
    "Line智能邊緣代理人": "module-card-ops",
    "系統設定":           "module-card-admin",
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

        # ── 管理員分頁多選 ──────────────────────────────────
        st.markdown("### ⚙️ 本次開放功能")
        all_display = [DISPLAY_NAMES[p] for p in ALL_PAGES]
        default_display = [DISPLAY_NAMES[p] for p in ALL_PAGES if p in enabled]
        is_admin_user = st.session_state.get("is_admin", False)
        if is_admin_user:
            # 若 session state 尚未設定（例如頁面重整後仍登入），以 enabled_pages 初始化
            if "sidebar_pages_multiselect" not in st.session_state:
                st.session_state["sidebar_pages_multiselect"] = default_display
            selected_display = st.multiselect(
                "選擇本次開放的功能模組",
                options=all_display,
                label_visibility="collapsed",
                key="sidebar_pages_multiselect",
            )
        else:
            # Non-admin: show read-only list of their allowed pages
            allowed_display = [DISPLAY_NAMES.get(p, p) for p in enabled if p in DISPLAY_NAMES]
            st.markdown("**您可使用的功能：**")
            for d in allowed_display:
                st.caption(f"✅ {d}")
            selected_display = allowed_display  # Cannot change
        new_enabled: set[str] = {REVERSE_NAMES[d] for d in selected_display if d in REVERSE_NAMES}
        if not is_admin_user:
            # Non-admin: keep their original enabled pages, no change
            new_enabled = enabled
        st.session_state["enabled_pages"] = new_enabled

        # ── 快速跳轉下拉選單 ────────────────────────────────
        st.divider()
        st.markdown("### 🚀 快速進入")
        nav_opts = ["— 選擇功能模組 —"] + [DISPLAY_NAMES[p] for p in ALL_PAGES if p in new_enabled]
        chosen_display = st.selectbox(
            "功能導航",
            options=nav_opts,
            label_visibility="collapsed",
            key="portal_nav_select",
        )
        if chosen_display and chosen_display != "— 選擇功能模組 —":
            internal_key = REVERSE_NAMES.get(chosen_display)
            if internal_key and internal_key in ALL_PAGES:
                st.switch_page(ALL_PAGES[internal_key][0])

        # 未開放模組提示
        locked_pages = [p for p in ALL_PAGES if p not in new_enabled]
        if locked_pages:
            for lp in locked_pages:
                st.caption(f"🔒 {DISPLAY_NAMES[lp]}（已關閉）")

        # Admin-only password management
        if st.session_state.get("is_admin", False):
            st.divider()
            st.markdown("### 🔐 密碼權限管理")
            with st.expander("管理存取密碼", expanded=False):
                access_db = _load_access_control()

                # Show existing passwords
                st.markdown("**目前的存取密碼：**")
                for pw, cfg in list(access_db.items()):
                    is_admin_pw = cfg.get("role") == "admin"
                    role_icon = "👑" if is_admin_pw else "👤"
                    with st.container():
                        col_pw, col_del = st.columns([4, 1])
                        with col_pw:
                            pages_str = "、".join(cfg.get("allowed_pages", []))
                            st.markdown(f"{role_icon} **`{pw}`** ({cfg.get('display_name','')}) → {pages_str}")
                        with col_del:
                            if not is_admin_pw:  # Cannot delete admin
                                if st.button("🗑️", key=f"del_{pw}", help=f"刪除密碼 {pw}"):
                                    del access_db[pw]
                                    _save_access_control(access_db)
                                    st.rerun()

                st.divider()
                st.markdown("**新增存取密碼：**")
                new_pw = st.text_input("新密碼", placeholder="輸入新密碼…", key="new_pw_input")
                new_name = st.text_input("使用者名稱", placeholder="例：行銷部長", key="new_name_input")
                new_pages = st.multiselect(
                    "可存取的功能模組",
                    options=list(ALL_PAGES.keys()),
                    default=["數據戰情中心"],
                    key="new_pages_select",
                )

                if st.button("➕ 新增密碼", use_container_width=True, key="add_pw_btn"):
                    if new_pw and new_pw.strip():
                        if new_pw in access_db:
                            st.warning("⚠️ 此密碼已存在，請換一個")
                        elif len(new_pw) < 4:
                            st.warning("⚠️ 密碼至少需要 4 個字元")
                        else:
                            access_db[new_pw] = {
                                "role": "viewer",
                                "display_name": new_name.strip() or "一般用戶",
                                "allowed_pages": new_pages,
                            }
                            _save_access_control(access_db)
                            st.success(f"✅ 已新增密碼：{new_pw}")
                            st.rerun()
                    else:
                        st.warning("⚠️ 請輸入密碼")

        st.divider()
        if st.button("🔒 登出", use_container_width=True):
            for k in ("authenticated", "is_admin", "enabled_pages", "user_display_name", "user_role"):
                st.session_state.pop(k, None)
            st.rerun()

    # 全域樣式（側欄分隔 + 手機響應式）
    inject_global_css()

    # 主體
    st.markdown('<div class="hq-title">🏢 嗑肉數位總部</div>', unsafe_allow_html=True)
    st.markdown('<div class="hq-subtitle">管理員指揮中心 ｜ 功能別模組導航</div>', unsafe_allow_html=True)
    user_name = st.session_state.get("user_display_name", "管理員")
    is_admin = st.session_state.get("is_admin", False)
    role_badge = "👑 管理員" if is_admin else "👤 一般用戶"
    st.markdown(f'<div class="welcome-bar">✅ {role_badge} [{user_name}] 已驗證，歡迎回到總部 — 請在左側多選框勾選本次開放的功能模組，再用下拉選單快速進入</div>',
                unsafe_allow_html=True)

    enabled_now = st.session_state.get("enabled_pages", set())

    cols = st.columns(2, gap="large")
    page_items = list(ALL_PAGES.items())
    for i, (page_name, (path, icon, desc)) in enumerate(page_items):
        # Skip system settings for non-admin
        if page_name == "系統設定" and not st.session_state.get("is_admin", False):
            continue
        col = cols[i % 2]
        extra_class = CARD_CLASSES.get(page_name, "")
        locked = page_name not in enabled_now
        with col:
            display_name = DISPLAY_NAMES.get(page_name, page_name)
            lock_badge = '<span style="position:absolute;top:12px;right:16px;font-size:1.4rem;">🔒</span>' if locked else ''
            opacity = '0.5' if locked else '1'
            card_html = (
                f'<div class="module-card {extra_class}" style="position:relative;opacity:{opacity};">'
                f'{lock_badge}'
                f'<div class="icon-wrap">{card_icon_html(icon, size=40)}</div>'
                f'<h2>{display_name}</h2>'
                f'<p>{desc}</p>'
                f'</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)
            if not locked:
                st.page_link(path, label=f"→ 進入 {display_name}", use_container_width=True)
            else:
                st.caption("🔒 尚未開放，請在左側多選框勾選啟用")


# ============================================================
# 主程式
# ============================================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if st.session_state["authenticated"]:
    show_portal()
else:
    show_login()
