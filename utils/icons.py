"""
utils/icons.py
Heroicons v2 outline — 線條感 SVG 圖示庫（24×24 viewport，2px stroke）
用法：
    from utils.icons import icon_html, ICONS
    st.markdown(icon_html("chart-bar", size=20, color="#E63B1F"), unsafe_allow_html=True)
"""
from __future__ import annotations

# ── SVG path data（Heroicons 2.0 outline）────────────────────────────────────
_PATHS: dict[str, str] = {
    # 數據 / 圖表
    "chart-bar": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75'
        'C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75Z'
        'M9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25'
        'c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625Z'
        'M16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75'
        'c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />'
    ),
    "chart-line": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0'
        '-5.94-2.281m5.94 2.28-2.28 5.941" />'
    ),
    "chart-pie": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M10.5 6a7.5 7.5 0 1 0 7.5 7.5h-7.5V6Z" />'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M13.5 10.5H21A7.5 7.5 0 0 0 13.5 3v7.5Z" />'
    ),
    "chart-radar": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M12 3v1m0 16v1M4.22 4.22l.707.707m12.02 12.02.707.707'
        'M1.5 12h1m18 0h1M4.22 19.78l.707-.707M18.95 5.22l.707-.707" />'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M12 8.25a3.75 3.75 0 1 0 0 7.5 3.75 3.75 0 0 0 0-7.5Z" />'
    ),

    # 追蹤 / 清單
    "clipboard-list": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108'
        'c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08'
        'm-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5'
        'a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0'
        'A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586'
        'm-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25'
        'm0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25'
        'c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375'
        'c0-.621-.504-1.125-1.125-1.125H8.25Z" />'
    ),
    "check-circle": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />'
    ),

    # AI / 智慧
    "light-bulb": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189'
        'a6.01 6.01 0 0 1-1.5-.189m3.75 7.478'
        'a12.06 12.06 0 0 1-4.5 0m3.75 2.383'
        'a14.406 14.406 0 0 1-3 0M14.25 18v-.192'
        'c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 1 0-7.517 0'
        'c.85.493 1.509 1.333 1.509 2.316V18" />'
    ),
    "cpu-chip": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5'
        'm-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21'
        'm3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75'
        'a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5'
        'a2.25 2.25 0 0 0 2.25 2.25Zm.75-12h9v9h-9v-9Z" />'
    ),
    "sparkles": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09'
        'L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25'
        'l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12'
        'l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z'
        'M18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456'
        'L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25'
        'l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6'
        'l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z'
        'M16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423'
        'L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423'
        'l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423'
        'l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />'
    ),

    # 品牌 / 行銷
    "star": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345'
        'l5.518.442c.499.04.701.663.321.988l-4.204 3.602'
        'a.563.563 0 0 0-.182.557l1.285 5.385'
        'a.562.562 0 0 1-.84.61l-4.725-2.885'
        'a.562.562 0 0 0-.586 0L6.982 20.54'
        'a.562.562 0 0 1-.84-.61l1.285-5.386'
        'a.562.562 0 0 0-.182-.557l-4.204-3.602'
        'a.562.562 0 0 1 .321-.988l5.518-.442'
        'a.563.563 0 0 0 .475-.345L11.48 3.5Z" />'
    ),
    "megaphone": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5'
        'a4.5 4.5 0 1 1 0-9h.75c.704 0 1.402-.03 2.09-.09'
        'm0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511'
        'l-.657.38c-.551.318-1.26.117-1.527-.461'
        'a20.845 20.845 0 0 1-1.44-4.282m3.102.069'
        'a18.03 18.03 0 0 1-.59-4.59c0-1.586.205-3.124.59-4.59'
        'm0 9.18a23.848 23.848 0 0 1 8.835 2.535'
        'M10.34 6.66a23.847 23.847 0 0 1 8.835-2.535'
        'M10.34 6.66V15.84m0-9.18V3.75'
        'c0-.69.56-1.25 1.25-1.25h.5c.69 0 1.25.56 1.25 1.25v.75" />'
    ),
    "globe-alt": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M12 21a9.004 9.004 0 0 0 8.716-6.747'
        'M12 21a9.004 9.004 0 0 1-8.716-6.747'
        'M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3'
        'm0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3'
        'm0 0a8.997 8.997 0 0 1 7.843 4.582'
        'M12 3a8.997 8.997 0 0 0-7.843 4.582'
        'm15.686 0A11.953 11.953 0 0 1 12 10.5'
        'c-2.998 0-5.74-1.1-7.843-2.918'
        'm15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253'
        'm0 0A17.919 17.919 0 0 1 12 16.5'
        'c-3.162 0-6.133-.815-8.716-2.247'
        'm0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418" />'
    ),

    # 新聞 / 內容
    "newspaper": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5'
        'm3-9h3.375c.621 0 1.125.504 1.125 1.125V18'
        'a2.25 2.25 0 0 1-2.25 2.25M16.5 7.5V18'
        'a2.25 2.25 0 0 0 2.25 2.25M16.5 7.5V4.875'
        'c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18'
        'a2.25 2.25 0 0 0 2.25 2.25h13.5M6 7.5h3v3H6v-3Z" />'
    ),
    "calendar": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5'
        'a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25'
        'm-18 0A2.25 2.25 0 0 0 5.25 21h13.5'
        'A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5'
        'A2.25 2.25 0 0 1 5.25 9h13.5'
        'a2.25 2.25 0 0 1 2.25 2.25v7.5" />'
    ),
    "key": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M15.75 5.25a3 3 0 0 1 3 3m3 0'
        'a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43'
        'L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818'
        'c0-.597.237-1.17.659-1.591l6.499-6.499'
        'c.404-.404.527-1 .43-1.563A6 6 0 0 1 21.75 8.25Z" />'
    ),

    # 競品 / 比較
    "arrows-right-left": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5'
        'm0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />'
    ),
    "scale": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75'
        'M12 20.25c1.472 0 2.882.265 4.185.75'
        'M18.75 4.97A48.416 48.416 0 0 0 12 4.5'
        'c-2.291 0-4.545.16-6.75.47m13.5 0'
        'c1.01.143 2.01.317 3 .52m-3-.52 2.62 10.726'
        'c.122.499-.106 1.028-.589 1.202'
        'a5.989 5.989 0 0 1-2.031.352 5.989 5.989 0 0 1-2.031-.352'
        'c-.483-.174-.711-.703-.59-1.202L18.75 4.971Z'
        'm-16.5.52c.99-.203 1.99-.377 3-.52m0 0 2.62 10.726'
        'c.122.499-.106 1.028-.589 1.202'
        'a5.989 5.989 0 0 1-2.031.352 5.989 5.989 0 0 1-2.031-.352'
        'c-.483-.174-.711-.703-.59-1.202L5.25 5.491Z" />'
    ),

    # 情感 / 使用者
    "face-smile": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M15.182 15.182a4.5 4.5 0 0 1-6.364 0M21 12'
        'a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M9 9.75h.008v.008H9V9.75Zm6 0h.008v.008H15V9.75Z" />'
    ),
    "magnifying-glass": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196'
        'a7.5 7.5 0 0 0 10.607 10.607Z" />'
    ),

    # YouTube / 媒體
    "play-circle": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M15.91 11.672a.375.375 0 0 1 0 .656l-5.603 3.113'
        'a.375.375 0 0 1-.557-.328V8.887'
        'c0-.286.307-.466.557-.327l5.603 3.112Z" />'
    ),

    # 系統 / 設定
    "cog": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94'
        'l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127'
        '.325.196.72.257 1.075.124l1.217-.456'
        'a1.125 1.125 0 0 1 1.37.49l1.296 2.247'
        'a1.125 1.125 0 0 1-.26 1.431l-1.003.827'
        'c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255'
        'c-.008.378.137.75.43.991l1.004.827'
        'c.424.35.534.955.26 1.43l-1.298 2.247'
        'a1.125 1.125 0 0 1-1.369.491l-1.217-.456'
        'c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128'
        'c-.331.183-.581.495-.644.869l-.213 1.281'
        'c-.09.543-.56.94-1.11.94h-2.594'
        'c-.55 0-1.019-.398-1.11-.94l-.213-1.281'
        'c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127'
        'c-.325-.196-.72-.257-1.076-.124l-1.217.456'
        'a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247'
        'a1.125 1.125 0 0 1 .26-1.431l1.004-.827'
        'c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255'
        'c.007-.38-.138-.751-.43-.992l-1.004-.827'
        'a1.125 1.125 0 0 1-.26-1.43l1.297-2.247'
        'a1.125 1.125 0 0 1 1.37-.491l1.216.456'
        'c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128'
        '.332-.183.582-.495.644-.869l.214-1.28Z" />'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />'
    ),
    "home": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="m2.25 12 8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12'
        'M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75'
        'v-4.875c0-.621.504-1.125 1.125-1.125h2.25'
        'c.621 0 1.125.504 1.125 1.125V21h4.125'
        'c.621 0 1.125-.504 1.125-1.125V9.75'
        'M8.25 21h8.25" />'
    ),
    "arrow-left": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />'
    ),
    "lock-closed": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75'
        'm-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75'
        'a2.25 2.25 0 0 0-2.25-2.25H6.75'
        'a2.25 2.25 0 0 0-2.25 2.25v6.75'
        'a2.25 2.25 0 0 0 2.25 2.25Z" />'
    ),
    "shield-check": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M9 12.75 11.25 15 15 9.75m-3-7.036'
        'A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749'
        'c0 5.592 3.824 10.29 9 11.623'
        '5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751'
        'h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />'
    ),
    "bell": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31'
        'A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75'
        'a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31'
        'm5.714 0a24.255 24.255 0 0 1-5.714 0'
        'm5.714 0a3 3 0 1 1-5.714 0" />'
    ),
    # 趨勢
    "trending-up": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0'
        '-5.94-2.281m5.94 2.28-2.28 5.941" />'
    ),
    # 評論 / 筆記
    "pencil-square": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M16.862 4.487 18.55 2.8a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07'
        'a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685'
        'a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Z'
        'm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25'
        'A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />'
    ),
    # 心跳健康
    "heart": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M21 8.25c0-2.485-2.099-4.5-4.688-4.5'
        '-1.935 0-3.597 1.126-4.312 2.733'
        '-.715-1.607-2.377-2.733-4.313-2.733'
        'C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12Z" />'
    ),
    # 平台 / 調整
    "adjustments": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0'
        'M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0'
        'm3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75'
        'm-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />'
    ),
    # 地圖 / Place
    "map-pin": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5'
        'a7.5 7.5 0 1 1 15 0Z" />'
    ),
    # 插件
    "plug": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M13.5 16.875h3.375m0 0h3.375m-3.375 0V13.5m0 3.375v3.375'
        'M6 10.5h2.25a2.25 2.25 0 0 0 2.25-2.25V6'
        'a2.25 2.25 0 0 0-2.25-2.25H6A2.25 2.25 0 0 0 3.75 6v2.25'
        'A2.25 2.25 0 0 0 6 10.5Zm0 9.75h2.25A2.25 2.25 0 0 0 10.5 18'
        'v-2.25a2.25 2.25 0 0 0-2.25-2.25H6'
        'a2.25 2.25 0 0 0-2.25 2.25V18A2.25 2.25 0 0 0 6 20.25Z" />'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M15.75 6a2.25 2.25 0 1 0 4.5 0 2.25 2.25 0 0 0-4.5 0Z" />'
    ),
    # 文件
    "document-text": (
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5'
        'A1.125 1.125 0 0 1 13.5 7.125v-1.5'
        'a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5'
        'm-7.5 3H12M10.5 2.25H5.625'
        'c-.621 0-1.125.504-1.125 1.125v17.25'
        'c0 .621.504 1.125 1.125 1.125h12.75'
        'c.621 0 1.125-.504 1.125-1.125V11.25'
        'a9 9 0 0 0-9-9Z" />'
    ),
}


