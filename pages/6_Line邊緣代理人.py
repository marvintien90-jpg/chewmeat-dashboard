"""
6_Line邊緣代理人.py — v5.0
嗑肉數位總部：Line 邊緣代理人全景看板
v5.0：三 Tab 架構 / LINE API 設定移至 App UI / 跑馬燈 / AI 智能概況 / 儀表板圖表
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random, re

# ── 頁面設定 ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="嗑肉數位總部 ｜ Line 邊緣代理人 v5",
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

# ── Edge Store + NLP + Line 工具初始化 ───────────────────────────
from utils import edge_store, edge_nlp
edge_store.init_db()

from utils.ui_helpers import inject_global_css
inject_global_css()

try:
    from utils import line_utils as _line_utils
    _HAS_LINE_UTILS = True
except ImportError:
    _HAS_LINE_UTILS = False

# ── Plotly (可選) ────────────────────────────────────────────────
try:
    import plotly.express as px
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False

# ================================================================
# LINE API 設定：頁面載入時從 SQLite 注入 os.environ
# ================================================================
_LINE_CFG_KEYS = [
    "LINE_CHANNEL_SECRET",
    "LINE_CHANNEL_ACCESS_TOKEN",
    "LINE_COMMANDER_USER_ID",
    "LINE_WEBHOOK_SERVER_URL",
]
for _k in _LINE_CFG_KEYS:
    if not os.environ.get(_k):
        _v = edge_store.get_setting(f"app_cfg_{_k}")
        if _v:
            os.environ[_k] = _v

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
.ai-close-label {
    font-size: 11px; color: #27AE60; font-weight: 600;
    margin-top: 4px; padding: 2px 8px;
    background: rgba(39,174,96,0.1); border-radius: 6px;
    display: inline-block;
}
.ai-commentary {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-left: 4px solid #00D4FF; border-radius: 10px;
    padding: 16px 20px; color: #e0f0ff;
    font-size: 0.92rem; line-height: 1.8;
    margin: 10px 0;
}
@keyframes marquee_scroll {
    from { transform: translateX(100vw); }
    to   { transform: translateX(-100%); }
}
.marquee-wrapper {
    background: linear-gradient(90deg, #1A1A2E, #16213E);
    border-radius: 10px; padding: 12px 0; overflow: hidden;
    border: 1px solid rgba(0,212,255,0.25); margin-bottom: 1rem;
}
.marquee-inner {
    white-space: nowrap;
    animation: marquee_scroll 30s linear infinite;
    display: inline-block;
    font-size: 0.9rem;
    color: #e0f0ff;
    padding: 0 20px;
}
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ================================================================
# 常數
# ================================================================
STORE_LIST   = edge_nlp.STORE_LIST
MANAGER_LIST = ["張主管", "李主管", "王主管", "陳主管", "林主管"]

_CAT_CN       = edge_nlp.CAT_CN
_LEVEL_LABELS = edge_nlp.LEVEL_LABELS

classify_v2     = edge_nlp.classify_v2
is_confirmation = edge_nlp.is_confirmation

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


# ================================================================
# 初始化 Session State
# ================================================================
def _edge_init():
    defaults = {
        "edge_show_closed":      False,
        "edge_last_scan":        datetime.now(),
        "edge_seeded":           False,
        "edge_webhook_result":   None,
        "edge_last_auto_check":  None,
        "edge_last_maintenance": None,
        "edge_show_report":      False,
        "edge_show_learning":    False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.edge_seeded:
        if edge_store.count_events() == 0:
            for evt in _generate_mock_events():
                edge_store.save_event(evt)
        st.session_state.edge_seeded = True


def _generate_mock_events() -> list[dict]:
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
# 核心邏輯函數
# ================================================================
def process_webhook(content: str, user: str = "模擬用戶",
                    store: str = "") -> dict:
    if not store:
        store = random.choice(STORE_LIST)

    wh_id = edge_store.cache_webhook(content, "sim_user", "sim_group")

    if is_confirmation(content):
        closed_n = edge_store.auto_close_confirmation_for_store(store)
        edge_store.mark_webhook_processed(wh_id)
        return {
            "type": "confirmation",
            "content": content,
            "store": store,
            "auto_closed": closed_n,
        }

    level, keyword_cat = classify_v2(content)

    merge_id = edge_store.find_merge_candidate(store, user, level)
    if merge_id:
        edge_store.merge_event_content(merge_id, content)
        edge_store.mark_webhook_processed(wh_id)
        return {"type": "merged", "merge_id": merge_id,
                "content": content, "level": level}

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


def _resolve_store_from_webhook(group_id: str, text: str) -> str:
    if group_id:
        db_store = edge_store.get_store_for_group(group_id)
        if db_store:
            return db_store
    if group_id and _HAS_LINE_UTILS:
        env_map = _line_utils.get_group_store_map()
        if group_id in env_map:
            return env_map[group_id]
    extracted = edge_nlp.extract_store_from_text(text)
    if extracted:
        return extracted
    return "Line群組"


def process_pending_webhooks() -> int:
    unprocessed = edge_store.get_unprocessed_webhooks()
    if not unprocessed:
        return 0

    count = 0
    for wh in unprocessed:
        text     = (wh.get("raw_text") or "").strip()
        group_id = wh.get("group_id", "")
        uid      = wh.get("line_user_id", "")

        if not text:
            edge_store.mark_webhook_processed(wh["id"])
            continue

        store      = _resolve_store_from_webhook(group_id, text)
        user_alias = f"Line_{uid[-6:]}" if uid else "Line用戶"

        if is_confirmation(text):
            edge_store.auto_close_confirmation_for_store(store)
        else:
            level, keyword_cat = classify_v2(text)
            merge_id = edge_store.find_merge_candidate(store, user_alias, level)
            if merge_id:
                edge_store.merge_event_content(merge_id, text)
            else:
                edge_store.save_event({
                    "level":       level,
                    "store":       store,
                    "user_alias":  user_alias,
                    "content":     text,
                    "status":      "pending",
                    "keyword_cat": keyword_cat,
                    "group_id":    group_id,
                })

        edge_store.mark_webhook_processed(wh["id"])
        count += 1

    return count


def run_webhook_poll() -> None:
    key  = "edge_last_webhook_poll"
    last = st.session_state.get(key)
    now  = datetime.now()
    if last is not None and (now - last).total_seconds() < 30:
        return
    n = process_pending_webhooks()
    st.session_state[key] = now
    if n > 0:
        st.toast(f"📨 從 Line 群組收到 {n} 筆新訊息", icon="📲")


def run_auto_closure_check() -> None:
    key  = "edge_last_auto_check"
    last = st.session_state.get(key)
    now  = datetime.now()
    if last is not None and (now - last).total_seconds() < 300:
        return
    n_silence = edge_store.auto_close_by_silence(silence_minutes=5)
    n_expired = edge_store.auto_close_expired()
    st.session_state[key] = now
    total = n_silence + n_expired
    if total > 0:
        st.toast(
            f"🤖 AI 智能結案：{n_silence} 筆藍色靜默期滿、{n_expired} 筆觀察期到期",
            icon="✅"
        )


def run_daily_maintenance() -> None:
    key  = "edge_last_maintenance"
    last = st.session_state.get(key)
    now  = datetime.now()
    if last is not None and (now - last).total_seconds() < 86400:
        return
    archived = edge_store.auto_archive_old_events(days=30)
    cleaned  = edge_store.cleanup_old_webhooks(days=7)
    st.session_state[key] = now
    if archived > 0 or cleaned > 0:
        st.toast(
            f"🗂️ 日常維護：歸檔 {archived} 筆舊事件、清理 {cleaned} 筆 Webhook 緩存",
            icon="🧹"
        )


def check_scheduled_report_push() -> None:
    if not _HAS_LINE_UTILS:
        return
    commander_id = _line_utils.get_commander_user_id()
    if not commander_id:
        return
    now   = datetime.now()
    today = now.strftime("%Y-%m-%d")
    for push_hour in [17, 19]:
        if now.hour == push_hour and now.minute < 10:
            setting_key = f"report_pushed_{today}_{push_hour}h"
            if not edge_store.get_setting(setting_key):
                try:
                    report  = generate_battle_report()
                    success = _line_utils.push_message(commander_id, report)
                    if success:
                        edge_store.set_setting(setting_key, now.isoformat())
                        st.toast(f"📱 {push_hour}:00 戰報已推播至總指揮 Line", icon="📊")
                    else:
                        st.toast("⚠️ 戰報推播失敗，請確認 LINE_CHANNEL_ACCESS_TOKEN", icon="❌")
                except Exception as e:
                    st.toast(f"戰報推播異常：{e}", icon="❌")


def generate_ai_strategic_summary(events: list[dict]) -> str:
    red_p   = [e for e in events if e["level"] == "red"    and e["status"] == "pending"]
    yel_p   = [e for e in events if e["level"] == "yellow" and e["status"] == "pending"]
    blu_p   = [e for e in events if e["level"] == "blue"   and e["status"] == "pending"]
    overdue = edge_store.get_overdue_red_events(hours=4)
    repeats = edge_store.get_repeat_repairs_24h()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY", "") or ""
        except Exception:
            pass

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = (
                "你是嗑肉連鎖餐飲的數位運營分析師。\n"
                "根據以下今日現場事件摘要，用繁體中文給出恰好 3 句話的戰略點評，"
                "每句不超過 50 字，聚焦風險、行動建議、後續追蹤三個維度：\n\n"
                f"• 紅色警戒（緊急）：{len(red_p)} 件\n"
                f"• 黃色行動（支援）：{len(yel_p)} 件\n"
                f"• 藍色任務（例行）：{len(blu_p)} 件\n"
                f"• 逾時未處理（>4H）：{len(overdue)} 件\n"
                f"• 24H 重複報修門店：{len(repeats)} 家"
                + (f"（{', '.join(r['store'] for r in repeats[:3])}）" if repeats else "") + "\n\n"
                "請直接輸出 3 句戰略建議，無需標題或編號。"
            )
            msg = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=250,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception:
            pass

    # Rule-based Fallback
    lines = []

    if overdue:
        stores = "、".join(e["store"] for e in overdue[:2])
        lines.append(
            f"⚠️ {stores} 等 {len(overdue)} 件紅色事件已逾 4 小時未回報，"
            f"請主管立即介入確認現場狀況。"
        )
    elif red_p:
        lines.append(
            f"今日共 {len(red_p)} 件紅色警戒待處理，"
            f"建議優先排查設備故障與電力異常，避免影響營業。"
        )
    else:
        lines.append("目前紅色警戒清空，現場運營狀況穩定，持續保持每小時巡查頻率。")

    if repeats:
        stores = "、".join(r["store"] for r in repeats[:2])
        lines.append(
            f"{stores} 出現 24H 重複報修，疑似設備系統性問題，"
            f"建議安排廠商進行深度維保評估。"
        )
    elif yel_p:
        lines.append(
            f"黃色支援需求 {len(yel_p)} 件，人力調度請提前協調，"
            f"假日旺季前應預先建立備援名單。"
        )
    else:
        lines.append("黃色支援需求低，人力配置合理，日常調度流程順暢。")

    total_p = len(red_p) + len(yel_p) + len(blu_p)
    if total_p > 10:
        lines.append(
            f"今日待處理事件達 {total_p} 件，建議啟動緊急協調機制，"
            f"分流主管責任範疇並設定 2H 回報節點。"
        )
    elif total_p > 0:
        lines.append(
            f"今日共 {total_p} 件待處理事件，依三色分級有序推進，"
            f"預計今日內可清零，建議晚間戰報確認結案率。"
        )
    else:
        lines.append(
            "今日事件已全數結案，整體運營表現優良，"
            "建議總部同步整理本日最佳應對實踐，納入 SOP 更新。"
        )

    return "\n\n".join(lines)


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


def generate_battle_report() -> str:
    now    = datetime.now()
    evts   = edge_store.load_events()
    red_p  = [e for e in evts if e["level"] == "red"    and e["status"] == "pending"]
    yel_p  = [e for e in evts if e["level"] == "yellow" and e["status"] == "pending"]
    blu_p  = [e for e in evts if e["level"] == "blue"   and e["status"] == "pending"]

    repeat_stores = edge_store.get_repeat_repairs_24h()
    overdue       = edge_store.get_overdue_red_events(hours=4)

    logs = edge_store.load_decision_logs(limit=50)
    mgr_today: dict[str, int] = {}
    today_str = now.strftime("%Y-%m-%d")
    for log in logs:
        if log["ts"].startswith(today_str):
            m = log["assigned_to"]
            mgr_today[m] = mgr_today.get(m, 0) + 1
    top_mgrs = sorted(mgr_today.items(), key=lambda x: x[1], reverse=True)[:3]

    ai_closed = [e for e in evts if e.get("auto_closed_at") and
                 str(e.get("auto_closed_at", "")).startswith(today_str)]

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
        f"\n🤖 【AI 自動結案（今日）】{len(ai_closed)} 件",
        "\n🏆 【今日熱心榜】",
        *(
            [f"  {'🥇🥈🥉'[i]} {n}：今日指派 {c} 次"
             for i, (n, c) in enumerate(top_mgrs)]
            or ["  （今日尚無決策紀錄）"]
        ),
        "\n" + "=" * 32,
        "📊 由分身參謀自動彙整 · SQLite v5 · AI Edge Agent",
    ]
    return "\n".join(lines)


# ================================================================
# 渲染函數：對話氣泡
# ================================================================
def render_avatar_bubble(item: dict):
    is_mon  = item["status"] in ["monitoring", "closed"]
    bg_cls  = "bg-monitoring" if is_mon else f"bg-{item['level']}"

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

    auto_closed_at = item.get("auto_closed_at")
    ai_close_html  = ""
    if auto_closed_at and item["status"] == "closed":
        try:
            ac_time = datetime.fromisoformat(str(auto_closed_at)).strftime("%H:%M")
        except Exception:
            ac_time = "—"
        close_note = item.get("close_note", "AI 自動結案")
        ai_close_html = (
            f'<div style="margin-top:6px;">'
            f'<span class="ai-close-label">🤖 {close_note}於 {ac_time}</span>'
            f'</div>'
        )

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
        {ai_close_html}
    </div>
</div>
""", unsafe_allow_html=True)

    if item["status"] == "pending":
        if st.button("🎯 開啟決策沙盒", key=f"open_{item['id']}", use_container_width=True):
            show_decision_sandbox(item)


