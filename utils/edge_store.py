"""
utils/edge_store.py
Edge Agent 數據存儲層 — SQLite 後台 (v2.0)

Streamlit Cloud 使用 /tmp 路徑（重啟後清空，適合 Demo）。
本地開發可設定環境變數 EDGE_DB_PATH 指向永久路徑。

資料表：
  events          — 事件主表
  decision_logs   — 每次核准決策的記錄
  manager_weights — 主管責任偏好權重（3+ 次自動升為預設）
  webhook_cache   — Line Webhook 原始訊息暫存
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
        """)


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
    """儲存一筆事件，回傳新 ID"""
    row = _evt_to_row(evt)
    with _conn() as db:
        cur = db.execute(
            """INSERT INTO events
               (level, store, user_alias, content, created_at, status,
                assigned_to, response_deadline, monitoring_until, group_key, keyword_cat)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (row["level"], row["store"], row["user_alias"], row["content"],
             row["created_at"], row.get("status", "pending"),
             row.get("assigned_to"), row.get("response_deadline"),
             row.get("monitoring_until"), row.get("group_key", ""),
             row.get("keyword_cat", ""))
        )
        return cur.lastrowid


def update_event(event_id: int, **kwargs) -> None:
    """動態更新事件欄位，支援 datetime 自動轉 ISO 字串"""
    if not kwargs:
        return
    # 轉換 datetime 值
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
        # 寫入決策日誌
        db.execute(
            """INSERT INTO decision_logs
               (ts, event_id, level, store, assigned_to, draft_modified, keyword_cat)
               VALUES (?,?,?,?,?,?,?)""",
            (now, event_id, level, store, assigned_to, int(draft_modified), cat)
        )
        # Upsert 主管權重
        db.execute(
            """INSERT INTO manager_weights (manager, category, cnt, is_default, updated_at)
               VALUES (?, ?, 1, 0, ?)
               ON CONFLICT(manager, category)
               DO UPDATE SET cnt=cnt+1, updated_at=excluded.updated_at""",
            (assigned_to, cat, now)
        )
        # 滿 3 次自動升級為預設建議
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
        # P1: 精確 category 的 default
        row = db.execute(
            """SELECT manager FROM manager_weights
               WHERE category=? AND is_default=1
               ORDER BY cnt DESC LIMIT 1""",
            (cat,)
        ).fetchone()
        if row:
            return row["manager"]
        # P2: 相同 level prefix 最高 cnt
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
