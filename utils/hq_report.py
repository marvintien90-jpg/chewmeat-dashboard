"""
utils/hq_report.py — 嗑肉數位總部每日推播資料聚合器 v1.0
供 line_webhook.py 排程任務呼叫（08:30 早晨 / 20:00 晚間）

資料來源：
  1. Line 邊緣代理人 — edge_store SQLite（永遠可用）
  2. 數據戰情中心   — Google Sheets 公開 CSV（無需認證）
  3. 專案追蹤師     — Google Sheets via gspread（需 GCP_SERVICE_ACCOUNT_JSON）
"""
from __future__ import annotations
import os, io, re, json, logging, requests
from datetime import datetime, timedelta, date
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("kerou.hq_report")
TZ = ZoneInfo("Asia/Taipei")

WEEKDAY_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]

# ── 常數（與 lib/config.py 同步）──────────────────────────────────────────
REVENUE_SHEET_ID = "1NZQEJgL-HkB08JSW6zsVHRSyl_XgwLc5etUqSF0O9ow"
REVENUE_SHEET_GIDS: dict[str, str] = {
    "2025-01": "672482866",  "2025-02": "1943981506", "2025-03": "847955849",
    "2025-04": "591730250",  "2025-05": "695013616",  "2025-06": "897256004",
    "2025-07": "593028448",  "2025-08": "836455215",  "2025-09": "1728608975",
    "2025-10": "2043079442", "2025-11": "1307429413", "2025-12": "1838876978",
    "2026-01": "872131612",  "2026-02": "162899314",  "2026-03": "1575135129",
    "2026-04": "1702412906", "2026-05": "1499115222", "2026-06": "467088033",
}
CLOSED_STORES = {
    "北屯軍福店", "犝犝楠梓店", "高雄大順店", "高雄自由店", "高雄鼎強店", "鳳山文中店",
}


def _now() -> datetime:
    return datetime.now(TZ)


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════════════
# 1. Line 邊緣代理人統計（edge_store SQLite，永遠可用）
# ═══════════════════════════════════════════════════════════════════

def _brief_event(e: dict, max_store: int = 7, max_content: int = 20) -> str:
    """單一事件簡要描述：門店─事件內容"""
    store   = str(e.get("store", "")).strip()[:max_store]
    content = str(e.get("content", "")).strip()[:max_content]
    return f"{store}─{content}"


def collect_edge_stats() -> dict:
    """收集 edge_store 全量統計 + 各類型簡要描述"""
    from utils import edge_store
    today = _today_str()
    evts  = edge_store.load_events(limit=500)

    pending    = [e for e in evts if e.get("status") == "pending"]
    monitoring = [e for e in evts if e.get("status") == "monitoring"]
    red_p      = [e for e in pending if e.get("level") == "red"]
    yellow_p   = [e for e in pending if e.get("level") == "yellow"]
    blue_p     = [e for e in pending if e.get("level") == "blue"]

    today_evts  = [e for e in evts if str(e.get("created_at", ""))[:10] == today]
    closed_today = [e for e in evts
                    if e.get("status") == "closed"
                    and str(e.get("created_at", ""))[:10] == today]

    overdue = edge_store.get_overdue_red_events(hours=2) or []
    repeats = edge_store.get_repeat_repairs_24h() or []

    decisions   = edge_store.load_decision_logs(limit=200) or []
    today_decs  = [d for d in decisions if str(d.get("ts", ""))[:10] == today]
    auto_closed = [e for e in evts
                   if e.get("auto_closed_at")
                   and str(e.get("created_at", ""))[:10] == today]

    return {
        # 待處理清單
        "red_p":    red_p,
        "yellow_p": yellow_p,
        "blue_p":   blue_p,
        "monitoring": monitoring,
        # 今日統計
        "today_new_red":    [e for e in today_evts if e.get("level") == "red"],
        "today_new_yellow": [e for e in today_evts if e.get("level") == "yellow"],
        "today_new_blue":   [e for e in today_evts if e.get("level") == "blue"],
        "closed_today":     closed_today,
        "today_decs":       today_decs,
        "auto_closed_today": auto_closed,
        # 警示
        "overdue": overdue,
        "repeats": repeats,
        # 簡要文字（供訊息插入）
        "red_briefs":    [_brief_event(e) for e in red_p[:3]],
        "yellow_briefs": [_brief_event(e) for e in yellow_p[:2]],
        "overdue_briefs":[_brief_event(e) for e in overdue[:2]],
        "repeat_briefs": [
            f"{r.get('store', '?')}（{r.get('cnt', r.get('count', '?'))}次）"
            for r in repeats[:3]
        ],
    }


