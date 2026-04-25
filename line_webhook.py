"""
line_webhook.py — Line Messaging API Webhook 接收器 v1.0
嗑肉數位總部：FastAPI 服務，接收 Line 群組訊息 → 寫入 edge_store

══════════════════════════════════════════════════════════
本地開發啟動：
    pip install -r requirements-webhook.txt
    uvicorn line_webhook:app --reload --port 8000

ngrok 暴露（用於 Line Developer Console 設定）：
    ngrok http 8000
    → Webhook URL: https://xxxx.ngrok.io/webhook

Render.com 部署（見 render.yaml）：
    Build Command : pip install -r requirements-webhook.txt
    Start Command : uvicorn line_webhook:app --host 0.0.0.0 --port $PORT

Line Developer Console 設定：
    Messaging API > Webhook Settings
    Webhook URL: https://<your-domain>/webhook
    ✅ Use webhook（開啟）
    ✅ Auto-reply messages（關閉，改由本服務回覆）

Streamlit Secrets（.streamlit/secrets.toml）或 Render 環境變數：
    LINE_CHANNEL_SECRET       = "32 碼 Channel Secret"
    LINE_CHANNEL_ACCESS_TOKEN = "Channel Access Token（長期）"
    LINE_GROUP_STORE_MAP      = '{"C群組ID1": "崇德店", "C群組ID2": "美村店"}'
    EDGE_DB_PATH              = "/data/edge_agent.db"  # Render persistent disk
    LINE_REPLY_ON_EVENT       = "true"   # 收到事件時是否自動回覆確認訊息
══════════════════════════════════════════════════════════
"""
from __future__ import annotations
import sys, os, json, logging, re, atexit
sys.path.insert(0, os.path.dirname(__file__))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
from typing import Optional
from datetime import datetime, timedelta

from utils import edge_store
from utils import edge_nlp
from utils.line_utils import (
    verify_signature,
    get_channel_secret,
    get_channel_access_token,
    get_group_store_map,
    send_reply,
    push_message,
    get_user_display_name,
    push_event_flex,
    push_resolution_flex,
    push_with_quick_reply,
)

# ── 初始化 ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kerou.webhook")


# ═══════════════════════════════════════════════════════════════════
# 排程任務（APScheduler — 24/7 主動巡邏）
# ═══════════════════════════════════════════════════════════════════

def _get_commander_id() -> str:
    return os.environ.get("LINE_COMMANDER_USER_ID", "").strip()


def _job_overdue_patrol():
    """每 1 小時：紅色事件超過 2 小時未處理 → 提醒 Commander"""
    try:
        commander_id = _get_commander_id()
        if not commander_id:
            return
        overdue = edge_store.get_overdue_red_events(hours=2)
        if not overdue:
            return
        lines = [f"🚨 【超時未處理】{len(overdue)} 筆紅色事件 >2h："]
        for e in overdue[:5]:
            lines.append(f"  🔴 #{e['id']} {e['store']} — {e['content'][:30]}")
        if len(overdue) > 5:
            lines.append(f"  … 另 {len(overdue)-5} 筆")
        lines.append("\n請輸入「核准 #N」或「結案 #N」處理")
        push_message(commander_id, "\n".join(lines))
        logger.info(f"[Scheduler] overdue_patrol: {len(overdue)} events pushed")
    except Exception as e:
        logger.error(f"[Scheduler] overdue_patrol error: {e}", exc_info=True)


def _job_monitoring_patrol():
    """每 3 小時：monitoring 狀態超過 6 小時未結案 → 催促 Commander"""
    try:
        commander_id = _get_commander_id()
        if not commander_id:
            return
        cutoff = (datetime.now() - timedelta(hours=6)).isoformat()
        evts = edge_store.load_events(limit=300)
        stale = [
            e for e in evts
            if e.get("status") == "monitoring"
            and str(e.get("created_at", "")) <= cutoff
        ]
        if not stale:
            return
        lines = [f"⏰ 【待結案追蹤】{len(stale)} 筆處理中 >6h："]
        for e in stale[:5]:
            assigned = e.get("assigned_to") or "—"
            lines.append(f"  🟡 #{e['id']} {e['store']} ({assigned}) — {e['content'][:25]}")
        if len(stale) > 5:
            lines.append(f"  … 另 {len(stale)-5} 筆")
        lines.append("\n已完成請輸入「結案 #N」")
        push_message(commander_id, "\n".join(lines))
        logger.info(f"[Scheduler] monitoring_patrol: {len(stale)} stale events pushed")
    except Exception as e:
        logger.error(f"[Scheduler] monitoring_patrol error: {e}", exc_info=True)


def _job_morning_briefing():
    """每天 08:00：早安簡報"""
    try:
        commander_id = _get_commander_id()
        if not commander_id:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        dedup_key = f"sched_morning_{today}"
        if edge_store.get_setting(dedup_key):
            return
        evts       = edge_store.load_events(limit=300)
        pending    = [e for e in evts if e["status"] == "pending"]
        monitoring = [e for e in evts if e["status"] == "monitoring"]
        red_p      = [e for e in pending if e["level"] == "red"]
        yellow_p   = [e for e in pending if e["level"] == "yellow"]
        lines = [
            f"☀️ 【早安簡報】{today}",
            f"",
            f"🔴 紅色待處理：{len(red_p)} 筆",
            f"🟡 黃色待處理：{len(yellow_p)} 筆",
            f"👀 監控中：{len(monitoring)} 筆",
        ]
        if red_p:
            lines.append(f"\n🚨 緊急：")
            for e in red_p[:3]:
                lines.append(f"  #{e['id']} {e['store']} — {e['content'][:30]}")
        lines.append("\n💪 今天也辛苦了！")
        push_message(commander_id, "\n".join(lines))
        edge_store.set_setting(dedup_key, datetime.now().isoformat())
        logger.info(f"[Scheduler] morning_briefing sent: {len(pending)} pending")
    except Exception as e:
        logger.error(f"[Scheduler] morning_briefing error: {e}", exc_info=True)


def _job_battle_report(push_hour: int):
    """每天 17:00 / 19:00：戰報推播"""
    try:
        commander_id = _get_commander_id()
        if not commander_id:
            return
        today     = datetime.now().strftime("%Y-%m-%d")
        dedup_key = f"sched_battle_{today}_{push_hour}h"
        if edge_store.get_setting(dedup_key):
            return
        evts        = edge_store.load_events(limit=300)
        pending     = [e for e in evts if e["status"] == "pending"]
        monitoring  = [e for e in evts if e["status"] == "monitoring"]
        closed_today = [
            e for e in evts
            if e["status"] == "closed"
            and str(e.get("created_at", ""))[:10] == today
        ]
        overdue  = edge_store.get_overdue_red_events(hours=4)
        repeats  = edge_store.get_repeat_repairs_24h()
        emoji    = "🌇" if push_hour == 17 else "🌙"
        label    = "傍晚" if push_hour == 17 else "晚間"
        lines = [
            f"{emoji} 【{label}戰報 {today}】",
            f"",
            f"🔴 紅色待處理：{sum(1 for e in pending if e['level']=='red')}",
            f"🟡 黃色待處理：{sum(1 for e in pending if e['level']=='yellow')}",
            f"🔵 藍色待處理：{sum(1 for e in pending if e['level']=='blue')}",
            f"👀 監控中：{len(monitoring)}",
            f"✅ 今日結案：{len(closed_today)}",
        ]
        if overdue:
            lines.append(f"\n⚠️ 超時未結案：{len(overdue)} 筆（>4h）")
        if repeats:
            stores = "、".join(r["store"] for r in repeats[:3])
            lines.append(f"🔁 重複報修門店：{stores}")
        if not pending and not overdue:
            lines.append(f"\n🎉 今日運營順暢，所有事件均已處理！")
        push_message(commander_id, "\n".join(lines))
        edge_store.set_setting(dedup_key, datetime.now().isoformat())
        logger.info(f"[Scheduler] battle_report {push_hour}h sent")
    except Exception as e:
        logger.error(f"[Scheduler] battle_report error: {e}", exc_info=True)