# ================================================================
# 決策沙盒 Dialog
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

    keyword_cat = item.get("keyword_cat", level)
    rec_mgr = edge_store.get_recommended_manager(level, keyword_cat)
    rec_stats = next(
        (s for s in edge_store.get_manager_stats()
         if s["manager"] == rec_mgr and s["category"] == (keyword_cat or level)),
        None
    )
    if rec_mgr:
        cnt    = rec_stats["cnt"] if rec_stats else "?"
        is_def = bool(rec_stats and rec_stats.get("is_default"))
        badge  = "⭐ 預設" if is_def else f"（歷史指派 {cnt} 次）"
        st.markdown(
            f'<div class="rec-badge">💡 AI 推薦主管：<strong>{rec_mgr}</strong> '
            f'<span style="opacity:0.7;font-size:0.78rem;">{badge} · 類別：{cat_cn or level}</span></div>',
            unsafe_allow_html=True
        )

    st.markdown("---")
    st.markdown("#### 👥 責任歸屬指派")
    default_idx = MANAGER_LIST.index(rec_mgr) if rec_mgr in MANAGER_LIST else 0
    assigned = st.selectbox(
        "指定執行主管",
        MANAGER_LIST,
        index=default_idx,
        key=f"mgr_{item['id']}"
    )

    st.markdown("#### ✍️ 審核分身草稿")
    raw_draft = generate_draft(item).replace("[指定主管]", assigned)
    edited = st.text_area(
        "編輯草稿後按核准發送",
        value=raw_draft, height=220,
        key=f"draft_{item['id']}"
    )

    group_id = item.get("group_id", "")
    if group_id and _HAS_LINE_UTILS:
        st.caption(f"📡 來源群組：`{group_id[:20]}...` — 核准後將自動推播回此群組")
    elif not group_id:
        st.caption("⚠️ 此事件無群組 ID（來自模擬器），核准後不會推播至 Line")

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "🚀 一次性核准並發送", type="primary",
            use_container_width=True, key=f"approve_{item['id']}"
        ):
            now       = datetime.now()
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

            push_ok = False
            if group_id and _HAS_LINE_UTILS:
                line_msg = edited.strip()
                push_ok  = _line_utils.push_message(group_id, line_msg)

            if push_ok:
                st.success(
                    "✅ 指令已推播至 Line 群組！\n\n"
                    "🕒 4H 時效追蹤已啟動\n"
                    "👀 24H 觀察期已啟動\n"
                    "📊 決策紀錄已寫入責任地圖"
                )
            elif group_id:
                st.warning(
                    "⚠️ Line 推播失敗（請確認 LINE_CHANNEL_ACCESS_TOKEN 已設定）\n\n"
                    "✅ 資料庫狀態已更新為 MONITORING"
                )
            else:
                st.success(
                    "✅ 決策已記錄（模擬模式，無 Line 推播）\n\n"
                    "🕒 4H 時效追蹤已啟動\n"
                    "👀 24H 觀察期已啟動\n"
                    "📊 決策紀錄已寫入責任地圖"
                )

            st.balloons()
            st.rerun()
    with c2:
        if st.button("❌ 取消", use_container_width=True, key=f"cancel_{item['id']}"):
            st.rerun()


