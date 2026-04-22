"""
6_Line邊緣代理人.py — v2.0
嗑肉數位總部：分身參謀全景看板
新增：SQLite 數據橋接 / 語意腦強化 / 責任地圖學習 / Webhook 模擬器 / 戰報排程
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random, re

# ── 頁面設定 ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="嗑肉數位總部 ｜ Line 邊緣代理人",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 認證守衛 ─────────────────────────────────────────────────────
if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("app.py", label="← 返回數位總部大門")
    st.stop()

if "Line智能邊緣代理人" not in st.session_state.get("enabled_pages", set()):
    st.error("🔒 本功能尚未開放")
    st.page_link("app.py", label="← 返回總部")
    st.stop()

# ── Edge Store 初始化 ─────────────────────────────────────────────
from utils import edge_store
edge_store.init_db()

from utils.ui_helpers import inject_global_css
inject_global_css()

# ================================================================
# CSS
# ================================================================
st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #E63B1F 0%, #C62828 100%);
    padding: 20px 30px; border-radius: 15px; color: white;
    margin-bottom: 20px; box-shadow: 0 4px 15px rgba(230,59,31,0.3);
}
.chat-bubble {
    padding: 18px; border-radius: 18px; margin-bottom: 12px;
    display: flex; align-items: flex-start;
    box-shadow: 2px 2px 10px rgba(0,0,0,0.08);
    transition: all 0.3s ease;
}
.chat-bubble:hover { transform: translateY(-2px); box-shadow: 4px 4px 15px rgba(0,0,0,0.15); }
.bg-red        { background-color: #FFEBE9; border-left: 8px solid #E63B1F; }
.bg-yellow     { background-color: #FFF9E6; border-left: 8px solid #F1C40F; }
.bg-blue       { background-color: #E8F4FD; border-left: 8px solid #3498DB; }
.bg-monitoring { background-color: #F8F9FA; border-left: 8px solid #BDC3C7; opacity: 0.6; }
.avatar {
    width: 45px; height: 45px; border-radius: 50%;
    background: linear-gradient(135deg, #E63B1F 0%, #FF6B4A 100%);
    color: white; margin-right: 15px; display: flex;
    justify-content: center; align-items: center;
    font-weight: bold; flex-shrink: 0; font-size: 16px;
}
.store-tag {
    display: inline-block; background-color: rgba(0,0,0,0.08);
    padding: 2px 10px; border-radius: 12px;
    font-size: 12px; margin-right: 6px; font-weight: 600;
}
.time-warning { color: #E63B1F; font-weight: bold; font-size: 13px; }
.time-normal  { color: #666; font-size: 12px; }
.column-header {
    padding: 12px; border-radius: 10px; color: white;
    text-align: center; font-weight: bold; font-size: 16px; margin-bottom: 15px;
}
.header-red    { background: linear-gradient(135deg, #E63B1F 0%, #C62828 100%); }
.header-yellow { background: linear-gradient(135deg, #F39C12 0%, #E67E22 100%); }
.header-blue   { background: linear-gradient(135deg, #3498DB 0%, #2980B9 100%); }
.rec-badge {
    background: linear-gradient(90deg, #1A1A2E, #16213E);
    color: #00D4FF; border-radius: 8px; padding: 8px 14px;
    font-size: 0.85rem; font-weight: 700; margin-bottom: 10px;
    border: 1px solid rgba(0,212,255,0.3);
    display: flex; align-items: center; gap: 8px;
}
.cat-badge {
    display: inline-block; font-size: 0.72rem; padding: 1px 7px;
    border-radius: 10px; background: rgba(230,59,31,0.12);
    color: #E63B1F; font-weight: 600; margin-left: 6px;
}
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ================================================================
# 常數
# ================================================================
STORE_LIST = [
    "崇德店", "美村店", "公益店", "北屯店", "南屯店",
    "西屯店", "東區店", "北區店", "南區店", "中區店",
    "豐原店", "太平店", "大里店", "霧峰店", "沙鹿店",
]
MANAGER_LIST = ["張主管", "李主管", "王主管", "陳主管", "林主管"]


# ================================================================
# 增強 NLP v2 — 關鍵字分類 + 語意終點判定
# ================================================================
# 三色關鍵字庫（含子類別，支援責任地圖學習）
_RED_CATS: dict[str, list[str]] = {
    "red-equipment": ["故障", "壞了", "不動了", "無法運作", "無法結帳", "死機", "當機"],
    "red-temperature": ["溫度異常", "冷藏", "冷凍異常", "溫控"],
    "red-power": ["斷電", "停電", "電源故障", "跳電"],
    "red-safety": ["漏水", "火警", "受傷", "危險"],
    "red-other": ["異常", "停擺", "報廢", "緊急", "無法"],
}
_YELLOW_CATS: dict[str, list[str]] = {
    "yellow-staffing": ["支援", "人手不足", "工讀生", "人力", "幫忙"],
    "yellow-material": ["物料", "需要", "協助", "準備", "額外"],
    "yellow-delivery": ["配送", "外送", "調度", "訂單量"],
}
_BLUE_CATS: dict[str, list[str]] = {
    "blue-inventory": ["盤點", "庫存不足", "補貨", "包材"],
    "blue-task": ["結帳", "清潔", "任務", "完成", "派發"],
    "blue-report": ["回報", "等待", "總部"],
}

# 擴充確認語意（模糊結案辨識）
_CONFIRM_PATTERNS = [
    r"收到", r"搞定", r"ok了?", r"好了", r"處理完了?", r"完成了?",
    r"確認", r"好的", r"沒問題", r"已處理", r"結案了?", r"送達",
    r"到了", r"搞好了", r"修好了", r"補完了", r"解決了",
    r"弄好了", r"處理好了", r"done", r"finished", r"ok$",
]

_LEVEL_LABELS = {"red": "🔴 紅色警戒", "yellow": "🟡 黃色行動", "blue": "🔵 藍色任務"}
_CAT_CN: dict[str, str] = {
    "red-equipment":   "設備故障",  "red-temperature": "溫度異常",
    "red-power":       "電力異常",  "red-safety":      "安全事故",
    "red-other":       "紅區-其他", "yellow-staffing": "人力支援",
    "yellow-material": "物料協助",  "yellow-delivery": "配送調度",
    "blue-inventory":  "庫存盤點",  "blue-task":       "例行任務",
    "blue-report":     "回報確認",
}


def classify_v2(text: str) -> tuple[str, str]:
    """
    增強分類器 v2
    回傳 (level, keyword_cat)
    """
    t = text or ""
    for cat, kws in _RED_CATS.items():
        if any(kw in t for kw in kws):
            return "red", cat
    for cat, kws in _YELLOW_CATS.items():
        if any(kw in t for kw in kws):
            return "yellow", cat
    for cat, kws in _BLUE_CATS.items():
        if any(kw in t for kw in kws):
            return "blue", cat
    return "blue", "blue-task"


def is_confirmation(text: str) -> bool:
    """判斷是否為「模糊結案確認」語意"""
    t = (text or "").lower()
    return any(re.search(p, t) for p in _CONFIRM_PATTERNS)


# ================================================================
# 初始化 Session State（UI 旗標）
# ================================================================
def _edge_init():
    defaults = {
        "edge_show_report":   False,
        "edge_show_learning": False,
        "edge_show_closed":   False,
        "edge_last_scan":     datetime.now(),
        "edge_seeded":        False,
        "edge_webhook_result": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # 第一次執行且 DB 為空 → 填入 Mock 資料
    if not st.session_state.edge_seeded:
        if edge_store.count_events() == 0:
            for evt in _generate_mock_events():
                edge_store.save_event(evt)
        st.session_state.edge_seeded = True


def _generate_mock_events() -> list[dict]:
    """產生初始 Mock 資料"""
    samples = [
        ("red",    "red-equipment",   "崇德店 POS 機故障，無法結帳！",          "店員小美", 5),
        ("red",    "red-temperature", "美村店冷藏櫃溫度異常，商品可能要報廢",    "店員阿強", 3),
        ("red",    "red-power",       "公益店招牌電源故障，晚上無法運作",         "店長王姐", 1),
        ("yellow", "yellow-staffing", "北屯店人手不足，請求支援一名工讀生",       "店長阿豪", 2),
        ("yellow", "yellow-material", "南屯店周末活動需要額外協助準備物料",       "店員Amy",  1),
        ("yellow", "yellow-delivery", "西屯店需要支援配送，訂單量突增",           "店長老陳", 0),
        ("blue",   "blue-inventory",  "東區店米食原料庫存不足，請安排補貨",       "店員小林", 6),
        ("blue",   "blue-task",       "北區店盤點作業完成，等待總部處理",         "店長小花", 4),
        ("blue",   "blue-inventory",  "南區店包材補貨任務已派發",                 "店員阿傑", 3),
        ("blue",   "blue-task",       "中區店每日結帳任務已完成",                 "店長Mark", 1),
    ]
    events = []
    for i, (lv, cat, content, user, hr) in enumerate(samples):
        status = "closed" if i == 9 else "pending"
        events.append({
            "id": i + 1,
            "level": lv,
            "keyword_cat": cat,
            "store": random.choice(STORE_LIST),
            "user_alias": user,
            "content": content,
            "created_at": datetime.now() - timedelta(hours=hr, minutes=random.randint(0, 59)),
            "status": status,
            "assigned_to": None,
            "response_deadline": None,
            "monitoring_until": None,
        })
    return events


# ================================================================
# Webhook 模擬器
# ================================================================
_WEBHOOK_TEMPLATES = [
    {"content": "{store} POS 機故障，無法結帳！",            "user": "店員小美"},
    {"content": "{store} 冷藏櫃溫度異常，需緊急處理",        "user": "店長王姐"},
    {"content": "{store} 斷電，客人全部在等",                 "user": "店員阿強"},
    {"content": "{store} 人手不足，請求支援工讀生",           "user": "店長阿豪"},
    {"content": "{store} 需要支援配送，訂單量突增",           "user": "店員Amy"},
    {"content": "{store} 原料庫存不足，請安排補貨",           "user": "店員小林"},
    {"content": "{store} 盤點完成，等待總部確認",             "user": "店長小花"},
    {"content": "搞定了，設備已修復",                         "user": "維修師傅"},
    {"content": "OK了，補貨已到位",                           "user": "店長Mark"},
    {"content": "{store} 已處理完，請結案",                   "user": "店長老陳"},
]


def process_webhook(content: str, user: str = "模擬用戶",
                    store: str = "") -> dict:
    """
    處理一則 Webhook 訊息：
    1. 緩存原始訊息
    2. 判斷是否為確認訊息（觸發結案）
    3. 分類並檢查 5 分鐘合併窗口
    4. 儲存新事件或合併
    回傳處理結果 dict
    """
    if not store:
        store = random.choice(STORE_LIST)

    # 1. 緩存
    wh_id = edge_store.cache_webhook(content, "sim_user", "sim_group")

    # 2. 確認語意 → 嘗試關閉 monitoring 事件
    if is_confirmation(content):
        edge_store.mark_webhook_processed(wh_id)
        return {"type": "confirmation", "content": content, "store": store}

    # 3. 分類
    level, keyword_cat = classify_v2(content)

    # 4. 5 分鐘合併
    merge_id = edge_store.find_merge_candidate(store, user, level)
    if merge_id:
        edge_store.merge_event_content(merge_id, content)
        edge_store.mark_webhook_processed(wh_id)
        return {"type": "merged", "merge_id": merge_id,
                "content": content, "level": level}

    # 5. 新事件
    new_id = edge_store.save_event({
        "level": level, "store": store,
        "user_alias": user, "content": content,
        "created_at": datetime.now(), "status": "pending",
        "keyword_cat": keyword_cat,
    })
    edge_store.mark_webhook_processed(wh_id)
    return {"type": "new", "id": new_id,
            "level": level, "keyword_cat": keyword_cat,
            "content": content, "store": store}


# ================================================================
# 決策草稿生成器
# ================================================================
def generate_draft(item: dict) -> str:
    level, store = item["level"], item["store"]
    user         = item.get("user") or item.get("user_alias", "相關人員")
    content      = item["content"]
    cat_cn       = _CAT_CN.get(item.get("keyword_cat", ""), "")
    cat_note     = f"（類別：{cat_cn}）" if cat_cn else ""

    if level == "red":
        return (
            f"【🔴 緊急指令 - {store}】{cat_note}\n\n"
            f"收到 {user} 回報狀況：{content}\n\n"
            f"1. 請店長立即確保現場安全（電力/止滑/客戶動線）\n"
            f"2. 請 [指定主管] 於 4 小時內回報維修廠商到場時間\n"
            f"3. 同步回報損失評估與替代方案\n\n"
            f"此為紅區事件，將進入 4 小時時效追蹤。"
        )
    elif level == "yellow":
        return (
            f"【🟡 行動指令 - {store}】{cat_note}\n\n"
            f"收到 {user} 的協助請求：{content}\n\n"
            f"1. 請 [指定主管] 確認調度時間與資源\n"
            f"2. 由 {user} 確認支援到位後回報結案\n"
            f"3. 若 24 小時內無異常，系統自動存檔"
        )
    else:
        return (
            f"【🔵 任務指令 - {store}】{cat_note}\n\n"
            f"收到 {user} 回報：{content}\n\n"
            f"任務已登記，請依 SOP 處理完畢後於群組回報「已完成」。\n"
            f"5 分鐘無異議將自動結案。"
        )


# ================================================================
# 決策沙盒（含 AI 推薦主管）
# ================================================================
@st.dialog("🛡️ 分身決策沙盒")
def show_decision_sandbox(item: dict):
    level = item["level"]
    emoji = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}[level]

    st.markdown(f"### {emoji} {_LEVEL_LABELS[level]}")
    cat_cn = _CAT_CN.get(item.get("keyword_cat", ""), "")
    if cat_cn:
        st.markdown(f'<span class="cat-badge">📂 {cat_cn}</span>', unsafe_allow_html=True)

    st.info(
        f"**📍 {item['store']}** | "
        f"👤 {item.get('user') or item.get('user_alias','')}\n\n"
        f"**店鋪原文：** {item['content']}"
    )
    st.markdown(f"⏰ 發生時間：`{item['created_at'].strftime('%Y-%m-%d %H:%M')}`")

    # ── AI 推薦主管 ───────────────────────────────────────────────
    keyword_cat = item.get("keyword_cat", level)
    rec_mgr = edge_store.get_recommended_manager(level, keyword_cat)
    rec_stats = next(
        (s for s in edge_store.get_manager_stats()
         if s["manager"] == rec_mgr and s["category"] == (keyword_cat or level)),
        None
    )
    if rec_mgr:
        cnt = rec_stats["cnt"] if rec_stats else "?"
        is_def = bool(rec_stats and rec_stats.get("is_default"))
        badge = "⭐ 預設" if is_def else f"（歷史指派 {cnt} 次）"
        st.markdown(
            f'<div class="rec-badge">💡 AI 推薦主管：<strong>{rec_mgr}</strong> '
            f'<span style="opacity:0.7;font-size:0.78rem;">{badge} · 類別：{cat_cn or level}</span></div>',
            unsafe_allow_html=True
        )

    # ── 責任指派 ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 👥 責任歸屬指派")
    default_idx = MANAGER_LIST.index(rec_mgr) if rec_mgr in MANAGER_LIST else 0
    assigned = st.selectbox(
        "指定執行主管",
        MANAGER_LIST,
        index=default_idx,
        key=f"mgr_{item['id']}"
    )

    # ── 草稿編輯 ─────────────────────────────────────────────────
    st.markdown("#### ✍️ 審核分身草稿")
    raw_draft = generate_draft(item).replace("[指定主管]", assigned)
    edited = st.text_area(
        "編輯草稿後按核准發送",
        value=raw_draft, height=220,
        key=f"draft_{item['id']}"
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "🚀 一次性核准並發送", type="primary",
            use_container_width=True, key=f"approve_{item['id']}"
        ):
            now = datetime.now()
            mon_until = now + timedelta(hours=24)
            res_dl    = (now + timedelta(hours=4)) if level == "red" else None

            edge_store.update_event(
                item["id"],
                status="monitoring",
                assigned_to=assigned,
                monitoring_until=mon_until,
                response_deadline=res_dl,
            )
            edge_store.log_decision(
                event_id=item["id"], level=level,
                store=item["store"], assigned_to=assigned,
                draft_modified=(edited != raw_draft),
                keyword_cat=keyword_cat,
            )
            st.success(
                f"✅ 指令已發送至 Line 群組！\n\n"
                f"🕒 4H 時效追蹤已啟動\n"
                f"👀 24H 觀察期已啟動\n"
                f"📊 決策紀錄已寫入責任地圖"
            )
            st.balloons()
            st.rerun()
    with c2:
        if st.button("❌ 取消", use_container_width=True, key=f"cancel_{item['id']}"):
            st.rerun()


# ================================================================
# 對話氣泡渲染器
# ================================================================
def render_avatar_bubble(item: dict):
    is_mon = item["status"] in ["monitoring", "closed"]
    bg_cls = "bg-monitoring" if is_mon else f"bg-{item['level']}"

    hours_passed = (datetime.now() - item["created_at"]).total_seconds() / 3600
    if item["level"] == "red" and hours_passed > 4 and item["status"] == "pending":
        time_html = '<span class="time-warning">🚨 超過 4 小時未回報！</span>'
    else:
        time_html = f'<span class="time-normal">🕐 {item["created_at"].strftime("%H:%M")}</span>'

    status_lbl = {"pending": "⏳ 待處理", "monitoring": "👀 觀察中", "closed": "✅ 已結案"}
    avatar_ch  = item["store"][0] if item["store"] else "?"
    cat_cn     = _CAT_CN.get(item.get("keyword_cat", ""), "")
    cat_html   = f'<span class="cat-badge">{cat_cn}</span>' if cat_cn else ""
    assigned   = f' | 負責：{item["assigned_to"]}' if item.get("assigned_to") else ""
    user_name  = item.get("user") or item.get("user_alias", "")

    st.markdown(f"""
