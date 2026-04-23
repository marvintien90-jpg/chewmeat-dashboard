"""
6_Line邊緣代理人.py — v6.2
嗑肉數位總部：Line 邊緣代理人全景看板
v6.2：Render Webhook Server 橋接層 / 遠端 REST API 模式
      LINE 訊息接收架構：LINE → Render FastAPI → REST API → Streamlit Cloud
      群組操作全面支援遠端 API（unrecognized_groups / groups CRUD）
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random, re
import json as _json

# ── 頁面設定 ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="嗑肉數位總部 ｜ Line 邊緣代理人 v6.1",
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
# 遠端 Webhook Server 橋接層 (v6.2)
# ================================================================
# 當 LINE_WEBHOOK_SERVER_URL 指向真實 Render 伺服器時，
# 自動透過 REST API 讀取事件與群組，解決 Streamlit Cloud + Render 跨服務資料共享問題。
# localhost / 127.0.0.1 視為本機開發模式，仍直接讀本機 SQLite。

def _get_webhook_base_url() -> str:
    """
    取得 Webhook Server Base URL。
    優先順序：st.secrets → os.environ → SQLite 設定。
    localhost / 127.0.0.1 = 本機模式，回傳空字串。
    """
    url = ""
    try:
        url = (st.secrets.get("LINE_WEBHOOK_SERVER_URL", "") or "").strip().rstrip("/")
    except Exception:
        pass
    if not url:
        url = os.environ.get("LINE_WEBHOOK_SERVER_URL", "").strip().rstrip("/")
    if not url:
        url = (edge_store.get_setting("app_cfg_LINE_WEBHOOK_SERVER_URL") or "").strip().rstrip("/")
    # localhost = 本機模式（不走遠端 API）
    if url and "localhost" not in url and "127.0.0.1" not in url:
        return url
    return ""


def _remote_get(path: str, timeout: int = 6) -> dict | None:
    """對 Webhook Server 發 GET 請求；失敗回傳 None（自動 fallback 到本機 SQLite）。"""
    base = _get_webhook_base_url()
    if not base:
        return None
    try:
        import requests as _req
        r = _req.get(f"{base}{path}", timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _remote_post(path: str, body: dict, timeout: int = 6) -> bool:
    """對 Webhook Server 發 POST 請求；成功回傳 True。"""
    base = _get_webhook_base_url()
    if not base:
        return False
    try:
        import requests as _req
        r = _req.post(f"{base}{path}", json=body, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _remote_delete(path: str, timeout: int = 6) -> bool:
    """對 Webhook Server 發 DELETE 請求；成功回傳 True。"""
    base = _get_webhook_base_url()
    if not base:
        return False
    try:
        import requests as _req
        r = _req.delete(f"{base}{path}", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _parse_dt_safe(v):
    """嘗試將字串解析為 datetime；失敗回傳原值。"""
    if v and isinstance(v, str):
        try:
            return datetime.fromisoformat(v)
        except Exception:
            pass
    return v


# ── 智能資料載入（遠端優先 → 本機 SQLite fallback）────────────────

def load_events_smart() -> list[dict]:
    """
    載入事件：
    1. 若 Webhook Server URL 已設定 → 呼叫 GET /api/events
    2. 否則 → 讀本機 SQLite（開發模式 / 尚未部署）
    """
    data = _remote_get("/api/events", timeout=5)
    if data is not None:
        evts = data.get("events", [])
        for e in evts:
            for k in ("created_at", "response_deadline", "monitoring_until", "auto_closed_at"):
                e[k] = _parse_dt_safe(e.get(k))
            e.setdefault("user", e.get("user_alias", ""))
        return evts
    return edge_store.load_events()


def load_groups_smart() -> list[dict]:
    """載入群組綁定清單：遠端優先 → 本機 SQLite。"""
    data = _remote_get("/api/groups", timeout=5)
    if data is not None:
        return data.get("groups", [])
    return edge_store.load_line_groups()


def upsert_group_smart(gid: str, store: str, bot: str = "") -> None:
    """新增/更新群組對應（雙寫：遠端 + 本機）。"""
    if _get_webhook_base_url():
        _remote_post("/api/groups", {"group_id": gid, "store_name": store, "bot_name": bot})
    edge_store.upsert_line_group(gid, store, bot)


def delete_group_smart(gid: str) -> None:
    """刪除群組對應（雙刪：遠端 + 本機）。"""
    if _get_webhook_base_url():
        _remote_delete(f"/api/groups/{gid}")
    edge_store.delete_line_group(gid)


def get_unrecognized_groups_smart() -> list[dict]:
    """取得未辨識群組：遠端優先 → 本機 SQLite。"""
    data = _remote_get("/api/unrecognized_groups", timeout=5)
    if data is not None:
        return data.get("groups", [])
    return edge_store.get_unrecognized_groups()


def dismiss_group_smart(gid: str) -> None:
    """移除未辨識群組（雙刪：遠端 + 本機）。"""
    if _get_webhook_base_url():
        _remote_delete(f"/api/unrecognized_groups/{gid}")
    edge_store.dismiss_unrecognized_group(gid)


def get_group_messages_smart(gid: str, limit: int = 3) -> list[dict]:
    """取得群組最近訊息：遠端優先 → 本機 SQLite。"""
    data = _remote_get(f"/api/unrecognized_groups/{gid}/messages?limit={limit}", timeout=5)
    if data is not None:
        return data.get("messages", [])
    return edge_store.get_group_recent_messages(gid, limit)


def get_webhook_server_health() -> dict:
    """
    查詢 Webhook Server 健康狀態。
    回傳：{"url": str, "online": bool, "detail": dict | None, "mode": str}
    """
    base = _get_webhook_base_url()
    if not base:
        return {"url": "", "online": False, "detail": None, "mode": "local"}
    try:
        import requests as _req
        r = _req.get(f"{base}/health", timeout=4)
        if r.status_code == 200:
            return {"url": base, "online": True, "detail": r.json(), "mode": "remote"}
        return {"url": base, "online": False, "detail": {"http": r.status_code}, "mode": "remote"}
    except Exception as e:
        return {"url": base, "online": False, "detail": {"error": str(e)[:80]}, "mode": "remote"}

# ================================================================
# LINE API 設定：頁面載入時注入 os.environ
# 優先順序：st.secrets（Streamlit Cloud）→ SQLite（本機/DB 設定）→ os.environ 維持原值
# ================================================================
_LINE_CFG_KEYS = [
    "LINE_CHANNEL_SECRET",
    "LINE_CHANNEL_ACCESS_TOKEN",
    "LINE_COMMANDER_USER_ID",
    "LINE_WEBHOOK_SERVER_URL",
]
for _k in _LINE_CFG_KEYS:
    if not os.environ.get(_k):
        # 1. Streamlit Cloud Secrets（部署環境，最優先）
        _sv = ""
        try:
            _sv = (st.secrets.get(_k, "") or "").strip()
        except Exception:
            pass
        if _sv:
            os.environ[_k] = _sv
        else:
            # 2. SQLite（本機 DB 設定值）
            _v = edge_store.get_setting(f"app_cfg_{_k}")
            if _v:
                os.environ[_k] = _v

# ── Claude AI API Key 注入（優先順序：st.secrets → SQLite → os.environ 維持原值）──
if not os.environ.get("ANTHROPIC_API_KEY"):
    # 1. Streamlit Cloud Secrets（永久儲存，優先）
    _secrets_key = ""
    try:
        _secrets_key = (st.secrets.get("ANTHROPIC_API_KEY", "") or "").strip()
    except Exception:
        pass
    if _secrets_key:
        os.environ["ANTHROPIC_API_KEY"] = _secrets_key
    else:
        # 2. SQLite（本機 / 同一 session 內有效）
        _sqlite_key = (edge_store.get_setting("app_cfg_ANTHROPIC_API_KEY") or "").strip()
        if _sqlite_key:
            os.environ["ANTHROPIC_API_KEY"] = _sqlite_key

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
    animation: marquee_scroll 60s linear infinite;
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
# 常數 & Helper
# ================================================================
MANAGER_LIST = ["張主管", "李主管", "王主管", "陳主管", "林主管"]

_CAT_CN       = edge_nlp.CAT_CN
_LEVEL_LABELS = edge_nlp.LEVEL_LABELS

classify_v2     = edge_nlp.classify_v2
is_confirmation = edge_nlp.is_confirmation


def get_store_list() -> list[str]:
    """取得門店清單（由使用者自行建立，預設為空清單）"""
    stored = edge_store.get_setting("app_custom_store_list")
    if stored:
        try:
            lst = _json.loads(stored)
            if isinstance(lst, list):
                return lst
        except Exception:
            pass
    return []


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
        "edge_webhook_result":   None,
        "edge_last_auto_check":  None,
        "edge_last_maintenance": None,
        "edge_show_report":      False,
        "edge_show_learning":    False,
        "edge_view":             "dashboard",
        # 看板篩選
        "edge_kanban_show_closed": False,
        "edge_kanban_level_filter": [],
        # 戰報篩選
        "edge_report_range":     "近7日",
        "edge_report_stores":    [],
        "edge_report_levels":    [],
        "edge_show_report_view": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # 不再自動植入 mock 事件，讓系統從空白狀態啟動


# ================================================================
# 核心邏輯函數
# ================================================================
def process_webhook(content: str, user: str = "模擬用戶",
                    store: str = "") -> dict:
    if not store:
        _sl = get_store_list()
        store = random.choice(_sl) if _sl else "未指定門店"

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
        # fallback 1: st.secrets（Streamlit Cloud 永久設定）
        try:
            api_key = (st.secrets.get("ANTHROPIC_API_KEY", "") or "").strip()
        except Exception:
            pass
    if not api_key:
        # fallback 2: SQLite（本 session 設定）
        api_key = (edge_store.get_setting("app_cfg_ANTHROPIC_API_KEY") or "").strip()
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key  # 確保後續流程一致

    if api_key:
        # 清除上次錯誤
        st.session_state.pop("edge_ai_last_error", None)
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
                model="claude-haiku-4-5",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            st.session_state["edge_ai_last_error"] = str(e)

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
        "📊 由分身參謀自動彙整 · SQLite v6 · AI Edge Agent",
    ]
    return "\n".join(lines)


def generate_battle_report_filtered(evts: list[dict], filters: dict) -> str:
    """根據篩選條件產生戰報文字"""
    now = datetime.now()
    red_p  = [e for e in evts if e["level"] == "red"    and e["status"] == "pending"]
    yel_p  = [e for e in evts if e["level"] == "yellow" and e["status"] == "pending"]
    blu_p  = [e for e in evts if e["level"] == "blue"   and e["status"] == "pending"]

    range_label = filters.get("range", "近7日")
    store_label = "、".join(filters.get("stores", [])) or "全部門店"
    level_label = "、".join(filters.get("levels", [])) or "全部等級"

    lines = [
        "🛡️ 【嗑肉數位總部 · 篩選戰報】",
        f"📅 {now.strftime('%Y-%m-%d %H:%M')}",
        f"📊 範圍：{range_label} ｜ 門店：{store_label} ｜ 等級：{level_label}",
        "=" * 32,
        f"\n🔴 【紅色警戒】{len(red_p)} 件（待處理）",
        *[f"  • {e['store']}：{e['content'][:40]}" for e in red_p[:5]],
        f"\n🟡 【黃色行動】{len(yel_p)} 件（待處理）",
        *[f"  • {e['store']}：{e['content'][:40]}" for e in yel_p[:5]],
        f"\n🔵 【藍色任務】{len(blu_p)} 件（待處理）",
        *[f"  • {e['store']}：{e['content'][:40]}" for e in blu_p[:3]],
        "\n" + "=" * 32,
        "📊 由分身參謀自動彙整 · SQLite v6 · AI Edge Agent",
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
@st.dialog("📡 全景戰報預覽 v6")
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
# 側欄（含導覽 + 統計 + 篩選 + 底部）
# ================================================================
def render_sidebar(evts: list[dict]):
    with st.sidebar:
        st.markdown("## 🛡️ 控制台")
        st.divider()

        # ── 導覽按鈕 ──────────────────────────────────────────────
        current_view = st.session_state.get("edge_view", "dashboard")

        nav_items = [
            ("dashboard", "📊 智能儀表板"),
            ("kanban",    "🎯 事件看板"),
            ("report",    "📋 戰報中心"),
            ("settings",  "⚙️ 系統設定"),
        ]
        for view_key, view_label in nav_items:
            btn_type = "primary" if current_view == view_key else "secondary"
            if st.button(view_label, key=f"nav_{view_key}",
                         type=btn_type, use_container_width=True):
                st.session_state["edge_view"] = view_key
                st.rerun()

        st.divider()

        # ── 即時統計（4 metric）──────────────────────────────────────
        today_str = datetime.now().strftime("%Y-%m-%d")
        ai_cnt = sum(
            1 for e in evts
            if e.get("auto_closed_at") and str(e.get("auto_closed_at", "")).startswith(today_str)
        )
        r_cnt = len([e for e in evts if e["level"] == "red"    and e["status"] == "pending"])
        y_cnt = len([e for e in evts if e["level"] == "yellow" and e["status"] == "pending"])
        b_cnt = len([e for e in evts if e["level"] == "blue"   and e["status"] == "pending"])

        st.markdown("**📊 即時統計**")
        m1, m2 = st.columns(2)
        m1.metric("🔴 紅色", r_cnt)
        m2.metric("🟡 黃色", y_cnt)
        m3, m4 = st.columns(2)
        m3.metric("🔵 藍色", b_cnt)
        m4.metric("🤖 AI結案", ai_cnt)

        # ── 看板模式專屬篩選 ──────────────────────────────────────
        if current_view == "kanban":
            st.divider()
            st.markdown("**🎯 看板篩選**")
            st.session_state["edge_kanban_show_closed"] = st.checkbox(
                "顯示已結案",
                value=st.session_state.get("edge_kanban_show_closed", False),
                key="kanban_show_closed_cb",
            )
            st.session_state["edge_kanban_level_filter"] = st.multiselect(
                "等級篩選（空=全部）",
                ["紅色", "黃色", "藍色"],
                default=st.session_state.get("edge_kanban_level_filter", []),
                key="kanban_level_ms",
            )

        # ── 戰報模式專屬篩選 ──────────────────────────────────────
        if current_view == "report":
            st.divider()
            st.markdown("**📋 報表篩選**")
            st.session_state["edge_report_range"] = st.selectbox(
                "時間範圍",
                ["今日", "近3日", "近7日", "近30日"],
                index=["今日", "近3日", "近7日", "近30日"].index(
                    st.session_state.get("edge_report_range", "近7日")
                ),
                key="report_range_sel",
            )
            st.session_state["edge_report_stores"] = st.multiselect(
                "門店篩選（空=全部）",
                get_store_list(),
                default=st.session_state.get("edge_report_stores", []),
                key="report_stores_ms",
            )
            st.session_state["edge_report_levels"] = st.multiselect(
                "等級篩選（空=全部）",
                ["紅色", "黃色", "藍色"],
                default=st.session_state.get("edge_report_levels", []),
                key="report_levels_ms",
            )
            if st.button("📋 生成戰報", key="sidebar_gen_report",
                         type="primary", use_container_width=True):
                st.session_state["edge_show_report_view"] = True
                st.rerun()

        st.divider()

        # ── 底部：返回 + Line API 狀態 ────────────────────────────
        st.page_link("app.py", label="← 返回總部大門")
        st.divider()

        # ── Line API 狀態 ──────────────────────────────────────────
        st.markdown("**📡 LINE API**")
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
                    cached = _line_utils.check_connection()
                    st.session_state[cache_key] = cached
                    st.session_state[cache_ts]  = now_ts
                if cached.get("ok"):
                    st.caption(f"🟢 已連線 · {cached.get('bot_name','—')}")
                else:
                    st.caption(f"🔴 連線失敗 · {cached.get('reason','')[:20]}")
                if st.button("🔄 重驗", key="edge_line_recheck", use_container_width=True):
                    st.session_state.pop("edge_line_status_cache", None)
                    st.rerun()
            else:
                st.caption("⚪ 尚未設定 API 金鑰")
                st.caption("→ 請至「⚙️ 系統設定」填入")
        else:
            st.caption("⚪ 模擬模式（requests 未安裝）")

        # ── Claude AI 狀態 ─────────────────────────────────────────
        st.markdown("**🤖 Claude AI**")
        _ai_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if _ai_key:
            _ai_err = st.session_state.get("edge_ai_last_error")
            if _ai_err:
                st.caption("🔴 API 錯誤")
                st.caption("→ 請確認 Key 是否正確")
            else:
                st.caption("🟢 已設定（claude-haiku-4-5）")
        else:
            st.caption("⚪ 尚未設定 API Key")
            st.caption("→ 請至「⚙️ 系統設定」填入")

        # ── 門店快速狀態 ───────────────────────────────────────────
        _sc = len(get_store_list())
        st.markdown("**🏪 門店管理**")
        if _sc:
            st.caption(f"🟢 已設定 {_sc} 間門店")
        else:
            st.caption("⚪ 尚未設定門店")
            st.caption("→ 請至「⚙️ 系統設定」新增")


# ================================================================
# 檢視一：智能儀表板
# ================================================================
def render_view_dashboard(evts: list[dict]):
    # ── 無門店提示橫幅 ────────────────────────────────────────────
    if not get_store_list():
        st.warning(
            "🏪 尚未設定任何門店 — 請前往左側 **⚙️ 系統設定 → 🏪 門店管理** 新增門店，"
            "才能正確分類事件與生成戰報。目前使用示範門店顯示模擬資料。"
        )

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

    # AI 狀態提示
    _ai_key_set = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    _ai_err     = st.session_state.get("edge_ai_last_error")
    if not _ai_key_set:
        st.info(
            "💡 目前顯示規則推導摘要。"
            "前往 **⚙️ 系統設定 → 🤖 Claude AI 設定** 填入 API Key 可啟用 Claude AI 分析。"
        )
    elif _ai_err:
        st.warning(
            f"⚠️ Claude AI 呼叫失敗：`{_ai_err[:120]}`\n\n"
            "→ 請至 **⚙️ 系統設定 → 🤖 Claude AI 設定** 確認 API Key 是否正確。"
        )
    else:
        st.caption("🟢 由 Claude AI (claude-haiku-4-5) 根據今日事件自動生成")

    st.markdown("---")

    # ── 頂部 4 指標 ──────────────────────────────────────────────
    today_str = datetime.now().strftime("%Y-%m-%d")
    r_cnt = len([e for e in evts if e["level"] == "red"    and e["status"] == "pending"])
    y_cnt = len([e for e in evts if e["level"] == "yellow" and e["status"] == "pending"])
    b_cnt = len([e for e in evts if e["level"] == "blue"   and e["status"] == "pending"])
    ai_cnt = sum(
        1 for e in evts
        if e.get("auto_closed_at") and str(e.get("auto_closed_at", "")).startswith(today_str)
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
# 檢視二：事件看板
# ================================================================
def render_view_kanban(evts: list[dict]):
    show_closed   = st.session_state.get("edge_kanban_show_closed", False)
    level_filter  = st.session_state.get("edge_kanban_level_filter", [])

    # 等級中文→英文對應
    _lv_map = {"紅色": "red", "黃色": "yellow", "藍色": "blue"}
    active_levels = [_lv_map[lv] for lv in level_filter] if level_filter else ["red", "yellow", "blue"]

    # ── 重複報修警告橫幅 ──────────────────────────────────────
    repeat_stores = edge_store.get_repeat_repairs_24h()
    if repeat_stores:
        names = "、".join(r["store"] for r in repeat_stores)
        st.warning(
            f"⚡ **24H 重複報修警示**：{names} 在過去 24 小時內出現多次紅色事件，請重點跟進！"
        )

    col_r, col_y, col_b = st.columns(3)

    def _render_col(col, level: str, header_html: str):
        with col:
            st.markdown(header_html, unsafe_allow_html=True)
            if level not in active_levels:
                st.info("（已隱藏此等級）")
                return
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
# 檢視三：戰報中心
# ================================================================
def render_view_report(evts: list[dict]):
    st.markdown("### 📋 戰報中心")

    # 讀取 sidebar 篩選條件
    range_label  = st.session_state.get("edge_report_range", "近7日")
    sel_stores   = st.session_state.get("edge_report_stores", [])
    sel_levels   = st.session_state.get("edge_report_levels", [])

    # 時間範圍篩選
    now   = datetime.now()
    today = now.date()
    _range_map = {
        "今日":   lambda e: e["created_at"].date() == today,
        "近3日":  lambda e: e["created_at"] >= now - timedelta(days=3),
        "近7日":  lambda e: e["created_at"] >= now - timedelta(days=7),
        "近30日": lambda e: e["created_at"] >= now - timedelta(days=30),
    }
    filtered = [e for e in evts if _range_map.get(range_label, lambda x: True)(e)]

    # 門店篩選
    if sel_stores:
        filtered = [e for e in filtered if e["store"] in sel_stores]

    # 等級篩選
    _lv_map = {"紅色": "red", "黃色": "yellow", "藍色": "blue"}
    if sel_levels:
        active_lv = [_lv_map[lv] for lv in sel_levels]
        filtered = [e for e in filtered if e["level"] in active_lv]

    # ── 篩選後統計 ─────────────────────────────────────────────
    r_p = [e for e in filtered if e["level"] == "red"    and e["status"] == "pending"]
    y_p = [e for e in filtered if e["level"] == "yellow" and e["status"] == "pending"]
    b_p = [e for e in filtered if e["level"] == "blue"   and e["status"] == "pending"]

    st.markdown(
        f"**篩選條件：** 時間 `{range_label}` ｜ "
        f"門店 `{'全部' if not sel_stores else '、'.join(sel_stores)}` ｜ "
        f"等級 `{'全部' if not sel_levels else '、'.join(sel_levels)}`"
    )
    st.markdown(f"共篩選出 **{len(filtered)}** 筆事件")

    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 紅色待處理", len(r_p))
    c2.metric("🟡 黃色待處理", len(y_p))
    c3.metric("🔵 藍色待處理", len(b_p))

    st.markdown("---")

    # ── 戰報預覽 ───────────────────────────────────────────────
    show_report = st.session_state.get("edge_show_report_view", False)
    if show_report:
        st.markdown("#### 📄 戰報預覽")
        filters = {
            "range":  range_label,
            "stores": sel_stores,
            "levels": sel_levels,
        }
        report_text = generate_battle_report_filtered(filtered, filters)
        st.code(report_text, language=None)

        st.markdown("---")
        st.markdown("#### 🤖 AI 戰略點評")
        with st.spinner("AI 分析中..."):
            commentary = generate_ai_strategic_summary(filtered)
        st.markdown(
            f'<div class="ai-commentary">{commentary}</div>',
            unsafe_allow_html=True
        )
        st.caption("💡 由 Claude AI 根據篩選事件自動生成（無 API Key 時切換規則推導）")

        st.markdown("---")
        if st.button("📤 推播至 Line 總指揮", type="primary", key="report_push_btn"):
            if _HAS_LINE_UTILS:
                commander_id = _line_utils.get_commander_user_id()
                if commander_id:
                    success = _line_utils.push_message(commander_id, report_text)
                    if success:
                        st.success("✅ 戰報已推播至 Line 總指揮！")
                    else:
                        st.error("❌ 推播失敗，請確認 Line API 設定")
                else:
                    st.warning("⚠️ 尚未設定 Commander User ID")
            else:
                st.success("✅ 戰報推播（模擬模式）")
        if st.button("🔄 重新篩選", key="report_reset_btn"):
            st.session_state["edge_show_report_view"] = False
            st.rerun()
    else:
        st.info("👈 請在左側 Sidebar 設定篩選條件，點擊「📋 生成戰報」即可預覽")

        # 顯示篩選後事件清單
        if filtered:
            st.markdown("#### 📋 篩選結果預覽")
            rows = []
            for e in sorted(filtered, key=lambda x: x["created_at"], reverse=True)[:20]:
                emoji = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}.get(e["level"], "⚪")
                rows.append({
                    "等級": f"{emoji} {_LEVEL_LABELS.get(e['level'], e['level'])}",
                    "門店": e["store"],
                    "狀態": {"pending": "⏳ 待處理", "monitoring": "👀 觀察中", "closed": "✅ 已結案"}.get(e["status"], e["status"]),
                    "內容": e["content"][:35] + ("..." if len(e["content"]) > 35 else ""),
                    "時間": e["created_at"].strftime("%m/%d %H:%M"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ================================================================
# 檢視四：系統設定
# ================================================================
def render_view_settings():
    st.markdown("### ⚙️ 系統設定")

    tab_status, tab_ai, tab_stores, tab_line, tab_groups, tab_dev = st.tabs([
        "🔧 系統狀態",
        "🤖 Claude AI",
        "🏪 門店管理",
        "📡 LINE API",
        "🔗 群組綁定",
        "🧪 開發者工具",
    ])

    # ──────────────────────────────────────────────────────────────
    # Tab 1：系統狀態總覽
    # ──────────────────────────────────────────────────────────────
    with tab_status:
        st.markdown("#### 🔧 系統狀態總覽")
        st.caption("各模組設定一覽，快速確認是否已完成初始化。")

        # Claude AI — 偵測 Key 來源
        _ai_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        _ai_err = st.session_state.get("edge_ai_last_error", "")
        _ai_secrets = ""
        try:
            _ai_secrets = (st.secrets.get("ANTHROPIC_API_KEY", "") or "").strip()
        except Exception:
            pass
        _ai_sqlite = (edge_store.get_setting("app_cfg_ANTHROPIC_API_KEY") or "").strip()
        if _ai_err:
            ai_status = f"🔴 呼叫失敗：{_ai_err[:60]}"
        elif _ai_secrets:
            ai_status = "🟢 已設定（來源：Streamlit Cloud Secrets，永久有效）"
        elif _ai_sqlite:
            ai_status = "🟡 已設定（來源：SQLite，重啟後失效）"
        elif _ai_key:
            ai_status = "🔵 已設定（來源：環境變數）"
        else:
            ai_status = "⚪ 尚未設定 API Key"

        # LINE API（優先讀 os.environ，已由頁面載入時從 st.secrets/SQLite 注入）
        _line_secret = (os.environ.get("LINE_CHANNEL_SECRET")
                        or edge_store.get_setting("app_cfg_LINE_CHANNEL_SECRET") or "")
        _line_token  = (os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
                        or edge_store.get_setting("app_cfg_LINE_CHANNEL_ACCESS_TOKEN") or "")
        _line_cmd    = (os.environ.get("LINE_COMMANDER_USER_ID")
                        or edge_store.get_setting("app_cfg_LINE_COMMANDER_USER_ID") or "")
        if _line_secret and _line_token:
            line_status = "🟢 Channel Secret 與 Token 已設定"
            if not _line_cmd:
                line_status += "（Commander ID 未設定）"
        else:
            line_status = "⚪ 尚未設定 Channel Secret 或 Token"

        # 門店
        _store_list = get_store_list()
        store_status = f"🟢 已設定 {len(_store_list)} 間門店" if _store_list else "⚪ 尚未設定任何門店"

        # 群組綁定
        _groups = edge_store.load_line_groups()
        group_status = f"🟢 已綁定 {len(_groups)} 個群組" if _groups else "⚪ 尚無群組綁定"

        # 事件資料
        _evt_cnt = edge_store.count_events()
        evt_status = f"🟢 資料庫已有 {_evt_cnt} 筆事件" if _evt_cnt else "⚪ 尚無事件資料"

        # Webhook Server 狀態（快速查詢，timeout=3 秒）
        _wh_health = get_webhook_server_health()
        if _wh_health["mode"] == "remote":
            _wh_url_short = _wh_health["url"].replace("https://", "").replace("http://", "")[:40]
            if _wh_health["online"]:
                _wh_detail = _wh_health.get("detail") or {}
                _evt_cnt_remote = _wh_detail.get("db_events", "?")
                wh_status = f"🟢 線上（{_wh_url_short}，資料庫 {_evt_cnt_remote} 筆事件）"
            else:
                _err = (_wh_health.get("detail") or {}).get("error", "無法連線")
                wh_status = f"🔴 離線（{_wh_url_short}）：{_err[:40]}"
        else:
            wh_status = "⚪ 本機模式（localhost / 尚未部署 Render）— 見「📡 LINE API」Tab 設定部署說明"

        rows = [
            {"模組": "🤖 Claude AI",        "狀態": ai_status},
            {"模組": "🌐 Webhook Server",    "狀態": wh_status},
            {"模組": "📡 LINE API",          "狀態": line_status},
            {"模組": "🏪 門店管理",          "狀態": store_status},
            {"模組": "🔗 群組綁定",          "狀態": group_status},
            {"模組": "📂 事件資料",          "狀態": evt_status},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("**⚡ 快速操作**")
        qc1, qc2, qc3 = st.columns(3)
        if qc1.button("🔄 重新載入所有設定", use_container_width=True, key="qs_reload"):
            st.cache_data.clear()
            st.rerun()
        if qc2.button("📋 立即產生戰報", use_container_width=True, key="qs_report"):
            st.session_state.edge_show_report = True
            st.rerun()
        if qc3.button("📖 責任地圖日誌", use_container_width=True, key="qs_learning"):
            st.session_state.edge_show_learning = True
            st.rerun()

    # ──────────────────────────────────────────────────────────────
    # Tab 2：Claude AI 設定
    # ──────────────────────────────────────────────────────────────
    with tab_ai:
        st.markdown("#### 🤖 Claude AI 設定")

        # ── 偵測當前 Key 來源 ──────────────────────────────────────
        _env_key     = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        _sqlite_key  = (edge_store.get_setting("app_cfg_ANTHROPIC_API_KEY") or "").strip()
        _secrets_key = ""
        try:
            _secrets_key = (st.secrets.get("ANTHROPIC_API_KEY", "") or "").strip()
        except Exception:
            pass

        # 決定顯示哪個來源
        if _secrets_key:
            _masked = _secrets_key[:8] + "..." + _secrets_key[-4:] if len(_secrets_key) > 12 else "（已設定）"
            st.success(f"🟢 **Streamlit Cloud Secrets** 已設定 API Key：`{_masked}`")
            st.caption("此為最高優先來源，App 重啟後仍有效。")
        elif _sqlite_key:
            _masked = _sqlite_key[:8] + "..." + _sqlite_key[-4:] if len(_sqlite_key) > 12 else "（已設定）"
            st.warning(
                f"🟡 **SQLite（暫存）** 已設定 API Key：`{_masked}`\n\n"
                "⚠️ 此儲存方式在 **Streamlit Cloud 重啟後會清空**。"
                "請將 Key 設定到 Streamlit Cloud Secrets 以確保永久生效（見下方說明）。"
            )
        elif _env_key:
            st.info("🔵 API Key 已在環境變數中（本 session 有效）")
        else:
            st.error("⚪ 尚未設定任何 API Key")

        st.divider()

        # ── 儲存表單 ──────────────────────────────────────────────
        st.markdown("**📝 輸入並儲存 API Key**")
        with st.form("ai_api_form"):
            cfg_anthropic = st.text_input(
                "Anthropic API Key",
                value="",
                type="password",
                placeholder="sk-ant-api03-xxxxxxxx（留空則不更新）",
            )
            ai_save_btn = st.form_submit_button("💾 儲存到 SQLite（本 session）", type="primary", use_container_width=True)

        if ai_save_btn:
            _new_key = cfg_anthropic.strip()
            if _new_key:
                edge_store.set_setting("app_cfg_ANTHROPIC_API_KEY", _new_key)
                os.environ["ANTHROPIC_API_KEY"] = _new_key
                st.session_state.pop("edge_ai_last_error", None)
                st.success("✅ API Key 已儲存至 SQLite 並注入本 session 環境")
                st.info(
                    "💡 **要讓 Key 在 Streamlit Cloud 重啟後仍有效**，"
                    "請到 Streamlit Cloud dashboard → 你的 App → Settings → Secrets，"
                    "新增一行：\n\n`ANTHROPIC_API_KEY = \"你的key\"`"
                )
                st.rerun()
            else:
                st.warning("⚠️ 未輸入任何值，原設定不變")

        st.divider()

        # ── 測試連線 ──────────────────────────────────────────────
        st.markdown("**🔌 測試 Claude AI 連線**")
        if st.button("🤖 立即測試", use_container_width=False, key="test_ai_btn", type="primary"):
            # 按優先順序取得 key
            api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if not api_key:
                try:
                    api_key = (st.secrets.get("ANTHROPIC_API_KEY", "") or "").strip()
                except Exception:
                    pass
            if not api_key:
                api_key = (edge_store.get_setting("app_cfg_ANTHROPIC_API_KEY") or "").strip()
            if not api_key:
                st.warning("⚠️ 請先設定 Anthropic API Key（見上方說明）")
            else:
                with st.spinner("連線測試中，請稍候..."):
                    try:
                        import anthropic
                        client = anthropic.Anthropic(api_key=api_key)
                        msg = client.messages.create(
                            model="claude-haiku-4-5",
                            max_tokens=30,
                            messages=[{"role": "user", "content": "請回覆「嗑肉連線成功」六個字"}],
                        )
                        reply = msg.content[0].text.strip() if msg.content else "（無回應）"
                        # 測試成功：注入 env 並清錯誤
                        os.environ["ANTHROPIC_API_KEY"] = api_key
                        st.session_state.pop("edge_ai_last_error", None)
                        st.success(f"🟢 **Claude AI 連線成功！** 模型回應：{reply}")
                        st.balloons()
                    except Exception as e:
                        err_msg = str(e)
                        st.session_state["edge_ai_last_error"] = err_msg
                        st.error(f"🔴 **連線失敗**：`{err_msg}`")
                        if "authentication" in err_msg.lower() or "api_key" in err_msg.lower() or "401" in err_msg:
                            st.warning("→ API Key 無效或已過期，請重新申請：https://console.anthropic.com/")
                        elif "credit" in err_msg.lower() or "quota" in err_msg.lower() or "402" in err_msg:
                            st.warning("→ 帳戶額度不足，請至 Anthropic Console 充值")
                        elif "not_found" in err_msg.lower() or "404" in err_msg:
                            st.warning("→ 模型名稱錯誤或不可用，已自動回退至規則推導")

        st.divider()

        # ── Streamlit Cloud Secrets 設定說明 ───────────────────────
        with st.expander("📖 如何永久儲存 API Key（Streamlit Cloud）", expanded=not bool(_secrets_key)):
            st.markdown("""
