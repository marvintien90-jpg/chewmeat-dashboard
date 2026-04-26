"""pages/7_帳號管理.py — 帳號資安管理系統"""
import streamlit as st, json
from utils.icons import icon_svg

# ── 權限守門 ──────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.warning("請先登入"); st.stop()
if st.session_state.get("user_role") != "admin":
    st.error("此頁面僅限系統管理員存取"); st.stop()

from utils import auth_manager, edge_store
edge_store.init_db()  # 確保 accounts / login_history / it_health_log 資料表存在

st.set_page_config(page_title="帳號管理", page_icon="🔐", layout="wide")

ROLE_LABELS = {"admin":"系統管理員","manager":"部門主管","staff":"一般員工"}
ROLE_COLORS = {"admin":"🔴","manager":"🟡","staff":"🟢"}
STATUS_ICON = {"active":"✅ 生效中","disabled":"⛔ 已停用"}

# ── Header ────────────────────────────────────────────────────────
st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;padding:12px 0 4px">
  {icon_svg("shield-check",32,"#6366f1")}
  <div>
    <h2 style="margin:0;font-size:1.5rem;font-weight:700">帳號資安管理</h2>
    <p style="margin:0;font-size:.85rem;color:#888">帳號生命週期・登入記錄・權限控管</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 功能列 ────────────────────────────────────────────────────────
accounts = auth_manager.list_accounts()
active_cnt   = sum(1 for a in accounts if a["status"] == "active")
disabled_cnt = sum(1 for a in accounts if a["status"] == "disabled")
history      = auth_manager.get_login_history(limit=100)
fail_today   = sum(1 for h in history if not h["success"])

col1,col2,col3,col4 = st.columns(4)
col1.metric("生效帳號", active_cnt, help="目前可登入帳號數")
col2.metric("停用帳號", disabled_cnt, help="已停用（保留記錄）")
col3.metric("今日登入失敗", fail_today, help="可能的資安風險")
col4.metric("帳號總數", len(accounts))

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["📋 帳號總覽", "➕ 新增帳號", "⚙️ 帳號設定", "📜 登入記錄"])

# ══════════════════════════════════════════════════════════════════
# Tab 1：帳號總覽
# ══════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("#### 所有帳號")
    if not accounts:
        st.info("尚無帳號")
    else:
        for acct in accounts:
            role_emoji = ROLE_COLORS.get(acct["role"],"⚪")
            status_txt = STATUS_ICON.get(acct["status"],"?")
            pages_list = json.loads(acct.get("allowed_pages","[]") or "[]")
            with st.expander(f"{role_emoji} **{acct['display_name']}** (`{acct['username']}`)  ·  {status_txt}"):
                c1,c2,c3 = st.columns(3)
                c1.markdown(f"**角色** {ROLE_LABELS.get(acct['role'],acct['role'])}")
                c2.markdown(f"**部門** {acct.get('dept') or '—'}")
                c3.markdown(f"**建立** {str(acct.get('created_at',''))[:10]}")
                st.markdown(f"**可使用頁面：** {' · '.join(pages_list) if pages_list else '無'}")
                if acct.get("last_login"):
                    st.caption(f"最後登入：{str(acct['last_login'])[:19]}")
                if acct.get("disabled_at"):
                    st.caption(f"停用時間：{str(acct['disabled_at'])[:19]}  停用者：{acct.get('disabled_by','')}")

# ══════════════════════════════════════════════════════════════════
# Tab 2：新增帳號
# ══════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("#### 建立新帳號")
    with st.form("create_account_form"):
        c1,c2 = st.columns(2)
        new_username     = c1.text_input("帳號名稱 *", placeholder="例：mary_hr")
        new_display      = c2.text_input("顯示名稱 *", placeholder="例：Mary 人資")
        new_password     = c1.text_input("密碼 *", type="password", placeholder="至少 4 個字元")
        new_role         = c2.selectbox("角色", list(ROLE_LABELS.keys()),
                                        format_func=lambda r: ROLE_LABELS[r])
        new_dept         = c1.text_input("部門", placeholder="例：人資、行銷")
        new_pages        = st.multiselect("可存取頁面",
                                          auth_manager.ALL_PAGES,
                                          default=auth_manager.ROLE_DEFAULT_PAGES.get(new_role,[]))
        submitted = st.form_submit_button("✅ 建立帳號", use_container_width=True, type="primary")
        if submitted:
            ok, msg = auth_manager.create_account(
                new_username, new_password, new_display, new_role, new_dept, new_pages)
            if ok: st.success(msg); st.rerun()
            else:  st.error(msg)

# ══════════════════════════════════════════════════════════════════
# Tab 3：帳號設定
# ══════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### 管理現有帳號")
    non_admin = [a for a in accounts if a["username"] != st.session_state.get("username","admin")]
    if not non_admin:
        st.info("目前只有您的 admin 帳號，請先新增其他帳號")
    else:
        sel = st.selectbox("選擇帳號",
                           [a["username"] for a in non_admin],
                           format_func=lambda u: f"{next(a['display_name'] for a in non_admin if a['username']==u)} ({u})")
        acct = auth_manager.get_account(sel)
        if acct:
            status = acct["status"]
            st.info(f"**{acct['display_name']}** · {ROLE_LABELS.get(acct['role'])} · {STATUS_ICON.get(status)}")
            c1,c2,c3 = st.columns(3)

            # 啟用 / 停用
            if status == "active":
                if c1.button("⛔ 停用帳號", use_container_width=True):
                    ok, msg = auth_manager.disable_account(sel, st.session_state.get("username","admin"))
                    st.success(msg) if ok else st.error(msg); st.rerun()
            else:
                if c1.button("✅ 重新啟用", use_container_width=True, type="primary"):
                    ok, msg = auth_manager.enable_account(sel)
                    st.success(msg) if ok else st.error(msg); st.rerun()

            # 更改密碼
            with c2.popover("🔑 更改密碼"):
                new_pw = st.text_input("新密碼", type="password", key=f"pw_{sel}")
                if st.button("確認更改", key=f"pw_btn_{sel}"):
                    ok, msg = auth_manager.change_password(sel, new_pw)
                    st.success(msg) if ok else st.error(msg)

            # 更新頁面權限
            with c3.popover("🛡️ 權限管理"):
                cur_pages = json.loads(acct.get("allowed_pages","[]") or "[]")
                new_pages = st.multiselect("可存取頁面", auth_manager.ALL_PAGES,
                                           default=cur_pages, key=f"pg_{sel}")
                if st.button("儲存權限", key=f"pg_btn_{sel}"):
                    ok, msg = auth_manager.update_permissions(sel, new_pages)
                    st.success(msg) if ok else st.error(msg)

# ══════════════════════════════════════════════════════════════════
# Tab 4：登入記錄
# ══════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("#### 登入歷史記錄")
    filter_user = st.selectbox("篩選帳號", ["全部"] + [a["username"] for a in accounts])
    hist = auth_manager.get_login_history(
        None if filter_user == "全部" else filter_user, limit=100)
    if not hist:
        st.info("尚無登入記錄")
    else:
        import pandas as pd
        df = pd.DataFrame(hist)[["login_at","username","success","ip_address","fail_reason"]]
        df.columns = ["時間","帳號","成功","IP","失敗原因"]
        df["成功"] = df["成功"].map({1:"✅",0:"❌"})
        df["時間"] = df["時間"].str[:19]
        st.dataframe(df, use_container_width=True, hide_index=True)