def _start_scheduler():
    """啟動 APScheduler（背景執行緒，隨 uvicorn process 存活）"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger

        sched = BackgroundScheduler(timezone="Asia/Taipei")

        # 每 1 小時：紅色超時巡邏（首次延遲 5 分鐘，避免剛啟動時立即觸發）
        sched.add_job(
            _job_overdue_patrol, IntervalTrigger(hours=1), id="overdue_patrol",
            next_run_time=datetime.now() + timedelta(minutes=5),
        )
        # 每 3 小時：monitoring 事件追蹤
        sched.add_job(
            _job_monitoring_patrol, IntervalTrigger(hours=3), id="monitoring_patrol",
            next_run_time=datetime.now() + timedelta(minutes=10),
        )
        # 每天 08:00 早安簡報
        sched.add_job(
            _job_morning_briefing, CronTrigger(hour=8, minute=0), id="morning_briefing",
        )
        # 每天 17:00 / 19:00 戰報
        sched.add_job(
            lambda: _job_battle_report(17), CronTrigger(hour=17, minute=0), id="battle_17",
        )
        sched.add_job(
            lambda: _job_battle_report(19), CronTrigger(hour=19, minute=0), id="battle_19",
        )

        sched.start()
        atexit.register(lambda: sched.shutdown(wait=False))
        logger.info("[Scheduler] APScheduler started — 5 jobs active (overdue/monitoring patrol + morning/17h/19h reports)")
        return sched
    except ImportError:
        logger.warning("[Scheduler] apscheduler not installed — scheduled jobs disabled")
        return None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """FastAPI lifespan：啟動排程器，關閉時由 atexit 清理。"""
    _start_scheduler()
    yield


app = FastAPI(
    title="嗑肉數位總部 · Line Webhook",
    description="Line Messaging API Webhook 接收器",
    version="2.0.0",
    lifespan=_lifespan,
)

# 是否對每筆事件自動回覆（預設關閉，避免洗版；設 LINE_REPLY_ON_EVENT=true 開啟）
_REPLY_ON_EVENT = os.environ.get("LINE_REPLY_ON_EVENT", "false").lower() == "true"

# 初始化資料庫（建表 + migration）
edge_store.init_db()
logger.info(f"Edge DB ready: {os.environ.get('EDGE_DB_PATH', '/tmp/edge_agent.db')}")

# 名稱快取 TTL：同一 user_id 在 TTL 秒內不重複呼叫 LINE API
_NAME_CACHE_TTL = 3600  # 1 小時
_name_cache: dict[str, tuple[str, float]] = {}  # {user_id: (name, timestamp)}

# AI 起草暫存：{event_id: draft_text}（記憶體，重啟後清空）
_pending_drafts: dict[int, str] = {}

# 信心度推播門檻（低於此值靜默存檔，不推 Commander）
_CONFIDENCE_THRESHOLD = 0.6


def _get_cached_display_name(user_id: str, group_id: str = "") -> str:
    """
    取得用戶顯示名稱，使用記憶體快取（TTL 1 小時）。
    順序：記憶體快取 → LINE API → fallback Line_後6碼
    """
    import time
    if not user_id:
        return "Line用戶"
    now = time.time()
    cached = _name_cache.get(user_id)
    if cached and now - cached[1] < _NAME_CACHE_TTL:
        return cached[0]
    # 呼叫 LINE API
    try:
        name = get_user_display_name(user_id, group_id)
    except Exception:
        name = ""
    if not name:
        name = f"Line_{user_id[-6:]}"
    _name_cache[user_id] = (name, now)
    logger.info(f"Display name resolved: {user_id[:8]}... → {name}")
    return name


# ═══════════════════════════════════════════════════════════════════
# 健康檢查端點
# ═══════════════════════════════════════════════════════════════════
@app.get("/health")
async def health_check():
    """
    Render.com 健康檢查 & 狀態確認。
    Line Developer Console 可用此端點確認服務存活。
    """
    return {
        "status":         "ok",
        "ts":             datetime.now().isoformat(),
        "db_events":      edge_store.count_events(),
        "line_connected": bool(get_channel_access_token()),
    }


@app.get("/")
async def root():
    return PlainTextResponse("嗑肉 Line Webhook v1.0 · Running ✓")


# ═══════════════════════════════════════════════════════════════════
# Line Webhook 主端點
# ═══════════════════════════════════════════════════════════════════
@app.post("/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: Optional[str] = Header(None, alias="X-Line-Signature"),
):
    """
    接收 Line Messaging API 推送的事件。

    流程：
    1. 讀取原始 body（用於簽名驗證）
    2. HMAC-SHA256 簽名驗證
    3. 解析 JSON payload
    4. 逐一處理 message 事件 → edge_store
    5. 回傳 200 OK（Line 要求必須在 1 秒內回應）
    """
    body_bytes = await request.body()

    # ── 1. 簽名驗證 ───────────────────────────────────────────────
    channel_secret = get_channel_secret()
    if channel_secret:
        if not x_line_signature:
            logger.warning("Missing X-Line-Signature header")
            raise HTTPException(status_code=400, detail="Missing X-Line-Signature")
        if not verify_signature(body_bytes, x_line_signature, channel_secret):
            logger.warning("Signature verification FAILED — possible forgery")
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        logger.warning("LINE_CHANNEL_SECRET 未設定 — 跳過簽名驗證（僅限測試環境）")

    # ── 2. 解析 JSON ──────────────────────────────────────────────
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    # ── 3. 逐一處理事件 ──────────────────────────────────────────
    results = []
    for event in payload.get("events", []):
        try:
            result = _handle_event(event)
            if result:
                results.append(result)
        except Exception as e:
            logger.error(f"Event handling error: {e}", exc_info=True)
            results.append({"type": "error", "message": str(e)})

    logger.info(f"Processed {len(results)} events from {len(payload.get('events',[]))} total")
    return JSONResponse({"ok": True, "processed": len(results), "results": results})


# ═══════════════════════════════════════════════════════════════════
# 事件處理核心
# ═══════════════════════════════════════════════════════════════════
def _handle_event(event: dict) -> Optional[dict]:
    """
    處理單一 Line 事件。
    支援 type=message（文字）、type=postback。
    """
    # ── Postback 事件（Quick Reply / Flex 按鈕）──────────────────
    if event.get("type") == "postback":
        data     = event.get("postback", {}).get("data", "")
        user_id  = event.get("source", {}).get("userId", "")
        return _handle_postback(data, user_id)

    # 只處理文字訊息
    if event.get("type") != "message":
        return None
    msg = event.get("message", {})
    if msg.get("type") != "text":
        return None

    text         = (msg.get("text") or "").strip()
    reply_token  = event.get("replyToken", "")
    source       = event.get("source", {})
    source_type  = source.get("type", "user")   # user / group / room
    line_user_id = source.get("userId", "")
    group_id     = source.get("groupId", "") if source_type == "group" else ""

    if not text:
        return None

    logger.info(
        f"[{source_type}] uid={line_user_id[:8]}... "
        f"gid={group_id[:8] if group_id else ''}... text={text[:60]}"
    )

    # ── A. Commander 指令型控制（直接文字指令）──────────────────
    commander_id = os.environ.get("LINE_COMMANDER_USER_ID", "").strip()
    if commander_id and line_user_id == commander_id:
        cmd_result = _handle_commander_command(text, reply_token)
        if cmd_result is not None:
            return cmd_result

    # ── 1. 緩存原始訊息 ──────────────────────────────────────────
    wh_id = edge_store.cache_webhook(
        raw_text=text,
        line_user_id=line_user_id,
        group_id=group_id,
    )

    # ── 2. 解析門店 ──────────────────────────────────────────────
    store = _resolve_store(group_id, text)

    # ── 3. 用戶顯示名稱（LINE 真實名稱 → 快取 → fallback ID 後綴）──
    user_alias = _get_cached_display_name(line_user_id, group_id)

    # ── 4. 確認語意 → 推播「建議結案」卡片給 Commander（非自動結案）
    if edge_nlp.is_confirmation(text):
        edge_store.mark_webhook_processed(wh_id)
        logger.info(f"Confirmation detected from {store}: {text[:40]}")

        # 找到該門店最近一筆 pending/monitoring 事件
        evts       = edge_store.load_events(limit=100)
        target_evt = next(
            (e for e in evts
             if e.get("store") == store
             and e.get("status") in ("pending", "monitoring")),
            None,
        )

        if target_evt and commander_id:
            try:
                push_resolution_flex(
                    commander_id,
                    target_evt,
                    confirm_user  = user_alias,
                    confirm_text  = text,
                )
                logger.info(f"Suggested closure of event #{target_evt['id']} to commander")
            except Exception as e:
                logger.warning(f"push_resolution_flex failed: {e}")

        return {"type": "confirmation", "store": store,
                "suggest_close": target_evt.get("id") if target_evt else None}

    # ── 5. NLP 分類 + 信心度評分 ─────────────────────────────────
    level, keyword_cat, confidence = edge_nlp.classify_with_confidence(text)

    # 信心度不足 → 靜默存檔，不推播 Commander
    if confidence < _CONFIDENCE_THRESHOLD:
        edge_store.mark_webhook_processed(wh_id)
        logger.info(
            f"Low confidence ({confidence:.2f}) event from {store}, silently archived: {text[:40]}"
        )
        return {"type": "low_confidence", "store": store, "confidence": confidence}

    # ── 6. 5 分鐘合併窗口 ────────────────────────────────────────
    merge_id = edge_store.find_merge_candidate(store, user_alias, level)
    if merge_id:
        edge_store.merge_event_content(merge_id, text)
        edge_store.mark_webhook_processed(wh_id)
        logger.info(f"Merged into event #{merge_id}")

        if _REPLY_ON_EVENT and reply_token:
            emoji = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}.get(level, "📌")
            send_reply(reply_token, f"{emoji} 訊息已合併至現有事件 #{merge_id}。")

        return {"type": "merged", "merge_id": merge_id, "level": level}

    # ── 7. 儲存新事件（v4 加入 group_id 支援逆向回傳）──────────
    new_id = edge_store.save_event({
        "level":       level,
        "store":       store,
        "user_alias":  user_alias,
        "content":     text,
        "status":      "pending",
        "keyword_cat": keyword_cat,
        "group_id":    group_id,     # v4：記錄來源群組，核准時逆向推播用
    })
    edge_store.mark_webhook_processed(wh_id)
    logger.info(
        f"New event #{new_id} [{level}/{keyword_cat}] conf={confidence:.2f} "
        f"{store}: {text[:40]}"
    )

    # ── 8. 回覆確認 ──────────────────────────────────────────────
    if _REPLY_ON_EVENT and reply_token:
        emoji    = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}.get(level, "📌")
        cat_cn   = edge_nlp.CAT_CN.get(keyword_cat, keyword_cat)
        reply_tx = (
            f"{emoji} 分身參謀已收到！\n"
            f"📍 {store} · 事件 #{new_id}\n"
            f"📂 類別：{cat_cn}\n"
            f"⏳ 指令稍後由總部下達，請稍候。"
        )
        send_reply(reply_token, reply_tx)

    # ── 9. 推播 Flex Message 給 Commander（帶信心度 + 新按鈕）────
    if commander_id:
        liff_base = os.environ.get("LIFF_URL", "").strip()
        if not liff_base:
            _wh_url = os.environ.get("LINE_WEBHOOK_SERVER_URL", "").strip().rstrip("/")
            if _wh_url and "localhost" not in _wh_url and "127.0.0.1" not in _wh_url:
                liff_base = f"{_wh_url}/liff"
        evt_obj = {
            "id":          new_id,
            "level":       level,
            "store":       store,
            "user_alias":  user_alias,
            "content":     text,
            "keyword_cat": keyword_cat,
            "confidence":  confidence,   # v2：傳入信心度供 Flex 卡顯示
        }
        try:
            push_event_flex(commander_id, evt_obj, liff_base_url=liff_base)
        except Exception as e:
            logger.warning(f"push_event_flex to commander failed: {e}")

    return {
        "type":        "new",
        "id":          new_id,
        "level":       level,
        "keyword_cat": keyword_cat,
        "store":       store,
    }


# ═══════════════════════════════════════════════════════════════════
# A. Commander 指令型控制
# ═══════════════════════════════════════════════════════════════════
_CMD_RE = re.compile(
    r'(核准|結案|拒絕|轉傳|發送|取消|轉派)\s*#?(\d+)(?:\s+(.+))?'
)


def _handle_commander_command(text: str, reply_token: str) -> Optional[dict]:
    """
    解析 Commander 發送的文字指令並執行。
    支援格式：
      核准 #8            → 核准事件 8
      核准 #8 張窗口     → 核准事件 8，指派窗口為「張窗口」
      結案 #8            → 結案事件 8
      轉傳 #8 崇德店     → 核准事件 8 並改推播到崇德店對應群組
      發送 #8            → 發送 _pending_drafts[8] 存的 AI 草稿
      發送 #8 [修改版]   → 發送修改後的文字（取代草稿）
      取消 #8            → 取消草稿（不發送）
      轉派 #8 張窗口     → 重新起草指派版本給張窗口並推播
    回傳 None 表示不是指令（交由後續正常流程處理）。
    """
    m = _CMD_RE.search(text)
    if not m:
        return None

    action   = m.group(1)
    event_id = int(m.group(2))
    param    = (m.group(3) or "").strip()

    commander_id = os.environ.get("LINE_COMMANDER_USER_ID", "").strip()

    # ── 核准 ───────────────────────────────────────────────────────
    if action == "核准":
        evts = edge_store.load_events(limit=300)
        evt  = next((e for e in evts if e.get("id") == event_id), None)
        if not evt:
            if commander_id:
                push_message(commander_id, f"❌ 找不到事件 #{event_id}")
            return {"type": "cmd_error", "event_id": event_id, "reason": "not_found"}

        assigned = param or "（未指派）"
        group_id = evt.get("group_id", "")
        from datetime import timedelta
        now       = datetime.now()
        mon_until = now + timedelta(hours=24)
        res_dl    = (now + timedelta(hours=4)) if evt.get("level") == "red" else None
        edge_store.update_event(
            event_id, status="monitoring", assigned_to=assigned,
            monitoring_until=mon_until, response_deadline=res_dl,
        )
        edge_store.log_decision(
            event_id=event_id, level=evt.get("level", "blue"),
            store=evt.get("store", ""), assigned_to=assigned,
            draft_modified=False, keyword_cat=evt.get("keyword_cat", ""),
        )
        if group_id:
            push_message(group_id, f"✅ 事件 #{event_id} 已核准，執行窗口：{assigned}")
        if commander_id:
            push_message(commander_id, f"✅ 已核准事件 #{event_id}，指派：{assigned}")
        logger.info(f"Commander approved event #{event_id} -> {assigned}")
        return {"type": "cmd_approve", "event_id": event_id, "assigned": assigned}

    # ── 結案 ───────────────────────────────────────────────────────
    elif action == "結案":
        edge_store.update_event(event_id, status="closed")
        _pending_drafts.pop(event_id, None)
        if commander_id:
            push_message(commander_id, f"✅ 事件 #{event_id} 已結案")
        logger.info(f"Commander closed event #{event_id}")
        return {"type": "cmd_close", "event_id": event_id}

    # ── 拒絕 ───────────────────────────────────────────────────────
    elif action == "拒絕":
        edge_store.update_event(event_id, status="closed")
        _pending_drafts.pop(event_id, None)
        if commander_id:
            push_message(commander_id, f"✅ 事件 #{event_id} 已拒絕並結案")
        return {"type": "cmd_reject", "event_id": event_id}

    # ── 發送 草稿（有或無修改版）────────────────────────────────
    elif action == "發送":
        evts = edge_store.load_events(limit=300)
        evt  = next((e for e in evts if e.get("id") == event_id), None)
        if not evt:
            if commander_id:
                push_message(commander_id, f"❌ 找不到事件 #{event_id}")
            return {"type": "cmd_error", "event_id": event_id, "reason": "not_found"}

        # param 有值時為修改版，否則用原草稿
        draft_text = param if param else _pending_drafts.get(event_id, "")
        if not draft_text:
            if commander_id:
                push_message(
                    commander_id,
                    f"❌ 事件 #{event_id} 沒有待發草稿，請先點「📝 AI起草」"
                )
            return {"type": "cmd_error", "event_id": event_id, "reason": "no_draft"}

        group_id     = evt.get("group_id", "")
        draft_mod    = bool(param)  # 有修改過
        from datetime import timedelta
        now       = datetime.now()
        mon_until = now + timedelta(hours=24)
        res_dl    = (now + timedelta(hours=4)) if evt.get("level") == "red" else None

        # 推播到群組
        push_ok = False
        if group_id:
            push_ok = push_message(group_id, draft_text)

        # 更新事件狀態
        edge_store.update_event(
            event_id, status="monitoring", assigned_to="Commander 指令",
            monitoring_until=mon_until, response_deadline=res_dl,
        )
        edge_store.log_decision(
            event_id=event_id, level=evt.get("level", "blue"),
            store=evt.get("store", ""), assigned_to="Commander 指令",
            draft_modified=draft_mod, keyword_cat=evt.get("keyword_cat", ""),
        )
        _pending_drafts.pop(event_id, None)

        if commander_id:
            status_emoji = "✅" if push_ok else "⚠️"
            push_message(
                commander_id,
                f"{status_emoji} 事件 #{event_id} 草稿已發送到群組"
                + ("（已修改版）" if draft_mod else "")
            )
        logger.info(
            f"Commander sent draft for event #{event_id}, modified={draft_mod}"
        )
        return {"type": "cmd_send", "event_id": event_id, "draft_modified": draft_mod}

    # ── 取消 草稿 ─────────────────────────────────────────────────
    elif action == "取消":
        dropped = _pending_drafts.pop(event_id, None)
        if commander_id:
            if dropped:
                push_message(commander_id, f"✅ 事件 #{event_id} 草稿已取消")
            else:
                push_message(commander_id, f"ℹ️ 事件 #{event_id} 沒有待取消的草稿")
        return {"type": "cmd_cancel_draft", "event_id": event_id, "had_draft": bool(dropped)}

    # ── 轉傳 / 轉派 ──────────────────────────────────────────────
    elif action in ("轉傳", "轉派"):
        evts = edge_store.load_events(limit=300)
        evt  = next((e for e in evts if e.get("id") == event_id), None)
        if not evt:
            if commander_id:
                push_message(commander_id, f"❌ 找不到事件 #{event_id}")
            return {"type": "cmd_error", "event_id": event_id, "reason": "not_found"}

        target_group = ""
        if param:
            groups = edge_store.load_line_groups()
            for g in groups:
                if g.get("store_name") == param:
                    target_group = g["group_id"]
                    break

        from datetime import timedelta
        now       = datetime.now()
        mon_until = now + timedelta(hours=24)
        edge_store.update_event(event_id, status="monitoring",
                                monitoring_until=mon_until)
        edge_store.log_decision(
            event_id=event_id, level=evt.get("level", "blue"),
            store=evt.get("store", ""), assigned_to=f"轉派:{param}",
            draft_modified=False, keyword_cat=evt.get("keyword_cat", ""),
        )

        # 嘗試 AI 起草指派版本
        if target_group:
            delegate_text = (
                f"📢 【{evt.get('store','')}→{param}】轉派任務\n"
                f"事件 #{event_id}：{evt.get('content','')[:80]}\n"
                f"請 {param} 接手處理，回覆「搞定 #{event_id}」後結案。"
            )
            push_message(target_group, delegate_text)
        if commander_id:
            push_message(
                commander_id,
                f"✅ 事件 #{event_id} 已轉派至 {param}"
                + (f"（群組 {target_group[:12]}...）" if target_group else "（未找到對應群組）")
            )
        return {"type": "cmd_forward", "event_id": event_id, "target": param}

    return None


# ═══════════════════════════════════════════════════════════════════
# AI 草稿生成
# ═══════════════════════════════════════════════════════════════════
def _generate_ai_draft(evt: dict) -> str:
    """
    呼叫 Claude API（claude-haiku）為事件生成任務指令草稿。
    失敗時回傳預設模板。
    """
    level      = evt.get("level", "blue")
    store      = evt.get("store", "")
    content    = evt.get("content", "")
    keyword_cat = evt.get("keyword_cat", "")
    event_id   = evt.get("id", 0)

    emoji_map  = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}
    emoji      = emoji_map.get(level, "🔵")
    cat_cn     = {"red-equipment": "設備故障", "red-temperature": "溫度異常",
                  "red-power": "電力異常", "red-safety": "安全事故",
                  "red-other": "緊急事件", "yellow-staffing": "人力支援",
                  "yellow-material": "物料協助", "yellow-delivery": "配送調度",
                  "blue-inventory": "庫存盤點", "blue-task": "例行任務",
                  "blue-report": "回報確認"}.get(keyword_cat, "現場事件")

    # 預設模板（API 失敗時 fallback）
    fallback = (
        f"{emoji} 【{cat_cn}任務指令】\n"
        f"📍 {store}  事件 #{event_id}\n"
        f"📋 事項：{content}\n"
        f"✅ 請立即處理並於完成後回覆「搞定 #{event_id}」"
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return fallback

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        urgency = {"red": "緊急（1 小時內）", "yellow": "盡快（4 小時內）",
                   "blue": "今日內"}.get(level, "今日內")

        system_prompt = (
            "你是「嗑肉餐飲」的現場指令助理。請根據門店回報的訊息，"
            "生成一條簡潔清晰的繁體中文任務指令，供門店主管下達給現場人員。\n"
            "要求：\n"
            "1. 開頭加分類 emoji\n"
            "2. 說明任務性質與具體行動\n"
            "3. 末行加「完成後回覆：搞定 #<event_id>」\n"
            "4. 整體不超過 100 字\n"
            "5. 只輸出任務指令本身，不要說明或前言"
        )
        user_msg = (
            f"門店：{store}\n"
            f"類別：{cat_cn}\n"
            f"事件 ID：#{event_id}\n"
            f"回報內容：{content}\n"
            f"緊急程度：{urgency}"
        )

        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
        )
        draft = resp.content[0].text.strip() if resp.content else fallback
        logger.info(f"AI draft generated for event #{event_id}: {draft[:60]}")
        return draft

    except Exception as e:
        logger.warning(f"_generate_ai_draft failed: {e}")
        return fallback


# ═══════════════════════════════════════════════════════════════════
# C. Postback 處理（Quick Reply / Flex 按鈕）
# ═══════════════════════════════════════════════════════════════════
def _handle_postback(data: str, user_id: str) -> Optional[dict]:
    """
    處理 LINE postback 事件。
    支援 action 類型：
      draft:<id>        → AI 起草回覆草稿，私訊 Commander
      observe:<id>      → 列入觀察（記錄不回應）
      dismiss:<id>      → 略過（標記為 closed）
      delegate:<id>     → 轉派提示（提示 Commander 發送「轉派 #N 窗口名」）
      close_confirm:<id>→ Commander 確認結案（建議結案卡後確認）
      keep_observe:<id> → 繼續觀察（不結案）
      approve:<id>      → 舊版相容：直接核准
      close:<id>        → 舊版相容：直接結案
    """
    commander_id = os.environ.get("LINE_COMMANDER_USER_ID", "").strip()

    def _get_event(eid: int):
        evts = edge_store.load_events(limit=300)
        return next((e for e in evts if e.get("id") == eid), None)

    def _parse_id(raw: str) -> Optional[int]:
        try:
            return int(raw.split(":", 1)[1])
        except (ValueError, IndexError):
            return None

    # ── 📝 AI 起草回覆 ────────────────────────────────────────────
    if data.startswith("draft:"):
        event_id = _parse_id(data)
        if event_id is None:
            return None
        evt = _get_event(event_id)
        if not evt:
            if commander_id:
                push_message(commander_id, f"❌ 找不到事件 #{event_id}")
            return {"type": "postback_error", "event_id": event_id}

        if commander_id:
            push_message(commander_id, f"⏳ 正在為事件 #{event_id} 生成 AI 草稿…")

        draft = _generate_ai_draft(evt)
        _pending_drafts[event_id] = draft

        if commander_id:
            push_message(
                commander_id,
                f"📝 事件 #{event_id} AI 草稿：\n\n"
                f"{draft}\n\n"
                f"───────────────\n"
                f"發送：回覆「發送 #{event_id}」\n"
                f"修改：回覆「發送 #{event_id} [修改版文字]」\n"
                f"取消：回覆「取消 #{event_id}」\n"
                f"轉派：回覆「轉派 #{event_id} 窗口名稱」"
            )
        logger.info(f"Postback draft generated for event #{event_id}")
        return {"type": "postback_draft", "event_id": event_id}

    # ── 👀 列入觀察 ───────────────────────────────────────────────
    elif data.startswith("observe:"):
        event_id = _parse_id(data)
        if event_id is None:
            return None
        edge_store.update_event(event_id, status="monitoring")
        if commander_id:
            push_message(commander_id, f"👀 事件 #{event_id} 已列入觀察（不回應現場）")
        logger.info(f"Postback observe event #{event_id}")
        return {"type": "postback_observe", "event_id": event_id}

    # ── 🔕 略過 ───────────────────────────────────────────────────
    elif data.startswith("dismiss:"):
        event_id = _parse_id(data)
        if event_id is None:
            return None
        edge_store.update_event(event_id, status="closed")
        _pending_drafts.pop(event_id, None)
        if commander_id:
            push_message(commander_id, f"🔕 事件 #{event_id} 已略過（直接結案）")
        logger.info(f"Postback dismiss event #{event_id}")
        return {"type": "postback_dismiss", "event_id": event_id}

    # ── 🔁 轉派提示 ──────────────────────────────────────────────
    elif data.startswith("delegate:"):
        event_id = _parse_id(data)
        if event_id is None:
            return None
        # 取得可用窗口名單提示
        raw = edge_store.get_setting("app_cfg_WINDOW_LIST") or "[]"
        try:
            windows = json.loads(raw)
        except Exception:
            windows = []
        win_hint = "、".join(windows[:5]) if windows else "（尚未設定執行窗口）"
        if commander_id:
            push_message(
                commander_id,
                f"🔁 事件 #{event_id} — 轉派指令格式：\n"
                f"「轉派 #{event_id} [窗口名稱]」\n\n"
                f"目前執行窗口：{win_hint}"
            )
        return {"type": "postback_delegate", "event_id": event_id}

    # ── ✅ 建議結案確認 ───────────────────────────────────────────
    elif data.startswith("close_confirm:"):
        event_id = _parse_id(data)
        if event_id is None:
            return None
        edge_store.update_event(event_id, status="closed")
        _pending_drafts.pop(event_id, None)
        if commander_id:
            push_message(commander_id, f"✅ 事件 #{event_id} 已確認結案")
        logger.info(f"Postback close_confirm event #{event_id}")
        return {"type": "postback_close_confirm", "event_id": event_id}

    # ── 👀 繼續觀察（建議結案卡－否決）──────────────────────────
    elif data.startswith("keep_observe:"):
        event_id = _parse_id(data)
        if event_id is None:
            return None
        edge_store.update_event(event_id, status="monitoring")
        if commander_id:
            push_message(commander_id, f"👀 事件 #{event_id} 繼續觀察中（未結案）")
        logger.info(f"Postback keep_observe event #{event_id}")
        return {"type": "postback_keep_observe", "event_id": event_id}

    # ── 舊版相容：approve / close ────────────────────────────────
    elif data.startswith("approve:"):
        event_id = _parse_id(data)
        if event_id is None:
            return None
        evt = _get_event(event_id)
        if not evt:
            if commander_id:
                push_message(commander_id, f"❌ 找不到事件 #{event_id}")
            return {"type": "postback_error", "event_id": event_id}

        from datetime import timedelta
        now       = datetime.now()
        mon_until = now + timedelta(hours=24)
        res_dl    = (now + timedelta(hours=4)) if evt.get("level") == "red" else None
        edge_store.update_event(
            event_id, status="monitoring", assigned_to="（Postback 核准）",
            monitoring_until=mon_until, response_deadline=res_dl,
        )
        edge_store.log_decision(
            event_id=event_id, level=evt.get("level", "blue"),
            store=evt.get("store", ""), assigned_to="（Postback 核准）",
            draft_modified=False, keyword_cat=evt.get("keyword_cat", ""),
        )
        group_id = evt.get("group_id", "")
        if group_id:
            push_message(group_id, f"✅ 事件 #{event_id} 已核准，總部正在處理中。")
        if commander_id:
            push_message(commander_id, f"✅ 事件 #{event_id} 已透過 Postback 核准。")
        logger.info(f"Postback approved event #{event_id} by user {user_id[:8]}")
        return {"type": "postback_approve", "event_id": event_id}

    elif data.startswith("close:"):
        event_id = _parse_id(data)
        if event_id is None:
            return None
        edge_store.update_event(event_id, status="closed")
        _pending_drafts.pop(event_id, None)
        if commander_id:
            push_message(commander_id, f"✅ 事件 #{event_id} 已透過 Postback 結案。")
        logger.info(f"Postback closed event #{event_id} by user {user_id[:8]}")
        return {"type": "postback_close", "event_id": event_id}

    return None


# ═══════════════════════════════════════════════════════════════════
# 輔助：門店解析
# ═══════════════════════════════════════════════════════════════════
def _resolve_store(group_id: str, text: str) -> str:
    """
    門店解析優先順序：
      1. DB line_groups 表（最優先，由 UI 配置）
      2. LINE_GROUP_STORE_MAP 環境變數
      3. 從訊息文字萃取（"崇德店 POS 故障" → "崇德店"）
      4. 預設值 "Line群組"
    """
    # P1: DB 對應表
    if group_id:
        db_store = edge_store.get_store_for_group(group_id)
        if db_store:
            return db_store

    # P2: 環境變數對應表
    if group_id:
        env_map = get_group_store_map()
        if group_id in env_map:
            return env_map[group_id]

    # P3: 從文字萃取
    extracted = edge_nlp.extract_store_from_text(text)
    if extracted:
        return extracted

    # P4: 預設
    return "Line群組"


# ═══════════════════════════════════════════════════════════════════
# 管理 API（供 Streamlit Dashboard 呼叫）
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/events")
async def get_events(limit: int = 100):
    """取得最新事件（供 Streamlit Cloud 遠端讀取用）"""
    events = edge_store.load_events(limit=limit)
    # 轉換 datetime 為字串以利 JSON 序列化
    for e in events:
        for k in ("created_at", "response_deadline", "monitoring_until"):
            v = e.get(k)
            if v and hasattr(v, "isoformat"):
                e[k] = v.isoformat()
    return JSONResponse({"events": events, "count": len(events)})


@app.get("/api/scheduler/status")
async def scheduler_status():
    """排程器狀態（供 Dashboard 顯示）"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        jobs_info = []
        # 透過 atexit registered 物件無法直接查詢，改透過 APScheduler internals
        # 用簡易方式：列出預定任務清單
        jobs_info = [
            {"id": "overdue_patrol",   "desc": "🔴 紅色超時巡邏",   "interval": "每 1 小時"},
            {"id": "monitoring_patrol","desc": "⏰ 監控追蹤",        "interval": "每 3 小時"},
            {"id": "morning_briefing", "desc": "☀️ 早安簡報",        "interval": "每天 08:00"},
            {"id": "battle_17",        "desc": "🌇 傍晚戰報",        "interval": "每天 17:00"},
            {"id": "battle_19",        "desc": "🌙 晚間戰報",        "interval": "每天 19:00"},
        ]
        return {"scheduler": "running", "jobs": jobs_info, "timezone": "Asia/Taipei"}
    except Exception as e:
        return {"scheduler": "error", "detail": str(e)}


