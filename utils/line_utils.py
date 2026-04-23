"""
utils/line_utils.py
Line Messaging API 工具函數

功能：
  - HMAC-SHA256 簽名驗證（channel_secret）
  - 金鑰統一讀取（env var → st.secrets fallback）
  - 群組→門店對應表解析（LINE_GROUP_STORE_MAP）
  - Reply API / Push API / Bot Info 查詢
  - push_battle_report()：推播戰報至指定群組

金鑰設定方式（.streamlit/secrets.toml）：
  LINE_CHANNEL_SECRET      = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  LINE_CHANNEL_ACCESS_TOKEN= "eyJ0eXAiOiJKV1Qi..."
  LINE_GROUP_STORE_MAP      = '{"C1234567890abcdef": "崇德店", "C9876543210fedcba": "美村店"}'
"""
from __future__ import annotations
import hmac, hashlib, base64, json, os, logging
from typing import Optional

logger = logging.getLogger(__name__)

_LINE_REPLY_URL   = "https://api.line.me/v2/bot/message/reply"
_LINE_PUSH_URL    = "https://api.line.me/v2/bot/message/push"
_LINE_INFO_URL    = "https://api.line.me/v2/bot/info"
_LINE_PROFILE_URL = "https://api.line.me/v2/bot/profile/{userId}"
_LINE_GROUP_MEMBER_URL = "https://api.line.me/v2/bot/group/{groupId}/member/{userId}"


# ── 金鑰讀取 ──────────────────────────────────────────────────────
def _get_secret(key: str) -> str:
    """
    優先讀取環境變數；若不存在，嘗試 st.secrets（Streamlit 環境）。
    適用於 Render.com（環境變數）及 Streamlit Cloud（secrets.toml）兩種部署。
    """
    val = os.environ.get(key, "").strip()
    if not val:
        try:
            import streamlit as st
            val = (st.secrets.get(key) or "").strip()
        except Exception:
            pass
    return val


def get_channel_secret() -> str:
    return _get_secret("LINE_CHANNEL_SECRET")


def get_channel_access_token() -> str:
    return _get_secret("LINE_CHANNEL_ACCESS_TOKEN")


def get_commander_user_id() -> str:
    """
    總指揮的個人 Line userId（U 開頭，32 碼）。
    用於每日 17:00 / 19:00 戰報私訊推送。
    在 .streamlit/secrets.toml 設定：LINE_COMMANDER_USER_ID = "Uxxxxxxxxx"
    取得方式：在 Bot 與指揮官的對話中，webhook 事件 source.userId 即為此 ID。
    """
    return _get_secret("LINE_COMMANDER_USER_ID")


def get_group_store_map() -> dict[str, str]:
    """
    解析 LINE_GROUP_STORE_MAP（JSON 字串）。
    格式：{"<groupId>": "<門店名稱>", ...}
    Line groupId 格式為 'C' 開頭的 32 碼字串。
    """
    raw = _get_secret("LINE_GROUP_STORE_MAP")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {k: str(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, AttributeError):
        logger.warning("LINE_GROUP_STORE_MAP 格式錯誤，應為合法 JSON 字串")
        return {}


# ── 簽名驗證 ──────────────────────────────────────────────────────
def verify_signature(body: bytes, x_line_signature: str,
                     channel_secret: str) -> bool:
    """
    驗證 Line Webhook 請求的 HMAC-SHA256 簽名。

    Line 簽名計算規則：
        hash  = HMAC-SHA256(channel_secret, raw_request_body)
        sig   = base64(hash)

    Args:
        body:               原始 HTTP 請求 body（bytes）
        x_line_signature:   Header X-Line-Signature 的值
        channel_secret:     Channel Secret

    Returns:
        True 若簽名合法，否則 False
    """
    if not channel_secret or not x_line_signature:
        return False
    digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    # 使用 compare_digest 防止時序攻擊
    return hmac.compare_digest(expected, x_line_signature)


# ── Line Messaging API 請求 ───────────────────────────────────────
def _line_post(url: str, payload: dict) -> tuple[int, dict]:
    """
    送出 Line Messaging API POST 請求。
    回傳 (status_code, response_json)。
    """
    import requests
    token = get_channel_access_token()
    if not token:
        return 0, {"error": "LINE_CHANNEL_ACCESS_TOKEN 未設定"}
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=10,
        )
        try:
            rj = resp.json()
        except Exception:
            rj = {"raw": resp.text}
        return resp.status_code, rj
    except requests.RequestException as e:
        logger.error(f"Line API request failed: {e}")
        return 0, {"error": str(e)}


