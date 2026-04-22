"""
utils/edge_store.py
Edge Agent 數據存儲層 — SQLite 後台 (v3.0)

Streamlit Cloud 使用 /tmp 路徑（重啟後清空，適合 Demo）。
本地開發可設定環境變數 EDGE_DB_PATH 指向永久路徑。

資料表：
  events          — 事件主表（v3 新增 image_url / auto_closed_at / close_note）
  decision_logs   — 每次核准決策的記錄
  manager_weights — 主管責任偏好權重（3+ 次自動升為預設）
  webhook_cache   — Line Webhook 原始訊息暫存
  archive_events  — 超過 30 天事件歸檔表（v3 新增）
"""
from __future__ import annotations
import sqlite3, os
from datetime import datetime, timedelta
from typing import Optional

# ── 資料庫路徑 ────────────────────────────────────────────────────
_DB_PATH = os.environ.get("EDGE_DB_PATH", "/tmp/edge_agent.db")


# ── 連線工廠 ──────────────────────────────────────────────────────
def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


# ── 建立資料表 ────────────────────────────────────────────────────
def init_db() -> None:
    with _conn() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            level             TEXT    NOT NULL,
            store             TEXT    NOT NULL,
            user_alias        TEXT    NOT NULL,
            content           TEXT    NOT NULL,
            created_at        TEXT    NOT NULL,
            status            TEXT    DEFAULT 'pending',
            assigned_to       TEXT,
            response_deadline TEXT,
            monitoring_until  TEXT,
            group_key         TEXT,
            keyword_cat       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS decision_logs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            ts             TEXT    NOT NULL,
            event_id       INTEGER,
            level          TEXT,
            store          TEXT,
            assigned_to    TEXT    NOT NULL,
            draft_modified INTEGER DEFAULT 0,
            keyword_cat    TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS manager_weights (
            manager    TEXT    NOT NULL,
            category   TEXT    NOT NULL,
            cnt        INTEGER DEFAULT 1,
            is_default INTEGER DEFAULT 0,
            updated_at TEXT    NOT NULL,
            PRIMARY KEY (manager, category)
        );

        CREATE TABLE IF NOT EXISTS webhook_cache (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_text     TEXT    NOT NULL,
            line_user_id TEXT    DEFAULT '',
            group_id     TEXT    DEFAULT '',
            received_at  TEXT    NOT NULL,
            processed    INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS archive_events (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            orig_id        INTEGER,
            level          TEXT,
            store          TEXT,
            user_alias     TEXT,
            content        TEXT,
            created_at     TEXT,
            status         TEXT,
            assigned_to    TEXT,
            keyword_cat    TEXT    DEFAULT '',
            image_url      TEXT    DEFAULT '',
            auto_closed_at TEXT,
            close_note     TEXT    DEFAULT '',
            archived_at    TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS line_groups (
            group_id    TEXT    PRIMARY KEY,
            store_name  TEXT    NOT NULL,
            bot_name    TEXT    DEFAULT '',
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key        TEXT    PRIMARY KEY,
            value      TEXT    NOT NULL,
            updated_at TEXT    NOT NULL
        );
        """)
    # v3/v4 欄位 Migration（idempotent）
    _migrate_v3()


def _migrate_v3() -> None:
    """v3/v4 新增欄位（idempotent）：image_url / auto_closed_at / close_note / group_id"""
    new_cols = [
        ("image_url",      "TEXT DEFAULT ''"),
        ("auto_closed_at", "TEXT"),
        ("close_note",     "TEXT DEFAULT ''"),
        ("group_id",       "TEXT DEFAULT ''"),   # v4：追蹤來源 Line 群組 ID，支援逆向回傳
    ]
    with _conn() as db:
        existing = {row[1] for row in db.execute("PRAGMA table_info(events)").fetchall()}
        for col_name, col_def in new_cols:
            if col_name not in existing:
                try:
                    db.execute(f"ALTER TABLE events ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass  # 已存在時 SQLite 不支援 IF NOT EXISTS，吞掉即可


# ── 型別轉換工具 ──────────────────────────────────────────────────
def _iso(dt) -> Optional[str]:
    return dt.isoformat() if isinstance(dt, datetime) else dt


def _dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _evt_to_row(evt: dict) -> dict:
    """dict（含 datetime）→ SQLite-ready dict"""
    row = dict(evt)
    row["created_at"]        = _iso(row.get("created_at")) or datetime.now().isoformat()
    row["response_deadline"] = _iso(row.get("response_deadline"))
    row["monitoring_until"]  = _iso(row.get("monitoring_until"))
    row["user_alias"]        = row.get("user_alias") or row.get("user", "未知")
    return row


def _evt_from_row(row: dict) -> dict:
    """SQLite row → dict（datetime 物件）"""
    evt = dict(row)
    evt["created_at"]        = _dt(evt.get("created_at")) or datetime.now()
    evt["response_deadline"] = _dt(evt.get("response_deadline"))
    evt["monitoring_until"]  = _dt(evt.get("monitoring_until"))
    # backward-compat：其他模組用 item["user"]
    evt["user"] = evt.get("user_alias", "")
    # v3 欄位保持原始字串或 None（頁面端自行解析）
    return evt


# ── 事件 CRUD ─────────────────────────────────────────────────────
def load_events(limit: int = 300) -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_evt_from_row(dict(r)) for r in rows]


def count_events() -> int:
    with _conn() as db:
        return db.execute("SELECT COUNT(*) FROM events").fetchone()[0]


def save_event(evt: dict) -> int:
    """儲存一筆事件，回傳新 ID。v4 新增 group_id 欄位支援逆向回傳。"""
    row = _evt_to_row(evt)
    with _conn() as db:
        cur = db.execute(
            """INSERT INTO events
               (level, store, user_alias, content, created_at, status,
                assigned_to, response_deadline, monitoring_until,
                group_key, keyword_cat, group_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row["level"], row["store"], row["user_alias"], row["content"],
             row["created_at"], row.get("status", "pending"),
             row.get("assigned_to"), row.get("response_deadline"),
             row.get("monitoring_until"), row.get("group_key", ""),
             row.get("keyword_cat", ""), row.get("group_id", ""))
        )
        return cur.lastrowid


def update_event(event_id: int, **kwargs) -> None:
    """動態更新事件欄位，支援 datetime 自動轉 ISO 字串"""
    if not kwargs:
        return
    sanitized = {k: (_iso(v) if isinstance(v, datetime) else v) for k, v in kwargs.items()}
    sets = ", ".join(f"{k}=?" for k in sanitized)
    vals = list(sanitized.values()) + [event_id]
    with _conn() as db:
        db.execute(f"UPDATE events SET {sets} WHERE id=?", vals)


def auto_close_expired() -> int:
    """24H 觀察期到期的 monitoring 事件自動結案，回傳關閉筆數"""
    now_str = datetime.now().isoformat()
    with _conn() as db:
        cur = db.execute(
            """UPDATE events SET status='closed'
               WHERE status='monitoring'
               AND monitoring_until IS NOT NULL
               AND monitoring_until <= ?""",
            (now_str,)
        )
        return cur.rowcount


# ── v3：智能結案監聽器 ────────────────────────────────────────────
def auto_close_by_silence(silence_minutes: int = 5) -> int:
    """
    掃描 pending 的藍色事件，若建立時間 > silence_minutes 分鐘前
    且仍為 pending，視為「靜默期滿」自動結案。
    回傳自動結案筆數。
    """
    cutoff  = (datetime.now() - timedelta(minutes=silence_minutes)).isoformat()
    now_str = datetime.now().isoformat()
    with _conn() as db:
        cur = db.execute(
            """UPDATE events
               SET status='closed', auto_closed_at=?, close_note='AI 靜默期自動結案'
               WHERE level='blue' AND status='pending' AND created_at <= ?""",
            (now_str, cutoff)
        )
        return cur.rowcount


def auto_close_confirmation_for_store(store: str) -> int:
    """
    當收到確認語意訊息時，自動結案該門店最近一筆 monitoring 事件。
    回傳關閉筆數（0 或 1）。
    """
    now_str = datetime.now().isoformat()
    with _conn() as db:
        row = db.execute(
            """SELECT id FROM events
               WHERE store=? AND status='monitoring'
               ORDER BY created_at DESC LIMIT 1""",
            (store,)
        ).fetchone()
        if row:
            db.execute(
                """UPDATE events
                   SET status='closed', auto_closed_at=?, close_note='確認語意自動結案'
                   WHERE id=?""",
                (now_str, row["id"])
            )
            return 1
    return 0


# ── v3：多模態辨識接口預留 ────────────────────────────────────────
def analyze_completion_photo(image_url: str, event_context: dict) -> dict:
    """
    完工照片多模態辨識接口（預留）。
    目前回傳佔位結果；未來可接入 Claude Vision / Google Vision API。

    Args:
        image_url:      完工照片 URL
        event_context:  事件 dict（含 id, level, store, content）

    Returns:
        dict with keys: analyzed, reason, image_url, event_id
    """
    return {
        "analyzed":  False,
        "reason":    "多模態辨識接口預留，尚未啟用（Vision API 整合規劃中）",
        "image_url": image_url,
        "event_id":  event_context.get("id"),
    }


# ── v3：數據清理 ──────────────────────────────────────────────────
def auto_archive_old_events(days: int = 30) -> int:
    """
    將超過 N 天的已結案 / 觀察中事件搬移至 archive_events 資料表。
    回傳搬移筆數。
    """
    cutoff      = (datetime.now() - timedelta(days=days)).isoformat()
    archived_at = datetime.now().isoformat()

    with _conn() as db:
        rows = db.execute(
            """SELECT * FROM events
               WHERE status IN ('closed', 'monitoring') AND created_at <= ?""",
            (cutoff,)
        ).fetchall()

        if not rows:
            return 0

        for r in rows:
            r = dict(r)
            db.execute(
                """INSERT INTO archive_events
                   (orig_id, level, store, user_alias, content, created_at,
                    status, assigned_to, keyword_cat, image_url,
                    auto_closed_at, close_note, archived_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    r["id"], r["level"], r["store"], r["user_alias"],
                    r["content"], r["created_at"], r["status"],
                    r.get("assigned_to"), r.get("keyword_cat", ""),
                    r.get("image_url", ""), r.get("auto_closed_at"),
                    r.get("close_note", ""), archived_at,
                )
            )

        ids = [dict(r)["id"] for r in rows]
        placeholders = ",".join("?" * len(ids))
        db.execute(f"DELETE FROM events WHERE id IN ({placeholders})", ids)

        return len(ids)


def cleanup_old_webhooks(days: int = 7) -> int:
    """刪除超過 N 天的已處理 Webhook 緩存，回傳刪除筆數"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with _conn() as db:
        cur = db.execute(
            "DELETE FROM webhook_cache WHERE processed=1 AND received_at <= ?",
            (cutoff,)
        )
        return cur.rowcount


# ── 事件合併（5 分鐘內同門店同用戶）──────────────────────────────
def find_merge_candidate(store: str, user_alias: str, level: str,
                          window_minutes: int = 5) -> Optional[int]:
    """在時間窗口內找可合併的 pending 事件 ID，無則回傳 None"""
    cutoff = (datetime.now() - timedelta(minutes=window_minutes)).isoformat()
    with _conn() as db:
        row = db.execute(
            """SELECT id FROM events
               WHERE store=? AND user_alias=? AND level=?
               AND status='pending' AND created_at >= ?
               ORDER BY created_at DESC LIMIT 1""",
            (store, user_alias, level, cutoff)
        ).fetchone()
    return row["id"] if row else None


def merge_event_content(event_id: int, extra_content: str) -> None:
    """在現有事件內容後追加新訊息（用 ／ 分隔）"""
    with _conn() as db:
        row = db.execute("SELECT content FROM events WHERE id=?", (event_id,)).fetchone()
        if row:
            merged = row["content"] + " ／ " + extra_content
            db.execute("UPDATE events SET content=? WHERE id=?", (merged, event_id))


# ── Webhook 緩存 ──────────────────────────────────────────────────
def cache_webhook(raw_text: str, line_user_id: str = "", group_id: str = "") -> int:
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO webhook_cache (raw_text, line_user_id, group_id, received_at) VALUES (?,?,?,?)",
            (raw_text, line_user_id, group_id, datetime.now().isoformat())
        )
        return cur.lastrowid


def mark_webhook_processed(wh_id: int) -> None:
    with _conn() as db:
        db.execute("UPDATE webhook_cache SET processed=1 WHERE id=?", (wh_id,))


def get_unprocessed_webhooks() -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM webhook_cache WHERE processed=0 ORDER BY received_at"
        ).fetchall()
    return [dict(r) for r in rows]