@app.get("/api/stats")
async def get_stats():
    """即時統計（供 Streamlit 側邊欄狀態卡使用）"""
    evts = edge_store.load_events()
    return {
        "total":      len(evts),
        "pending":    sum(1 for e in evts if e["status"] == "pending"),
        "monitoring": sum(1 for e in evts if e["status"] == "monitoring"),
        "closed":     sum(1 for e in evts if e["status"] == "closed"),
        "red_pending": sum(1 for e in evts if e["level"]=="red" and e["status"]=="pending"),
    }


@app.post("/api/groups")
async def upsert_group(request: Request):
    """
    新增 / 更新 Line 群組→門店對應。
    Body: {"group_id": "Cxxx", "store_name": "崇德店", "bot_name": "嗑肉Bot"}
    """
    body = await request.json()
    gid   = body.get("group_id", "").strip()
    store = body.get("store_name", "").strip()
    bot   = body.get("bot_name", "").strip()
    if not gid or not store:
        raise HTTPException(status_code=400, detail="group_id and store_name required")
    edge_store.upsert_line_group(gid, store, bot)
    return {"ok": True, "group_id": gid, "store_name": store}


@app.get("/api/groups")
async def list_groups():
    """列出所有群組對應設定"""
    return {"groups": edge_store.load_line_groups()}


