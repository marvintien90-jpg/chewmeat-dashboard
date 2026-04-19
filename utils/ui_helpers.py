"""
共用 UI 工具 — 跑馬燈 + AI 摘要 + 資料來源標注 + 全域樣式
"""
from __future__ import annotations
import streamlit as st
from utils.icons import section_header_html  # re-export for convenience

# ── Plotly 鎖定設定（禁用 pan/zoom/drag，保留 hover）──────────────────────────
PLOTLY_CONFIG: dict = {
    "scrollZoom": False,
    "displayModeBar": False,
    "staticPlot": False,       # False = hover tooltip 仍啟用
    "doubleClick": False,
}

PLOTLY_HOVER_LABEL: dict = {
    "bgcolor": "rgba(30,30,30,0.88)",
    "bordercolor": "#E63B1F",
    "font": {"size": 12, "color": "white", "family": "system-ui, sans-serif"},
}

# ── 跑馬燈 CSS ────────────────────────────────────────────────────────────────
MARQUEE_CSS = """
<style>
.marquee-wrapper {
    background: linear-gradient(90deg, #E63B1F, #C1320F);
    border-radius: 8px;
    padding: 8px 16px;
    overflow: hidden;
    margin-bottom: 1rem;
    position: relative;
}
.marquee-inner {
    display: inline-block;
    white-space: nowrap;
    animation: scroll-left 45s linear infinite;
    color: white;
    font-size: 0.88rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}
@keyframes scroll-left {
    0%   { transform: translateX(110vw); }
    100% { transform: translateX(-100%); }
}
.ai-summary-banner {
    background: linear-gradient(135deg, #FFF8F6 0%, #FFE8DC 100%);
    border: 1.5px solid #FFCBB8;
    border-left: 5px solid #E63B1F;
    border-radius: 12px;
    padding: 1rem 1.4rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 8px rgba(230,59,31,0.07);
}
.ai-summary-banner h4 {
    color: #C1320F; font-size: 0.95rem; margin: 0 0 0.5rem 0; font-weight: 800;
}
.ai-summary-banner p {
    color: #444; font-size: 0.85rem; line-height: 1.7; margin: 0;
}
.ai-summary-banner ul {
    margin: 0; padding-left: 1.2rem;
}
.ai-summary-banner li {
    color: #444; font-size: 0.85rem; line-height: 1.8;
}
.source-badge {
    display: inline-block; background: #F8F9FA; color: #6C757D;
    border: 1px solid #DEE2E6; border-radius: 4px;
    padding: 2px 8px; font-size: 0.72rem; margin-top: 4px;
}
</style>
"""