def send_reply(reply_token: str, text: str) -> bool:
    """
    使用 reply API 回覆訊息。
    reply_token 由 webhook 事件取得，30 秒內有效且只能使用一次。
    """
    if not reply_token:
        return False
    code, _ = _line_post(_LINE_REPLY_URL, {
        "replyToken": reply_token,
        "messages":   [{"type": "text", "text": text[:2000]}],
    })
    return code == 200


def push_message(to: str, text: str) -> bool:
    """
    使用 push API 主動推播訊息至用戶或群組。
    to: Line userId（U 開頭）或 groupId（C 開頭）
    """
    if not to:
        return False
    code, resp = _line_post(_LINE_PUSH_URL, {
        "to":       to,
        "messages": [{"type": "text", "text": text[:2000]}],
    })
    if code != 200:
        logger.warning(f"push_message failed to={to[:8]}... status={code} resp={resp}")
    return code == 200


def get_user_display_name(user_id: str, group_id: str = "") -> str:
    """
    呼叫 LINE API 取得用戶的真實顯示名稱（displayName）。
    優先用群組成員 API（較精確），fallback 到個人 profile API。
    失敗時回傳空字串（由呼叫端決定 fallback）。

    Args:
        user_id:  LINE userId（U 開頭）
        group_id: 所在群組 ID（C 開頭，可空）
    Returns:
        displayName 字串，失敗回傳 ""
    """
    import requests
    token = get_channel_access_token()
    if not token or not user_id:
        return ""
    headers = {"Authorization": f"Bearer {token}"}

    # 優先：群組成員 API
    if group_id:
        try:
            url  = _LINE_GROUP_MEMBER_URL.format(groupId=group_id, userId=user_id)
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("displayName", "")
        except Exception:
            pass

    # Fallback：個人 profile API
    try:
        url  = _LINE_PROFILE_URL.format(userId=user_id)
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("displayName", "")
    except Exception:
        pass

    return ""


def push_battle_report(group_id: str, report_text: str) -> bool:
    """
    推播戰報文字至指定 Line 群組。
    group_id: 群組 ID（C 開頭）
    """
    if not group_id:
        logger.warning("push_battle_report: group_id 未設定")
        return False
    return push_message(group_id, report_text)


def push_with_quick_reply(to: str, text: str, event_id: int) -> bool:
    """推播帶 Quick Reply 按鈕的訊息（核准/結案）"""
    if not to:
        return False
    code, _ = _line_post(_LINE_PUSH_URL, {
        "to": to,
        "messages": [{
            "type": "text",
            "text": text[:2000],
            "quickReply": {
                "items": [
                    {
                        "type": "action",
                        "action": {
                            "type": "postback",
                            "label": "✅ 核准",
                            "data": f"approve:{event_id}",
                            "displayText": "✅ 核准",
                        },
                    },
                    {
                        "type": "action",
                        "action": {
                            "type": "postback",
                            "label": "❌ 結案",
                            "data": f"close:{event_id}",
                            "displayText": "❌ 結案",
                        },
                    },
                    {
                        "type": "action",
                        "action": {
                            "type": "message",
                            "label": "📋 查看",
                            "text": f"查看 #{event_id}",
                        },
                    },
                ]
            },
        }]
    })
    return code == 200