@app.get("/api/unrecognized_groups")
async def get_unrecognized_groups_api():
    """
    未辨識群組列表（有訊息但尚未綁定門店）。
    供 Streamlit Dashboard 在「群組綁定」Tab 顯示快速綁定介面。
    """
    groups = edge_store.get_unrecognized_groups()
    return {"groups": [dict(g) for g in groups]}


@app.get("/api/unrecognized_groups/{group_id}/messages")
async def get_group_messages_api(group_id: str, limit: int = 5):
    """取得指定未辨識群組最近幾筆訊息，幫助辨識是哪間門店。"""
    msgs = edge_store.get_group_recent_messages(group_id, limit)
    return {"messages": [dict(m) for m in msgs]}


@app.delete("/api/unrecognized_groups/{group_id}")
async def dismiss_group_api(group_id: str):
    """
    移除未辨識群組的 webhook_cache 紀錄（略過不綁定）。
    """
    edge_store.dismiss_unrecognized_group(group_id)
    return {"ok": True, "group_id": group_id}


@app.delete("/api/groups/{group_id}")
async def delete_group_api(group_id: str):
    """
    刪除群組→門店對應綁定。
    """
    edge_store.delete_line_group(group_id)
    return {"ok": True, "group_id": group_id}


# ═══════════════════════════════════════════════════════════════════
# 事件核准 API（供 Streamlit Cloud 遠端更新 webhook server DB）
# ═══════════════════════════════════════════════════════════════════
@app.post("/api/events/{event_id}/approve")
async def approve_event_api(event_id: int, request: Request):
    """
    Streamlit Cloud 核准事件 → 更新 webhook server 的 SQLite DB。
    同步：
      1. 將事件狀態改為 monitoring
      2. 記錄決策 log
      3. 推播任務指令到 LINE 群組（group_id）
      4. 推播核准通知到 Commander（LINE_COMMANDER_USER_ID）
    Body:
      {
        "assigned_to": "負責人",
        "line_msg": "任務指令全文",
        "group_id": "Cxxx",          // 推播目標群組
        "level": "blue|yellow|red",
        "store": "門店名",
        "keyword_cat": "分類",
        "draft_modified": false
      }
    """
    from datetime import timedelta
    body = await request.json()
    assigned    = body.get("assigned_to", "").strip()
    line_msg    = body.get("line_msg", "").strip()
    group_id    = body.get("group_id", "").strip()
    level       = body.get("level", "blue")
    store       = body.get("store", "")
    keyword_cat = body.get("keyword_cat", "")
    draft_mod   = body.get("draft_modified", False)

    now       = datetime.now()
    mon_until = now + timedelta(hours=24)
    res_dl    = (now + timedelta(hours=4)) if level == "red" else None

    # 1. 更新事件狀態
    edge_store.update_event(
        event_id,
        status="monitoring",
        assigned_to=assigned,
        monitoring_until=mon_until,
        response_deadline=res_dl,
    )

    # 2. 決策 log
    edge_store.log_decision(
        event_id=event_id, level=level,
        store=store, assigned_to=assigned,
        draft_modified=draft_mod,
        keyword_cat=keyword_cat,
    )

    push_group_ok = False
    push_cmd_ok   = False

    # 3. 推播任務指令到群組
    if group_id and line_msg:
        push_group_ok = push_message(group_id, line_msg)
        logger.info(f"Push to group {group_id[:8]}...: {'ok' if push_group_ok else 'fail'}")

    # 4. 推播核准通知到 Commander 個人 LINE（Flex Message）
    commander_id = os.environ.get("LINE_COMMANDER_USER_ID", "")
    if commander_id and line_msg:
        liff_base = os.environ.get("LIFF_URL", "").strip()
        if not liff_base:
            _wh_url = os.environ.get("LINE_WEBHOOK_SERVER_URL", "").strip().rstrip("/")
            if _wh_url and "localhost" not in _wh_url and "127.0.0.1" not in _wh_url:
                liff_base = f"{_wh_url}/liff"
        evt_obj = {
            "id":          event_id,
            "level":       level,
            "store":       store,
            "user_alias":  assigned,
            "content":     line_msg,
            "keyword_cat": keyword_cat,
        }
        try:
            push_cmd_ok = push_event_flex(commander_id, evt_obj, liff_base_url=liff_base)
        except Exception:
            cmd_notify = (
                f"✅ 【核准通知】\n"
                f"📍 {store} · 事件 #{event_id}\n"
                f"👤 指派：{assigned}\n"
                f"📋 指令：{line_msg[:80]}{'...' if len(line_msg)>80 else ''}"
            )
            push_cmd_ok = push_message(commander_id, cmd_notify)
        logger.info(f"Push to commander {commander_id[:8]}...: {'ok' if push_cmd_ok else 'fail'}")

    return {
        "ok": True,
        "event_id": event_id,
        "push_group": push_group_ok,
        "push_commander": push_cmd_ok,
    }