<div class="chat-bubble {bg_cls}">
    <div class="avatar">{avatar_ch}</div>
    <div style="flex:1;">
        <div style="margin-bottom:6px;">
            <span class="store-tag">🏷️ {item['store']}</span>
            <span class="store-tag">👤 {user_name}</span>
            {cat_html}
        </div>
        <div style="font-size:14px;color:#333;margin-bottom:6px;line-height:1.5;">{item['content']}</div>
        <div style="font-size:12px;color:#888;">{time_html} | {status_lbl[item['status']]}{assigned}</div>
    </div>
</div>
""", unsafe_allow_html=True)

    if item["status"] == "pending":
        if st.button("🎯 開啟決策沙盒", key=f"open_{item['id']}", use_container_width=True):
            show_decision_sandbox(item)


# ================================================================
# 自動化：24H 觀察期結束 → 結案
# ================================================================
def auto_process():
    closed_n = edge_store.auto_close_expired()
    return closed_n


# ================================================================
# 戰報產生器 v2（含重複報修 & 逾時紅標）
# ================================================================
def generate_battle_report() -> str:
    now    = datetime.now()
    evts   = edge_store.load_events()
    red_p  = [e for e in evts if e["level"] == "red"    and e["status"] == "pending"]
    yel_p  = [e for e in evts if e["level"] == "yellow" and e["status"] == "pending"]
    blu_p  = [e for e in evts if e["level"] == "blue"   and e["status"] == "pending"]

    # 重複報修（24H 同店 ≥2 次）
    repeat_stores = edge_store.get_repeat_repairs_24h()

    # 逾時紅標（> 4H 未回報）
    overdue = edge_store.get_overdue_red_events(hours=4)

    # 今日熱心榜（取決策日誌）
    logs = edge_store.load_decision_logs(limit=50)
    mgr_today: dict[str, int] = {}
    today_str = now.strftime("%Y-%m-%d")
    for log in logs:
        if log["ts"].startswith(today_str):
            m = log["assigned_to"]
            mgr_today[m] = mgr_today.get(m, 0) + 1
    top_mgrs = sorted(mgr_today.items(), key=lambda x: x[1], reverse=True)[:3]

    lines = [
        "🛡️ 【嗑肉數位總部 · 全景戰報】",
        f"📅 {now.strftime('%Y-%m-%d %H:%M')}",
        "=" * 32,
        f"\n🔴 【紅色警戒】{len(red_p)} 件",
        *[f"  • {e['store']}：{e['content'][:40]}" for e in red_p[:5]],
        f"\n🟡 【黃色行動】{len(yel_p)} 件",
        *[f"  • {e['store']}：{e['content'][:40]}" for e in yel_p[:5]],
        f"\n🔵 【藍色任務】{len(blu_p)} 件",
        *[f"  • {e['store']}：{e['content'][:40]}" for e in blu_p[:3]],
        "\n⚠️ 【逾時紅標（>4H 未回報）】",
        *(
            [f"  🚨 {e['store']}：{e['content'][:30]}... "
             f"（{int((now - e['created_at']).total_seconds()/3600)}H 前）"
             for e in overdue]
            or ["  ✅ 目前無超時事件"]
        ),
        "\n🔄 【24H 重複報修】",
        *(
            [f"  ⚡ {r['store']}：24H 內 {r['cnt']} 次紅色報修（需重點跟進）"
             for r in repeat_stores]
            or ["  ✅ 目前無重複報修"]
        ),
        "\n🏆 【今日熱心榜】",
        *(
            [f"  {'🥇🥈🥉'[i]} {n}：今日指派 {c} 次"
             for i, (n, c) in enumerate(top_mgrs)]
            or ["  （今日尚無決策紀錄）"]
        ),
        "\n" + "=" * 32,
        "📊 由分身參謀自動彙整 · SQLite v2",
    ]
    return "\n".join(lines)


# ================================================================
# 側欄（含 Webhook 模擬器 + 戰報排程）
# ================================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🛡️ 分身參謀控制台")
        st.divider()

        # ── 掃描狀態 ──────────────────────────────────────────────
        last = st.session_state.edge_last_scan
        nxt  = last + timedelta(minutes=30)
        st.markdown("**🔄 數據掃描狀態**")
        st.caption(f"上次掃描：{last.strftime('%H:%M:%S')}")
        st.caption(f"下次掃描：{nxt.strftime('%H:%M:%S')}")

        if st.button("⚡ 手動觸發掃描", use_container_width=True, key="edge_scan_btn"):
            st.session_state.edge_last_scan = datetime.now()
            n = random.randint(1, 2)
            for _ in range(n):
                tmpl = random.choice(_WEBHOOK_TEMPLATES)
                store = random.choice(STORE_LIST)
                content = tmpl["content"].format(store=store)
                process_webhook(content, user=tmpl["user"], store=store)
            st.success(f"已掃描到 {n} 筆新事件")
            st.rerun()

        st.divider()

        # ── Webhook 模擬器（新功能）───────────────────────────────
        st.markdown("**🤖 模擬 Webhook 訊息**")
        custom_msg = st.text_input(
            "自訂訊息（留空 = 隨機）",
            key="edge_webhook_input",
            placeholder="例：崇德店 POS 故障",
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📨 隨機模擬", use_container_width=True, key="edge_sim_random"):
                tmpl = random.choice(_WEBHOOK_TEMPLATES)
                store = random.choice(STORE_LIST)
                content = tmpl["content"].format(store=store)
                result = process_webhook(content, user=tmpl["user"], store=store)
                st.session_state.edge_webhook_result = result
                st.rerun()
        with c2:
            if st.button(
                "📤 送出", use_container_width=True,
                key="edge_sim_custom",
                disabled=not custom_msg.strip(),
            ):
                result = process_webhook(custom_msg.strip())
                st.session_state.edge_webhook_result = result
                st.rerun()

        # 顯示上次 Webhook 結果
        r = st.session_state.get("edge_webhook_result")
        if r:
            if r["type"] == "new":
                st.success(f"✅ 新事件 #{r['id']}（{_LEVEL_LABELS.get(r['level'],r['level'])}）\n{r['content'][:40]}")
            elif r["type"] == "merged":
                st.info(f"🔗 已合併至事件 #{r['merge_id']}\n{r['content'][:40]}")
            else:
                st.info(f"🔍 確認語意，嘗試結案\n{r['content'][:40]}")

        st.divider()

        # ── 顯示過濾 ──────────────────────────────────────────────
        st.markdown("**🎯 顯示過濾**")
        st.session_state.edge_show_closed = st.checkbox(
            "顯示已結案事件",
            value=st.session_state.edge_show_closed,
            key="edge_closed_cb",
        )

        st.divider()

        # ── 即時統計 ──────────────────────────────────────────────
        evts = edge_store.load_events()
        st.markdown("**📊 即時統計**")
        st.metric("總事件數",  len(evts))
        st.metric("待處理",    len([e for e in evts if e["status"] == "pending"]))
        st.metric("觀察中",    len([e for e in evts if e["status"] == "monitoring"]))
        st.metric("已結案",    len([e for e in evts if e["status"] == "closed"]))

        st.divider()

        # ── 戰報排程（新功能）────────────────────────────────────
        st.markdown("**⏰ 戰報排程**")
        now = datetime.now()
        next_report = now.replace(hour=16, minute=50, second=0, microsecond=0)
        if now >= next_report:
            next_report += timedelta(days=1)
        mins_left = int((next_report - now).total_seconds() / 60)
        st.caption(f"📅 下次自動戰報：`{next_report.strftime('%m/%d %H:%M')}`")
        st.caption(f"⏳ 倒數：{mins_left // 60}h {mins_left % 60}m")

        if st.button("📋 立即產生戰報", use_container_width=True, type="primary", key="edge_report_btn"):
            st.session_state.edge_show_report = True

        st.divider()

        # ── 決策學習日誌 ──────────────────────────────────────────
        st.markdown("**🧠 責任地圖 & 決策日誌**")
        logs = edge_store.load_decision_logs(limit=5)
        st.caption(f"已累積 {edge_store.load_decision_logs.__doc__ or len(logs)} 筆 →")
        mgr_stats = edge_store.get_manager_stats()
        defaults  = [s for s in mgr_stats if s["is_default"]]
        if defaults:
            for d in defaults[:3]:
                st.caption(f"⭐ {d['manager']} → {_CAT_CN.get(d['category'], d['category'])}（{d['cnt']} 次）")
        if st.button("📖 查看完整日誌", key="edge_learning_btn"):
            st.session_state.edge_show_learning = True

        st.divider()
        st.page_link("app.py", label="← 返回總部大門")


# ================================================================
# 主看板
# ================================================================
def render_main_dashboard():
    st.markdown("""
