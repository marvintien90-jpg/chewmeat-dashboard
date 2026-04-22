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
import sys, os, json, logging
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, PlainTextResponse
from typing import Optional
from datetime import datetime

from utils import edge_store
from utils import edge_nlp
from utils.line_utils import (
    verify_signature,
    get_channel_secret,
    get_channel_access_token,
    get_group_store_map,
    send_reply,
    push_message,
)

# ── 初始化 ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kerou.webhook")

app = FastAPI(
    title="嗑肉數位總部 · Line Webhook",
    description="Line Messaging API Webhook 接收器",
    version="1.0.0",
)

# 是否對每筆事件自動回覆（可透過環境變數關閉）
_REPLY_ON_EVENT = os.environ.get("LINE_REPLY_ON_EVENT", "true").lower() == "true"

# 初始化資料庫（建表 + migration）
edge_store.init_db()
logger.info(f"Edge DB ready: {os.environ.get('EDGE_DB_PATH', '/tmp/edge_agent.db')}")


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
    目前只處理 type=message 且 message.type=text 的文字訊息。
    """
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
        f"gid={group_id[:8]}... text={text[:60]}"
    )

    # ── 1. 緩存原始訊息 ──────────────────────────────────────────
    wh_id = edge_store.cache_webhook(
        raw_text=text,
        line_user_id=line_user_id,
        group_id=group_id,
    )

    # ── 2. 解析門店 ──────────────────────────────────────────────
    store = _resolve_store(group_id, text)

    # ── 3. 用戶別名（隱藏完整 ID）────────────────────────────────
    user_alias = f"Line_{line_user_id[-6:]}" if line_user_id else "Line用戶"

    # ── 4. 確認語意 → 自動結案 ───────────────────────────────────
    if edge_nlp.is_confirmation(text):
        closed_n = edge_store.auto_close_confirmation_for_store(store)
        edge_store.mark_webhook_processed(wh_id)
        logger.info(f"Confirmation: closed {closed_n} monitoring event(s) for {store}")

        if _REPLY_ON_EVENT and reply_token:
            send_reply(reply_token, f"✅ 已收到確認！{store} 的相關事件已結案。")

        return {"type": "confirmation", "store": store, "closed": closed_n}

    # ── 5. NLP 分類 ──────────────────────────────────────────────
    level, keyword_cat = edge_nlp.classify_v2(text)

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
    logger.info(f"New event #{new_id} [{level}/{keyword_cat}] {store}: {text[:40]}")

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

    return {
        "type":        "new",
        "id":          new_id,
        "level":       level,
        "keyword_cat": keyword_cat,
        "store":       store,
    }


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("line_webhook:app", host="0.0.0.0", port=8000, reload=True)
