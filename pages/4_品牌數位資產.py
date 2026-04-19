"""
4_品牌數位資產.py — 品牌監控 × 爬蟲數據分析（完整版）
三分頁：主品牌現況 | 競爭品牌對照 | 口碑AI診斷
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 品牌數位資產",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("main_portal.py", label="← 返回數位總部大門")
    st.stop()

if "品牌數位資產" not in st.session_state.get("enabled_pages", set()):
    st.error("🔒 本功能尚未開放")
    st.page_link("main_portal.py", label="← 返回總部")
    st.stop()

from utils.brand_scraper import (
    get_trends_interest, get_related_keywords,
    fetch_google_news, get_brand_google_rating,
    analyze_brand_sentiment, scrape_competitor_news,
    calculate_six_indicators, load_brand_config, save_brand_config,
    aggregate_taiwan_platforms, calculate_platform_median_stats,
    generate_ai_diagnosis, get_competitor_overview,
    generate_ai_keywords, get_competitor_scores,
    get_search_suggestions, fetch_news_volume_trend, fetch_youtube_brand_presence,
    HAS_PYTRENDS, HAS_BS4,
    TAIWAN_PLATFORMS,
)
from utils.ui_helpers import render_marquee, render_ai_summary

# ── CSS ───────────────────────────────────────────
st.markdown("""
<style>
    .main .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    [data-testid="stSidebarNav"] {display: none !important;}
    [data-testid="stSidebar"] {background: #FAFAFA;}

    .section-header {
        background: #E63B1F; color: white;
        padding: 7px 16px; border-radius: 8px;
        margin: 1rem 0 0.5rem; font-weight: 700; font-size: 0.95rem;
    }
    [data-testid="stMetric"] {
        background: #FFFFFF; padding: 14px; border-radius: 10px;
        border: 1.5px solid #F0E8E5;
        box-shadow: 0 1px 4px rgba(230,59,31,0.07);
    }
    .news-card {
        background: #FFFFFF; border: 1.5px solid #F0E8E5;
        border-left: 5px solid #E63B1F; border-radius: 10px;
        padding: 0.9rem 1.1rem; margin-bottom: 0.6rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        font-size: 0.88rem;
    }
    .news-card.positive { border-left-color: #27AE60; }
    .news-card.negative { border-left-color: #E74C3C; }
    .news-card.neutral  { border-left-color: #95A5A6; }
    .news-title {
        font-weight: 600; color: #1A1A1A; text-decoration: none;
        font-size: 0.9rem;
    }
    .news-title:hover { color: #E63B1F; text-decoration: underline; }
    .news-meta { font-size: 0.77rem; color: #888; margin: 4px 0; }
    .news-desc { font-size: 0.82rem; color: #555; line-height: 1.5; }
    .sentiment-positive { color: #27AE60; font-weight: 700; }
    .sentiment-negative { color: #E74C3C; font-weight: 700; }
    .sentiment-neutral  { color: #888; font-weight: 700; }
    .kw-tag {
        display: inline-block; background: #FFF3EE; color: #C1320F;
        border: 1px solid #FFCBB8; border-radius: 20px;
        padding: 3px 12px; font-size: 0.78rem; font-weight: 600;
        margin: 3px 4px; text-decoration: none;
    }
    .kw-tag:hover { background: #FFE8DC; }
    .kw-tag.rising { background: #E8F8F5; color: #1E8449; border-color: #A9DFBF; }
    .kw-tag.rising:hover { background: #D4EFDF; }
    .indicator-card {
        background: #FFFFFF; border: 1.5px solid #F0E8E5;
        border-radius: 12px; padding: 1rem; text-align: center;
        box-shadow: 0 2px 8px rgba(230,59,31,0.06);
    }
    .competitor-tag {
        display: inline-block; background: #2C3E50; color: white;
        border-radius: 6px; padding: 4px 10px; font-size: 0.78rem;
        margin: 2px 3px;
    }
    .warning-card {
        background: #FFF0F0; border-left: 4px solid #E74C3C;
        border-radius: 8px; padding: 10px 14px; margin-bottom: 0.5rem;
        font-size: 0.87rem;
    }
    .opportunity-card {
        background: #F0FFF4; border-left: 4px solid #27AE60;
        border-radius: 8px; padding: 10px 14px; margin-bottom: 0.5rem;
        font-size: 0.87rem;
    }
    .discussion-item {
        background: #F8F9FA; border-left: 3px solid #3498DB;
        border-radius: 6px; padding: 8px 12px; margin-bottom: 0.4rem;
        font-size: 0.86rem;
    }
    .source-badge {
        display: inline-block; background: #F8F9FA; color: #6C757D;
        border: 1px solid #DEE2E6; border-radius: 4px;
        padding: 2px 8px; font-size: 0.72rem; margin-top: 4px;
    }
    .data-quality-note {
        background: #FFFBF0; border: 1px solid #FFE082; border-radius: 6px;
        padding: 8px 12px; font-size: 0.78rem; color: #7B5E00; margin: 4px 0 12px;
    }
</style>
""", unsafe_allow_html=True)

# ── Chart palette ──────────────────────────────────
CHART_PALETTE = [
    "#E63B1F",  # brand red
    "#F5A623",  # amber
    "#4A90E2",  # blue
    "#7ED321",  # green
    "#9B59B6",  # purple
    "#1ABC9C",  # teal
    "#E74C3C",  # crimson
    "#3498DB",  # sky blue
    "#2ECC71",  # emerald
    "#F39C12",  # orange
]

# ── Sidebar ───────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎨 品牌行銷部")
    st.caption("即時品牌監控 × 爬蟲數據分析")
    st.divider()
    st.page_link("main_portal.py",              label="🏢 返回總部大門")
    st.page_link("pages/1_數據戰情中心.py",      label="📊 數據戰情中心")
    st.page_link("pages/2_專案追蹤師.py",        label="🗂️ 專案追蹤師")
    st.page_link("pages/3_決策AI偵察.py",        label="🧠 決策AI偵察")
    st.divider()

    # Brand config expander
    cfg = load_brand_config()
    with st.expander("⚙️ 品牌設定", expanded=False):
        brand_name_inp = st.text_input("品牌名稱", value=cfg.get("brand_name", "嗑肉石鍋"), key="brand_name_inp")
        brand_kw_inp = st.text_area(
            "品牌關鍵字（每行一個）",
            value="\n".join(cfg.get("brand_keywords", ["嗑肉石鍋", "嗑肉", "石鍋料理"])),
            height=100, key="brand_kw_inp",
        )
        comp_inp = st.text_area(
            "競品（每行一個）",
            value="\n".join(cfg.get("competitors", ["韓金館", "豆府韓國料理", "橋村炸雞", "王品集團", "瓦城"])),
            height=100, key="comp_inp",
        )
        geo_inp = st.selectbox("地區", ["TW", "HK", "SG", "US"],
                               index=["TW","HK","SG","US"].index(cfg.get("geo","TW")), key="geo_inp")
        tf_map = {"近1個月": "today 1-m", "近3個月": "today 3-m",
                  "近6個月": "today 6-m", "近12個月": "today 12-m"}
        tf_label = st.selectbox("趨勢時間範圍", list(tf_map.keys()),
                                index=list(tf_map.values()).index(cfg.get("timeframe","today 3-m")),
                                key="tf_label_inp")
        st.divider()

        # ── Google 評分動態資產設定 ──────────────────
        st.markdown("**⭐ Google 評分來源設定**")

        # API key status display
        import os as _os
        _has_places = bool(_os.environ.get("GOOGLE_PLACES_API_KEY", ""))
        _has_serp   = bool(_os.environ.get("SERPAPI_KEY", ""))
        st.caption(
            f"{'🟢' if _has_places else '⚪'} Google Places API {'已啟用' if _has_places else '未設定'} ｜ "
            f"{'🟢' if _has_serp else '⚪'} SerpApi {'已啟用' if _has_serp else '未設定'}"
        )

        # Layer 1: Place IDs
        with st.expander("🗺️ Layer 1 — Google Place IDs（最精準）", expanded=bool(cfg.get("place_ids"))):
            st.caption("透過 Google Maps Platform Places API 直接取得門市官方評分。每行一筆：「門市名稱:ChIJ門市ID」或直接貼上 Place ID。")
            st.caption("[如何取得 Place ID？](https://developers.google.com/maps/documentation/javascript/examples/places-placeid-finder)")
            place_ids_inp = st.text_area(
                "Place IDs（每行一筆）",
                value="\n".join(cfg.get("place_ids", [])),
                height=80, key="place_ids_inp",
                placeholder="台中總店:ChIJxxxxxxxx\n高雄店:ChIJyyyyyyyy",
            )
            if not _has_places:
                st.info("💡 設定環境變數 `GOOGLE_PLACES_API_KEY` 後即可啟用 — Google 每月 $200 免費額度，單品牌監控幾乎零成本。")

        # Layer 2: SerpApi (env only — no config needed)
        if not _has_serp:
            with st.expander("🔌 Layer 2 — SerpApi（快速落地）", expanded=False):
                st.caption("設定環境變數 `SERPAPI_KEY` 後自動啟用。無需額外設定，5 行代碼搞定，不受 Google DOM 更新影響。")
                st.caption("[申請 SerpApi 免費試用](https://serpapi.com/)")
        else:
            st.success("🔌 SerpApi 已連接，自動補位 Places API")

        # Layer 3: QSC Internal Google Sheets
        with st.expander("📋 Layer 3 — QSC 內部週報（業務鉤稽）", expanded=bool(cfg.get("qsc_sheet_id"))):
            st.caption("直接連向內部門市週報 Google Sheets，將「Google 評分」欄位同步至儀表板，這是業務數據同步，非手動輸入。")
            qsc_sheet_inp = st.text_input(
                "QSC Google Sheets ID",
                value=cfg.get("qsc_sheet_id", ""),
                key="qsc_sheet_inp",
                placeholder="貼上 Sheets 網址中的 spreadsheet ID",
            )
            qsc_col_inp = st.text_input(
                "Google 評分欄位名稱",
                value=cfg.get("qsc_rating_col", "Google評分"),
                key="qsc_col_inp",
            )

        # Layer 4: Manual fallback
        with st.expander("✏️ Layer 4 — 手動輸入（最後備案）", expanded=bool(cfg.get("manual_rating"))):
            manual_rating_inp = st.number_input(
                "Google 評分 (1.0–5.0，0=停用)",
                min_value=0.0, max_value=5.0, step=0.1,
                value=float(cfg.get("manual_rating") or 0),
                key="manual_rating_inp",
            )
            manual_review_inp = st.number_input(
                "評論數 (0=自動取得)",
                min_value=0, step=10,
                value=int(cfg.get("manual_review_count") or 0),
                key="manual_review_inp",
            )

        if st.button("💾 儲存設定", type="primary", use_container_width=True, key="save_cfg_btn"):
            new_cfg = {
                "brand_name": brand_name_inp.strip(),
                "brand_keywords": [k.strip() for k in brand_kw_inp.strip().split("\n") if k.strip()][:5],
                "competitors": [c.strip() for c in comp_inp.strip().split("\n") if c.strip()][:6],
                "geo": geo_inp,
                "timeframe": tf_map[tf_label],
                "manual_rating": manual_rating_inp if manual_rating_inp > 0 else None,
                "manual_review_count": manual_review_inp if manual_review_inp > 0 else None,
                "place_ids": [p.strip() for p in place_ids_inp.strip().split("\n") if p.strip()],
                "qsc_sheet_id": qsc_sheet_inp.strip(),
                "qsc_rating_col": qsc_col_inp.strip() or "Google評分",
            }
            save_brand_config(new_cfg)
            st.cache_data.clear()
            st.success("✅ 已儲存，正在重新載入…")
            st.rerun()

    if st.button("🔄 重新抓取所有資料", use_container_width=True, key="refresh_all_btn"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.caption("套件狀態")
    st.caption(f"{'✅' if HAS_PYTRENDS else '⚠️'} pytrends {'已安裝' if HAS_PYTRENDS else '未安裝'}")
    st.caption(f"{'✅' if HAS_BS4 else '⚠️'} beautifulsoup4 {'已安裝' if HAS_BS4 else '未安裝'}")
    import os as _os2
    _has_places2 = bool(_os2.environ.get("GOOGLE_PLACES_API_KEY", ""))
    _has_serp2   = bool(_os2.environ.get("SERPAPI_KEY", ""))
    _has_anthropic2 = bool(_os2.environ.get("ANTHROPIC_API_KEY", ""))
    st.caption(f"{'🟢' if _has_places2 else '⚪'} Google Places API")
    st.caption(f"{'🟢' if _has_serp2 else '⚪'} SerpApi")
    st.caption(f"{'🟢' if _has_anthropic2 else '⚪'} Claude AI")

# Re-load config
cfg = load_brand_config()
brand_name  = cfg["brand_name"]
brand_kws   = cfg["brand_keywords"]
competitors = cfg["competitors"]
geo         = cfg["geo"]
timeframe   = cfg["timeframe"]

# ── Title ─────────────────────────────────────────
st.markdown("# 🎨 品牌數位資產監控")
st.markdown("**即時爬蟲分析** — 品牌聲量・Google評分・競品動態・關鍵字趨勢・口碑AI診斷")
st.divider()

# ── Load data with progress ────────────────────────
progress_bar = st.progress(0, text="初始化…")

progress_bar.progress(8, text="🔍 抓取 Google 評分（動態資產三層架構）…")
_manual_r  = cfg.get("manual_rating")
_manual_rc = cfg.get("manual_review_count")
_place_ids = tuple(cfg.get("place_ids", []))      # tuple for cache hashability
_qsc_sheet = cfg.get("qsc_sheet_id", "")
_qsc_col   = cfg.get("qsc_rating_col", "Google評分")
rating_data = get_brand_google_rating(
    brand_name,
    manual_rating=_manual_r,
    manual_review_count=_manual_rc,
    place_ids=_place_ids,
    qsc_sheet_id=_qsc_sheet,
    qsc_rating_col=_qsc_col,
)
rating_source = rating_data.get("source", "")   # defined early — used by marquee ticker below

progress_bar.progress(18, text="📈 讀取 Google Trends…")
# Include competitors in Trends query so Tab 2 comparison charts can render
_trends_kws = (brand_kws[:1] + [c for c in competitors[:3] if c.strip()])[:5]
trends_data = get_trends_interest(_trends_kws if len(_trends_kws) > 1 else brand_kws, timeframe=timeframe, geo=geo)

progress_bar.progress(30, text="🧮 計算六項品牌指標…")
indicators = calculate_six_indicators(brand_name, competitors)

progress_bar.progress(42, text="😊 分析網路情感…")
sentiment = analyze_brand_sentiment(brand_kws[:2])

progress_bar.progress(53, text="🏷️ 抓取相關關鍵字…")
related_kw = get_related_keywords(brand_kws[0] if brand_kws else brand_name, geo=geo)

progress_bar.progress(63, text="⚔️ 監控競品動態…")
comp_news = scrape_competitor_news(competitors)

progress_bar.progress(68, text="🔍 取得搜尋熱門建議…")
search_suggestions = get_search_suggestions(brand_kws[0] if brand_kws else brand_name)

progress_bar.progress(73, text="🌐 掃描台灣各平台聲量…")
platform_data = aggregate_taiwan_platforms(brand_kws)
platform_stats = calculate_platform_median_stats(platform_data)

progress_bar.progress(78, text="📅 建立品牌聲量時間趨勢…")
news_trend = fetch_news_volume_trend(brand_kws, months=6)

progress_bar.progress(83, text="▶️ 掃描 YouTube 品牌曝光…")
youtube_data = fetch_youtube_brand_presence(brand_name)

progress_bar.progress(92, text="🤖 產生 AI 診斷報告…")
ai_diagnosis = generate_ai_diagnosis(
    brand_name, indicators, platform_stats, trends_data, comp_news
)

progress_bar.progress(100, text="✅ 資料載入完成！")
progress_bar.empty()

# ── 跑馬燈 ─────────────────────────────────────────
rating_val = rating_data.get("rating")
sentiment_score = sentiment.get("score", 0)
total_news = sentiment.get("total", 0)
avg_indicator = ai_diagnosis.get("avg_score", 0)
render_marquee([
    (f"Google 評分 {rating_val:.1f} ({rating_source.split(' ')[0]})" if rating_val else "Google 評分 抓取中"),
    f"情感分數 {sentiment_score:+d}",
    f"近期新聞 {total_news} 篇",
    f"平台聲量 {platform_data.get('total', 0)} 篇",
    f"聲量趨勢 {news_trend.get('total', 0)} 篇(近6月)",
    f"品牌健康指數 {avg_indicator} 分",
    f"資料更新：{datetime.now().strftime('%m/%d %H:%M')}",
])

# ── 三分頁 ─────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🏠 主品牌現況", "⚔️ 競爭品牌對照", "🤖 口碑AI診斷"])


# ═══════════════════════════════════════════════════
# TAB 1 — 主品牌現況
# ═══════════════════════════════════════════════════
with tab1:
    # KPI Row
    st.markdown('<div class="section-header">📊 品牌健康總覽</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    review_count = rating_data.get("review_count") or cfg.get("manual_review_count")
    rating_source = rating_data.get("source", "")
    # Source badge: show which layer provided the data
    _source_icons = {
        "Google Places API":          ("🟢", "官方 Places API"),
        "SerpApi (Google Maps)":       ("🔌", "SerpApi 代理"),
        "SerpApi (Knowledge Graph)":   ("🔌", "SerpApi KG"),
        "QSC 內部週報":                ("📋", "QSC 週報同步"),
        "手動設定":                    ("🔧", "手動設定"),
    }
    _si, _sl = _source_icons.get(rating_source, ("⚠️", "未取得"))
    _rating_note = f" {_si}"
    _rating_help = (
        f"來源：{_sl}｜{rating_data.get('note', '')}\n"
        "🟢=Places API 🔌=SerpApi 📋=QSC週報 🔧=手動設定 ⚠️=未取得\n"
        "在左側品牌設定中依序設定各層以取得真實評分"
    )
    c1.metric("⭐ Google 評分",
              f"{rating_val:.1f} / 5.0{_rating_note}" if rating_val else f"—{_rating_note}",
              help=_rating_help)
    c2.metric("📝 評論數", f"{review_count:,}" if review_count else "—")
    c3.metric("📰 近期新聞", f"{total_news} 篇")
    c4.metric("🎯 情感分數", f"{sentiment_score:+d}",
              delta=f"正面 {sentiment.get('positive',0)} / 負面 {sentiment.get('negative',0)}",
              delta_color="normal")

    st.markdown(f"""
<div class="data-quality-note">
📊 <b>資料基底說明：</b>
搜尋熱度來自 Google Trends API（{cfg.get('timeframe','today 3-m')} · 地區:{cfg.get('geo','TW')}）；
口碑聲量來自 Google News RSS 搜尋；
情感分析基於 {sentiment.get('total',0)} 篇文章正負關鍵字比對（非 AI 模型）；
評分資料來自 Google 搜尋知識圖譜爬取（可能因反爬蟲機制而無法取得）。
<span class="source-badge">資料時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
<span class="source-badge">分析關鍵字：{'、'.join(brand_kws[:3])}</span>
</div>
""", unsafe_allow_html=True)

    st.divider()

    # 六大品牌健康指標 — Radar + chips
    st.markdown('<div class="section-header">🔬 六大品牌健康指標</div>', unsafe_allow_html=True)
    col_radar, col_ind = st.columns([1, 1], gap="large")

    with col_radar:
        ind_names  = [v["label"] for v in indicators.values()]
        ind_scores = [v["score"] for v in indicators.values()]
        fig_radar = go.Figure(go.Scatterpolar(
            r=ind_scores + [ind_scores[0]],
            theta=ind_names + [ind_names[0]],
            fill="toself",
            fillcolor="rgba(230,59,31,0.15)",
            line=dict(color="#E63B1F", width=2.5),
            marker=dict(size=8, color="#E63B1F"),
        ))
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], tickfont_size=9),
                angularaxis=dict(tickfont_size=12),
            ),
            showlegend=False, height=360,
            margin=dict(t=30, b=30, l=30, r=30),
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_radar, use_container_width=True, config={"displayModeBar": False})

    with col_ind:
        for name, ind_data in indicators.items():
            score = ind_data["score"]
            icon  = ind_data["icon"]
            desc  = ind_data["description"]
            color = "#27AE60" if score >= 70 else ("#E67E22" if score >= 40 else "#E74C3C")
            st.markdown(f"""
            <div style="margin-bottom:12px;">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="font-size:0.88rem;font-weight:600;">{icon} {name}</span>
                <span style="font-size:0.88rem;font-weight:700;color:{color};">{score}</span>
              </div>
              <div style="background:#F0E8E5;border-radius:6px;height:8px;">
                <div style="background:{color};width:{score}%;height:8px;border-radius:6px;"></div>
              </div>
              <div style="font-size:0.74rem;color:#999;margin-top:2px;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    # 經營人觀點
    _avg_score = ai_diagnosis.get("avg_score", 0)
    if _avg_score < 60:
        _operator_insight = "品牌整體健康度偏低，建議本季優先投資口碑修復與搜尋能見度。競品環境下，曝光不足將加速市場份額流失。"
        _insight_color = "#E74C3C"
    elif _avg_score < 75:
        _operator_insight = "品牌基礎穩固但有明顯提升空間。建議聚焦在評分提升（影響消費決策）與關鍵字覆蓋（影響獲客成本）兩個最高槓桿指標。"
        _insight_color = "#F39C12"
    else:
        _operator_insight = "品牌健康度良好。此階段適合進行品牌延伸與新客拓展，維持現有聲量優勢的同時加強差異化定位。"
        _insight_color = "#27AE60"

    st.markdown(f"""
<div style="background:linear-gradient(135deg,#FAFAFA,#F5F5F5);border:1.5px solid {_insight_color}33;
            border-left:5px solid {_insight_color};border-radius:12px;padding:1rem 1.4rem;margin:1rem 0;">
  <div style="font-size:0.8rem;color:#888;margin-bottom:4px;">👔 經營人觀點 · 基於六項指標加權分析</div>
  <div style="font-size:0.9rem;line-height:1.7;color:#333;">{_operator_insight}</div>
</div>
""", unsafe_allow_html=True)

    st.divider()

    # 品牌聲量時間趨勢
    st.markdown('<div class="section-header">📅 品牌聲量時間趨勢</div>', unsafe_allow_html=True)
    trend_data_pts = news_trend.get("data", [])
    if trend_data_pts:
        df_trend = pd.DataFrame(trend_data_pts)
        fig_trend = go.Figure()
        fig_trend.add_scatter(
            x=df_trend["month"], y=df_trend["count"],
            mode="lines+markers",
            name="新聞提及數",
            line=dict(color="#E63B1F", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(230,59,31,0.10)",
            marker=dict(size=8, color="#E63B1F"),
            text=df_trend["count"],
            textposition="top center",
        )
        fig_trend.update_layout(
            yaxis_title="月度新聞提及數", xaxis_title="月份",
            height=280, plot_bgcolor="white", paper_bgcolor="white",
            font_family="sans-serif",
            xaxis=dict(gridcolor="#F5F5F5"),
            yaxis=dict(gridcolor="#F5F5F5"),
            margin=dict(t=20, b=20),
        )
        total_mentions = news_trend.get("total", 0)
        st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})
        st.caption(f"📊 來源：Google News RSS · 過去6個月共 {total_mentions} 篇新聞提及")
    else:
        st.info("聲量趨勢數據建立中，請稍後重新抓取。")

    # Google Trends supplemental (show if available, else show info)
    if trends_data.get("available") and trends_data.get("df"):
        with st.expander("📈 Google Trends 搜尋趨勢（補充）", expanded=False):
            df_tr = pd.DataFrame(trends_data["df"])
            kw_cols = [c for c in df_tr.columns if c != "date"]
            fig_tr = go.Figure()
            for i, kw in enumerate(kw_cols):
                if kw in df_tr.columns:
                    fig_tr.add_scatter(name=kw, x=df_tr["date"], y=df_tr[kw], mode="lines",
                        line=dict(width=2, color=CHART_PALETTE[i % len(CHART_PALETTE)]))
            fig_tr.update_layout(height=260, plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_tr, use_container_width=True, config={"displayModeBar": False})
    else:
        trends_err = trends_data.get("error", "")
        if trends_err:
            st.caption(f"ℹ️ Google Trends 暫不可用：{trends_err[:80]}")

    st.divider()

    # 相關關鍵字 — multi-source logic
    # Determine which keyword source to use
    _kw_source = ""
    if related_kw.get("top") or related_kw.get("rising"):
        top_list = related_kw.get("top", [])
        rising_list = related_kw.get("rising", [])
        _kw_source = "Google Trends"
    elif search_suggestions.get("available") and (search_suggestions.get("top") or search_suggestions.get("rising")):
        top_list = search_suggestions.get("top", [])
        rising_list = search_suggestions.get("rising", [])
        _kw_source = "Google搜尋建議"
    else:
        with st.spinner("🤖 生成 AI 關鍵字建議…"):
            ai_kw = generate_ai_keywords(brand_name, brand_kws, geo=geo)
        top_list = ai_kw.get("top", [])
        rising_list = ai_kw.get("rising", [])
        _kw_source = ai_kw.get("source", "AI生成")

    _kw_badge_html = f' <span style="background:#E8F8F5;color:#1E8449;border:1px solid #A9DFBF;border-radius:4px;padding:1px 7px;font-size:0.72rem;font-weight:600;">{_kw_source}</span>'
    st.markdown(f'<div class="section-header">🏷️ 品牌相關關鍵字{_kw_badge_html}</div>', unsafe_allow_html=True)

    col_top, col_rising = st.columns(2, gap="large")
    with col_top:
        st.markdown("**🔝 熱門關鍵字**")
        if top_list:
            tags_html = "".join(
                f'<a href="https://www.google.com/search?q={item.get("query","")}" '
                f'target="_blank" class="kw-tag">{item.get("query","")}'
                f'<span style="color:#999;font-size:0.7rem;"> {item.get("value",0)}</span></a>'
                for item in top_list[:12]
            )
            st.markdown(tags_html, unsafe_allow_html=True)
        else:
            st.caption("暫無資料")
    with col_rising:
        st.markdown("**📈 上升中關鍵字**")
        if rising_list:
            tags_html = "".join(
                f'<a href="https://www.google.com/search?q={item.get("query","")}" '
                f'target="_blank" class="kw-tag rising">{item.get("query","")}'
                f'<span style="color:#888;font-size:0.7rem;"> {item.get("value","")}</span></a>'
                for item in rising_list[:12]
            )
            st.markdown(tags_html, unsafe_allow_html=True)
        else:
            st.caption("暫無資料")

    st.divider()

    # YouTube 品牌曝光
    st.markdown('<div class="section-header">▶️ YouTube 品牌曝光</div>', unsafe_allow_html=True)
    yt_videos = youtube_data.get("videos", [])
    if yt_videos:
        st.caption(f"找到 {youtube_data.get('count', 0)} 部相關影片（YouTube RSS）")
        for vid in yt_videos[:5]:
            title = vid.get("title", "")
            link = vid.get("link", "")
            pub = vid.get("published", "")
            title_html = f'<a href="{link}" target="_blank" class="news-title">{title}</a>' if link else f'<span class="news-title">{title}</span>'
            st.markdown(f'<div class="news-card"><div>{title_html}</div><div class="news-meta">YouTube · {pub}</div></div>', unsafe_allow_html=True)
    else:
        st.info("目前 YouTube 上尚無相關品牌影片，建議開始影音行銷佈局。")

    st.divider()

    # 品牌新聞動態
    st.markdown('<div class="section-header">📰 品牌新聞動態</div>', unsafe_allow_html=True)
    brand_news = fetch_google_news(brand_name, num=10)
    articles_sent = sentiment.get("articles", [])
    # Merge sentiment info into brand_news if available
    sent_map = {a.get("title", ""): a for a in articles_sent}
    if brand_news:
        for art in brand_news:
            title  = art.get("title", "（無標題）")
            link   = art.get("link", "")
            src    = art.get("source", "")
            dt     = art.get("pub_date", "")[:16] if art.get("pub_date") else ""
            desc   = art.get("description", "")[:150]
            sent_info = sent_map.get(title, {})
            sent_cls   = sent_info.get("sentiment", "neutral")
            sent_label = sent_info.get("sentiment_label", "中性")
            title_html = (f'<a href="{link}" target="_blank" class="news-title">{title}</a>'
                          if link else f'<span class="news-title">{title}</span>')
            st.markdown(f"""
<div class="news-card {sent_cls}">
  {title_html}
  <div class="news-meta">{src} · {dt} · <span class="sentiment-{sent_cls}">{sent_label}</span></div>
  <div class="news-desc">{desc}</div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("暫無品牌新聞資料。")


# ═══════════════════════════════════════════════════
# TAB 2 — 競爭品牌對照
# ═══════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-header">⚔️ 競品搜尋聲量比較</div>', unsafe_allow_html=True)

    if trends_data.get("available") and trends_data.get("df"):
        df_tr_all = pd.DataFrame(trends_data["df"])
        kw_cols_all = [c for c in df_tr_all.columns if c != "date"]

        if len(kw_cols_all) > 1:
            # Grouped bar: each keyword's average interest
            avg_vals = {kw: df_tr_all[kw].mean() for kw in kw_cols_all if kw in df_tr_all.columns}
            df_avg = pd.DataFrame([
                {"品牌/關鍵字": k, "平均搜尋量": round(v, 1)}
                for k, v in sorted(avg_vals.items(), key=lambda x: -x[1])
            ])
            bar_colors = [CHART_PALETTE[i % len(CHART_PALETTE)] for i in range(len(df_avg))]
            fig_cmp = go.Figure(go.Bar(
                x=df_avg["品牌/關鍵字"], y=df_avg["平均搜尋量"],
                marker_color=bar_colors,
                text=df_avg["平均搜尋量"],
                textposition="outside",
            ))
            fig_cmp.update_layout(
                title="搜尋聲量對比（平均指數）", yaxis_title="平均搜尋量指數",
                plot_bgcolor="white", paper_bgcolor="white",
                height=320, font_family="sans-serif",
            )
            st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar": False})

            st.divider()

            # Pie: search share
            st.markdown('<div class="section-header">📊 搜尋聲量份額</div>', unsafe_allow_html=True)
            fig_pie = go.Figure(go.Pie(
                labels=df_avg["品牌/關鍵字"].tolist(),
                values=df_avg["平均搜尋量"].tolist(),
                marker_colors=CHART_PALETTE[:len(df_avg)],
                textinfo="label+percent",
                hole=0.35,
            ))
            fig_pie.update_layout(
                height=320, margin=dict(t=20, b=10, l=10, r=10),
                paper_bgcolor="white", showlegend=True,
            )
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("需要至少設定一個競品才能顯示對比圖表。請在側邊欄品牌設定中新增競品。")
    else:
        st.info("Google Trends 資料暫不可用，無法顯示競品對比圖表。")

    st.divider()

    # 各競品最新動態
    st.markdown('<div class="section-header">📰 各競品最新動態</div>', unsafe_allow_html=True)
    if comp_news:
        brand_news_map = {}
        for art in comp_news:
            b = art.get("brand", "其他")
            brand_news_map.setdefault(b, []).append(art)

        comp_tabs = st.tabs([f"⚔️ {b} ({len(arts)})" for b, arts in brand_news_map.items()])
        for ctab, (comp_brand, arts) in zip(comp_tabs, brand_news_map.items()):
            with ctab:
                for art in arts[:5]:
                    src   = art.get("source", "")
                    dt    = art.get("pub_date", "")[:16] if art.get("pub_date") else ""
                    title = art.get("title", "（無標題）")
                    link  = art.get("link", "")
                    desc  = art.get("description", "")[:120]
                    title_html = (f'<a href="{link}" target="_blank" class="news-title">{title}</a>'
                                  if link else f'<span class="news-title">{title}</span>')
                    st.markdown(f"""
<div class="news-card">
  {title_html}
  <div class="news-meta">{src} · {dt}</div>
  <div class="news-desc">{desc}</div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("⚠️ 暫無競品活動新聞，請稍後再試或調整競品設定。")

    st.divider()

    # 競品指標比較表
    st.markdown('<div class="section-header">📋 競品指標比較表</div>', unsafe_allow_html=True)
    st.caption("六維指標綜合分數（0–100）。搜尋熱度來自 Google Trends，口碑聲量／情感分數來自 Google News，評分指數來自 Google 評分換算。")

    ind_names_list = list(indicators.keys())
    comp_table_rows = []
    comp_table_rows.append({
        "品牌": f"🔴 {brand_name}（本品）",
        **{n: indicators[n]["score"] for n in ind_names_list}
    })

    comp_score_cache = {}
    for comp_b in competitors[:5]:
        with st.spinner(f"📡 抓取 {comp_b} 數據…"):
            cdata = get_competitor_scores(comp_b)
        comp_score_cache[comp_b] = cdata
        sc = cdata.get("scores", {})
        row = {"品牌": comp_b}
        for n in ind_names_list:
            v = sc.get(n)
            row[n] = v if v is not None else "—"
        comp_table_rows.append(row)

    df_comp_table = pd.DataFrame(comp_table_rows)
    # Ensure mixed int/str columns are all object type to avoid PyArrow conversion errors
    for _col in df_comp_table.columns:
        if _col != "品牌":
            df_comp_table[_col] = df_comp_table[_col].apply(
                lambda v: str(int(v)) if isinstance(v, (int, float)) and not pd.isna(v) else ("—" if v is None or str(v) in ("None", "nan") else str(v))
            )
    st.dataframe(df_comp_table, use_container_width=True, hide_index=True)

    # Competitor Radar Chart
    st.divider()
    st.markdown('<div class="section-header">🕸️ 競品六維雷達對比</div>', unsafe_allow_html=True)

    radar_dims = ["口碑聲量", "情感分數", "評分指數"]
    own_vals = [indicators[d]["score"] for d in radar_dims]

    fig_radar_comp = go.Figure()
    # Own brand
    fig_radar_comp.add_trace(go.Scatterpolar(
        r=own_vals + [own_vals[0]],
        theta=radar_dims + [radar_dims[0]],
        fill="toself",
        fillcolor="rgba(230,59,31,0.15)",
        line=dict(color="#E63B1F", width=2.5),
        name=f"🔴 {brand_name}",
    ))

    # Competitors
    comp_colors = ["#4A90E2", "#27AE60", "#9B59B6", "#F39C12", "#1ABC9C"]
    comp_fill_colors = ["rgba(74,144,226,0.08)", "rgba(39,174,96,0.08)", "rgba(155,89,182,0.08)", "rgba(243,156,18,0.08)", "rgba(26,188,156,0.08)"]
    for ci, (comp_b, cdata) in enumerate(comp_score_cache.items()):
        sc = cdata.get("scores", {})
        comp_vals = [sc.get(d) for d in radar_dims]
        # Skip if all None
        if all(v is None for v in comp_vals):
            continue
        # Replace None with 0 for plotting
        comp_vals_plot = [v if v is not None else 0 for v in comp_vals]
        fig_radar_comp.add_trace(go.Scatterpolar(
            r=comp_vals_plot + [comp_vals_plot[0]],
            theta=radar_dims + [radar_dims[0]],
            fill="toself",
            fillcolor=comp_fill_colors[ci % len(comp_fill_colors)],
            line=dict(color=comp_colors[ci % len(comp_colors)], width=2),
            name=comp_b,
        ))

    fig_radar_comp.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickfont_size=9),
            angularaxis=dict(tickfont_size=12),
        ),
        showlegend=True,
        legend=dict(orientation="h", y=-0.15),
        height=380,
        margin=dict(t=30, b=60, l=30, r=30),
        paper_bgcolor="white",
    )
    st.plotly_chart(fig_radar_comp, use_container_width=True, config={"displayModeBar": False})
    st.caption("雷達對比維度：口碑聲量（Google News 提及數）、情感分數（正面評論佔比）、評分指數（Google評分換算）。「—」代表數據未取得，以0分繪製。")

    # Show ratings and news for competitors
    st.markdown("**競品評分與聲量詳情**")
    for comp_b, cdata in comp_score_cache.items():
        if cdata.get("available"):
            rating = cdata.get("rating")
            news_cnt = cdata.get("news_count", 0)
            sent = cdata.get("sentiment_score", 0)
            rating_str = f"⭐ {rating:.1f}" if rating else "⭐ 未取得"
            st.markdown(f"**{comp_b}** — {rating_str} ｜ 📰 近期新聞 {news_cnt} 篇 ｜ 情感 {sent:+d}")
        else:
            st.markdown(f"**{comp_b}** — 暫無資料")

    st.caption("搜尋熱度（🔍）和關鍵字覆蓋（🏷️）需 Google Trends 跨品牌查詢，以「—」標示。競品數據來源同本品：Google News RSS + Google評分爬取。")


# ═══════════════════════════════════════════════════
# TAB 3 — 口碑AI診斷
# ═══════════════════════════════════════════════════
with tab3:
    # 台灣各平台聲量分佈
    st.markdown('<div class="section-header">🌐 台灣各平台聲量分佈</div>', unsafe_allow_html=True)
    platform_counts = platform_data.get("platforms", {})
    if platform_counts:
        df_plat = pd.DataFrame([
            {"平台": k, "文章數": v}
            for k, v in platform_counts.items() if v > 0
        ]).sort_values("文章數", ascending=True)
        if not df_plat.empty:
            _plat_colors = [CHART_PALETTE[i % len(CHART_PALETTE)] for i in range(len(df_plat))]
            fig_plat = go.Figure(go.Bar(
                x=df_plat["文章數"], y=df_plat["平台"],
                orientation="h",
                marker=dict(color=_plat_colors),
                text=df_plat["文章數"],
                textposition="outside",
            ))
            fig_plat.update_layout(
                title=f"台灣平台聲量（共 {platform_data.get('total',0)} 篇）",
                xaxis_title="文章數", height=360,
                plot_bgcolor="white", paper_bgcolor="white",
                font_family="sans-serif",
            )
            st.plotly_chart(fig_plat, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("各平台目前無相關文章，品牌聲量有待提升。")
    else:
        st.info("平台聲量資料載入中，請稍候或點擊重新抓取。")

    st.divider()

    # 跨平台中位數情感分析 — Gauge
    st.markdown('<div class="section-header">📊 跨平台中位數情感分析</div>', unsafe_allow_html=True)
    median_sent = platform_stats.get("median_sentiment", 0)
    col_g, col_g2 = st.columns([1, 2], gap="large")
    with col_g:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=median_sent,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "跨平台中位數情感"},
            delta={"reference": 0},
            gauge={
                "axis": {"range": [-100, 100]},
                "bar": {"color": "#E63B1F"},
                "steps": [
                    {"range": [-100, -30], "color": "#FDECEC"},
                    {"range": [-30, 30],   "color": "#FEF9E7"},
                    {"range": [30, 100],   "color": "#E9F7EF"},
                ],
                "threshold": {"line": {"color": "#333", "width": 2},
                              "thickness": 0.75, "value": 0},
            }
        ))
        fig_gauge.update_layout(
            height=250, margin=dict(t=30, b=10, l=20, r=20),
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})
        st.caption(f"基於 {platform_stats.get('total_volume', 0)} 篇跨平台文章計算")
    with col_g2:
        pb = platform_stats.get("platform_breakdown", {})
        if pb:
            pb_rows = []
            for plat_name, pd_data in pb.items():
                total_p = pd_data.get("total", 0)
                if total_p > 0:
                    pos_r = round(pd_data.get("pos", 0) / total_p * 100)
                    neg_r = round(pd_data.get("neg", 0) / total_p * 100)
                    pb_rows.append({
                        "平台": plat_name,
                        "文章總數": total_p,
                        "正面%": f"{pos_r}%",
                        "負面%": f"{neg_r}%",
                        "中性%": f"{100-pos_r-neg_r}%",
                    })
            if pb_rows:
                df_pb = pd.DataFrame(pb_rows)
                st.dataframe(df_pb, use_container_width=True, hide_index=True)

    st.divider()

    # AI 診斷報告
    st.markdown('<div class="section-header">🤖 AI 品牌健康診斷報告</div>', unsafe_allow_html=True)

    if ai_diagnosis.get("ai_powered"):
        st.success("🤖 本報告由 Claude AI 自動分析生成")
    else:
        st.info("📊 本報告由規則引擎生成 · 如需 AI 深度分析請設定 ANTHROPIC_API_KEY 環境變數")

    _pb_count = len(platform_stats.get("platform_breakdown", {}))
    st.markdown(f"""
<div class="data-quality-note">
🌐 <b>口碑數據基底：</b>
本分析基於 {platform_data.get('total',0)} 篇跨平台文章（{', '.join(list(TAIWAN_PLATFORMS.keys())[:5])} 等 {len(TAIWAN_PLATFORMS)} 個平台），
透過 Google News RSS 以站點篩選方式抓取。情感判斷為關鍵字規則引擎（非語意模型），結果為近似值。
<span class="source-badge">中位數計算基於 {_pb_count} 個有效平台</span>
</div>
""", unsafe_allow_html=True)

    summary_lines = ai_diagnosis.get("summary", [])
    warnings_list = ai_diagnosis.get("warnings", [])
    opportunities = ai_diagnosis.get("opportunities", [])
    discussion_topics = ai_diagnosis.get("discussion_topics", [])

    if summary_lines:
        for sl in summary_lines:
            st.info(sl)

    col_warn, col_opp = st.columns(2, gap="large")
    with col_warn:
        st.markdown("**🚨 警示項目**")
        if warnings_list:
            for w in warnings_list:
                st.markdown(f'<div class="warning-card">⚠️ {w}</div>', unsafe_allow_html=True)
        else:
            st.success("目前無警示項目")

    with col_opp:
        st.markdown("**✅ 機會點**")
        if opportunities:
            for o in opportunities:
                st.markdown(f'<div class="opportunity-card">{o}</div>', unsafe_allow_html=True)
        else:
            st.info("暫無特殊機會點")

    if discussion_topics:
        st.divider()
        st.markdown("**💬 可討論議題**")
        for i, topic in enumerate(discussion_topics, 1):
            st.markdown(f'<div class="discussion-item">{i}. {topic}</div>', unsafe_allow_html=True)

    st.divider()

    # 各平台文章列表（可展開）
    st.markdown('<div class="section-header">📋 各平台文章列表</div>', unsafe_allow_html=True)
    plat_articles = platform_stats.get("articles", platform_data.get("articles", []))
    if plat_articles:
        # Group by platform
        plat_art_map = {}
        for art in plat_articles:
            p = art.get("platform", "其他")
            plat_art_map.setdefault(p, []).append(art)

        for plat_name, arts in plat_art_map.items():
            with st.expander(f"📌 {plat_name} ({len(arts)} 篇)", expanded=False):
                for art in arts[:8]:
                    title  = art.get("title", "（無標題）")
                    link   = art.get("link", "")
                    src    = art.get("source", "")
                    dt     = art.get("pub_date", "")[:16] if art.get("pub_date") else ""
                    desc   = art.get("description", "")[:120]
                    sent_c = art.get("sentiment", "neutral")
                    sent_labels = {"positive": "正面", "negative": "負面", "neutral": "中性"}
                    sent_l = sent_labels.get(sent_c, "中性")
                    title_html = (f'<a href="{link}" target="_blank" class="news-title">{title}</a>'
                                  if link else f'<span class="news-title">{title}</span>')
                    st.markdown(f"""
<div class="news-card {sent_c}">
  {title_html}
  <div class="news-meta">{src} · {dt} · <span class="sentiment-{sent_c}">{sent_l}</span></div>
  <div class="news-desc">{desc}</div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("暫無各平台文章資料，請稍後重新抓取。")

# ── Footer ─────────────────────────────────────────
st.divider()
st.caption(f"🕐 資料抓取時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ｜ 數據來源：Google Trends / Google News / 台灣各大平台")