# ── Public API ────────────────────────────────────────────────────────────────

def icon_svg(name: str, size: int = 20, color: str = "currentColor") -> str:
    """Return a raw <svg>...</svg> string for inline use."""
    path_data = _PATHS.get(name, _PATHS["sparkles"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" '
        f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" '
        f'style="display:inline-block;vertical-align:middle;flex-shrink:0;">'
        f'{path_data}'
        f'</svg>'
    )


def icon_html(
    name: str,
    size: int = 20,
    color: str = "currentColor",
    bg: str = "",
    padding: str = "6px",
    border_radius: str = "8px",
) -> str:
    """Return icon wrapped in a styled container div (for standalone display)."""
    svg = icon_svg(name, size, color)
    bg_style = f"background:{bg};padding:{padding};border-radius:{border_radius};display:inline-flex;align-items:center;justify-content:center;" if bg else ""
    return f'<span style="{bg_style}">{svg}</span>'


def section_header_html(
    icon_name: str,
    title: str,
    icon_color: str = "#E63B1F",
    icon_size: int = 18,
    badge: str = "",
) -> str:
    """
    Return HTML for a section header with SVG line icon.
    Matches .section-header CSS class styling.
    """
    svg = icon_svg(icon_name, size=icon_size, color=icon_color)
    badge_html = (
        f'<span style="margin-left:8px;font-size:0.72rem;'
        f'background:rgba(230,59,31,0.12);color:#E63B1F;'
        f'border-radius:20px;padding:2px 10px;font-weight:700;'
        f'vertical-align:middle;">{badge}</span>'
        if badge else ""
    )
    return (
        f'<div class="section-header" style="display:flex;align-items:center;gap:8px;">'
        f'{svg}<span>{title}</span>{badge_html}</div>'
    )


def card_icon_html(name: str, size: int = 40, color: str = "white") -> str:
    """Large icon for module cards (homepage)."""
    svg = icon_svg(name, size=size, color=color)
    return (
        f'<span style="display:flex;align-items:center;justify-content:center;'
        f'width:{size+16}px;height:{size+16}px;'
        f'background:rgba(255,255,255,0.15);'
        f'border:1.5px solid rgba(255,255,255,0.3);'
        f'border-radius:12px;margin:0 auto 0.7rem;">'
        f'{svg}</span>'
    )


# ── Icon mapping for existing emoji → SVG name ───────────────────────────────
EMOJI_TO_ICON: dict[str, str] = {
    "📊": "chart-bar",
    "🗂️": "clipboard-list",
    "🧠": "light-bulb",
    "🎨": "sparkles",
    "⚙️": "cog",
    "🏢": "home",
    "⭐": "star",
    "📰": "newspaper",
    "📈": "trending-up",
    "⚔️": "arrows-right-left",
    "🌐": "globe-alt",
    "▶️": "play-circle",
    "🤖": "cpu-chip",
    "🏷️": "key",
    "📅": "calendar",
    "😊": "face-smile",
    "🔍": "magnifying-glass",
    "📋": "clipboard-list",
    "🔒": "lock-closed",
    "❤️": "heart",
    "🔔": "bell",
}