# ── 全域樣式（側欄分隔 + SVG 圖示容器 + 手機響應式）──────────────────────────
GLOBAL_CSS = """
<style>
/* ── 側欄暗色主題（全面配色修正）──────────────────────── */
[data-testid="stSidebar"] {
    background: #1A1A1A !important;
    border-right: 2px solid #2E2E2E;
    box-shadow: 4px 0 18px rgba(0,0,0,0.35);
}
/* 所有文字類元素 */
[data-testid="stSidebar"] *,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] .stMarkdown h4,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    color: #D0D0D0 !important;
}
/* 輸入框背景與文字 */
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stTextArea textarea {
    background: #2A2A2A !important;
    color: #E8E8E8 !important;
    border-color: #444 !important;
}
/* Selectbox / multiselect */
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stMultiSelect > div > div {
    background: #2A2A2A !important;
    color: #E8E8E8 !important;
    border-color: #444 !important;
}
[data-testid="stSidebar"] .stSelectbox span,
[data-testid="stSidebar"] .stMultiSelect span {
    color: #E8E8E8 !important;
}
/* Multiselect tags */
[data-testid="stSidebar"] [data-baseweb="tag"] {
    background: rgba(230,59,31,0.25) !important;
}
[data-testid="stSidebar"] [data-baseweb="tag"] span {
    color: #FFA080 !important;
}
/* Selectbox dropdown icon */
[data-testid="stSidebar"] svg[data-testid="stIconMaterial"] {
    fill: #AAA !important;
}
/* Button */
[data-testid="stSidebar"] button {
    background: #2A2A2A !important;
    color: #D0D0D0 !important;
    border-color: #444 !important;
}
[data-testid="stSidebar"] button:hover {
    background: rgba(230,59,31,0.2) !important;
    color: #FF8060 !important;
}
/* Expander */
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: #222 !important;
    border-color: #333 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    color: #D0D0D0 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
    color: #FF8060 !important;
}
/* Divider */
[data-testid="stSidebar"] hr {
    border-color: #333 !important;
}
/* Radio buttons */
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    color: #D0D0D0 !important;
}
/* Checkbox */
[data-testid="stSidebar"] [data-testid="stCheckbox"] label {
    color: #D0D0D0 !important;
}
/* Slider */
[data-testid="stSidebar"] [data-testid="stSlider"] p {
    color: #D0D0D0 !important;
}
/* Page links */
[data-testid="stSidebar"] .stPageLink a {
    color: #B0B0B0 !important;
    font-size: 0.85rem;
    padding: 4px 0;
    transition: color 0.15s;
}
[data-testid="stSidebar"] .stPageLink a:hover {
    color: #FF7A5C !important;
}
[data-testid="stSidebar"] .sidebar-nav-icon {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: #CCC;
    font-size: 0.85rem;
    padding: 6px 4px;
    border-radius: 6px;
    width: 100%;
    transition: background 0.15s, color 0.15s;
    text-decoration: none;
    cursor: pointer;
}
[data-testid="stSidebar"] .sidebar-nav-icon:hover {
    background: rgba(230,59,31,0.15);
    color: #FF7A5C !important;
}
[data-testid="stSidebar"] .sidebar-section-title {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: #666 !important;
    padding: 12px 4px 4px;
}

/* ── Section header（含 SVG 圖示）──────────────────── */
.section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 1.0rem;
    font-weight: 800;
    color: #1A1A1A;
    padding: 0.4rem 0;
    margin: 1.2rem 0 0.6rem;
    border-bottom: 2px solid #F0F0F0;
}
.section-header svg {
    flex-shrink: 0;
}

/* ── KPI 卡片 ────────────────────────────────────────── */
.kpi-card {
    background: white;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.07);
    border: 1px solid #F0F0F0;
    transition: box-shadow 0.2s;
}
.kpi-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

/* ── Plotly 圖表容器（防止意外拖移） ────────────────── */
[data-testid="stPlotlyChart"] {
    user-select: none;
    -webkit-user-select: none;
}
[data-testid="stPlotlyChart"] .js-plotly-plot {
    cursor: default !important;
}

/* ── 手機響應式（max-width: 768px）──────────────────── */
@media (max-width: 768px) {
    /* 側欄自動收起時不遮擋主內容 */
    [data-testid="stSidebar"] {
        box-shadow: none;
    }
    /* 卡片單欄 */
    .module-grid {
        grid-template-columns: 1fr !important;
        gap: 1rem !important;
    }
    /* Section header 字型縮小 */
    .section-header {
        font-size: 0.9rem;
    }
    /* KPI 數字縮小 */
    .kpi-value {
        font-size: 1.6rem !important;
    }
    /* 跑馬燈字型 */
    .marquee-inner {
        font-size: 0.78rem;
    }
    /* 圖表最小高度 */
    [data-testid="stPlotlyChart"] {
        min-height: 220px;
    }
    /* Streamlit columns: 在手機寬度強制換行 */
    [data-testid="column"] {
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }
    /* 標籤頁在小螢幕捲動 */
    [data-testid="stTabs"] {
        overflow-x: auto;
    }
}
@media (max-width: 480px) {
    .kpi-card {
        padding: 0.7rem 0.8rem;
    }
    .section-header {
        font-size: 0.82rem;
    }
}
</style>
"""


def inject_global_css() -> None:
    """Inject sidebar separation + SVG icon styles + mobile responsive CSS."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_marquee(items: list) -> None:
    """Render a horizontally scrolling ticker bar. items = list of short strings."""
    separator = "　　｜　　"
    text = separator.join(f"🔔 {it}" for it in items)
    st.markdown(MARQUEE_CSS + f"""
<div class="marquee-wrapper">
  <span class="marquee-inner">{text}&nbsp;&nbsp;&nbsp;&nbsp;{text}</span>
</div>
""", unsafe_allow_html=True)


def render_section_header(icon_name: str, title: str, badge: str = "") -> None:
    """Render a section header with SVG line icon via st.markdown."""
    st.markdown(
        section_header_html(icon_name, title, badge=badge),
        unsafe_allow_html=True,
    )


def render_ai_summary(title: str, bullets: list) -> None:
    """Render an AI summary card with bullet points."""
    bullet_html = "".join(f"<li>{b}</li>" for b in bullets)
    st.markdown(f"""
<div class="ai-summary-banner">
  <h4>🤖 {title}</h4>
  <ul>{bullet_html}</ul>
</div>
""", unsafe_allow_html=True)


def render_data_source_footer(sources: list) -> None:
    """Render a professional data source attribution footer.
    sources = [{"name": "Google Trends", "note": "近3個月", "records": 90}, ...]
    """
    items = " · ".join(
        f'<span class="source-badge">{s["name"]} {s.get("note", "")}'
        f'{(" · " + str(s["records"]) + " 筆") if s.get("records") else ""}</span>'
        for s in sources
    )
    st.markdown(
        MARQUEE_CSS + f'<div style="margin-top:6px;">{items}</div>',
        unsafe_allow_html=True,
    )