@app.post("/api/events/{event_id}/close")
async def close_event_api(event_id: int, request: Request):
    """手動結案 API"""
    body = await request.json()
    note = body.get("note", "手動結案")
    edge_store.update_event(event_id, status="closed")
    return {"ok": True, "event_id": event_id}


# ═══════════════════════════════════════════════════════════════════
# 執行窗口 API（供 LIFF 頁面使用）
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/window_list")
async def get_window_list_api():
    """取得執行窗口列表（供 LIFF 頁面使用）"""
    raw = edge_store.get_setting("app_cfg_WINDOW_LIST") or "[]"
    try:
        names = json.loads(raw)
    except Exception:
        names = ["（未指派）"]
    return {"windows": names if names else ["（未指派）"]}


# ═══════════════════════════════════════════════════════════════════
# D. LIFF 頁面（LINE 內嵌瀏覽器決策介面）
# ═══════════════════════════════════════════════════════════════════
@app.get("/liff", response_class=HTMLResponse)
async def liff_page(event_id: int = 0):
    """LIFF 決策頁面（在 LINE 內嵌瀏覽器中開啟）"""
    html = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>嗑肉決策系統</title>
<script src="https://static.line-scdn.net/liff/edge/versions/2.22.3/sdk.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #f0f2f5; min-height: 100vh; padding: 16px;
    color: #222;
  }
  .card {
    background: white; border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    padding: 20px; margin-bottom: 16px;
  }
  .header {
    background: linear-gradient(135deg, #E63B1F, #C62828);
    color: white; border-radius: 16px;
    padding: 20px; margin-bottom: 16px; text-align: center;
  }
  .header h1 { font-size: 1.3rem; margin-bottom: 4px; }
  .header p  { font-size: 0.85rem; opacity: 0.85; }
  .level-badge {
    display: inline-block; padding: 4px 14px; border-radius: 20px;
    font-weight: bold; font-size: 0.85rem; margin-bottom: 12px;
  }
  .level-red    { background: #FFEBE9; color: #E74C3C; border: 1.5px solid #E74C3C; }
  .level-yellow { background: #FFF9E6; color: #F39C12; border: 1.5px solid #F39C12; }
  .level-blue   { background: #E8F4FD; color: #3498DB; border: 1.5px solid #3498DB; }
  .field-label  { font-size: 0.78rem; color: #888; margin-bottom: 4px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
  .field-value  { font-size: 0.95rem; color: #333; margin-bottom: 14px; }
  .content-box  {
    background: #f8f9fa; border-radius: 10px; padding: 12px 14px;
    font-size: 0.95rem; line-height: 1.6; color: #333; margin-bottom: 14px;
    border-left: 4px solid #3498DB;
  }
  select {
    width: 100%; padding: 10px 12px; border-radius: 10px;
    border: 1.5px solid #ddd; font-size: 0.95rem;
    background: white; color: #333; margin-bottom: 14px;
    appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%23888' stroke-width='1.5' fill='none'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 12px center;
    background-size: 12px;
  }
  .btn {
    width: 100%; padding: 14px; border: none; border-radius: 12px;
    font-size: 1rem; font-weight: bold; cursor: pointer;
    margin-bottom: 10px; transition: all 0.2s ease;
    letter-spacing: 0.5px;
  }
  .btn:active { transform: scale(0.97); }
  .btn-approve { background: #27AE60; color: white; }
  .btn-close   { background: #E74C3C; color: white; }
  .btn-cancel  { background: #ecf0f1; color: #555; }
  .success-screen {
    display: none; text-align: center; padding: 40px 20px;
  }
  .success-screen .icon { font-size: 4rem; margin-bottom: 16px; }
  .success-screen h2    { font-size: 1.4rem; color: #27AE60; margin-bottom: 8px; }
  .success-screen p     { color: #666; font-size: 0.9rem; }
  .loading { text-align: center; padding: 40px 20px; color: #888; font-size: 1rem; }
  .error-msg { color: #E74C3C; font-size: 0.85rem; padding: 8px 0; }
  .separator { border: none; border-top: 1px solid #eee; margin: 16px 0; }
</style>
</head>
<body>

<div class="header">
  <h1>🛡️ 嗑肉決策系統</h1>
  <p>LINE LIFF · 即時決策介面</p>
</div>

<div id="loading-screen" class="card loading">
  <p>⏳ 載入事件資料中...</p>
</div>

<div id="main-screen" style="display:none;">
  <div class="card">
    <div id="level-badge" class="level-badge"></div>
    <div class="field-label">事件 ID</div>
    <div id="evt-id" class="field-value"></div>
    <div class="field-label">門店</div>
    <div id="evt-store" class="field-value"></div>
    <div class="field-label">回報者</div>
    <div id="evt-user" class="field-value"></div>
    <div class="field-label">類別</div>
    <div id="evt-cat" class="field-value"></div>
    <div class="field-label">事件內容</div>
    <div id="evt-content" class="content-box"></div>
  </div>

  <div class="card">
    <div class="field-label">指定執行窗口</div>
    <select id="window-select"><option value="">載入中...</option></select>

    <div class="field-label">目標群組（推播對象）</div>
    <select id="group-select"><option value="">（不推播 / 保持原群組）</option></select>

    <hr class="separator">

    <button class="btn btn-approve" onclick="doApprove()">✅ 核准並推播</button>
    <button class="btn btn-close"   onclick="doClose()">❌ 結案</button>
    <button class="btn btn-cancel"  onclick="doCancel()">取消</button>
    <div id="error-msg" class="error-msg"></div>
  </div>
</div>

<div id="success-screen" class="success-screen card">
  <div class="icon" id="success-icon">✅</div>
  <h2 id="success-title">操作成功！</h2>
  <p id="success-msg">視窗將自動關閉...</p>
</div>

<script>
const TARGET_EVENT_ID = """ + str(event_id) + """;
let currentEvent = null;
let baseUrl = window.location.origin;

// LIFF 初始化
liff.init({ liffId: "placeholder" }).catch(() => {});

async function loadData() {
  try {
    // 取得事件列表
    const evtResp = await fetch(baseUrl + "/api/events?limit=300");
    const evtData = await evtResp.json();
    const events  = evtData.events || [];
    currentEvent  = events.find(e => e.id === TARGET_EVENT_ID);

    if (!currentEvent) {
      document.getElementById("loading-screen").innerHTML =
        "<p style='color:#E74C3C'>❌ 找不到事件 #" + TARGET_EVENT_ID + "</p>";
      return;
    }

    // 填充事件資訊
    const lvMap   = { red: "🔴 紅色警戒", yellow: "🟡 黃色行動", blue: "🔵 藍色任務" };
    const lvClass = { red: "level-red", yellow: "level-yellow", blue: "level-blue" };
    const badge   = document.getElementById("level-badge");
    badge.textContent  = lvMap[currentEvent.level] || currentEvent.level;
    badge.className    = "level-badge " + (lvClass[currentEvent.level] || "level-blue");

    document.getElementById("evt-id").textContent      = "#" + currentEvent.id;
    document.getElementById("evt-store").textContent   = currentEvent.store || "—";
    document.getElementById("evt-user").textContent    = currentEvent.user_alias || currentEvent.user || "—";
    document.getElementById("evt-cat").textContent     = currentEvent.keyword_cat || "—";
    document.getElementById("evt-content").textContent = currentEvent.content || "（無內容）";

    // 取得執行窗口列表
    const winResp = await fetch(baseUrl + "/api/window_list");
    const winData = await winResp.json();
    const winSel  = document.getElementById("window-select");
    winSel.innerHTML  = '<option value="">（請選擇執行窗口）</option>';
    (winData.windows || []).forEach(w => {
      const opt    = document.createElement("option");
      opt.value    = w; opt.textContent = w;
      winSel.appendChild(opt);
    });

    // 取得群組列表
    const grpResp = await fetch(baseUrl + "/api/groups");
    const grpData = await grpResp.json();
    const grpSel  = document.getElementById("group-select");
    grpSel.innerHTML = '<option value="">（不推播 / 保持原群組）</option>';
    (grpData.groups || []).forEach(g => {
      const opt    = document.createElement("option");
      opt.value    = g.group_id;
      opt.textContent = g.store_name + " (" + g.group_id.substring(0, 12) + "...)";
      if (g.group_id === currentEvent.group_id) opt.selected = true;
      grpSel.appendChild(opt);
    });

    document.getElementById("loading-screen").style.display = "none";
    document.getElementById("main-screen").style.display    = "block";
  } catch (err) {
    document.getElementById("loading-screen").innerHTML =
      "<p style='color:#E74C3C'>❌ 載入失敗：" + err.message + "</p>";
  }
}

async function doApprove() {
  if (!currentEvent) return;
  const assigned = document.getElementById("window-select").value || "（未指派）";
  const groupId  = document.getElementById("group-select").value || currentEvent.group_id || "";
  document.getElementById("error-msg").textContent = "";

  try {
    const resp = await fetch(baseUrl + "/api/events/" + currentEvent.id + "/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        assigned_to:   assigned,
        line_msg:      "✅ 事件 #" + currentEvent.id + " 已核准，執行窗口：" + assigned,
        group_id:      groupId,
        level:         currentEvent.level,
        store:         currentEvent.store,
        keyword_cat:   currentEvent.keyword_cat || "",
        draft_modified: false,
      }),
    });
    if (resp.ok) {
      showSuccess("✅", "核准成功！", "事件 #" + currentEvent.id + " 已核准，指派：" + assigned);
    } else {
      document.getElementById("error-msg").textContent = "❌ 操作失敗（HTTP " + resp.status + "）";
    }
  } catch (err) {
    document.getElementById("error-msg").textContent = "❌ 網路錯誤：" + err.message;
  }
}

async function doClose() {
  if (!currentEvent) return;
  document.getElementById("error-msg").textContent = "";
  try {
    const resp = await fetch(baseUrl + "/api/events/" + currentEvent.id + "/close", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: "LIFF 手動結案" }),
    });
    if (resp.ok) {
      showSuccess("✅", "結案成功！", "事件 #" + currentEvent.id + " 已結案。");
    } else {
      document.getElementById("error-msg").textContent = "❌ 操作失敗（HTTP " + resp.status + "）";
    }
  } catch (err) {
    document.getElementById("error-msg").textContent = "❌ 網路錯誤：" + err.message;
  }
}

function doCancel() {
  try { liff.closeWindow(); } catch (e) { window.history.back(); }
}

function showSuccess(icon, title, msg) {
  document.getElementById("main-screen").style.display    = "none";
  document.getElementById("success-screen").style.display = "block";
  document.getElementById("success-icon").textContent  = icon;
  document.getElementById("success-title").textContent = title;
  document.getElementById("success-msg").textContent   = msg;
  setTimeout(() => {
    try { liff.closeWindow(); } catch (e) {}
  }, 2500);
}

// 頁面載入
loadData();
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("line_webhook:app", host="0.0.0.0", port=8000, reload=True)
