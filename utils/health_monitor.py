"""utils/health_monitor.py — 24小時 IT 維護人員 v1.0"""
from __future__ import annotations
import os, time, logging, requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger("kerou.health_monitor")
TZ = ZoneInfo("Asia/Taipei")

RENDER_API_KEY    = os.environ.get("RENDER_API_KEY", "")
RENDER_SVC_ID     = os.environ.get("RENDER_SERVICE_ID", "srv-d7m2qre7r5hc73fvaetg")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LINE_TOKEN        = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_COMMANDER    = os.environ.get("LINE_COMMANDER_USER_ID", "")

def _now(): return datetime.now(TZ)

# ── 各服務健康檢查 ────────────────────────────────────────────────

def check_render_webhook() -> dict:
    try:
        t = time.time()
        r = requests.get("https://kerou-line-webhook.onrender.com/health", timeout=15)
        ms = int((time.time()-t)*1000)
        return {"service":"Render Webhook","ok":r.status_code==200,"latency_ms":ms,
                "detail":"正常" if r.status_code==200 else f"HTTP {r.status_code}"}
    except Exception as e:
        return {"service":"Render Webhook","ok":False,"latency_ms":0,"detail":str(e)[:80]}

def check_anthropic_api() -> dict:
    if not ANTHROPIC_API_KEY:
        return {"service":"Claude AI","ok":False,"latency_ms":0,"detail":"ANTHROPIC_API_KEY 未設定"}
    try:
        t = time.time()
        r = requests.get("https://api.anthropic.com/v1/models",
                         headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},
                         timeout=10)
        ms = int((time.time()-t)*1000)
        ok = r.status_code == 200
        return {"service":"Claude AI","ok":ok,"latency_ms":ms,
                "detail":"正常" if ok else f"HTTP {r.status_code} — {r.text[:60]}"}
    except Exception as e:
        return {"service":"Claude AI","ok":False,"latency_ms":0,"detail":str(e)[:80]}

def check_line_api() -> dict:
    if not LINE_TOKEN:
        return {"service":"LINE API","ok":False,"latency_ms":0,"detail":"LINE_CHANNEL_ACCESS_TOKEN 未設定"}
    try:
        t = time.time()
        r = requests.get("https://api.line.me/v2/bot/info",
                         headers={"Authorization":f"Bearer {LINE_TOKEN}"}, timeout=10)
        ms = int((time.time()-t)*1000)
        ok = r.status_code == 200
        detail = r.json().get("displayName","正常") if ok else f"HTTP {r.status_code}"
        return {"service":"LINE API","ok":ok,"latency_ms":ms,"detail":detail}
    except Exception as e:
        return {"service":"LINE API","ok":False,"latency_ms":0,"detail":str(e)[:80]}

def check_google_sheets() -> dict:
    try:
        t = time.time()
        from lib.config import get_service_account_info, DRIVE_SCOPES
        from google.oauth2.service_account import Credentials
        import gspread
        creds = Credentials.from_service_account_info(get_service_account_info(), scopes=DRIVE_SCOPES)
        gspread.authorize(creds)
        ms = int((time.time()-t)*1000)
        return {"service":"Google Sheets","ok":True,"latency_ms":ms,"detail":"授權正常"}
    except Exception as e:
        return {"service":"Google Sheets","ok":False,"latency_ms":0,"detail":str(e)[:80]}

def check_streamlit_cloud() -> dict:
    try:
        t = time.time()
        r = requests.get("https://marvintien90-jpg-chewmeat-dashboard-app-pj8awz.streamlit.app/",
                         timeout=20, allow_redirects=True)
        ms = int((time.time()-t)*1000)
        ok = r.status_code < 400
        return {"service":"Streamlit Cloud","ok":ok,"latency_ms":ms,
                "detail":"正常" if ok else f"HTTP {r.status_code}"}
    except Exception as e:
        return {"service":"Streamlit Cloud","ok":False,"latency_ms":0,"detail":str(e)[:80]}

def run_all_checks() -> list[dict]:
    results = []
    for fn in [check_render_webhook, check_anthropic_api, check_line_api,
               check_google_sheets, check_streamlit_cloud]:
        try:
            results.append(fn())
        except Exception as e:
            results.append({"service":fn.__name__,"ok":False,"latency_ms":0,"detail":str(e)})
    return results

# ── 日誌寫入 ──────────────────────────────────────────────────────

def log_results(results: list[dict], auto_repaired: bool = False):
    try:
        from utils import edge_store
        now = _now().isoformat()
        with edge_store._conn() as db:
            for r in results:
                db.execute(
                    "INSERT INTO it_health_log (check_time,service,status,latency_ms,detail,auto_repaired) VALUES (?,?,?,?,?,?)",
                    (now, r["service"], "ok" if r["ok"] else "fail",
                     r.get("latency_ms",0), r.get("detail",""), 1 if auto_repaired else 0)
                )
    except Exception as e:
        logger.warning(f"[health_monitor] log 寫入失敗: {e}")

# ── 自動修復 ──────────────────────────────────────────────────────