def push_event_flex(to: str, event: dict, liff_base_url: str = "") -> bool:
    """
    推播 Flex Message 決策卡片（v2：新按鈕設計）
    按鈕：[📝 AI起草回覆] [👀 列入觀察] [🔕 略過] + 第二列 [🔁 轉派] [📱 LIFF（可選）]
    """
    if not to:
        return False
    event_id   = event.get("id", 0)
    level      = event.get("level", "blue")
    store      = event.get("store", "")
    content    = event.get("content", "")[:60]
    user       = event.get("user_alias", "") or event.get("user", "")
    cat        = event.get("keyword_cat", "")
    confidence = event.get("confidence", None)   # 0.0~1.0，可選

    color_map = {"red": "#E74C3C", "yellow": "#F39C12", "blue": "#3498DB"}
    color     = color_map.get(level, "#3498DB")
    emoji_map = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}
    emoji     = emoji_map.get(level, "🔵")

    # 信心度文字（若有）
    conf_text = ""
    if confidence is not None:
        pct = int(confidence * 100)
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        conf_text = f"信心度：{bar} {pct}%"

    # ── 第一列按鈕：AI起草 / 觀察 / 略過 ─────────────────────────
    row1 = [
        {
            "type": "button",
            "action": {
                "type":        "postback",
                "label":       "📝 AI起草",
                "data":        f"draft:{event_id}",
                "displayText": f"📝 AI起草回覆 #{event_id}",
            },
            "style": "primary",
            "color": "#2471A3",
            "height": "sm",
            "flex": 2,
        },
        {
            "type": "button",
            "action": {
                "type":        "postback",
                "label":       "👀 觀察",
                "data":        f"observe:{event_id}",
                "displayText": f"👀 列入觀察 #{event_id}",
            },
            "style": "secondary",
            "height": "sm",
            "flex": 1,
        },
        {
            "type": "button",
            "action": {
                "type":        "postback",
                "label":       "🔕 略過",
                "data":        f"dismiss:{event_id}",
                "displayText": f"🔕 略過 #{event_id}",
            },
            "style": "secondary",
            "height": "sm",
            "flex": 1,
        },
    ]

    # ── 第二列按鈕：轉派 + LIFF（可選）──────────────────────────
    row2 = [
        {
            "type": "button",
            "action": {
                "type":        "postback",
                "label":       "🔁 轉派他人",
                "data":        f"delegate:{event_id}",
                "displayText": f"🔁 轉派 #{event_id}",
            },
            "style": "secondary",
            "height": "sm",
            "flex": 1,
        },
    ]
    if liff_base_url:
        liff_url = f"{liff_base_url}?event_id={event_id}"
        row2.append({
            "type": "button",
            "action": {"type": "uri", "label": "📱 詳細介面", "uri": liff_url},
            "style": "secondary",
            "height": "sm",
            "flex": 1,
        })

    # ── body contents ─────────────────────────────────────────────
    body_contents: list[dict] = [
        {
            "type":  "text",
            "text":  content or "（無內容）",
            "wrap":  True,
            "size":  "md",
            "color": "#333333",
        },
        {"type": "separator", "margin": "md"},
        {
            "type":   "text",
            "text":   f"類別：{cat}",
            "size":   "xs",
            "color":  "#888888",
            "margin": "md",
        },
    ]
    if conf_text:
        body_contents.append({
            "type":   "text",
            "text":   conf_text,
            "size":   "xs",
            "color":  "#AAAAAA",
            "margin": "xs",
        })

    flex_msg = {
        "type":    "flex",
        "altText": f"{emoji} 事件 #{event_id}｜{store}｜{content[:30]}",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type":            "box",
                "layout":          "vertical",
                "backgroundColor": color,
                "paddingAll":      "16px",
                "contents": [
                    {
                        "type":   "text",
                        "text":   f"{emoji} 事件 #{event_id}",
                        "color":  "#FFFFFF",
                        "weight": "bold",
                        "size":   "lg",
                    },
                    {
                        "type":   "text",
                        "text":   f"📍 {store}  👤 {user}",
                        "color":  "#FFFFFFCC",
                        "size":   "xs",
                        "margin": "xs",
                    },
                ],
            },
            "body": {
                "type":       "box",
                "layout":     "vertical",
                "paddingAll": "16px",
                "contents":   body_contents,
            },
            "footer": {
                "type":       "box",
                "layout":     "vertical",
                "spacing":    "sm",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type":     "box",
                        "layout":   "horizontal",
                        "spacing":  "sm",
                        "contents": row1,
                    },
                    {
                        "type":     "box",
                        "layout":   "horizontal",
                        "spacing":  "sm",
                        "contents": row2,
                    },
                ],
            },
        },
    }

    code, resp = _line_post(_LINE_PUSH_URL, {
        "to":       to,
        "messages": [flex_msg],
    })
    if code != 200:
        logger.warning(f"push_event_flex failed: {resp}")
    return code == 200