# ── 決策日誌 & 責任地圖學習 ──────────────────────────────────────
def log_decision(event_id: int, level: str, store: str,
                  assigned_to: str, draft_modified: bool,
                  keyword_cat: str = "") -> None:
    """記錄決策，並更新主管偏好權重（≥3 次自動設為預設）"""
    now  = datetime.now().isoformat()
    cat  = keyword_cat or level
    with _conn() as db:
        db.execute(
            """INSERT INTO decision_logs
               (ts, event_id, level, store, assigned_to, draft_modified, keyword_cat)
               VALUES (?,?,?,?,?,?,?)""",
            (now, event_id, level, store, assigned_to, int(draft_modified), cat)
        )
        db.execute(
            """INSERT INTO manager_weights (manager, category, cnt, is_default, updated_at)
               VALUES (?, ?, 1, 0, ?)
               ON CONFLICT(manager, category)
               DO UPDATE SET cnt=cnt+1, updated_at=excluded.updated_at""",
            (assigned_to, cat, now)
        )
        db.execute(
            """UPDATE manager_weights SET is_default=1
               WHERE manager=? AND category=? AND cnt >= 3""",
            (assigned_to, cat)
        )


def get_recommended_manager(level: str, keyword_cat: str = "") -> Optional[str]:
    """
    回傳此類別的建議負責人。
    優先順序：
      1. 該 keyword_cat 下被標記 is_default=1 的主管
      2. 該 level 下 cnt 最高的主管
    """
    cat = keyword_cat or level
    with _conn() as db:
        row = db.execute(
            """SELECT manager FROM manager_weights
               WHERE category=? AND is_default=1
               ORDER BY cnt DESC LIMIT 1""",
            (cat,)
        ).fetchone()
        if row:
            return row["manager"]
        row = db.execute(
            """SELECT manager FROM manager_weights
               WHERE category LIKE ? ORDER BY cnt DESC LIMIT 1""",
            (f"{level}%",)
        ).fetchone()
        if row:
            return row["manager"]
    return None