def auto_repair(failed: list[dict]) -> list[str]:
    actions = []
    for r in failed:
        svc = r["service"]
        if "Render Webhook" in svc:
            if RENDER_API_KEY:
                try:
                    resp = requests.post(
                        f"https://api.render.com/v1/services/{RENDER_SVC_ID}/deploys",
                        headers={"Authorization":f"Bearer {RENDER_API_KEY}","Content-Type":"application/json"},
                        json={"clearCache":"do_not_clear"}, timeout=15
                    )
                    actions.append(f"✅ Render Webhook：已觸發重新部署 (HTTP {resp.status_code})")
                except Exception as e:
                    actions.append(f"❌ Render Webhook 修復失敗：{str(e)[:40]}")
            else:
                actions.append("⚠️ Render Webhook 離線，缺少 RENDER_API_KEY 無法自動修復")
        elif "Claude AI" in svc:
            actions.append("⚠️ Claude AI 失敗，請確認 ANTHROPIC_API_KEY 是否有效")
        elif "LINE API" in svc:
            actions.append("⚠️ LINE API 失敗，請確認 LINE_CHANNEL_ACCESS_TOKEN 是否有效")
        elif "Google Sheets" in svc:
            actions.append("⚠️ Google Sheets 失敗，請確認 GCP_SERVICE_ACCOUNT_JSON 是否有效")
        elif "Streamlit" in svc:
            actions.append("⚠️ Streamlit Cloud 無回應，請至 share.streamlit.io 確認")
    return actions

# ── LINE 推播 ─────────────────────────────────────────────────────

def push_alert(message: str):
    if not LINE_TOKEN or not LINE_COMMANDER:
        return
    try:
        requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={"Authorization":f"Bearer {LINE_TOKEN}","Content-Type":"application/json"},
            json={"to":LINE_COMMANDER,"messages":[{"type":"text","text":message}]},
            timeout=10
        )
    except Exception as e:
        logger.warning(f"[health_monitor] LINE 推播失敗: {e}")

# ── 資安偵測 ──────────────────────────────────────────────────────

def check_security() -> list[dict]:
    threats = []
    try:
        from utils.auth_manager import get_failed_logins_last_hour
        fails = get_failed_logins_last_hour()
        for f in fails:
            threats.append({"type":"abnormal_login","severity":"high",
                            "detail":f"帳號 {f['username']} 1小時內登入失敗 {f['cnt']} 次"})
    except Exception:
        pass
    # API key 暴露檢查（env var 是否齊全）
    required_keys = ["ANTHROPIC_API_KEY","LINE_CHANNEL_SECRET","LINE_CHANNEL_ACCESS_TOKEN",
                     "GCP_SERVICE_ACCOUNT_JSON"]
    for k in required_keys:
        if not os.environ.get(k, ""):
            threats.append({"type":"missing_key","severity":"high","detail":f"{k} 環境變數缺失"})
    return threats

# ── 排程主函式 ────────────────────────────────────────────────────

def run_health_check_job():
    """每小時執行一次，無論正常與否都推 LINE 狀態摘要"""
    logger.info("[health_monitor] 健康檢查開始...")
    results = run_all_checks()
    failed  = [r for r in results if not r["ok"]]
    repaired = []

    if failed:
        repaired = auto_repair(failed)
        log_results(results, auto_repaired=bool(repaired))
        now_str = _now().strftime("%m/%d %H:%M")
        lines = [f"🚨 【IT 維護警示】{now_str}"]
        for r in failed:
            lines.append(f"❌ {r['service']}：{r['detail']}")
        if repaired:
            lines.append("\n🔧 自動修復：")
            lines.extend(repaired)
        lines.append("\n請至「IT維護人員」頁面查看詳情")
        push_alert("\n".join(lines))
        logger.warning(f"[health_monitor] {len(failed)} 個服務異常")
    else:
        log_results(results)
        # 每小時正常狀態也推播（Q10=B：每小時一次簡短狀態）
        now_str = _now().strftime("%m/%d %H:%M")
        ok_names = " · ".join(r["service"] for r in results if r["ok"])
        push_alert(f"✅ 【IT 每小時狀態】{now_str}\n所有服務正常：{ok_names}")
        logger.info("[health_monitor] 所有服務正常")

    # 資安偵測
    threats = check_security()
    if threats:
        now_str = _now().strftime("%m/%d %H:%M")
        lines = [f"🔐 【資安示警】{now_str}"]
        for t in threats:
            lines.append(f"⚠️ {t['detail']}")
        push_alert("\n".join(lines))

    return results

def get_recent_log(limit: int = 100) -> list[dict]:
    try:
        from utils import edge_store
        with edge_store._conn() as db:
            rows = db.execute(
                "SELECT * FROM it_health_log ORDER BY check_time DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_latest_status() -> dict[str, dict]:
    """取各服務最新一筆健康狀態"""
    logs = get_recent_log(200)
    latest = {}
    for entry in logs:
        svc = entry["service"]
        if svc not in latest:
            latest[svc] = entry
    return latest