# ═══════════════════════════════════════════════════════════════════
# 2. 數據戰情中心（公開 Google Sheets CSV，無需認證）
# ═══════════════════════════════════════════════════════════════════

def _parse_revenue_csv(content: bytes, year_month: str) -> list[dict]:
    """
    解析月份 CSV → [{store, target, revenue, pct}]
    與 data_engine.load_revenue_sheet 邏輯相同，但不依賴 Streamlit。
    """
    import pandas as pd
    year, month = int(year_month[:4]), int(year_month[5:7])
    try:
        raw = pd.read_csv(io.BytesIO(content), header=None)
    except Exception:
        return []

    # 解析日期欄（第2列，從第8欄起）
    date_row = raw.iloc[1, 7:]
    dates = []
    for val in date_row:
        s = str(val).strip()
        if s in ("nan", "合計"):
            continue
        m = re.match(r"(\d+)/(\d+)", s)
        if m:
            mo, d = int(m.group(1)), int(m.group(2))
            if mo == month:
                try:
                    dates.append(date(year, mo, d))
                except ValueError:
                    pass

    if not dates:
        return []

    store_data: dict[str, dict] = {}
    cur_store = cur_target = None

    for i in range(2, len(raw)):
        row = raw.iloc[i]
        if pd.notna(row.iloc[1]) and str(row.iloc[1]).strip():
            cur_store = str(row.iloc[1]).strip()
        if pd.notna(row.iloc[2]) and str(row.iloc[2]).strip():
            t = str(row.iloc[2]).replace(",", "").strip()
            try:
                cur_target = float(t)
            except ValueError:
                pass

        metric = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else ""
        if metric != "業績合計" or not cur_store:
            continue
        if cur_store in CLOSED_STORES:
            continue

        total_rev = 0.0
        for val in row.iloc[7: 7 + len(dates)]:
            s = str(val).strip().replace(",", "").replace(" ", "")
            if s not in ("nan", "", "#DIV/0!", "\\#DIV/0\\!"):
                try:
                    total_rev += float(s)
                except ValueError:
                    pass

        if cur_store not in store_data:
            store_data[cur_store] = {"store": cur_store, "target": cur_target or 0, "revenue": 0.0}
        store_data[cur_store]["revenue"] += total_rev
        if cur_target:
            store_data[cur_store]["target"] = cur_target

    result = []
    for s, d in store_data.items():
        target = d["target"]
        rev    = d["revenue"]
        pct    = (rev / target * 100) if target > 0 else 0.0
        result.append({"store": s, "target": target, "revenue": rev, "pct": pct})

    return result


def collect_revenue_stats() -> dict:
    """從公開 CSV 收集本月各門店達成率，計算排名與預警"""
    now = _now()
    ym  = now.strftime("%Y-%m")
    gid = REVENUE_SHEET_GIDS.get(ym)
    if not gid:
        return {"error": f"無 {ym} 月份 GID 設定"}

    try:
        url  = (f"https://docs.google.com/spreadsheets/d/{REVENUE_SHEET_ID}"
                f"/export?format=csv&gid={gid}")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        stores = _parse_revenue_csv(resp.content, ym)
    except Exception as ex:
        logger.warning(f"[hq_report] revenue fetch error: {ex}")
        return {"error": str(ex)[:60]}

    if not stores:
        return {"error": "解析後無資料（可能尚無本月業績）"}

    active = [s for s in stores if s["pct"] > 0]
    if not active:
        return {"error": "本月尚無業績資料"}

    sorted_stores = sorted(active, key=lambda x: x["pct"], reverse=True)
    top3    = sorted_stores[:3]
    bottom  = [s for s in sorted_stores if s["pct"] < 70]
    avg_pct = sum(s["pct"] for s in active) / len(active)
    total_rev = sum(s["revenue"] for s in active)

    return {
        "ym":           ym,
        "top3":         top3,
        "bottom_stores": bottom[:4],
        "avg_pct":      avg_pct,
        "total_rev":    total_rev,
        "store_count":  len(active),
        "red_count":    len(bottom),
    }


