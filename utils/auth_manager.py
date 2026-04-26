"""utils/auth_manager.py — 帳號生命週期管理 v1.0"""
from __future__ import annotations
import hashlib, json, logging
from datetime import datetime
from typing import Optional
from utils import edge_store

logger = logging.getLogger("kerou.auth_manager")

ROLES = {"admin": "系統管理員", "manager": "部門主管", "staff": "一般員工"}
ALL_PAGES = ["數據戰情中心","專案追蹤師","決策AI偵察","品牌數位資產",
             "系統設定","Line邊緣代理人","帳號管理","IT維護人員"]
ROLE_DEFAULT_PAGES = {
    "admin":   ALL_PAGES,
    "manager": ["數據戰情中心","專案追蹤師","決策AI偵察","品牌數位資產"],
    "staff":   ["數據戰情中心","品牌數位資產"],
}

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# ── 登入驗證 ──────────────────────────────────────────────────────

def authenticate(username: str, password: str, ip: str = "") -> Optional[dict]:
    with edge_store._conn() as db:
        row = db.execute(
            "SELECT * FROM accounts WHERE username=? AND status='active'", (username,)
        ).fetchone()
    if not row:
        _log(username, False, ip, "帳號不存在或已停用")
        return None
    if row["password_hash"] != _hash(password):
        _log(username, False, ip, "密碼錯誤")
        return None
    now = datetime.now().isoformat()
    with edge_store._conn() as db:
        db.execute("UPDATE accounts SET last_login=? WHERE username=?", (now, username))
    _log(username, True, ip)
    return dict(row)

def _log(username, success, ip="", reason=""):
    now = datetime.now().isoformat()
    with edge_store._conn() as db:
        db.execute(
            "INSERT INTO login_history (username,success,ip_address,login_at,fail_reason) VALUES (?,?,?,?,?)",
            (username, 1 if success else 0, ip, now, reason)
        )

# ── 帳號 CRUD ─────────────────────────────────────────────────────

def create_account(username: str, password: str, display_name: str,
                   role: str, dept: str = "", allowed_pages: list = None) -> tuple[bool, str]:
    if not username:        return False, "帳號名稱不可為空"
    if len(password) < 4:  return False, "密碼至少需要 4 個字元"
    if role not in ROLES:  return False, f"無效角色：{role}"
    pages = allowed_pages if allowed_pages is not None else ROLE_DEFAULT_PAGES.get(role, [])
    now = datetime.now().isoformat()
    try:
        with edge_store._conn() as db:
            db.execute(
                "INSERT INTO accounts (username,password_hash,display_name,role,dept,allowed_pages,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (username, _hash(password), display_name, role, dept,
                 json.dumps(pages, ensure_ascii=False), "active", now, now)
            )
        return True, f"帳號 {username} 已建立"
    except Exception as e:
        return (False, f"帳號名稱 '{username}' 已存在") if "UNIQUE" in str(e) else (False, str(e))

def list_accounts() -> list[dict]:
    with edge_store._conn() as db:
        rows = db.execute("SELECT * FROM accounts ORDER BY role, username").fetchall()
    return [dict(r) for r in rows]

def get_account(username: str) -> Optional[dict]:
    with edge_store._conn() as db:
        row = db.execute("SELECT * FROM accounts WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None

def disable_account(username: str, by: str = "admin") -> tuple[bool, str]:
    now = datetime.now().isoformat()
    with edge_store._conn() as db:
        cur = db.execute(
            "UPDATE accounts SET status='disabled',disabled_at=?,disabled_by=?,updated_at=? WHERE username=? AND role!='admin'",
            (now, by, now, username)
        )
    return (False, "帳號不存在或 admin 不可停用") if cur.rowcount == 0 else (True, f"{username} 已停用")

def enable_account(username: str) -> tuple[bool, str]:
    now = datetime.now().isoformat()
    with edge_store._conn() as db:
        cur = db.execute(
            "UPDATE accounts SET status='active',disabled_at=NULL,disabled_by=NULL,updated_at=? WHERE username=?",
            (now, username)
        )
    return (False, "帳號不存在") if cur.rowcount == 0 else (True, f"{username} 已啟用")

def change_password(username: str, new_pw: str) -> tuple[bool, str]:
    if len(new_pw) < 4: return False, "密碼至少 4 個字元"
    now = datetime.now().isoformat()
    with edge_store._conn() as db:
        cur = db.execute(
            "UPDATE accounts SET password_hash=?,updated_at=? WHERE username=?",
            (_hash(new_pw), now, username)
        )
    return (False, "帳號不存在") if cur.rowcount == 0 else (True, "密碼已更新")

def update_permissions(username: str, allowed_pages: list) -> tuple[bool, str]:
    now = datetime.now().isoformat()
    with edge_store._conn() as db:
        db.execute(
            "UPDATE accounts SET allowed_pages=?,updated_at=? WHERE username=?",
            (json.dumps(allowed_pages, ensure_ascii=False), now, username)
        )
    return True, "權限已更新"

def get_login_history(username: str = None, limit: int = 100) -> list[dict]:
    with edge_store._conn() as db:
        if username:
            rows = db.execute(
                "SELECT * FROM login_history WHERE username=? ORDER BY login_at DESC LIMIT ?",
                (username, limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM login_history ORDER BY login_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]

def get_failed_logins_last_hour() -> list[dict]:
    from datetime import timedelta
    hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    with edge_store._conn() as db:
        rows = db.execute(
            "SELECT username, COUNT(*) as cnt FROM login_history WHERE success=0 AND login_at>? GROUP BY username HAVING cnt>=3",
            (hour_ago,)
        ).fetchall()
    return [dict(r) for r in rows]