def load_decision_logs(limit: int = 100) -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM decision_logs ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_manager_stats() -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM manager_weights ORDER BY cnt DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── 戰報輔助：重複報修 & 逾時紅標 ───────────────────────────────
def get_repeat_repairs_24h() -> list[dict]:
    """過去 24H 內，同店出現 2 次以上紅色事件的店列表"""
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    with _conn() as db:
        rows = db.execute(
            """SELECT store, COUNT(*) AS cnt FROM events
               WHERE level='red' AND created_at >= ?
               GROUP BY store HAVING cnt >= 2
               ORDER BY cnt DESC""",
            (cutoff,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_overdue_red_events(hours: int = 4) -> list[dict]:
    """超過 N 小時仍 pending 的紅色事件"""
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    with _conn() as db:
        rows = db.execute(
            """SELECT * FROM events WHERE level='red' AND status='pending'
               AND created_at <= ? ORDER BY created_at""",
            (cutoff,)
        ).fetchall()
    return [_evt_from_row(dict(r)) for r in rows]


# ── Line 群組→門店 對應表 ─────────────────────────────────────────
def upsert_line_group(group_id: str, store_name: str,
                       bot_name: str = "") -> None:
    """
    新增或更新 Line 群組→門店對應。
    支援從 Streamlit UI 或 Webhook 事件觸發更新。
    """
    now = datetime.now().isoformat()
    with _conn() as db:
        db.execute(
            """INSERT INTO line_groups (group_id, store_name, bot_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(group_id)
               DO UPDATE SET store_name=excluded.store_name,
                             bot_name=excluded.bot_name,
                             updated_at=excluded.updated_at""",
            (group_id, store_name, bot_name, now, now)
        )


def get_store_for_group(group_id: str) -> Optional[str]:
    """
    從 line_groups 資料表查詢群組對應的門店名稱。
    優先順序：DB 記錄 > LINE_GROUP_STORE_MAP 環境變數（由呼叫方處理）
    """
    if not group_id:
        return None
    with _conn() as db:
        row = db.execute(
            "SELECT store_name FROM line_groups WHERE group_id=?",
            (group_id,)
        ).fetchone()
    return row["store_name"] if row else None


def load_line_groups() -> list[dict]:
    """回傳所有 Line 群組對應設定"""
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM line_groups ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_line_group(group_id: str) -> None:
    """刪除指定群組對應"""
    with _conn() as db:
        db.execute("DELETE FROM line_groups WHERE group_id=?", (group_id,))


def get_unrecognized_groups() -> list[dict]:
    """
    回傳 webhook_cache 中有訊息、但尚未在 line_groups 中綁定門店的群組。
    用於「未辨識群組快速綁定」UI。
    回傳欄位：group_id, msg_count, last_seen
    """
    with _conn() as db:
        rows = db.execute(
            """SELECT group_id,
                      COUNT(*)          AS msg_count,
                      MAX(received_at)  AS last_seen
               FROM webhook_cache
               WHERE group_id != ''
               AND group_id NOT IN (SELECT group_id FROM line_groups)
               GROUP BY group_id
               ORDER BY last_seen DESC""",
        ).fetchall()
    return [dict(r) for r in rows]


# ── Settings（系統設定 / 推播去重）────────────────────────────────
def get_setting(key: str) -> Optional[str]:
    """取得系統設定值，不存在則回傳 None"""
    with _conn() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    """儲存系統設定值（UPSERT）"""
    now = datetime.now().isoformat()
    with _conn() as db:
        db.execute(
            """INSERT INTO settings (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key)
               DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, now)
        )