# ═══════════════════════════════════════════════════════════════════
# 3. 專案追蹤師（gspread，需 GCP_SERVICE_ACCOUNT_JSON）
# ═══════════════════════════════════════════════════════════════════

def _get_dept_sheet_ids() -> dict[str, str]:
    """讀取部門 Sheet IDs：config/dept_sheets.json → env DEPT_SHEETS_JSON → 空"""
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, "config", "dept_sheets.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                ids = {k: str(v).strip() for k, v in data.items() if v and str(v).strip()}
                if ids:
                    return ids
        except Exception:
            pass
    # Render env var fallback
    raw = os.environ.get("DEPT_SHEETS_JSON", "")
    if raw:
        try:
            data = json.loads(raw)
            return {k: str(v).strip() for k, v in data.items() if v and str(v).strip()}
        except Exception:
            pass
    return {}


def collect_dept_stats() -> dict:
    """從 gspread 收集部門任務統計（需 GCP_SERVICE_ACCOUNT_JSON）"""
    # 取得 dept sheet IDs
    dept_ids = _get_dept_sheet_ids()
    if not dept_ids:
        return {"error": "部門 Sheet 未設定（請至系統設定頁或設定 DEPT_SHEETS_JSON env）"}

    # 取得 GCP 憑證
    try:
        from lib.config import get_service_account_info, DRIVE_SCOPES
        from google.oauth2.service_account import Credentials
        import gspread

        info = get_service_account_info()
        if not info:
            return {"error": "無 GCP 憑證（請設定 GCP_SERVICE_ACCOUNT_JSON）"}

        creds  = Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)
        client = gspread.authorize(creds)
    except ImportError as ex:
        return {"error": f"缺少套件：{ex}"}
    except Exception as ex:
        return {"error": f"GCP 憑證載入失敗：{str(ex)[:50]}"}

    all_rows: list[dict] = []
    errors:   list[str]  = []

    for dept, sheet_id in dept_ids.items():
        if not sheet_id:
            continue
        try:
            sh = client.open_by_key(sheet_id)
            ws = None
            for tab in ["任務", "Tasks", "工作清單", "工作項目", "Sheet1", "task", "tasks"]:
                try:
                    ws = sh.worksheet(tab)
                    break
                except Exception:
                    pass
            if ws is None:
                ws = sh.get_worksheet(0)
            if ws is None:
                continue
            for r in ws.get_all_records():
                r["_dept"] = dept
                all_rows.append(r)
        except Exception as ex:
            errors.append(f"{dept}: {str(ex)[:40]}")

    if not all_rows:
        return {"error": "無任何任務資料", "errors": errors}

    today_d = datetime.now().date()
    pending_list: list[dict] = []
    in_prog_list: list[dict] = []
    overdue_list: list[dict] = []
    done_list:    list[dict] = []
    red_items:    list[dict] = []

    _BLANK = frozenset({"", "nan", "NaN", "None", "none", "-", "—", "N/A"})

    for r in all_rows:
        # 任務名稱
        task_name = str(r.get("任務項目", r.get("名稱", r.get("what", "")))).strip()
        if task_name in _BLANK:
            continue

        dept = r.get("_dept", "")

        # 進度
        prog_str = str(r.get("目前進度", r.get("進度", "0"))).replace("%", "").strip()
        try:
            prog = int(float(prog_str))
        except (ValueError, TypeError):
            prog = 0

        # 截止日判斷
        dl_str  = str(r.get("截止日期", r.get("截止日", ""))).strip()
        is_over = False
        days_over = 0
        if dl_str and dl_str not in _BLANK:
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
                try:
                    dl_date = datetime.strptime(dl_str, fmt).date()
                    if dl_date < today_d and prog < 100:
                        is_over   = True
                        days_over = (today_d - dl_date).days
                    break
                except ValueError:
                    continue

        status_str = str(r.get("處理狀態", r.get("狀態", ""))).strip()

        if prog >= 100 or "完成" in status_str:
            done_list.append(r)
        elif is_over or "逾期" in status_str:
            overdue_list.append(r)
            red_items.append({
                "dept": dept, "name": task_name[:18],
                "prog": prog, "days_over": days_over,
            })
        elif prog > 0 or "執行" in status_str or "進行" in status_str:
            in_prog_list.append(r)
        else:
            pending_list.append(r)

    # 逾期最久排前
    red_items_sorted = sorted(red_items, key=lambda x: -x["days_over"])

    return {
        "total":          len(all_rows),
        "pending_count":  len(pending_list),
        "in_prog_count":  len(in_prog_list),
        "overdue_count":  len(overdue_list),
        "done_count":     len(done_list),
        "red_items":      red_items_sorted[:3],
        "errors":         errors,
    }


