"""
6_Line邊緣代理人.py
嗑肉數位總部：分身參謀全景看板 (Avatar Command Dashboard)
Line 智能邊緣代理人 (Edge Agent) 系統 — v1.0
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random
import re
import json

# ── 頁面設定 (必須最先) ──────────────────────────────────────────
st.set_page_config(
    page_title="嗑肉數位總部 ｜ Line 邊緣代理人",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 認證守衛 ────────────────────────────────────────────────────
if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("app.py", label="← 返回數位總部大門")
    st.stop()

if "Line智能邊緣代理人" not in st.session_state.get("enabled_pages", set()):
    st.error("🔒 本功能尚未開放")
    st.page_link("app.py", label="← 返回總部")
    st.stop()

# ── 共用 CSS helper ──────────────────────────────────────────────
from utils.ui_helpers import inject_global_css
inject_global_css()

# ================================================================
# CSS 視覺樣式定義 (橘紅 #E63B1F 主色系)
# ================================================================
st.markdown("""
<style>
/* 主標題 */
.main-header {
    background: linear-gradient(135deg, #E63B1F 0%, #C62828 100%);
    padding: 20px 30px;
    border-radius: 15px;
    color: white;
    margin-bottom: 20px;
    box-shadow: 0 4px 15px rgba(230, 59, 31, 0.3);
}

/* 對話氣泡 */
.chat-bubble {
    padding: 18px;
    border-radius: 18px;
    margin-bottom: 12px;
    display: flex;
    align-items: flex-start;
    box-shadow: 2px 2px 10px rgba(0,0,0,0.08);
    transition: all 0.3s ease;
}
.chat-bubble:hover {
    transform: translateY(-2px);
    box-shadow: 4px 4px 15px rgba(0,0,0,0.15);
}

/* 三色分級背景 */
.bg-red    { background-color: #FFEBE9; border-left: 8px solid #E63B1F; }
.bg-yellow { background-color: #FFF9E6; border-left: 8px solid #F1C40F; }
.bg-blue   { background-color: #E8F4FD; border-left: 8px solid #3498DB; }
.bg-monitoring { background-color: #F8F9FA; border-left: 8px solid #BDC3C7; opacity: 0.6; }

/* 頭像 */
.avatar {
    width: 45px;
    height: 45px;
    border-radius: 50%;
    background: linear-gradient(135deg, #E63B1F 0%, #FF6B4A 100%);
    color: white;
    margin-right: 15px;
    display: flex;
    justify-content: center;
    align-items: center;
    font-weight: bold;
    flex-shrink: 0;
    font-size: 16px;
}

/* 標籤 */
.store-tag {
    display: inline-block;
    background-color: rgba(0,0,0,0.08);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    margin-right: 6px;
    font-weight: 600;
}
.time-warning { color: #E63B1F; font-weight: bold; font-size: 13px; }
.time-normal  { color: #666; font-size: 12px; }

/* 欄位標題 */
.column-header {
    padding: 12px;
    border-radius: 10px;
    color: white;
    text-align: center;
    font-weight: bold;
    font-size: 16px;
    margin-bottom: 15px;
}
.header-red    { background: linear-gradient(135deg, #E63B1F 0%, #C62828 100%); }
.header-yellow { background: linear-gradient(135deg, #F39C12 0%, #E67E22 100%); }
.header-blue   { background: linear-gradient(135deg, #3498DB 0%, #2980B9 100%); }

/* 指標卡片 */
.metric-card {
    background: white;
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    text-align: center;
}

/* 隱藏 Streamlit 預設元素 */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ================================================================
# 【區塊 3】Mock 資料庫
# ================================================================
STORE_LIST = [
    "崇德店", "美村店", "公益店", "北屯店", "南屯店",
    "西屯店", "東區店", "北區店", "南區店", "中區店",
    "豐原店", "太平店", "大里店", "霧峰店", "沙鹿店"
]
MANAGER_LIST = ["張主管", "李主管", "王主管", "陳主管", "林主管"]


def _edge_init():
    """初始化 Edge Agent 專屬 session state（用 edge_ 前綴避免與其他頁面衝突）"""
    if "edge_events" not in st.session_state:
        st.session_state.edge_events = _generate_mock_events()
    if "edge_last_scan" not in st.session_state:
        st.session_state.edge_last_scan = datetime.now()
    if "edge_mgr_count" not in st.session_state:
        st.session_state.edge_mgr_count = {m: random.randint(0, 8) for m in MANAGER_LIST}
    if "edge_learning" not in st.session_state:
        st.session_state.edge_learning = []
    if "edge_show_report" not in st.session_state:
        st.session_state.edge_show_report = False
    if "edge_show_learning" not in st.session_state:
        st.session_state.edge_show_learning = False
    if "edge_show_closed" not in st.session_state:
        st.session_state.edge_show_closed = False


def _generate_mock_events():
    red_samples = [
        {"content": "崇德店 POS 機故障，無法結帳，客人排很長！",    "user": "店員小美"},
        {"content": "美村店冷藏櫃溫度異常，商品可能要報廢",          "user": "店員阿強"},
        {"content": "公益店招牌電源故障，晚上無法運作",              "user": "店長王姐"},
    ]
    yellow_samples = [
        {"content": "北屯店人手不足，請求支援一名工讀生",            "user": "店長阿豪"},
        {"content": "南屯店周末活動需要額外協助準備物料",            "user": "店員Amy"},
        {"content": "西屯店需要支援配送，訂單量突增",                "user": "店長老陳"},
    ]
    blue_samples = [
        {"content": "東區店米食原料庫存不足，請安排補貨",            "user": "店員小林"},
        {"content": "北區店盤點作業完成，等待總部處理",              "user": "店長小花"},
        {"content": "南區店包材補貨任務已派發",                      "user": "店員阿傑"},
        {"content": "中區店每日結帳任務已完成",                      "user": "店長Mark"},
    ]

    events, eid = [], 1
    for s in red_samples:
        events.append(_make_event(eid, "red", s, random.randint(0, 5)))
        eid += 1
    for s in yellow_samples:
        events.append(_make_event(eid, "yellow", s, random.randint(0, 3)))
        eid += 1
    for s in blue_samples:
        status = random.choice(["pending", "pending", "closed"])
        events.append(_make_event(eid, "blue", s, random.randint(0, 6), status=status))
        eid += 1
    return events


def _make_event(eid, level, sample, hour_offset, status="pending"):
    return {
        "id": eid,
        "level": level,
        "store": random.choice(STORE_LIST),
        "user": sample["user"],
        "content": sample["content"],
        "created_at": datetime.now() - timedelta(hours=hour_offset, minutes=random.randint(0, 59)),
        "status": status,
        "assigned_to": None,
        "response_deadline": None,
        "monitoring_until": None,
    }


# ================================================================
# 【區塊 4】NLP 分類引擎
# ================================================================
def classify_message(text):
    """關鍵字分類: red / yellow / blue"""
    red_kw    = ["故障", "無法運作", "無法", "異常", "停擺", "報廢", "緊急", "壞了", "斷電"]
    yellow_kw = ["支援", "協助", "請求", "不足", "需要", "幫忙"]
    blue_kw   = ["處理", "任務", "補貨", "盤點", "結帳", "清潔", "完成"]
    for kw in red_kw:
        if kw in (text or ""):
            return "red"
    for kw in yellow_kw:
        if kw in (text or ""):
            return "yellow"
    for kw in blue_kw:
        if kw in (text or ""):
            return "blue"
    return "blue"


def fuzzy_match_confirmation(text):
    """模糊語意辨識：是否為回簽確認訊息"""
    patterns = [r"收到", r"搞定", r"ok", r"處理完", r"完成", r"確認", r"好的", r"沒問題", r"已處理", r"結案"]
    t = (text or "").lower()
    return any(re.search(p, t) for p in patterns)


# ================================================================
# 【區塊 5】決策草稿生成器
# ================================================================
def generate_draft(item):
    level, store, user, content = item["level"], item["store"], item["user"], item["content"]
    if level == "red":
        return (
            f"【🔴 緊急指令 - {store}】\n\n"
            f"收到 {user} 回報狀況：{content}\n\n"
            f"1. 請店長立即確保現場安全（電力/止滑/客戶動線）\n"
            f"2. 請 [指定主管] 於 4 小時內回報維修廠商到場時間\n"
            f"3. 同步回報損失評估與替代方案\n\n"
            f"此為紅區事件，將進入 4 小時時效追蹤。"
        )
    elif level == "yellow":
        return (
            f"【🟡 行動指令 - {store}】\n\n"
            f"收到 {user} 的協助請求：{content}\n\n"
            f"1. 請 [指定主管] 確認調度時間與資源\n"
            f"2. 由 {user} 確認支援到位後回報結案\n"
            f"3. 若 24 小時內無異常，系統自動存檔"
        )
    else:
        return (
            f"【🔵 任務指令 - {store}】\n\n"
            f"收到 {user} 回報：{content}\n\n"
            f"任務已登記，請依 SOP 處理完畢後於群組回報「已完成」。\n"
            f"5 分鐘無異議將自動結案。"
        )


# ================================================================
# 【區塊 6】決策沙盒彈窗
# ================================================================
@st.dialog("🛡️ 分身決策沙盒")
def show_decision_sandbox(item):
    level_emoji = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}
    level_text  = {"red": "紅色警戒", "yellow": "黃色行動", "blue": "藍色任務"}

    st.markdown(f"### {level_emoji[item['level']]} {level_text[item['level']]}")
    st.info(f"**📍 {item['store']}** | 👤 {item['user']}\n\n**店鋪原文：** {item['content']}")
    st.markdown(f"⏰ 發生時間：`{item['created_at'].strftime('%Y-%m-%d %H:%M')}`")

    st.markdown("---")
    st.markdown("#### 👥 責任歸屬指派")
    assigned_manager = st.selectbox("指定執行主管", MANAGER_LIST, key=f"mgr_{item['id']}")

    st.markdown("#### ✍️ 審核分身草稿")
    raw_draft = generate_draft(item).replace("[指定主管]", assigned_manager)
    edited = st.text_area("編輯草稿後按核准發送", value=raw_draft, height=220, key=f"draft_{item['id']}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚀 一次性核准並發送", type="primary", use_container_width=True, key=f"approve_{item['id']}"):
            for evt in st.session_state.edge_events:
                if evt["id"] == item["id"]:
                    evt["status"] = "monitoring"
                    evt["assigned_to"] = assigned_manager
                    evt["monitoring_until"] = datetime.now() + timedelta(hours=24)
                    if item["level"] == "red":
                        evt["response_deadline"] = datetime.now() + timedelta(hours=4)
                    break
            st.session_state.edge_learning.append({
                "timestamp": datetime.now(),
                "event_id": item["id"],
                "level": item["level"],
                "assigned_to": assigned_manager,
                "draft_modified": (edited != raw_draft),
            })
            if assigned_manager in st.session_state.edge_mgr_count:
                st.session_state.edge_mgr_count[assigned_manager] += 1
            st.success("✅ 指令已發送至 Line 群組！\n\n🕒 4H 時效追蹤已啟動\n👀 24H 觀察期已啟動")
            st.balloons()
            st.rerun()
    with c2:
        if st.button("❌ 取消", use_container_width=True, key=f"cancel_{item['id']}"):
            st.rerun()


# ================================================================
# 【區塊 7】對話氣泡渲染器
# ================================================================
def render_avatar_bubble(item):
    is_monitoring = item["status"] in ["monitoring", "closed"]
    bg_class = "bg-monitoring" if is_monitoring else f"bg-{item['level']}"

    hours_passed = (datetime.now() - item["created_at"]).total_seconds() / 3600
    if item["level"] == "red" and hours_passed > 4 and item["status"] == "pending":
        time_html = '<span class="time-warning">🚨 超過 4 小時未回報！</span>'
    else:
        time_html = f'<span class="time-normal">🕐 {item["created_at"].strftime("%H:%M")}</span>'

    status_label = {"pending": "⏳ 待處理", "monitoring": "👀 觀察中", "closed": "✅ 已結案"}
    avatar_char = item["store"][0] if item["store"] else "?"

    assigned_html = f' | 負責：{item["assigned_to"]}' if item.get("assigned_to") else ""
    bubble_html = f"""
<div class="chat-bubble {bg_class}">
    <div class="avatar">{avatar_char}</div>
    <div style="flex:1;">
        <div style="margin-bottom:6px;">
            <span class="store-tag">🏷️ {item['store']}</span>
            <span class="store-tag">👤 {item['user']}</span>
        </div>
        <div style="font-size:14px;color:#333;margin-bottom:6px;line-height:1.5;">{item['content']}</div>
        <div style="font-size:12px;color:#888;">{time_html} | {status_label[item['status']]}{assigned_html}</div>
    </div>
</div>
"""
    st.markdown(bubble_html, unsafe_allow_html=True)

    if item["status"] == "pending":
        if st.button("🎯 開啟決策沙盒", key=f"open_{item['id']}", use_container_width=True):
            show_decision_sandbox(item)


# ================================================================
# 【區塊 8】自動化邏輯 — 24H 觀察期結束 → 自動結案
# ================================================================
def auto_process_monitoring():
    now = datetime.now()
    for evt in st.session_state.edge_events:
        if evt["status"] == "monitoring" and evt.get("monitoring_until"):
            if now >= evt["monitoring_until"]:
                evt["status"] = "closed"


# ================================================================
# 【區塊 9】全景戰報產生器
# ================================================================
def generate_battle_report():
    now    = datetime.now()
    events = st.session_state.edge_events
    red_p  = [e for e in events if e["level"] == "red"    and e["status"] == "pending"]
    yel_p  = [e for e in events if e["level"] == "yellow" and e["status"] == "pending"]
    blu_p  = [e for e in events if e["level"] == "blue"   and e["status"] == "pending"]

    risk_alerts = []
    for e in red_p:
        h = (now - e["created_at"]).total_seconds() / 3600
        if h > 4:
            risk_alerts.append(f"⚠️ {e['store']}：{e['content'][:30]}...（已逾時 {h:.1f} 小時）")

    top_mgrs = sorted(st.session_state.edge_mgr_count.items(), key=lambda x: x[1], reverse=True)[:3]

    lines = [
        "🛡️ 【嗑肉數位總部 · 全景戰報】",
        f"📅 {now.strftime('%Y-%m-%d %H:%M')}",
        "=" * 30,
        f"\n🔴 【紅色警戒】{len(red_p)} 件",
        *[f"  • {e['store']}：{e['content'][:40]}" for e in red_p[:5]],
        f"\n🟡 【黃色行動】{len(yel_p)} 件",
        *[f"  • {e['store']}：{e['content'][:40]}" for e in yel_p[:5]],
        f"\n🔵 【藍色任務】{len(blu_p)} 件",
        *[f"  • {e['store']}：{e['content'][:40]}" for e in blu_p[:3]],
        "\n⚠️ 【風險預警】",
        *(risk_alerts if risk_alerts else ["  ✅ 目前無超時事件"]),
        "\n🏆 【今日熱心榜】",
        *[f"  {'🥇🥈🥉'[i]} {n}：支援 {c} 次" for i, (n, c) in enumerate(top_mgrs)],
        "\n" + "=" * 30,
        "📊 由分身參謀自動彙整",
    ]
    return "\n".join(lines)


# ================================================================
# 【區塊 10】側邊欄
# ================================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🛡️ 分身參謀控制台")
        st.divider()

        # 掃描狀態
        last  = st.session_state.edge_last_scan
        nxt   = last + timedelta(minutes=30)
        st.markdown("**🔄 數據掃描狀態**")
        st.caption(f"上次掃描：{last.strftime('%H:%M:%S')}")
        st.caption(f"下次掃描：{nxt.strftime('%H:%M:%S')}")

        if st.button("⚡ 手動觸發掃描", use_container_width=True, key="edge_scan_btn"):
            st.session_state.edge_last_scan = datetime.now()
            cur_max = max(e["id"] for e in st.session_state.edge_events) if st.session_state.edge_events else 0
            samples = [
                ("red",    "豐原店冰箱故障，需緊急維修"),
                ("yellow", "太平店需要協助處理客訴"),
                ("blue",   "大里店月底盤點任務派發"),
            ]
            n = random.randint(1, 2)
            for i in range(n):
                s = random.choice(samples)
                st.session_state.edge_events.append({
                    "id": cur_max + i + 1,
                    "level": s[0],
                    "store": random.choice(STORE_LIST),
                    "user": random.choice(["店員小A", "店長Tom", "店員Lisa"]),
                    "content": s[1],
                    "created_at": datetime.now(),
                    "status": "pending",
                    "assigned_to": None,
                    "response_deadline": None,
                    "monitoring_until": None,
                })
            st.success(f"已掃描到 {n} 筆新事件")
            st.rerun()

        st.divider()

        # 顯示過濾
        st.markdown("**🎯 顯示過濾**")
        st.session_state.edge_show_closed = st.checkbox(
            "顯示已結案事件", value=st.session_state.edge_show_closed, key="edge_show_closed_cb"
        )

        st.divider()

        # 即時統計
        evts = st.session_state.edge_events
        st.markdown("**📊 即時統計**")
        st.metric("總事件數",  len(evts))
        st.metric("待處理",    len([e for e in evts if e["status"] == "pending"]))
        st.metric("觀察中",    len([e for e in evts if e["status"] == "monitoring"]))
        st.metric("已結案",    len([e for e in evts if e["status"] == "closed"]))

        st.divider()

        # 戰報 / 學習紀錄
        st.markdown("**📡 戰報推播**")
        if st.button("📋 產生 17:00 戰報", use_container_width=True, type="primary", key="edge_report_btn"):
            st.session_state.edge_show_report = True

        st.divider()
        st.markdown("**🧠 決策學習日誌**")
        st.caption(f"已累積 {len(st.session_state.edge_learning)} 筆決策紀錄")
        if st.button("📖 查看學習紀錄", key="edge_learning_btn"):
            st.session_state.edge_show_learning = True

        st.divider()
        st.page_link("app.py", label="← 返回總部大門")


# ================================================================
# 【區塊 11】主看板 — 紅/黃/藍三欄
# ================================================================
def render_main_dashboard():
    st.markdown("""
<div class="main-header">
    <h1 style="margin:0;">🛡️ 嗑肉數位總部</h1>
    <p style="margin:5px 0 0 0;opacity:0.9;">分身參謀全景看板 · Line Edge Agent Command Center</p>
</div>
""", unsafe_allow_html=True)

    evts = st.session_state.edge_events
    r_cnt = len([e for e in evts if e["level"] == "red"    and e["status"] == "pending"])
    y_cnt = len([e for e in evts if e["level"] == "yellow" and e["status"] == "pending"])
    b_cnt = len([e for e in evts if e["level"] == "blue"   and e["status"] == "pending"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔴 紅色警戒", r_cnt, delta="需立即處理" if r_cnt > 0 else None)
    m2.metric("🟡 黃色行動", y_cnt)
    m3.metric("🔵 藍色任務", b_cnt)
    m4.metric("🏪 監控門店", f"{len(STORE_LIST)} 家")
    st.markdown("---")

    show_closed = st.session_state.edge_show_closed

    col_r, col_y, col_b = st.columns(3)

    with col_r:
        st.markdown('<div class="column-header header-red">🔴 紅色警戒 · Critical</div>', unsafe_allow_html=True)
        items = [e for e in evts if e["level"] == "red"]
        if not show_closed:
            items = [e for e in items if e["status"] != "closed"]
        items.sort(key=lambda x: (x["status"] == "pending", x["created_at"]), reverse=True)
        for e in items:
            render_avatar_bubble(e)
        if not items:
            st.info("目前無紅色警戒事件 ✨")

    with col_y:
        st.markdown('<div class="column-header header-yellow">🟡 黃色行動 · Action</div>', unsafe_allow_html=True)
        items = [e for e in evts if e["level"] == "yellow"]
        if not show_closed:
            items = [e for e in items if e["status"] != "closed"]
        items.sort(key=lambda x: (x["status"] == "pending", x["created_at"]), reverse=True)
        for e in items:
            render_avatar_bubble(e)
        if not items:
            st.info("目前無黃色行動事件 ✨")

    with col_b:
        st.markdown('<div class="column-header header-blue">🔵 藍色任務 · Task</div>', unsafe_allow_html=True)
        items = [e for e in evts if e["level"] == "blue"]
        if not show_closed:
            items = [e for e in items if e["status"] != "closed"]
        items.sort(key=lambda x: (x["status"] == "pending", x["created_at"]), reverse=True)
        for e in items:
            render_avatar_bubble(e)
        if not items:
            st.info("目前無藍色任務事件 ✨")


# ================================================================
# 【區塊 12】戰報彈窗 & 學習紀錄彈窗
# ================================================================
@st.dialog("📡 全景戰報預覽")
def show_battle_report_dialog():
    st.markdown("#### 即將推播至 Line 總指揮私訊：")
    st.code(generate_battle_report(), language=None)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📤 模擬推播至 Line", type="primary", use_container_width=True, key="edge_send_btn"):
            st.success("✅ 戰報已推播！（模擬）")
            st.session_state.edge_show_report = False
            st.rerun()
    with c2:
        if st.button("關閉", use_container_width=True, key="edge_close_report_btn"):
            st.session_state.edge_show_report = False
            st.rerun()


@st.dialog("🧠 決策偏好學習紀錄")
def show_learning_dialog():
    logs = st.session_state.edge_learning
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True)
        mgr_counts: dict = {}
        for log in logs:
            m = log["assigned_to"]
            mgr_counts[m] = mgr_counts.get(m, 0) + 1
        st.markdown("#### 📊 指派偏好分析")
        for m, c in sorted(mgr_counts.items(), key=lambda x: x[1], reverse=True):
            st.markdown(f"- **{m}**：被指派 {c} 次")
    else:
        st.info("尚無決策紀錄")
    if st.button("關閉", use_container_width=True, key="edge_close_learning_btn"):
        st.session_state.edge_show_learning = False
        st.rerun()


# ================================================================
# 【主程式】
# ================================================================
def main():
    _edge_init()
    auto_process_monitoring()
    render_sidebar()
    render_main_dashboard()

    if st.session_state.edge_show_report:
        show_battle_report_dialog()
    if st.session_state.edge_show_learning:
        show_learning_dialog()


main()