<div class="main-header">
    <h1 style="margin:0;">🛡️ 嗑肉數位總部</h1>
    <p style="margin:5px 0 0 0;opacity:0.9;">
        分身參謀全景看板 v2.0 · Line Edge Agent Command Center<br>
        <small>SQLite 數據橋接 · 語意腦強化 · 責任地圖學習</small>
    </p>
</div>
""", unsafe_allow_html=True)

    evts  = edge_store.load_events()
    r_cnt = len([e for e in evts if e["level"] == "red"    and e["status"] == "pending"])
    y_cnt = len([e for e in evts if e["level"] == "yellow" and e["status"] == "pending"])
    b_cnt = len([e for e in evts if e["level"] == "blue"   and e["status"] == "pending"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔴 紅色警戒", r_cnt, delta="需立即處理" if r_cnt > 0 else None)
    m2.metric("🟡 黃色行動", y_cnt)
    m3.metric("🔵 藍色任務", b_cnt)
    m4.metric("🏪 監控門店", f"{len(STORE_LIST)} 家")

    # 重複報修警示橫幅
    repeat_stores = edge_store.get_repeat_repairs_24h()
    if repeat_stores:
        names = "、".join(r["store"] for r in repeat_stores)
        st.warning(f"⚡ **24H 重複報修警示**：{names} 在過去 24 小時內出現多次紅色事件，請重點跟進！")

    st.markdown("---")

    show_closed = st.session_state.edge_show_closed

    col_r, col_y, col_b = st.columns(3)

    def _render_col(col, level: str, header_html: str):
        with col:
            st.markdown(header_html, unsafe_allow_html=True)
            items = [e for e in evts if e["level"] == level]
            if not show_closed:
                items = [e for e in items if e["status"] != "closed"]
            items.sort(key=lambda x: (x["status"] == "pending", x["created_at"]), reverse=True)
            if items:
                for e in items:
                    render_avatar_bubble(e)
            else:
                st.info(f"目前無{_LEVEL_LABELS[level][2:]}事件 ✨")

    _render_col(col_r, "red",
                '<div class="column-header header-red">🔴 紅色警戒 · Critical</div>')
    _render_col(col_y, "yellow",
                '<div class="column-header header-yellow">🟡 黃色行動 · Action</div>')
    _render_col(col_b, "blue",
                '<div class="column-header header-blue">🔵 藍色任務 · Task</div>')


# ================================================================
# 戰報彈窗
# ================================================================
@st.dialog("📡 全景戰報預覽 v2")
def show_battle_report_dialog():
    st.markdown("#### 即將推播至 Line 總指揮私訊：")
    st.code(generate_battle_report(), language=None)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📤 模擬推播至 Line", type="primary",
                     use_container_width=True, key="edge_send_btn"):
            st.success("✅ 戰報已推播！（模擬）")
            st.session_state.edge_show_report = False
            st.rerun()
    with c2:
        if st.button("關閉", use_container_width=True, key="edge_close_report"):
            st.session_state.edge_show_report = False
            st.rerun()


# ================================================================
# 決策學習日誌彈窗（含責任地圖統計）
# ================================================================
@st.dialog("🧠 責任地圖 & 決策偏好學習紀錄")
def show_learning_dialog():
    tab1, tab2 = st.tabs(["📜 決策日誌", "⭐ 責任地圖"])

    with tab1:
        logs = edge_store.load_decision_logs(limit=50)
        if logs:
            df = pd.DataFrame(logs)
            st.dataframe(df[["ts","level","store","assigned_to","keyword_cat","draft_modified"]],
                         use_container_width=True)
        else:
            st.info("尚無決策紀錄")

    with tab2:
        stats = edge_store.get_manager_stats()
        if stats:
            df2 = pd.DataFrame(stats)
            df2["category_cn"] = df2["category"].map(lambda c: _CAT_CN.get(c, c))
            df2["狀態"] = df2["is_default"].map({1: "⭐ 預設", 0: "—"})
            st.dataframe(
                df2[["manager","category_cn","cnt","狀態"]].rename(columns={
                    "manager": "主管", "category_cn": "類別", "cnt": "指派次數"
                }),
                use_container_width=True
            )
            st.caption("💡 同一主管在同類別被指派 ≥ 3 次後，自動升為「預設建議負責人（⭐）」")
        else:
            st.info("尚無責任地圖資料 — 在決策沙盒核准幾次後即可累積")

    if st.button("關閉", use_container_width=True, key="edge_close_learning"):
        st.session_state.edge_show_learning = False
        st.rerun()


# ================================================================
# 主程式
# ================================================================
def main():
    _edge_init()
    auto_process()
    render_sidebar()
    render_main_dashboard()

    if st.session_state.get("edge_show_report"):
        show_battle_report_dialog()
    if st.session_state.get("edge_show_learning"):
        show_learning_dialog()


main()
