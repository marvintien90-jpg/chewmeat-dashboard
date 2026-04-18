"""
嗑肉石鍋 數位總部 — LINE Notify 通知模組
當智能戰情室開關開啟且偵測到異常時，主動推播白話摘要給指定 LINE 群組。
"""
import requests
import streamlit as st


def send_line_notify(token: str, message: str) -> bool:
    """
    傳送 LINE Notify 推播訊息。
    - token: LINE Notify 存取金鑰（在 LINE Notify 官網申請）
    - message: 推播文字內容
    回傳 True 表示成功，False 表示失敗。
    """
    if not token or not token.strip():
        return False

    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {token.strip()}"}
    payload = {"message": message}

    try:
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def build_revenue_alert_message(
    store_name: str,
    actual: float,
    target: float,
    deviation_pct: float,
    data_source: str = "",
) -> str:
    """
    產生「白話」LINE 推播摘要。
    data_source 用於證據鏈標註，例如「來源：營收表-台一店 G15」。
    """
    direction = "低於" if deviation_pct < 0 else "高於"
    abs_pct = abs(deviation_pct)
    gap = abs(actual - target)

    lines = [
        "",
        "🍲【嗑肉石鍋 自動警示】",
        f"門店：{store_name}",
        f"今日實際營業額：{actual:,.0f} 元",
        f"目標（日均）：{target:,.0f} 元",
        f"誤差：{direction}目標 {abs_pct:.1f}%（差距 {gap:,.0f} 元）",
        "",
        "📌 建議：請店長確認今日客流狀況，並回報異常原因。",
    ]

    if data_source:
        lines.append(f"🔗 資料來源：{data_source}")

    return "\n".join(lines)


def check_and_notify(
    store_revenue_dict: dict,
    store_target_dict: dict,
    token: str,
    threshold_pct: float = 5.0,
) -> list[dict]:
    """
    批次檢查所有門店的營收偏差。
    當偏差 >= threshold_pct（預設 5%）時，觸發 LINE 推播。
    回傳已推播的警示清單（供介面顯示）。

    store_revenue_dict: {門店名稱: 今日實際營業額}
    store_target_dict:  {門店名稱: 日均目標}
    """
    alerts = []

    for store, actual in store_revenue_dict.items():
        target = store_target_dict.get(store)
        if not target or target <= 0:
            continue

        deviation_pct = (actual - target) / target * 100

        if abs(deviation_pct) >= threshold_pct:
            source_ref = f"營收表-{store}"
            msg = build_revenue_alert_message(
                store_name=store,
                actual=actual,
                target=target,
                deviation_pct=deviation_pct,
                data_source=source_ref,
            )
            success = send_line_notify(token, msg)
            alerts.append({
                "門店": store,
                "實際營業額": actual,
                "日均目標": target,
                "偏差率": deviation_pct,
                "已推播": success,
                "資料來源": source_ref,
            })

    return alerts
