"""
共用 UI 工具 — 跑馬燈 + AI 摘要 + 資料來源標注
"""
from __future__ import annotations
import streamlit as st

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


def render_marquee(items: list) -> None:
    """Render a horizontally scrolling ticker bar. items = list of short strings."""
    separator = "　　｜　　"
    text = separator.join(f"🔔 {it}" for it in items)
    st.markdown(MARQUEE_CSS + f"""
<div class="marquee-wrapper">
  <span class="marquee-inner">{text}&nbsp;&nbsp;&nbsp;&nbsp;{text}</span>
</div>
""", unsafe_allow_html=True)


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
