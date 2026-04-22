"""
utils/edge_nlp.py
Edge Agent 共用 NLP 模組 — 分類器 / 確認語意偵測 / 門店萃取

由以下模組共用：
  - line_webhook.py          （FastAPI 接收器）
  - pages/6_Line邊緣代理人.py（Streamlit 看板）
"""
from __future__ import annotations
import re

# ── 三色關鍵字庫（含子類別）────────────────────────────────────────
RED_CATS: dict[str, list[str]] = {
    "red-equipment":   ["故障", "壞了", "不動了", "無法運作", "無法結帳", "死機", "當機"],
    "red-temperature": ["溫度異常", "冷藏", "冷凍異常", "溫控"],
    "red-power":       ["斷電", "停電", "電源故障", "跳電"],
    "red-safety":      ["漏水", "火警", "受傷", "危險"],
    "red-other":       ["異常", "停擺", "報廢", "緊急", "無法"],
}
YELLOW_CATS: dict[str, list[str]] = {
    "yellow-staffing": ["支援", "人手不足", "工讀生", "人力", "幫忙"],
    "yellow-material": ["物料", "需要", "協助", "準備", "額外"],
    "yellow-delivery": ["配送", "外送", "調度", "訂單量"],
}
BLUE_CATS: dict[str, list[str]] = {
    "blue-inventory": ["盤點", "庫存不足", "補貨", "包材"],
    "blue-task":      ["結帳", "清潔", "任務", "完成", "派發"],
    "blue-report":    ["回報", "等待", "總部"],
}

CONFIRM_PATTERNS: list[str] = [
    r"收到", r"搞定", r"ok了?", r"好了", r"處理完了?", r"完成了?",
    r"確認", r"好的", r"沒問題", r"已處理", r"結案了?", r"送達",
    r"到了", r"搞好了", r"修好了", r"補完了", r"解決了",
    r"弄好了", r"處理好了", r"done", r"finished", r"ok$",
]

LEVEL_LABELS: dict[str, str] = {
    "red":    "🔴 紅色警戒",
    "yellow": "🟡 黃色行動",
    "blue":   "🔵 藍色任務",
}
CAT_CN: dict[str, str] = {
    "red-equipment":   "設備故障",  "red-temperature": "溫度異常",
    "red-power":       "電力異常",  "red-safety":      "安全事故",
    "red-other":       "紅區-其他", "yellow-staffing": "人力支援",
    "yellow-material": "物料協助",  "yellow-delivery": "配送調度",
    "blue-inventory":  "庫存盤點",  "blue-task":       "例行任務",
    "blue-report":     "回報確認",
}

# 門店清單（用於從訊息文字中萃取）
STORE_LIST: list[str] = [
    "崇德店", "美村店", "公益店", "北屯店", "南屯店",
    "西屯店", "東區店", "北區店", "南區店", "中區店",
    "豐原店", "太平店", "大里店", "霧峰店", "沙鹿店",
]


# ── 核心函數 ──────────────────────────────────────────────────────
def classify_v2(text: str) -> tuple[str, str]:
    """
    對訊息文字進行三色分類。
    回傳 (level, keyword_cat)，level 為 'red' / 'yellow' / 'blue'。
    """
    t = text or ""
    for cat, kws in RED_CATS.items():
        if any(kw in t for kw in kws):
            return "red", cat
    for cat, kws in YELLOW_CATS.items():
        if any(kw in t for kw in kws):
            return "yellow", cat
    for cat, kws in BLUE_CATS.items():
        if any(kw in t for kw in kws):
            return "blue", cat
    return "blue", "blue-task"


def is_confirmation(text: str) -> bool:
    """判斷訊息是否符合「模糊結案確認」語意（16+ 種詞形）"""
    t = (text or "").lower()
    return any(re.search(p, t) for p in CONFIRM_PATTERNS)


def extract_store_from_text(text: str) -> str | None:
    """從訊息文字中萃取門店名稱（優先最長匹配）"""
    t = text or ""
    for store in STORE_LIST:
        if store in t:
            return store
    return None