**步驟：**
1. 前往 [Streamlit Cloud](https://share.streamlit.io/) → 找到你的 App
2. 點擊右上角 **⋮** → **Settings**
3. 選擇 **Secrets** 頁籤
4. 在文字框中加入：
```toml
ANTHROPIC_API_KEY = "sk-ant-api03-你的完整金鑰"
```
5. 點擊 **Save** → App 會自動重啟並套用

✅ 設定後每次重啟都會自動載入，不需要再手動輸入。
""")

        # ── 清除按鈕 ──────────────────────────────────────────────
        if _sqlite_key:
            if st.button("🗑️ 清除 SQLite 中的 API Key", key="clear_ai_key_btn", type="secondary"):
                edge_store.set_setting("app_cfg_ANTHROPIC_API_KEY", "")
                os.environ.pop("ANTHROPIC_API_KEY", None)
                st.session_state.pop("edge_ai_last_error", None)
                st.toast("✅ SQLite 中的 API Key 已清除")
                st.rerun()

    # ──────────────────────────────────────────────────────────────
    # Tab 3：門店管理
    # ──────────────────────────────────────────────────────────────
    with tab_stores:
        st.markdown("#### 🏪 門店管理")
        st.caption("請自行新增您的門店名稱。門店清單將用於事件分類、看板顯示與戰報統計。")

        current_stores = get_store_list()

        if not current_stores:
            st.warning("尚未設定任何門店，請使用下方「➕ 新增門店」開始建立清單。")
        else:
            st.markdown(f"目前共 **{len(current_stores)}** 間門店")
            cols_per_row = 3
            for row_start in range(0, len(current_stores), cols_per_row):
                row_stores = current_stores[row_start: row_start + cols_per_row]
                cols = st.columns(cols_per_row)
                for idx, sname in enumerate(row_stores):
                    with cols[idx]:
                        scol1, scol2 = st.columns([4, 1])
                        scol1.markdown(f"**{sname}**")
                        if scol2.button("✕", key=f"del_store_{sname}_{row_start}_{idx}",
                                        help=f"刪除 {sname}"):
                            new_list = [s for s in current_stores if s != sname]
                            edge_store.set_setting("app_custom_store_list", _json.dumps(new_list))
                            st.rerun()

        st.divider()
        st.markdown("#### ➕ 新增門店名稱")
        add_col1, add_col2 = st.columns([4, 1])
        new_store_name = add_col1.text_input(
            "門店名稱",
            key="new_store_name_input",
            placeholder="例：信義店、逢甲店、東區店…",
            label_visibility="collapsed",
        )
        if add_col2.button("新增", key="add_store_btn"):
            if new_store_name.strip():
                if new_store_name.strip() not in current_stores:
                    new_list = current_stores + [new_store_name.strip()]
                    edge_store.set_setting("app_custom_store_list", _json.dumps(new_list))
                    st.toast(f"✅ 已新增門店：{new_store_name.strip()}")
                    st.rerun()
                else:
                    st.warning(f"「{new_store_name.strip()}」已存在")
            else:
                st.warning("請輸入門店名稱")

        # 批次匯入
        st.divider()
        st.markdown("#### 📋 批次匯入")
        st.caption("每行輸入一個門店名稱，按「批次新增」一次加入所有門店。")
        bulk_input = st.text_area(
            "批次門店清單",
            key="bulk_store_input",
            placeholder="崇德店\n美村店\n公益店\n北屯店",
            height=120,
            label_visibility="collapsed",
        )
        if st.button("📋 批次新增", key="bulk_add_btn", use_container_width=False):
            lines = [l.strip() for l in bulk_input.splitlines() if l.strip()]
            added = []
            for s in lines:
                if s and s not in current_stores:
                    current_stores.append(s)
                    added.append(s)
            if added:
                edge_store.set_setting("app_custom_store_list", _json.dumps(current_stores))
                st.success(f"✅ 已批次新增 {len(added)} 間門店：{', '.join(added[:5])}{'…' if len(added) > 5 else ''}")
                st.rerun()
            else:
                st.info("沒有新門店可新增（輸入的名稱已存在或為空）")

        if current_stores:
            st.divider()
            if st.button("🗑️ 清空所有門店清單", key="clear_all_stores_btn", type="secondary"):
                edge_store.set_setting("app_custom_store_list", _json.dumps([]))
                st.toast("✅ 門店清單已清空")
                st.rerun()

    # ──────────────────────────────────────────────────────────────
    # Tab 4：LINE API 設定
    # ──────────────────────────────────────────────────────────────
    with tab_line:
        st.markdown("#### 📡 LINE API 設定")

        # ── Webhook Server 即時狀態卡 ──────────────────────────────
        _wh = get_webhook_server_health()
        if _wh["mode"] == "remote":
            if _wh["online"]:
                _d = _wh.get("detail") or {}
                st.success(
                    f"🟢 **Webhook Server 線上** · "
                    f"事件：{_d.get('db_events','?')} 筆 · "
                    f"LINE 已連線：{'✅' if _d.get('line_connected') else '❌'}\n\n"
                    f"`{_wh['url']}`"
                )
            else:
                _err = (_wh.get("detail") or {}).get("error", "連線失敗")
                st.error(
                    f"🔴 **Webhook Server 離線**：{_err}\n\n"
                    f"URL：`{_wh['url']}`\n\n"
                    "LINE 訊息目前無法接收。請確認 Render 服務正在執行。"
                )
        else:
            st.warning(
                "⚠️ **Webhook Server 尚未部署（本機模式）**\n\n"
                "目前 LINE 訊息無法接收到 App。請部署至 Render 並填入 Webhook URL（見下方說明）。"
            )

        st.divider()

        # ── Render 部署說明 ────────────────────────────────────────
        with st.expander("🚀 如何部署 Webhook Server 到 Render？（點我展開）", expanded=not bool(_wh["mode"] == "remote" and _wh["online"])):
            st.markdown("""
### 讓 LINE 訊息能被接收的三步驟

---

**步驟一：部署到 Render**
1. 前往 [render.com](https://render.com/) → 登入 → **New** → **Blueprint**
2. 連接你的 GitHub Repo（`KeRou-Digital-HQ`）
3. Render 會自動讀取 `render.yaml` 並建立服務（服務名稱：`kerou-line-webhook`）
4. 部署完成後記下你的服務 URL：`https://kerou-line-webhook.onrender.com`

**步驟二：填入 Render 環境變數**
前往 Render Dashboard → 你的服務 → **Environment** → 新增以下三個變數：
```
LINE_CHANNEL_SECRET       = 你的 32 碼 Channel Secret
LINE_CHANNEL_ACCESS_TOKEN = 你的長期 Channel Access Token
LINE_GROUP_STORE_MAP      = {} （先留空，待群組綁定後更新）
```

**步驟三：更新 LINE Developers Console**
1. 前往 [LINE Developers Console](https://developers.line.biz/console/)
2. 選擇你的 Messaging API Channel → **Messaging API** 頁面
3. **Webhook settings** → Webhook URL → 填入：
   ```
   https://kerou-line-webhook.onrender.com/webhook
   ```
4. 點 **Verify** → 確認回傳 `{"ok": true}`
5. 開啟 **Use webhook** 開關

**步驟四：將 Render URL 填入本 App**
1. 在下方表單的「③ Webhook 伺服器 URL」填入：
   ```
   https://kerou-line-webhook.onrender.com
   ```
   （不要加 `/webhook`，只填 base URL）
2. 儲存後 App 就會自動從 Render 讀取 LINE 訊息

---
⚠️ **注意**：Render **Free plan** 15 分鐘無請求後會休眠，LINE 訊息可能在喚醒期間遺失（~30 秒）。
如需穩定接收，建議升級為 **Starter plan**（$7/月）。
""")

        # ── 如何取得各欄位說明 ─────────────────────────────────────
        with st.expander("📖 各欄位如何取得？（點我展開）", expanded=False):
            st.markdown("""
**① Channel Secret & Channel Access Token**
1. 前往 [LINE Developers Console](https://developers.line.biz/console/)
2. 選擇你的 Provider → 選擇 Messaging API Channel
3. **Basic settings** 頁面 → 找到 `Channel secret`（點 Issue 或直接複製）
4. **Messaging API** 頁面 → 滑到最底 → `Channel access token` → 點 **Issue**

---

**② Commander User ID（總指揮的 LINE User ID，格式 U + 32碼）**

**最簡單方式：**
1. 在 LINE 上找到你的 Bot（嗑肉總部小幫手）
2. 直接傳送一則訊息給 Bot（1 對 1 聊天，不是群組）
3. 回到本 App → **群組綁定** 頁籤 → 查看「未辨識群組」，或前往「開發者工具」查看 Webhook 紀錄
4. 你的 User ID 會以 `U` 開頭出現

**或透過 Webhook 日誌：**
1. Webhook 伺服器收到訊息後，JSON 中 `source.userId` 欄位就是 User ID

---

**③ Webhook 伺服器 URL（Base URL，非 Webhook 完整 URL）**
- 本機開發：使用 [ngrok](https://ngrok.com/) 生成臨時 URL（例：`https://xxxx.ngrok.io`）
- 正式部署：Render 服務 URL（例：`https://kerou-line-webhook.onrender.com`）
- ⚠️ **只填 Base URL**，不要加 `/webhook`
""")

        with st.form("line_api_form"):
            cfg_secret = st.text_input(
                "① Channel Secret",
                value=edge_store.get_setting("app_cfg_LINE_CHANNEL_SECRET") or "",
                type="password",
                placeholder="留空則不更新",
            )
            cfg_token = st.text_input(
                "① Channel Access Token",
                value=edge_store.get_setting("app_cfg_LINE_CHANNEL_ACCESS_TOKEN") or "",
                type="password",
                placeholder="留空則不更新",
            )
            cfg_commander = st.text_input(
                "② Commander User ID（你的 LINE User ID，U 開頭 32 碼）",
                value=edge_store.get_setting("app_cfg_LINE_COMMANDER_USER_ID") or "",
                placeholder="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                help="傳訊息給 Bot 後，在群組綁定頁查看未辨識來源即可找到",
            )
            cfg_webhook_url = st.text_input(
                "③ Webhook 伺服器 URL",
                value=edge_store.get_setting("app_cfg_LINE_WEBHOOK_SERVER_URL") or "",
                placeholder="https://your-server.com/webhook",
            )
            save_btn = st.form_submit_button("💾 儲存 LINE 設定", type="primary", use_container_width=True)

        if save_btn:
            cfg_map = {
                "LINE_CHANNEL_SECRET":       cfg_secret.strip(),
                "LINE_CHANNEL_ACCESS_TOKEN": cfg_token.strip(),
                "LINE_COMMANDER_USER_ID":    cfg_commander.strip(),
                "LINE_WEBHOOK_SERVER_URL":   cfg_webhook_url.strip(),
            }
            saved = []
            for key, value in cfg_map.items():
                if value:
                    edge_store.set_setting(f"app_cfg_{key}", value)
                    os.environ[key] = value
                    saved.append(key)
            if saved:
                st.success(f"✅ 已儲存並注入：{', '.join(saved)}")
            else:
                st.info("⚠️ 所有欄位皆為空，設定未更新")
            st.rerun()

        st.divider()
        if st.button("🔌 測試 LINE 連線", use_container_width=False, key="test_line_btn"):
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

    # ──────────────────────────────────────────────────────────────
    # Tab 5：群組→門店 綁定
    # ──────────────────────────────────────────────────────────────
    with tab_groups:
        st.markdown("#### 🔗 群組 → 門店 綁定")

        # ── 如何取得 Group ID 說明 ─────────────────────────────────
        with st.expander("📖 如何取得 LINE 群組 ID？（點我展開）", expanded=False):
            st.markdown("""
**LINE 群組 ID 格式**：`C` 開頭，後接 32 碼英數字，例如 `Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

**取得方法（最簡單）：**
1. 將 Bot（嗑肉總部小幫手）**加入目標 LINE 群組**
2. 在群組中任意傳送一則訊息（任何內容都可以）
3. 回到本頁面 → 「未辨識群組」區塊會自動出現該群組的 ID
4. 選擇對應門店並點「綁定」即可

> 💡 群組 ID 不會在 LINE App 介面上直接顯示，只能透過 Webhook 取得。

**`sim_group` 是什麼？**
開發者工具的「隨機模擬 Webhook」會產生假的 `sim_group` 紀錄，這不是真實 LINE 群組。
可直接點「🗑️ 刪除」移除。
""")

        _sl_groups = get_store_list()
        if not _sl_groups:
            st.warning("⚠️ 請先至「🏪 門店管理」新增門店，才能進行群組綁定。")

        # ── 資料來源提示 ─────────────────────────────────────────
        _wh_mode = _get_webhook_base_url()
        if _wh_mode:
            st.info(f"🌐 **遠端模式**：群組資料來自 Webhook Server（{_wh_mode[:50]}）")
        else:
            st.caption("🔧 本機模式：讀取本機 SQLite（Webhook Server 尚未部署）")

        # ── 未辨識群組快速綁定 ────────────────────────────────────
        unrecognized = get_unrecognized_groups_smart()
        if unrecognized:
            with st.expander(f"🔍 未辨識群組 ({len(unrecognized)}) — 快速綁定", expanded=True):
                st.caption("以下群組傳來訊息但尚未綁定門店。查看最近訊息以辨識是哪間門店，再選擇對應門店綁定。")

                for g in unrecognized:
                    gid = g["group_id"]
                    gid_short = gid[:20] + "..."
                    is_sim = gid.startswith("sim_")

                    # 標題列
                    h1, h2 = st.columns([6, 1])
                    if is_sim:
                        h1.markdown(f"🔧 **`{gid_short}`** — 模擬測試群組（非真實 LINE 群組）")
                    else:
                        h1.markdown(f"📱 **`{gid_short}`**")
                    h1.caption(f"訊息數：{g['msg_count']} · 最後活動：{g['last_seen'][:16]}")

                    # 刪除按鈕
                    if h2.button("🗑️ 刪除", key=f"dismiss_{gid}", type="secondary",
                                  help="移除此未辨識群組紀錄"):
                        dismiss_group_smart(gid)
                        st.toast(f"✅ 已刪除群組紀錄：{gid_short}")
                        st.rerun()

                    # 最近訊息預覽（幫助辨識是哪間店）
                    recent_msgs = get_group_messages_smart(gid, limit=3)
                    if recent_msgs:
                        with st.expander(f"💬 最近 {len(recent_msgs)} 則訊息（點我展開辨識門店）"):
                            for m in recent_msgs:
                                sender = m.get("line_user_id", "未知")[:12] + "..."
                                ts     = m.get("received_at", "")[:16]
                                text   = m.get("raw_text", "（空）")[:80]
                                st.markdown(f"- `{ts}` **{sender}**：{text}")

                    # 綁定操作（模擬群組也可綁定，但提示）
                    if not is_sim:
                        cb_col, btn_col = st.columns([3, 1])
                        quick_store = cb_col.selectbox(
                            "選擇對應門店",
                            ["(略過)"] + _sl_groups,
                            key=f"quick_{gid}",
                        )
                        if btn_col.button("✅ 綁定", key=f"qbind_{gid}",
                                          disabled=(quick_store == "(略過)"),
                                          type="primary"):
                            upsert_group_smart(gid, quick_store)
                            st.toast(f"✅ {gid_short} → {quick_store}")
                            st.rerun()
                    else:
                        st.info("此為模擬測試群組，請點右上角「🗑️ 刪除」移除，或忽略。")

                    st.divider()
        else:
            if _wh_mode:
                st.info(
                    "📭 目前無未辨識群組（來自 Render Webhook Server）。\n\n"
                    "將 Bot 加入 LINE 群組後，群組傳訊息即會自動出現在這裡。"
                )
            else:
                st.warning(
                    "📭 目前無未辨識群組。\n\n"
                    "**原因**：Webhook Server 尚未部署，LINE 訊息沒有接收端。\n"
                    "請至「📡 LINE API」Tab 完成 Render 部署，LINE 群組訊息才能被記錄。"
                )

        # ── 已綁定群組列表 ────────────────────────────────────────
        st.markdown("#### ✅ 已綁定群組")
        groups = load_groups_smart()
        if groups:
            for g in groups:
                c1, c2, c3 = st.columns([5, 3, 1])
                c1.caption(f"`{g['group_id'][:24]}...`")
                c2.caption(f"🏪 {g['store_name']}")
                if c3.button("✕", key=f"del_grp_{g['group_id']}", help="解除此群組綁定"):
                    delete_group_smart(g["group_id"])
                    st.rerun()
        else:
            st.caption("尚無已綁定群組 — 請先在上方「未辨識群組」中選擇門店並綁定")

        # ── 手動新增（知道 Group ID 的進階操作）─────────────────────
        st.divider()
        st.markdown("#### ➕ 手動新增綁定（已知 Group ID）")
        st.caption("如果已知 LINE 群組 ID，可在此直接填入。")
        col_gid, col_store = st.columns([2, 2])
        new_gid = col_gid.text_input(
            "LINE 群組 ID (C 開頭)",
            key="edge_new_gid",
            placeholder="Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        )
        if _sl_groups:
            new_store = col_store.selectbox(
                "對應門店",
                _sl_groups,
                key="edge_new_store",
            )
        else:
            col_store.text_input(
                "對應門店名稱",
                key="edge_new_store_txt",
                placeholder="請先至門店管理新增門店",
                disabled=True,
            )
            new_store = ""
        if st.button("新增綁定", use_container_width=False, key="edge_add_group"):
            if new_gid.strip() and new_store:
                upsert_group_smart(new_gid.strip(), new_store)
                st.success(f"✅ 已新增：{new_gid[:24]}... → {new_store}")
                st.rerun()
            elif not new_gid.strip():
                st.warning("請輸入群組 ID")
            else:
                st.warning("請先至「🏪 門店管理」新增門店")

    # ──────────────────────────────────────────────────────────────
    # Tab 6：開發者工具
    # ──────────────────────────────────────────────────────────────
    with tab_dev:
        st.markdown("#### 🧪 開發者工具")
        st.caption("測試、模擬、壓力測試與維護工具（正式環境請謹慎使用）。")

        with st.expander("🤖 Webhook 模擬器", expanded=True):
            _dev_sl = get_store_list()
            _dev_fallback = ["崇德店", "美村店", "公益店", "北屯店", "南屯店"]
            _dev_pool = _dev_sl if _dev_sl else _dev_fallback

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("📨 隨機模擬 Webhook", use_container_width=True, key="dev_sim_random"):
                    tmpl    = random.choice(_WEBHOOK_TEMPLATES)
                    store   = random.choice(_dev_pool)
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

        with st.expander("🔥 壓力測試", expanded=False):
            st.caption("一次生成 20 筆隨機事件，測試看板與 manager_weights 學習")
            if st.button("🔥 壓力測試 (20筆)", use_container_width=True,
                         key="dev_stress_btn", type="secondary"):
                _dev_sl2 = get_store_list()
                _dev_pool2 = _dev_sl2 if _dev_sl2 else _dev_fallback
                with st.spinner("壓力測試中..."):
                    for i in range(20):
                        tmpl    = random.choice(_WEBHOOK_TEMPLATES)
                        store   = random.choice(_dev_pool2)
                        content = tmpl["content"].format(store=store)
                        unique_user = f"壓測_{i:02d}_{random.randint(100,999)}"
                        process_webhook(content, user=unique_user, store=store)
                st.session_state.edge_webhook_result = None
                st.success("✅ 壓力測試完成：20 筆事件已生成！")
                st.rerun()

        with st.expander("📋 報告 & 日誌", expanded=False):
            b1, b2 = st.columns(2)
            if b1.button("📋 立即產生戰報", use_container_width=True,
                         type="primary", key="dev_report_btn"):
                st.session_state.edge_show_report = True
                st.rerun()
            if b2.button("📖 責任地圖 & 決策日誌", key="dev_learning_btn", use_container_width=True):
                st.session_state.edge_show_learning = True
                st.rerun()


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

    evts = load_events_smart()  # 遠端 Webhook Server > 本機 SQLite

    render_sidebar(evts)

    # ── 頁面標題 ─────────────────────────────────────────────────
    st.markdown("""
<div class="main-header">
    <h1 style="margin:0;">🛡️ 嗑肉數位總部</h1>
    <p style="margin:5px 0 0 0;opacity:0.9;">
        Line 邊緣代理人 v6.2 · 智能儀表板 · 三色看板 · 戰報中心 · 系統設定<br>
        <small>Render Webhook Server 橋接 · 遠端 REST API · LINE 訊息接收架構</small>
    </p>
</div>
""", unsafe_allow_html=True)

    # ── 根據 edge_view 渲染對應頁面 ──────────────────────────────
    view = st.session_state.get("edge_view", "dashboard")
    if view == "dashboard":
        render_view_dashboard(evts)
    elif view == "kanban":
        render_view_kanban(evts)
    elif view == "report":
        render_view_report(evts)
    elif view == "settings":
        render_view_settings()

    # ── Dialog 觸發 ───────────────────────────────────────────────
    if st.session_state.get("edge_show_report"):
        show_battle_report_dialog()
    if st.session_state.get("edge_show_learning"):
        show_learning_dialog()


main()