# ═══════════════════════════════════════════════════════════════════
# 4. 組裝訊息
# ═══════════════════════════════════════════════════════════════════

def _section(title: str, lines: list[str]) -> str:
    return title + "\n" + "\n".join(lines)


def build_morning_report() -> str:
    """組裝 08:30 早晨戰情簡報"""
    now      = _now()
    date_str = now.strftime(f"%m/%d {WEEKDAY_ZH[now.weekday()]}")

    edge = collect_edge_stats()
    rev  = collect_revenue_stats()
    dept = collect_dept_stats()

    parts: list[str] = [
        f"☀️ 嗑肉早安簡報｜{date_str}",
        "━━━━━━━━━━━━━━━━",
    ]

    # ── 事件看板 ──────────────────────────────────────
    red_p    = edge.get("red_p",    [])
    yellow_p = edge.get("yellow_p", [])
    blue_p   = edge.get("blue_p",   [])
    overdue  = edge.get("overdue",  [])

    evt_lines = []
    if red_p:
        evt_lines.append(f"🔴 紅色緊急 {len(red_p)} 件")
        for b in edge.get("red_briefs", []):
            evt_lines.append(f"  ▸ {b}")
    else:
        evt_lines.append(f"🔴 紅色緊急  0 件 ✨")

    evt_lines.append(f"🟡 黃色行動 {len(yellow_p)} 件")
    for b in edge.get("yellow_briefs", []):
        evt_lines.append(f"  ▸ {b}")

    evt_lines.append(f"🔵 藍色任務 {len(blue_p)} 件")
    evt_lines.append(f"👀 監控中   {len(edge.get('monitoring', []))} 件")

    if overdue:
        evt_lines.append(f"⏰ 逾期未結(>2h)  {len(overdue)} 件")
        for b in edge.get("overdue_briefs", []):
            evt_lines.append(f"  ⚠️ {b}")

    parts.append("\n🚨 【事件看板】待處理")
    parts.extend(evt_lines)

    # ── 門店戰情 ──────────────────────────────────────
    parts.append("\n━━━━━━━━━━━━━━━━")
    parts.append(f"\n📊 【門店戰情】{rev.get('ym', '')}月")
    if "error" not in rev:
        top3   = rev.get("top3",         [])
        bottom = rev.get("bottom_stores", [])
        avg    = rev.get("avg_pct",       0.0)

        if top3:
            top_txt = "・".join(f"{s['store']} {s['pct']:.0f}%" for s in top3)
            parts.append(f"🏆 Top3：{top_txt}")

        if bottom:
            btm_txt = "・".join(f"{s['store']} {s['pct']:.0f}%" for s in bottom)
            parts.append(f"🔴 預警(<70%)：{btm_txt}")
        else:
            parts.append(f"✅ 無達成率預警")

        parts.append(f"📈 品牌均達成率 {avg:.0f}%")
    else:
        parts.append(f"⚠️ 暫無資料（{rev.get('error', '')}）")

    # ── 專案追蹤 ──────────────────────────────────────
    parts.append("\n━━━━━━━━━━━━━━━━")
    parts.append(f"\n📋 【專案追蹤】")
    if "error" not in dept:
        p_c = dept.get("pending_count", 0)
        i_c = dept.get("in_prog_count", 0)
        o_c = dept.get("overdue_count", 0)
        parts.append(f"📌 待辦 {p_c} 件  ⚡ 進行 {i_c} 件  🚫 逾期 {o_c} 件")
        for item in dept.get("red_items", [])[:2]:
            over_txt = f"逾期{item['days_over']}天" if item['days_over'] > 0 else f"進度{item['prog']}%"
            parts.append(f"  🔴 [{item['dept']}] {item['name']}（{over_txt}）")
    else:
        parts.append(f"⚠️ 暫無資料（{dept.get('error', '')}）")

    parts.append("\n━━━━━━━━━━━━━━━━")
    parts.append("⚡ 今日目標明確，加油！")

    return "\n".join(parts)