def push_resolution_flex(to: str, event: dict, confirm_user: str = "",
                         confirm_text: str = "") -> bool:
    """
    推播「建議結案」Flex 卡片給 Commander。
    當現場回報「搞定」「修好了」等確認語意時觸發，Commander 確認後才正式結案。
    按鈕：[✅ 確認結案] [👀 繼續觀察]
    """
    if not to:
        return False
    event_id = event.get("id", 0)
    store    = event.get("store", "")
    content  = event.get("content", "")[:60]
    level    = event.get("level", "blue")

    emoji_map = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}
    emoji     = emoji_map.get(level, "🔵")

    body_text = confirm_text[:80] if confirm_text else "現場回報已處理完畢"
    sub_text  = f"回報者：{confirm_user}" if confirm_user else ""

    body_contents: list[dict] = [
        {
            "type":  "text",
            "text":  f"原事件：{content}",
            "wrap":  True,
            "size":  "sm",
            "color": "#555555",
        },
        {"type": "separator", "margin": "sm"},
        {
            "type":   "text",
            "text":   f"📩 現場回覆：{body_text}",
            "wrap":   True,
            "size":   "md",
            "color":  "#27AE60",
            "margin": "sm",
            "weight": "bold",
        },
    ]
    if sub_text:
        body_contents.append({
            "type":   "text",
            "text":   sub_text,
            "size":   "xs",
            "color":  "#AAAAAA",
            "margin": "xs",
        })

    flex_msg = {
        "type":    "flex",
        "altText": f"💡 建議結案 #{event_id}｜{store}｜{body_text[:30]}",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type":            "box",
                "layout":          "vertical",
                "backgroundColor": "#27AE60",
                "paddingAll":      "14px",
                "contents": [
                    {
                        "type":   "text",
                        "text":   f"💡 建議結案",
                        "color":  "#FFFFFF",
                        "weight": "bold",
                        "size":   "lg",
                    },
                    {
                        "type":   "text",
                        "text":   f"{emoji} 事件 #{event_id}  📍 {store}",
                        "color":  "#FFFFFFCC",
                        "size":   "xs",
                        "margin": "xs",
                    },
                ],
            },
            "body": {
                "type":       "box",
                "layout":     "vertical",
                "paddingAll": "16px",
                "contents":   body_contents,
            },
            "footer": {
                "type":       "box",
                "layout":     "horizontal",
                "spacing":    "sm",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type":        "postback",
                            "label":       "✅ 確認結案",
                            "data":        f"close_confirm:{event_id}",
                            "displayText": f"✅ 確認結案 #{event_id}",
                        },
                        "style": "primary",
                        "color": "#27AE60",
                        "flex":  1,
                    },
                    {
                        "type": "button",
                        "action": {
                            "type":        "postback",
                            "label":       "👀 繼續觀察",
                            "data":        f"keep_observe:{event_id}",
                            "displayText": f"👀 繼續觀察 #{event_id}",
                        },
                        "style": "secondary",
                        "flex":  1,
                    },
                ],
            },
        },
    }

    code, resp = _line_post(_LINE_PUSH_URL, {
        "to":       to,
        "messages": [flex_msg],
    })
    if code != 200:
        logger.warning(f"push_resolution_flex failed: {resp}")
    return code == 200


# ── Bot 資訊查詢 ──────────────────────────────────────────────────
def check_connection() -> dict:
    """
    呼叫 Line GET /v2/bot/info 驗證連線狀態與 Bot 資訊。

    回傳 dict：
      ok (bool)          : 連線是否成功
      bot_name (str)     : Bot 顯示名稱
      bot_id   (str)     : Bot userId
      reason   (str)     : 失敗原因（僅 ok=False 時）
    """
    import requests
    token = get_channel_access_token()
    if not token:
        return {"ok": False, "reason": "LINE_CHANNEL_ACCESS_TOKEN 未設定"}

    secret = get_channel_secret()
    if not secret:
        return {"ok": False, "reason": "LINE_CHANNEL_SECRET 未設定"}

    try:
        resp = requests.get(
            _LINE_INFO_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "ok":       True,
                "bot_name": data.get("displayName", "（未取得）"),
                "bot_id":   data.get("userId", ""),
            }
        return {
            "ok":     False,
            "reason": f"HTTP {resp.status_code}",
            "detail": resp.text[:200],
        }
    except requests.RequestException as e:
        return {"ok": False, "reason": f"網路錯誤：{e}"}