# ================================================================
# 戰報彈窗
# ================================================================
@st.dialog("📡 全景戰報預覽 v5")
def show_battle_report_dialog():
    evts = edge_store.load_events()

    st.markdown("#### 即將推播至 Line 總指揮私訊：")
    st.code(generate_battle_report(), language=None)

    st.markdown("---")
    st.markdown("#### 🤖 AI 戰略點評")
    with st.spinner("分析今日戰情中..."):
        commentary = generate_ai_strategic_summary(evts)

    st.markdown(
        f'<div class="ai-commentary">{commentary}</div>',
        unsafe_allow_html=True
    )
    st.caption("💡 由 Claude AI 根據今日事件自動生成（無 API Key 時切換規則推導）")

    st.markdown("---")
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
# 決策學習日誌彈窗
# ================================================================
@st.dialog("🧠 責任地圖 & 決策偏好學習紀錄")
def show_learning_dialog():
    tab1, tab2 = st.tabs(["📜 決策日誌", "⭐ 責任地圖"])

    with tab1:
        logs = edge_store.load_decision_logs(limit=50)
        if logs:
            df = pd.DataFrame(logs)
            st.dataframe(
                df[["ts", "level", "store", "assigned_to", "keyword_cat", "draft_modified"]],
                use_container_width=True
            )
        else:
            st.info("尚無決策紀錄")

    with tab2:
        stats = edge_store.get_manager_stats()
        if stats:
            df2 = pd.DataFrame(stats)
            df2["category_cn"] = df2["category"].map(lambda c: _CAT_CN.get(c, c))
            df2["狀態"] = df2["is_default"].map({1: "⭐ 預設", 0: "—"})
            st.dataframe(
                df2[["manager", "category_cn", "cnt", "狀態"]].rename(columns={
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
# 側欄（精簡版）
# ================================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🛡️ 控制台")
        st.divider()

        # ── Line API 連線狀態（60秒緩存）────────────────────────────
        st.markdown("**📡 Line API 連線狀態**")
        if _HAS_LINE_UTILS:
            token  = _line_utils.get_channel_access_token()
            secret = _line_utils.get_channel_secret()
            if token and secret:
                cache_key = "edge_line_status_cache"
                cache_ts  = "edge_line_status_ts"
                cached  = st.session_state.get(cache_key)
                last_ts = st.session_state.get(cache_ts)
                now_ts  = datetime.now()
                if cached is None or (last_ts and (now_ts - last_ts).total_seconds() > 60):
                    with st.spinner("驗證中..."):
                        cached = _line_utils.check_connection()
                    st.session_state[cache_key] = cached
                    st.session_state[cache_ts]  = now_ts

                if cached.get("ok"):
                    st.success(f"🟢 已連線  **Bot：** {cached.get('bot_name','—')}")
                else:
                    st.error(f"🔴 連線失敗  {cached.get('reason','未知')}")
                if st.button("🔄 重新驗證", key="edge_line_recheck", use_container_width=True):
                    st.session_state.pop("edge_line_status_cache", None)
                    st.rerun()
            else:
                missing = []
                if not token:  missing.append("ACCESS_TOKEN")
                if not secret: missing.append("CHANNEL_SECRET")
                st.warning(f"⚪ 未設定：{', '.join(missing)}")
        else:
            st.caption("⚪ requests 未安裝（模擬模式）")

        st.divider()

        # ── 即時統計（4 metric）──────────────────────────────────────
        evts = edge_store.load_events()
        today_str = datetime.now().strftime("%Y-%m-%d")
        ai_cnt = sum(
            1 for e in evts
            if e.get("auto_closed_at") and str(e.get("auto_closed_at","")).startswith(today_str)
        )

        st.markdown("**📊 即時統計**")
        m1, m2 = st.columns(2)
        m1.metric("🔴 紅色", len([e for e in evts if e["level"] == "red" and e["status"] == "pending"]))
        m2.metric("🟡 黃色", len([e for e in evts if e["level"] == "yellow" and e["status"] == "pending"]))
        m3, m4 = st.columns(2)
        m3.metric("🔵 藍色", len([e for e in evts if e["level"] == "blue" and e["status"] == "pending"]))
        m4.metric("🤖 AI結案", ai_cnt)

        st.divider()

        # ── 顯示過濾 ──────────────────────────────────────────────
        st.markdown("**🎯 顯示過濾**")
        st.session_state.edge_show_closed = st.checkbox(
            "顯示已結案事件",
            value=st.session_state.edge_show_closed,
            key="edge_closed_cb",
        )

        st.divider()
        st.page_link("app.py", label="← 返回總部大門")


# ================================================================
# Tab 1：智能儀表板
# ================================================================
def render_tab_dashboard(evts: list[dict]):
    # ── 跑馬燈 ────────────────────────────────────────────────────
    pending_evts = [e for e in evts if e["status"] == "pending"]
    latest8 = sorted(pending_evts, key=lambda x: x["created_at"], reverse=True)[:8]
    if latest8:
        level_emoji = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}
        items_html = "  ·  ".join(
            f'{level_emoji.get(e["level"],"⚪")} {e["store"]}：{e["content"][:20]}...'
            for e in latest8
        )
        st.markdown(
            f'<div class="marquee-wrapper">'
            f'<div class="marquee-inner">{items_html}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{items_html}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="marquee-wrapper">'
            '<div class="marquee-inner" style="color:#aaa;">✅ 目前無待處理告警，現場運營正常</div>'
            '</div>',
            unsafe_allow_html=True
        )

    # ── AI 智能概況 ───────────────────────────────────────────────
    st.markdown("#### 🤖 AI 智能概況")
    with st.spinner("AI 分析中..."):
        commentary = generate_ai_strategic_summary(evts)
    st.markdown(
        f'<div class="ai-commentary">{commentary}</div>',
        unsafe_allow_html=True
    )
    st.caption("💡 由 Claude AI 根據今日事件自動生成（無 API Key 時切換規則推導）")

    st.markdown("---")

    # ── 頂部 4 指標 ──────────────────────────────────────────────
    today_str = datetime.now().strftime("%Y-%m-%d")
    r_cnt = len([e for e in evts if e["level"] == "red"    and e["status"] == "pending"])
    y_cnt = len([e for e in evts if e["level"] == "yellow" and e["status"] == "pending"])
    b_cnt = len([e for e in evts if e["level"] == "blue"   and e["status"] == "pending"])
    ai_cnt = sum(
        1 for e in evts
        if e.get("auto_closed_at") and str(e.get("auto_closed_at","")).startswith(today_str)
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔴 紅色警戒", r_cnt, delta="需立即處理" if r_cnt > 0 else None,
              delta_color="inverse")
    m2.metric("🟡 黃色行動", y_cnt)
    m3.metric("🔵 藍色任務", b_cnt)
    m4.metric("🤖 今日 AI 結案", ai_cnt)

    st.markdown("---")

    # ── 門店告警頻率長條圖 ─────────────────────────────────────
    st.markdown("#### 📊 門店告警頻率（待處理）")
    if pending_evts:
        store_counts: dict[str, int] = {}
        for e in pending_evts:
            s = e["store"]
            store_counts[s] = store_counts.get(s, 0) + 1

        chart_df = pd.DataFrame(
            sorted(store_counts.items(), key=lambda x: x[1], reverse=True),
            columns=["門店", "告警次數"]
        )

        if _HAS_PLOTLY:
            fig = px.bar(
                chart_df,
                x="門店", y="告警次數",
                color="告警次數",
                color_continuous_scale=["#3498DB", "#F39C12", "#E63B1F"],
                title="各門店待處理告警次數",
                labels={"門店": "門店", "告警次數": "待處理告警數"},
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(size=13),
                showlegend=False,
                coloraxis_showscale=False,
                margin=dict(t=40, b=10, l=10, r=10),
                height=280,
            )
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.bar_chart(chart_df.set_index("門店"))
    else:
        st.info("✅ 目前無待處理事件")

    st.markdown("---")

    # ── 最近 5 筆待處理事件簡易表格 ─────────────────────────────
    st.markdown("#### 📋 最近 5 筆待處理事件")
    if pending_evts:
        recent5 = sorted(pending_evts, key=lambda x: x["created_at"], reverse=True)[:5]
        rows = []
        for e in recent5:
            emoji = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}.get(e["level"], "⚪")
            rows.append({
                "等級": f"{emoji} {_LEVEL_LABELS.get(e['level'], e['level'])}",
                "門店": e["store"],
                "內容摘要": e["content"][:30] + ("..." if len(e["content"]) > 30 else ""),
                "回報者": e.get("user_alias", ""),
                "時間": e["created_at"].strftime("%m/%d %H:%M"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("✅ 目前無待處理事件")


# ================================================================
# Tab 2：事件看板
# ================================================================
def render_tab_kanban(evts: list[dict]):
    # ── 重複報修警告橫幅 ──────────────────────────────────────
    repeat_stores = edge_store.get_repeat_repairs_24h()
    if repeat_stores:
        names = "、".join(r["store"] for r in repeat_stores)
        st.warning(
            f"⚡ **24H 重複報修警示**：{names} 在過去 24 小時內出現多次紅色事件，請重點跟進！"
        )

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
# Tab 3：系統設定
# ================================================================
def render_tab_settings():

    # ── Section A：LINE API 設定 ─────────────────────────────────
    st.markdown("### 📡 LINE API 設定")
    with st.form("line_api_form"):
        cfg_secret  = st.text_input(
            "Channel Secret",
            value=edge_store.get_setting("app_cfg_LINE_CHANNEL_SECRET") or "",
            type="password",
            placeholder="留空則不更新",
        )
        cfg_token   = st.text_input(
            "Channel Access Token",
            value=edge_store.get_setting("app_cfg_LINE_CHANNEL_ACCESS_TOKEN") or "",
            type="password",
            placeholder="留空則不更新",
        )
        cfg_commander = st.text_input(
            "Commander User ID（總指揮 Line User ID）",
            value=edge_store.get_setting("app_cfg_LINE_COMMANDER_USER_ID") or "",
            placeholder="Uxxxxxxxxxxxxxxxx",
        )
        cfg_webhook_url = st.text_input(
            "Webhook 伺服器 URL",
            value=edge_store.get_setting("app_cfg_LINE_WEBHOOK_SERVER_URL") or "",
            placeholder="https://your-server.com/webhook",
        )
        save_btn = st.form_submit_button("💾 儲存設定", type="primary", use_container_width=True)

    if save_btn:
        cfg_map = {
            "LINE_CHANNEL_SECRET":       cfg_secret.strip(),
            "LINE_CHANNEL_ACCESS_TOKEN": cfg_token.strip(),
            "LINE_COMMANDER_USER_ID":    cfg_commander.strip(),
            "LINE_WEBHOOK_SERVER_URL":   cfg_webhook_url.strip(),
        }
        for key, value in cfg_map.items():
            if value:
                edge_store.set_setting(f"app_cfg_{key}", value)
                os.environ[key] = value
        st.success("✅ LINE API 設定已儲存並注入環境變數")
        st.rerun()

    # 測試連線按鈕
    if st.button("🔌 測試連線", use_container_width=False):
        if _HAS_LINE_UTILS:
            token  = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
            secret = os.environ.get("LINE_CHANNEL_SECRET", "")
            if token and secret:
                with st.spinner("連線測試中..."):
                    result = _line_utils.check_connection()
                if result.get("ok"):
                    st.success(f"🟢 連線成功！Bot 名稱：{result.get('bot_name','—')}")
                else:
                    st.error(f"🔴 連線失敗：{result.get('reason','未知錯誤')}")
            else:
                st.warning("⚠️ 請先填入並儲存 Channel Secret 和 Access Token")
        else:
            st.warning("⚠️ requests 套件未安裝，無法測試真實連線（目前為模擬模式）")

    st.divider()

    # ── Section B：群組→門店 綁定 ────────────────────────────────
    st.markdown("### 🔗 群組 → 門店 綁定")

    # 未辨識群組快速綁定
    unrecognized = edge_store.get_unrecognized_groups()
    if unrecognized:
        with st.expander(f"🔍 未辨識群組 ({len(unrecognized)}) — 快速綁定", expanded=True):
            st.caption("以下群組傳來訊息但尚未綁定門店，請快速綁定以啟動分類。")
            for g in unrecognized:
                gid_short = g["group_id"][:16] + "..."
                st.markdown(f"**`{gid_short}`**")
                st.caption(f"訊息數：{g['msg_count']} · 最後：{g['last_seen'][:16]}")
                cb_col, btn_col = st.columns([3, 1])
                quick_store = cb_col.selectbox(
                    "門店", ["(略過)"] + STORE_LIST,
                    key=f"quick_{g['group_id']}"
                )
                if btn_col.button("綁定", key=f"qbind_{g['group_id']}",
                                  disabled=(quick_store == "(略過)")):
                    edge_store.upsert_line_group(g["group_id"], quick_store)
                    st.toast(f"✅ {gid_short} → {quick_store}")
                    st.rerun()
                st.divider()

    # 已綁定群組列表
    st.markdown("#### 已綁定群組")
    groups = edge_store.load_line_groups()
    if groups:
        for g in groups:
            c1, c2, c3 = st.columns([4, 4, 1])
            c1.caption(f"`{g['group_id'][:20]}...`")
            c2.caption(g["store_name"])
            if c3.button("✕", key=f"del_grp_{g['group_id']}", help="刪除此對應"):
                edge_store.delete_line_group(g["group_id"])
                st.rerun()
    else:
        st.caption("尚無已綁定群組")

    # 手動新增
    st.markdown("#### ➕ 手動新增對應")
    col_gid, col_store = st.columns([2, 2])
    new_gid   = col_gid.text_input(
        "Line 群組 ID (C 開頭)",
        key="edge_new_gid",
        placeholder="C1234567890abcdef...",
    )
    new_store = col_store.selectbox(
        "對應門店（預設帶入戰情室門店名稱）",
        STORE_LIST,
        key="edge_new_store",
    )
    if st.button("新增綁定", use_container_width=False, key="edge_add_group"):
        if new_gid.strip():
            edge_store.upsert_line_group(new_gid.strip(), new_store)
            st.success(f"✅ {new_gid[:20]}... → {new_store}")
            st.rerun()
        else:
            st.warning("請輸入群組 ID")

    st.divider()

    # ── Section C：開發者工具 ────────────────────────────────────
    st.markdown("### 🔧 開發者工具")
    with st.expander("🔧 開發者工具（測試/壓力/維護）", expanded=False):

        st.markdown("#### 🤖 Webhook 模擬器")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📨 隨機模擬 Webhook", use_container_width=True, key="dev_sim_random"):
                tmpl    = random.choice(_WEBHOOK_TEMPLATES)
                store   = random.choice(STORE_LIST)
                content = tmpl["content"].format(store=store)
                result  = process_webhook(content, user=tmpl["user"], store=store)
                st.session_state.edge_webhook_result = result
                st.rerun()

        custom_msg = st.text_input(
            "自訂模擬訊息",
            key="dev_webhook_custom",
            placeholder="例：崇德店 POS 故障",
        )
        with col_b:
            if st.button(
                "📤 送出自訂訊息", use_container_width=True,
                key="dev_sim_custom",
                disabled=not custom_msg.strip(),
            ):
                result = process_webhook(custom_msg.strip())
                st.session_state.edge_webhook_result = result
                st.rerun()

        r = st.session_state.get("edge_webhook_result")
        if r:
            if r["type"] == "new":
                st.success(
                    f"✅ 新事件 #{r['id']}（{_LEVEL_LABELS.get(r['level'], r['level'])}）\n"
                    f"{r['content'][:40]}"
                )
            elif r["type"] == "merged":
                st.info(f"🔗 已合併至事件 #{r['merge_id']}\n{r['content'][:40]}")
            else:
                ac = r.get("auto_closed")
                if ac:
                    st.success(f"✅ 確認語意，已自動結案 {ac} 筆 monitoring 事件")
                else:
                    st.info(f"🔍 確認語意，無 monitoring 事件可結案\n{r['content'][:40]}")

        st.markdown("---")

        st.markdown("#### 🔥 壓力測試")
        st.caption("一次生成 20 筆隨機事件，測試看板與 manager_weights 學習")
        if st.button("🔥 壓力測試 (20筆)", use_container_width=True,
                     key="dev_stress_btn", type="secondary"):
            with st.spinner("壓力測試中..."):
                for i in range(20):
                    tmpl    = random.choice(_WEBHOOK_TEMPLATES)
                    store   = random.choice(STORE_LIST)
                    content = tmpl["content"].format(store=store)
                    unique_user = f"壓測_{i:02d}_{random.randint(100,999)}"
                    process_webhook(content, user=unique_user, store=store)
            st.session_state.edge_webhook_result = None
            st.success("✅ 壓力測試完成：20 筆事件已生成！")
            st.rerun()

        st.markdown("---")

        st.markdown("#### 📋 立即產生戰報")
        if st.button("📋 立即產生戰報", use_container_width=True,
                     type="primary", key="dev_report_btn"):
            st.session_state.edge_show_report = True
            st.rerun()

        st.markdown("---")

        st.markdown("#### 🧠 責任地圖 & 決策日誌")
        if st.button("📖 查看完整日誌", key="dev_learning_btn", use_container_width=True):
            st.session_state.edge_show_learning = True
            st.rerun()

        st.markdown("---")

        st.markdown("#### 🗑️ 清除全部事件")
        st.caption("⚠️ 此操作不可復原，將清除所有事件記錄")
        confirm_clear = st.checkbox("我確認要清除所有事件", key="dev_confirm_clear")
        if st.button(
            "🗑️ 清除全部事件",
            use_container_width=True,
            key="dev_clear_btn",
            type="secondary",
            disabled=not confirm_clear,
        ):
            try:
                from utils.edge_store import _conn
                with _conn() as con:
                    con.execute("DELETE FROM events")
                    con.execute("DELETE FROM webhook_cache")
                st.session_state.edge_seeded = False
                st.session_state.edge_webhook_result = None
                st.success("✅ 已清除所有事件與 Webhook 緩存")
                st.rerun()
            except Exception as e:
                st.error(f"清除失敗：{e}")


# ================================================================
# 主程式
# ================================================================
def main():
    _edge_init()

    # 背景程序
    run_webhook_poll()
    run_auto_closure_check()
    run_daily_maintenance()
    check_scheduled_report_push()

    render_sidebar()

    # ── 頁面標題 ─────────────────────────────────────────────────
    st.markdown("""
<div class="main-header">
    <h1 style="margin:0;">🛡️ 嗑肉數位總部</h1>
    <p style="margin:5px 0 0 0;opacity:0.9;">
        Line 邊緣代理人 v5.0 · 智能儀表板 · 三色看板 · 系統設定<br>
        <small>跑馬燈告警 · AI 智能概況 · LINE API App 內設定 · 開發者工具</small>
    </p>
</div>
""", unsafe_allow_html=True)

    evts = edge_store.load_events()

    # ── 三個 Tab ──────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📊 智能儀表板", "🎯 事件看板", "⚙️ 系統設定"])

    with tab1:
        render_tab_dashboard(evts)

    with tab2:
        render_tab_kanban(evts)

    with tab3:
        render_tab_settings()

    # ── Dialog 觸發 ───────────────────────────────────────────────
    if st.session_state.get("edge_show_report"):
        show_battle_report_dialog()
    if st.session_state.get("edge_show_learning"):
        show_learning_dialog()


main()