def build_evening_report() -> str:
    """組裝 20:00 晚間戰報"""
    now      = _now()
    date_str = now.strftime(f"%m/%d {WEEKDAY_ZH[now.weekday()]}")

    edge = collect_edge_stats()
    rev  = collect_revenue_stats()
    dept = collect_dept_stats()

    parts: list[str] = [
        f"🌙 嗑肉晚間戰報｜{date_str}",
        "━━━━━━━━━━━━━━━━",
    ]

    # ── 今日事件統計 ──────────────────────────────────
    t_r = len(edge.get("today_new_red",    []))
    t_y = len(edge.get("today_new_yellow", []))
    t_b = len(edge.get("today_new_blue",   []))
    cl  = len(edge.get("closed_today",     []))
    overdue = edge.get("overdue", [])

    parts.append(f"\n📊 【今日事件統計】")
    parts.append(f"🔴 紅色 {t_r}件新增  🟡 黃色 {t_y}件  🔵 藍色 {t_b}件")
    parts.append(f"✅ 今日結案 {cl} 件")

    if overdue:
        parts.append(f"⚠️ 仍逾期未結 {len(overdue)} 件")
        for b in edge.get("overdue_briefs", []):
            parts.append(f"  ▸ {b}")

    # ── AI 自動化 ──────────────────────────────────────
    dec_cnt  = len(edge.get("today_decs",        []))
    auto_cnt = len(edge.get("auto_closed_today", []))
    parts.append(f"\n🤖 【AI 自動化】")
    parts.append(f"💡 指派決策 {dec_cnt} 次  🤖 自動結案 {auto_cnt} 件")

    # ── 重複報修 ──────────────────────────────────────
    repeats = edge.get("repeats", [])
    if repeats:
        parts.append(f"\n🔁 【重複報修警示】")
        for b in edge.get("repeat_briefs", []):
            parts.append(f"  ⚠️ {b}")

    # ── 門店戰情（今日累計）───────────────────────────
    parts.append(f"\n━━━━━━━━━━━━━━━━")
    parts.append(f"\n📊 【門店戰情】{rev.get('ym', '')}月累計")
    if "error" not in rev:
        total_rev = rev.get("total_rev", 0.0)
        avg       = rev.get("avg_pct",   0.0)
        bottom    = rev.get("bottom_stores", [])
        top3      = rev.get("top3", [])

        if total_rev > 0:
            parts.append(f"💰 月累計業績 {total_rev / 10000:.1f} 萬")
        parts.append(f"📈 品牌均達成率 {avg:.0f}%")

        if top3:
            top_txt = "・".join(f"{s['store']} {s['pct']:.0f}%" for s in top3[:3])
            parts.append(f"🏆 Top3：{top_txt}")

        if bottom:
            btm_txt = "・".join(f"{s['store']} {s['pct']:.0f}%" for s in bottom)
            parts.append(f"🔴 預警：{btm_txt}")
    else:
        parts.append(f"⚠️ 暫無資料（{rev.get('error', '')}）")

    # ── 專案追蹤 ──────────────────────────────────────
    if "error" not in dept:
        i_c = dept.get("in_prog_count", 0)
        o_c = dept.get("overdue_count", 0)
        parts.append(f"\n📋 【專案追蹤】")
        parts.append(f"⚡ 進行中 {i_c} 件  🚫 逾期 {o_c} 件")
        for item in dept.get("red_items", [])[:2]:
            over_txt = f"逾期{item['days_over']}天" if item['days_over'] > 0 else f"進度{item['prog']}%"
            parts.append(f"  🔴 [{item['dept']}] {item['name']}（{over_txt}）")

    parts.append(f"\n━━━━━━━━━━━━━━━━")
    parts.append("辛苦了！明天繼續 💪")

    return "\n".join(parts)
