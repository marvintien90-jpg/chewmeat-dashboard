"""
utils/edge_nlp.py
Edge Agent 共用 NLP 模組 — 分類器 / 信心度評分 / 確認語意偵測 / 門店萃取

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

# ── 高信心度強關鍵字（直接升至 1.0）──────────────────────────────
_HIGH_CONFIDENCE_KWS: list[str] = [
    "故障", "壞了", "不動了", "死機", "當機", "斷電", "停電", "跳電",
    "漏水", "火警", "受傷", "危險", "溫度異常", "冷凍異常", "無法結帳",
    "緊急", "停擺", "報廢", "電源故障",
]

# ── 中信心度指標詞（升至 0.75）──────────────────────────────────
_MID_CONFIDENCE_KWS: list[str] = [
    "異常", "無法", "人手不足", "人力", "工讀生", "配送", "調度",
    "庫存不足", "補貨", "支援", "協助", "物料", "包材",
    "盤點", "訂單量", "外送",
]

# ── 低信心短句白名單（直接忽略，不建立事件）──────────────────────
_NOISE_PATTERNS: list[str] = [
    r"^[\U0001F000-\U0001FFFF]+$",   # 純 emoji
    r"^[!！?？。，、…]+$",           # 純標點
    r"^[\d\s]+$",                    # 純數字/空白
    r"^(ok|好|嗯|喔|哦|欸|蛤|嘿|hi|hey|哈|哈哈+|呵呵+|哈囉|hello|謝謝|感謝|辛苦了|加油|棒)$",
    r"^(測試|test|ping|在嗎|你好|早安|午安|晚安|晚餐|幾點|下班)$",
]

# ── 確認結案語意（觸發「建議結案」卡片，非自動結案）───────────────
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

# 信心度推播門檻（低於此值靜默存檔，不推播 Commander）
CONFIDENCE_THRESHOLD: float = 0.6


# ── 核心函數 ──────────────────────────────────────────────────────
def get_message_confidence(text: str) -> float:
    """
    評估訊息的「信心度」（0.0 ~ 1.0），代表此訊息真的是需要處理的現場事件的機率。

    規則（由高到低）：
      1. 雜訊白名單 → 0.0（直接忽略）
      2. 文字長度 < 5 字 → 0.1（太短，資訊不足）
      3. 包含高信心度強關鍵字 → 1.0
      4. 包含中信心度指標詞 → 0.75
      5. 文字長度 >= 15 字（較完整描述） → 0.6
      6. 文字長度 10~14 字 → 0.5
      7. 其他短文字 → 0.3
    """
    t = (text or "").strip()
    if not t:
        return 0.0

    # 1. 雜訊白名單（直接歸零）
    for pattern in _NOISE_PATTERNS:
        if re.match(pattern, t, re.IGNORECASE):
            return 0.0

    # 2. 太短
    char_count = len(t)
    if char_count < 5:
        return 0.1

    # 3. 高信心度強關鍵字
    if any(kw in t for kw in _HIGH_CONFIDENCE_KWS):
        return 1.0

    # 4. 中信心度指標詞
    if any(kw in t for kw in _MID_CONFIDENCE_KWS):
        return 0.75

    # 5-7. 長度啟發式
    if char_count >= 15:
        return 0.6
    if char_count >= 10:
        return 0.5
    return 0.3


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


def classify_with_confidence(text: str) -> tuple[str, str, float]:
    """
    分類 + 信心度一次取得。
    回傳 (level, keyword_cat, confidence)。
    confidence >= CONFIDENCE_THRESHOLD (0.6) 才推播給 Commander。
    """
    level, cat = classify_v2(text)
    conf = get_message_confidence(text)
    return level, cat, conf


def is_noise(text: str) -> bool:
    """判斷是否為雜訊訊息（不需建立事件）"""
    return get_message_confidence(text) < CONFIDENCE_THRESHOLD


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
