"""
品牌監控爬蟲系統 — Brand Monitoring Scraper Engine
數據來源: Google Trends / Google News RSS / Google Search / 情感分析
"""
from __future__ import annotations
import re
import time
import json
import io
import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
from typing import Optional

# ──────────────────────────────────────────────
# 安全 import（缺套件時優雅降級）
# ──────────────────────────────────────────────
# ── urllib3 v2 相容修補：method_whitelist → allowed_methods ──────────────
try:
    from urllib3.util.retry import Retry as _Retry
    _orig_retry_init = _Retry.__init__
    def _patched_retry_init(self, *args, **kwargs):
        if "method_whitelist" in kwargs:
            kwargs["allowed_methods"] = kwargs.pop("method_whitelist")
        _orig_retry_init(self, *args, **kwargs)
    _Retry.__init__ = _patched_retry_init  # type: ignore[method-assign]
except Exception:
    pass

try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
except ImportError:
    HAS_PYTRENDS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import anthropic as _anthropic_mod
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _make_pytrends(hl: str = "zh-TW", tz: int = 480):
    """Create TrendReq compatible with old and new urllib3 (method_whitelist → allowed_methods)."""
    if not HAS_PYTRENDS:
        return None
    for kwargs in [
        {"hl": hl, "tz": tz, "timeout": (10, 30), "retries": 2, "backoff_factor": 0.2},
        {"hl": hl, "tz": tz, "timeout": (10, 30)},
        {"hl": hl, "tz": tz},
    ]:
        try:
            return TrendReq(**kwargs)
        except TypeError:
            continue
    return None


# ──────────────────────────────────────────────
# Google Trends
# ──────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_trends_interest(keywords: list, timeframe: str = "today 3-m", geo: str = "TW") -> dict:
    """Get Google Trends search interest over time for up to 5 keywords."""
    if not HAS_PYTRENDS:
        return {"error": "pytrends 未安裝", "df": [], "available": False}
    if not keywords:
        return {"error": "請輸入關鍵字", "df": [], "available": False}

    try:
        pytrends = _make_pytrends()
        if pytrends is None:
            return {"error": "pytrends 初始化失敗", "df": [], "available": False}
        kw_list = [str(k).strip() for k in keywords[:5] if str(k).strip()]
        pytrends.build_payload(kw_list, timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()

        if df.empty:
            return {"error": "Google Trends 無資料", "df": [], "available": False}

        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])

        df = df.reset_index()
        df["date"] = df["date"].astype(str)
        return {
            "available": True,
            "df": df.to_dict("records"),
            "keywords": kw_list,
            "timeframe": timeframe,
        }
    except Exception as e:
        return {"error": str(e), "df": [], "available": False}


@st.cache_data(ttl=3600, show_spinner=False)
def get_related_keywords(keyword: str, geo: str = "TW") -> dict:
    """Get related and rising keywords from Google Trends."""
    if not HAS_PYTRENDS:
        return {"top": [], "rising": [], "available": False}

    try:
        pytrends = _make_pytrends()
        if pytrends is None:
            return {"top": [], "rising": [], "available": False}
        pytrends.build_payload([keyword], timeframe="today 1-m", geo=geo)
        related = pytrends.related_queries()

        top_list, rising_list = [], []
        if keyword in related:
            top_df = related[keyword].get("top")
            rising_df = related[keyword].get("rising")
            if top_df is not None and not top_df.empty:
                top_list = top_df.head(15).to_dict("records")
            if rising_df is not None and not rising_df.empty:
                rising_list = rising_df.head(15).to_dict("records")

        return {"top": top_list, "rising": rising_list, "available": True, "keyword": keyword}
    except Exception as e:
        return {"top": [], "rising": [], "available": False, "error": str(e)}


# ──────────────────────────────────────────────
# Google News RSS
# ──────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_google_news(query: str, num: int = 15) -> list:
    """Fetch news articles from Google News RSS feed."""
    articles = []
    try:
        encoded_q = requests.utils.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code != 200:
            return articles

        if HAS_BS4:
            soup = BeautifulSoup(resp.content, "xml")
            items = soup.find_all("item")[:num]
            for item in items:
                title_tag = item.find("title")
                link_tag = item.find("link")
                pub_tag = item.find("pubDate")
                source_tag = item.find("source")
                desc_tag = item.find("description")

                title = title_tag.get_text(strip=True) if title_tag else ""
                # Remove source suffix from title (e.g. " - 蘋果日報")
                title = re.sub(r'\s*-\s*[^-]+$', '', title).strip()

                articles.append({
                    "title": title,
                    "link": link_tag.get_text(strip=True) if link_tag else "",
                    "pub_date": pub_tag.get_text(strip=True) if pub_tag else "",
                    "source": source_tag.get_text(strip=True) if source_tag else "Google News",
                    "description": re.sub(r'<[^>]+>', '', desc_tag.get_text(strip=True) if desc_tag else "")[:200],
                })
        else:
            # Fallback: simple regex parsing
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', resp.text)
            for t in titles[1:num+1]:  # skip first (feed title)
                articles.append({"title": t, "link": "", "pub_date": "", "source": "", "description": ""})
    except Exception:
        pass
    return articles


# ──────────────────────────────────────────────
# Google 評分 — 三層動態資產架構
# Layer 1: Google Places API (官方)
# Layer 2: SerpApi / Outscraper (中繼代理)
# Layer 3: QSC 內部 Google Sheets (業務鉤稽)
# Layer 4: 手動輸入
# Layer 5: 爬蟲抓取 (fallback)
# ──────────────────────────────────────────────

def _get_rating_via_places_api(place_ids: list, api_key: str) -> Optional[dict]:
    """
    Layer 1: Google Maps Places API (官方付費，每月 $200 免費額度)
    place_ids: ["ChIJxxx...", "門市名稱:ChIJyyy..."]
    """
    all_ratings: list[float] = []
    all_counts: list[int] = []
    top_reviews: list[dict] = []

    for pid_entry in place_ids[:6]:
        pid = str(pid_entry).split(":")[-1].strip()
        if not pid or not pid.startswith("ChIJ"):
            continue
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/place/details/json",
                params={
                    "place_id": pid,
                    "fields": "name,rating,user_ratings_total,reviews",
                    "key": api_key,
                    "language": "zh-TW",
                },
                timeout=10,
            )
            data = resp.json()
            if data.get("status") != "OK":
                continue
            r = data["result"]
            if r.get("rating"):
                all_ratings.append(float(r["rating"]))
            if r.get("user_ratings_total"):
                all_counts.append(int(r["user_ratings_total"]))
            for rev in r.get("reviews", [])[:3]:
                top_reviews.append({
                    "author": rev.get("author_name", ""),
                    "rating": rev.get("rating", 0),
                    "text": rev.get("text", "")[:200],
                    "time": rev.get("relative_time_description", ""),
                })
        except Exception:
            continue

    if not all_ratings:
        return None
    return {
        "rating": round(sum(all_ratings) / len(all_ratings), 1),
        "review_count": sum(all_counts) if all_counts else None,
        "reviews": top_reviews,
        "available": True,
        "source": "Google Places API",
        "note": f"整合 {len(all_ratings)} 間門市官方評分",
    }


def _get_rating_via_serpapi(brand_name: str, api_key: str) -> Optional[dict]:
    """
    Layer 2: SerpApi — 代勞 Google 反爬，5 行實作，穩定不受 DOM 變動影響
    支援 SerpApi (serpapi.com) 及 Outscraper (outscraper.com) 格式
    """
    try:
        # SerpApi — Google Maps engine
        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_maps",
                "q": brand_name,
                "api_key": api_key,
                "hl": "zh-tw",
                "gl": "tw",
            },
            timeout=15,
        )
        data = resp.json()
        results = data.get("local_results", [])
        if results:
            ratings = [float(r["rating"]) for r in results[:5] if r.get("rating")]
            counts  = [int(r.get("reviews", 0)) for r in results[:5] if r.get("reviews")]
            if ratings:
                return {
                    "rating": round(sum(ratings) / len(ratings), 1),
                    "review_count": sum(counts) if counts else None,
                    "available": True,
                    "source": "SerpApi (Google Maps)",
                    "note": f"整合 {len(ratings)} 筆門市資料",
                }

        # SerpApi — Google Knowledge Panel fallback
        resp2 = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google",
                "q": brand_name,
                "api_key": api_key,
                "hl": "zh-tw",
                "gl": "tw",
            },
            timeout=15,
        )
        kp = resp2.json().get("knowledge_graph", {})
        if kp.get("rating"):
            return {
                "rating": float(kp["rating"]),
                "review_count": kp.get("reviews"),
                "available": True,
                "source": "SerpApi (Knowledge Graph)",
                "note": "來自 Google 搜尋知識面板",
            }
    except Exception:
        pass
    return None


def _get_rating_from_qsc_sheet(sheet_id: str, rating_col: str = "Google評分") -> Optional[dict]:
    """
    Layer 3: QSC 內部週報 Google Sheets — 業務數據同步，非手動輸入
    欄位格式：門市名稱 | Google評分 | 評論數 | 週次
    """
    try:
        from utils.sheet_validator import load_sheet_by_gid
        df = load_sheet_by_gid(sheet_id, "0")
        if df.empty:
            return None

        cols_lower = {c.strip().lower(): c for c in df.columns}
        # Try to find the rating column
        target = None
        for candidate in [rating_col, "Google評分", "google評分", "評分", "rating", "Google Rating"]:
            if candidate.strip().lower() in cols_lower:
                target = cols_lower[candidate.strip().lower()]
                break

        if not target:
            return None

        # Find review count column
        count_col = None
        for candidate in ["評論數", "評論總數", "review_count", "reviews", "評論"]:
            if candidate.strip().lower() in cols_lower:
                count_col = cols_lower[candidate.strip().lower()]
                break

        # Get latest valid rating (last non-null row)
        valid = df[df[target].notna()]
        if valid.empty:
            return None

        latest_row = valid.iloc[-1]
        raw = str(latest_row[target]).strip().replace("★", "").replace("⭐", "").replace(" ", "")
        try:
            r = float(raw)
            if not (1.0 <= r <= 5.0):
                return None
        except ValueError:
            return None

        count = None
        if count_col:
            try:
                count = int(float(str(latest_row.get(count_col, "")).replace(",", "")))
            except Exception:
                pass

        return {
            "rating": round(r, 1),
            "review_count": count,
            "available": True,
            "source": "QSC 內部週報",
            "note": f"Google Sheets 欄位「{target}」同步",
        }
    except Exception:
        return None


@st.cache_data(ttl=7200, show_spinner=False)
def get_brand_google_rating(
    brand_name: str,
    manual_rating=None,
    manual_review_count=None,
    place_ids: tuple = (),      # tuple for @st.cache_data hashability
    qsc_sheet_id: str = "",
    qsc_rating_col: str = "Google評分",
) -> dict:
    """
    動態資產評分取得 — 五層優先級瀑布：
    1. Google Places API  (GOOGLE_PLACES_API_KEY env + place_ids in config)
    2. SerpApi            (SERPAPI_KEY env)
    3. QSC Google Sheets  (qsc_sheet_id in config)
    4. 手動輸入           (manual_rating in config)
    5. 爬蟲 fallback      (Google Search knowledge panel)
    """
    _base = {
        "brand": brand_name,
        "rating": None,
        "review_count": None,
        "reviews": [],
        "available": False,
        "source": "",
        "note": "",
        "search_queries": [],
    }

    # ── Layer 1: Google Places API ───────────────
    places_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not places_key:
        try:
            places_key = st.secrets.get("GOOGLE_PLACES_API_KEY", "") or ""
        except Exception:
            pass
    if places_key and place_ids:
        res = _get_rating_via_places_api(list(place_ids), places_key)
        if res:
            return {**_base, **res, "brand": brand_name}

    # ── Layer 2: SerpApi ─────────────────────────
    serp_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not serp_key:
        try:
            serp_key = st.secrets.get("SERPAPI_KEY", "") or ""
        except Exception:
            pass
    if serp_key:
        res = _get_rating_via_serpapi(brand_name, serp_key)
        if res:
            return {**_base, **res, "brand": brand_name}

    # ── Layer 3: QSC Google Sheets ───────────────
    if qsc_sheet_id.strip():
        res = _get_rating_from_qsc_sheet(qsc_sheet_id.strip(), qsc_rating_col)
        if res:
            return {**_base, **res, "brand": brand_name}

    # ── Layer 4: 手動輸入 ────────────────────────
    if manual_rating:
        return {**_base,
            "rating": float(manual_rating),
            "review_count": int(manual_review_count) if manual_review_count else None,
            "available": True,
            "source": "手動設定",
            "note": "管理員手動輸入",
        }

    result = {
        "brand": brand_name,
        "rating": None,
        "review_count": None,
        "available": False,
        "source": "Google Search (knowledge panel scraping)",
        "search_queries": [],
        "note": "",
    }

    # Try multiple search queries
    queries = [
        f"{brand_name} 餐廳評分",
        f"{brand_name} Google評分",
        f"{brand_name} 台灣 評論",
        f"{brand_name} 石鍋 評分",
    ]

    all_ratings: list[float] = []
    all_review_counts: list[int] = []

    for query in queries:
        try:
            encoded = requests.utils.quote(query)
            url = f"https://www.google.com/search?q={encoded}&hl=zh-TW&gl=TW"
            resp = requests.get(url, headers=HEADERS, timeout=12)
            result["search_queries"].append(query)

            if not HAS_BS4 or resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            text = resp.text

            # JSON-LD
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    agg = data.get("aggregateRating", {}) if isinstance(data, dict) else {}
                    if agg.get("ratingValue"):
                        r = float(agg["ratingValue"])
                        c = int(agg.get("reviewCount", 0) or agg.get("ratingCount", 0))
                        if 1.0 <= r <= 5.0:
                            all_ratings.append(r)
                        if c > 0:
                            all_review_counts.append(c)
                except Exception:
                    pass

            # Regex patterns
            for m in re.finditer(r'"ratingValue":\s*"?([1-5]\.[0-9])"?', text):
                try:
                    r = float(m.group(1))
                    if 1.0 <= r <= 5.0:
                        all_ratings.append(r)
                except Exception:
                    pass

            for m in re.finditer(r'"reviewCount":\s*"?(\d+)"?', text):
                c = int(m.group(1))
                if c > 0:
                    all_review_counts.append(c)

            # Pattern for "X 則評論" or "X 筆評論"
            for m in re.finditer(r'([\d,]+)\s*(?:則|筆|個)?評論', text):
                c = int(m.group(1).replace(",", ""))
                if c > 0:
                    all_review_counts.append(c)

            time.sleep(0.3)
        except Exception:
            continue

    if all_ratings:
        result["rating"] = round(sum(all_ratings) / len(all_ratings), 1)
        result["available"] = True

    if all_review_counts:
        result["review_count"] = max(all_review_counts)

    if not result["rating"]:
        result["rating"] = None
        result["note"] = "反爬蟲機制阻擋，建議在品牌設定中手動輸入評分"

    return result


@st.cache_data(ttl=7200, show_spinner=False)
def get_competitor_overview(competitor: str) -> dict:
    """Get competitor brand rating and news using same methodology as own brand."""
    rating = get_brand_google_rating(competitor)
    news = fetch_google_news(competitor, num=8)
    sentiment_data = analyze_brand_sentiment([competitor])
    return {
        "name": competitor,
        "rating": rating,
        "news_count": len(news),
        "news": news,
        "sentiment_score": sentiment_data.get("score", 0),
        "sentiment_pos": sentiment_data.get("positive", 0),
        "sentiment_neg": sentiment_data.get("negative", 0),
    }


@st.cache_data(ttl=7200, show_spinner=False)
def get_multi_store_ratings(brand_name: str, store_list: list) -> list:
    """Get Google ratings for multiple store locations."""
    results = []
    for store in store_list[:8]:  # limit to avoid rate limiting
        query_name = f"{brand_name} {store}"
        r = get_brand_google_rating(query_name)
        r["store"] = store
        results.append(r)
        time.sleep(0.5)
    return results


# ──────────────────────────────────────────────
# 網路聲量分析
# ──────────────────────────────────────────────
POSITIVE_KW = [
    "好吃", "美味", "推薦", "必訪", "好評", "滿意", "棒", "讚", "熱門", "人氣",
    "新開", "開幕", "升級", "促銷", "優惠", "活動", "首選", "必吃", "網紅打卡",
    "排隊", "值得", "回訪", "喜歡", "超值", "豐盛", "新菜", "限定",
]
NEGATIVE_KW = [
    "難吃", "差評", "失望", "客訴", "抱怨", "食安", "問題", "不新鮮",
    "服務差", "等很久", "太貴", "不推", "避雷", "地雷", "關門", "歇業",
    "衛生", "異物", "投訴", "垃圾", "爛", "坑",
]


@st.cache_data(ttl=1800, show_spinner=False)
def analyze_brand_sentiment(keywords: list) -> dict:
    """Analyze online sentiment for brand from news articles."""
    result = {
        "positive": 0, "negative": 0, "neutral": 0,
        "total": 0, "score": 0,
        "articles": [], "available": False,
    }

    try:
        all_articles = []
        for kw in keywords[:3]:
            arts = fetch_google_news(kw, num=8)
            all_articles.extend(arts)
            time.sleep(0.3)

        seen_titles = set()
        unique_articles = []
        for a in all_articles:
            t = a.get("title", "")
            if t and t not in seen_titles:
                seen_titles.add(t)
                unique_articles.append(a)

        result["total"] = len(unique_articles)
        result["available"] = True

        for article in unique_articles:
            text = (article.get("title", "") + " " + article.get("description", "")).lower()
            pos = sum(1 for kw in POSITIVE_KW if kw in text)
            neg = sum(1 for kw in NEGATIVE_KW if kw in text)

            if pos > neg:
                result["positive"] += 1
                article["sentiment"] = "positive"
                article["sentiment_label"] = "正面"
            elif neg > pos:
                result["negative"] += 1
                article["sentiment"] = "negative"
                article["sentiment_label"] = "負面"
            else:
                result["neutral"] += 1
                article["sentiment"] = "neutral"
                article["sentiment_label"] = "中性"

            result["articles"].append(article)

        if result["total"] > 0:
            result["score"] = round(
                (result["positive"] - result["negative"]) / result["total"] * 100
            )
    except Exception as e:
        result["error"] = str(e)

    return result


# ──────────────────────────────────────────────
# 競品活動監控
# ──────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def scrape_competitor_news(competitors: list, max_per_brand: int = 5) -> list:
    """Scrape latest news/activities for competitor brands."""
    all_news = []
    for brand in competitors[:6]:
        query = f"{brand} 活動 優惠 新菜 新開"
        articles = fetch_google_news(query, num=max_per_brand)
        for a in articles:
            a["brand"] = brand
            all_news.append(a)
        time.sleep(0.4)

    # Sort: try to parse date
    def _parse_date(s: str):
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(s)
        except Exception:
            return datetime.min.replace(tzinfo=None)

    try:
        all_news.sort(key=lambda x: _parse_date(x.get("pub_date", "")), reverse=True)
    except Exception:
        pass

    return all_news[:30]


# ──────────────────────────────────────────────
# 六項品牌健康指標
# ──────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def calculate_six_indicators(
    brand_keyword: str,
    competitors: list,
    brand_rating: Optional[float] = None,
) -> dict:
    """
    Calculate six brand health indicators (0-100 scale).
    Returns dict with indicator name -> {score, label, description, icon}.
    """
    indicators = {
        "搜尋熱度":   {"score": 0, "label": "搜尋熱度",   "icon": "🔍", "description": "Google Trends 近3個月平均搜尋量"},
        "口碑聲量":   {"score": 0, "label": "口碑聲量",   "icon": "📢", "description": "網路新聞提及量（近期）"},
        "情感分數":   {"score": 0, "label": "情感分數",   "icon": "😊", "description": "正面評論佔比"},
        "競品對比":   {"score": 0, "label": "競品對比",   "icon": "⚔️", "description": "相對競品的搜尋份額"},
        "關鍵字覆蓋": {"score": 0, "label": "關鍵字覆蓋", "icon": "🏷️", "description": "相關搜尋關鍵字數量"},
        "評分指數":   {"score": 0, "label": "評分指數",   "icon": "⭐", "description": "Google 綜合評分換算"},
    }

    # 1. 搜尋熱度 + 競品對比 from Trends
    if HAS_PYTRENDS:
        try:
            pytrends = _make_pytrends()
            if pytrends is None:
                raise RuntimeError("pytrends 初始化失敗")
            all_kws = [brand_keyword] + [c for c in competitors[:4] if c != brand_keyword]
            all_kws = all_kws[:5]
            pytrends.build_payload(all_kws, timeframe="today 3-m", geo="TW")
            df = pytrends.interest_over_time()

            if not df.empty and brand_keyword in df.columns:
                brand_avg = df[brand_keyword].mean()
                indicators["搜尋熱度"]["score"] = min(100, round(brand_avg))

                comp_avgs = [df[c].mean() for c in competitors if c in df.columns]
                if comp_avgs:
                    total = brand_avg + sum(comp_avgs)
                    indicators["競品對比"]["score"] = min(100, round(brand_avg / total * 100)) if total > 0 else 50
                else:
                    indicators["競品對比"]["score"] = 55

            # 關鍵字覆蓋
            time.sleep(0.5)
            pytrends.build_payload([brand_keyword], timeframe="today 1-m", geo="TW")
            related = pytrends.related_queries()
            if brand_keyword in related:
                top = related[brand_keyword].get("top")
                cnt = len(top) if top is not None else 0
                indicators["關鍵字覆蓋"]["score"] = min(100, cnt * 5)
        except Exception:
            indicators["搜尋熱度"]["score"] = 50
            indicators["競品對比"]["score"] = 50
            indicators["關鍵字覆蓋"]["score"] = 40
    else:
        indicators["搜尋熱度"]["score"] = 50
        indicators["競品對比"]["score"] = 50
        indicators["關鍵字覆蓋"]["score"] = 40

    # 2. 口碑聲量 from news count
    try:
        news = fetch_google_news(brand_keyword, num=20)
        cnt = len(news)
        indicators["口碑聲量"]["score"] = min(100, cnt * 5)
    except Exception:
        indicators["口碑聲量"]["score"] = 35

    # 3. 情感分數
    try:
        sentiment = analyze_brand_sentiment([brand_keyword])
        total = sentiment.get("total", 0)
        if total > 0:
            pos_ratio = sentiment.get("positive", 0) / total
            indicators["情感分數"]["score"] = round(pos_ratio * 100)
        else:
            indicators["情感分數"]["score"] = 60
    except Exception:
        indicators["情感分數"]["score"] = 60

    # 4. 評分指數 from Google rating
    if brand_rating and brand_rating > 0:
        indicators["評分指數"]["score"] = round((brand_rating / 5.0) * 100)
    else:
        rating_data = get_brand_google_rating(brand_keyword)
        r = rating_data.get("rating")
        if r and r > 0:
            indicators["評分指數"]["score"] = round((r / 5.0) * 100)
        else:
            indicators["評分指數"]["score"] = 70  # default

    return indicators


# ──────────────────────────────────────────────
# 品牌配置存取
# ──────────────────────────────────────────────
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
BRAND_CONFIG_PATH = os.path.join(CONFIG_DIR, "brand_config.json")

DEFAULT_BRAND_CONFIG = {
    "brand_name": "嗑肉石鍋",
    "brand_keywords": ["嗑肉石鍋", "嗑肉", "石鍋料理"],
    "competitors": ["韓金館", "豆府韓國料理", "橋村炸雞", "王品集團", "瓦城"],
    "geo": "TW",
    "timeframe": "today 3-m",
    # Layer 4: 手動輸入
    "manual_rating": None,
    "manual_review_count": None,
    # Layer 1: Google Places API — 每行一筆 "門市名稱:ChIJxxx..." 或直接 "ChIJxxx..."
    "place_ids": [],
    # Layer 3: QSC 內部週報 Google Sheets
    "qsc_sheet_id": "",
    "qsc_rating_col": "Google評分",
}

def load_brand_config() -> dict:
    if os.path.exists(BRAND_CONFIG_PATH):
        try:
            with open(BRAND_CONFIG_PATH, "r", encoding="utf-8") as f:
                return {**DEFAULT_BRAND_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_BRAND_CONFIG.copy()

def save_brand_config(cfg: dict) -> bool:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(BRAND_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────
# 台灣各大平台爬蟲
# ──────────────────────────────────────────────
TAIWAN_PLATFORMS = {
    "PTT":      "site:ptt.cc",
    "Dcard":    "site:dcard.tw",
    "Mobile01": "site:mobile01.com",
    "巴哈姆特":  "site:gamer.com.tw",
    "愛評網":    "site:ipeen.com.tw",
    "LINE Today":"site:today.line.me",
    "Yahoo奇摩": "site:tw.news.yahoo.com",
    "ETtoday":  "site:ettoday.net",
    "三立新聞":  "site:setn.com",
    "網紅KOL":   "KOL 打卡 網紅 推薦",
}

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_platform_news(keyword: str, platform_name: str, site_filter: str, num: int = 5) -> list:
    """Fetch news for a specific Taiwan platform using Google News RSS with site filter."""
    query = f"{keyword} {site_filter}"
    articles = fetch_google_news(query, num=num)
    for a in articles:
        a["platform"] = platform_name
    return articles


@st.cache_data(ttl=1800, show_spinner=False)
def aggregate_taiwan_platforms(keywords: list, max_per_platform: int = 6) -> dict:
    """
    Aggregate brand mentions across major Taiwan online platforms.
    Returns aggregated data without store-level breakdown.
    """
    keyword = keywords[0] if keywords else ""
    if not keyword:
        return {"total": 0, "platforms": {}, "articles": [], "available": False}

    all_articles = []
    platform_counts = {}

    for platform_name, site_filter in TAIWAN_PLATFORMS.items():
        arts = fetch_platform_news(keyword, platform_name, site_filter, num=max_per_platform)
        platform_counts[platform_name] = len(arts)
        all_articles.extend(arts)
        time.sleep(0.2)

    # Deduplicate by title
    seen = set()
    unique = []
    for a in all_articles:
        t = a.get("title", "")
        if t and t not in seen:
            seen.add(t)
            unique.append(a)

    return {
        "total": len(unique),
        "platforms": platform_counts,
        "articles": unique,
        "available": True,
        "keyword": keyword,
    }


def calculate_platform_median_stats(platform_data: dict) -> dict:
    """Calculate median sentiment and volume statistics across platforms."""
    articles = platform_data.get("articles", [])
    if not articles:
        return {"median_sentiment": 0, "platform_breakdown": {}, "total_volume": 0}

    platform_breakdown = {}
    for a in articles:
        p = a.get("platform", "其他")
        text = (a.get("title", "") + " " + a.get("description", "")).lower()
        pos = sum(1 for kw in POSITIVE_KW if kw in text)
        neg = sum(1 for kw in NEGATIVE_KW if kw in text)

        if p not in platform_breakdown:
            platform_breakdown[p] = {"pos": 0, "neg": 0, "neutral": 0, "total": 0}

        platform_breakdown[p]["total"] += 1
        if pos > neg:
            platform_breakdown[p]["pos"] += 1
            a["sentiment"] = "positive"
        elif neg > pos:
            platform_breakdown[p]["neg"] += 1
            a["sentiment"] = "negative"
        else:
            platform_breakdown[p]["neutral"] += 1
            a["sentiment"] = "neutral"

    # Median sentiment score across platforms
    import statistics
    scores = []
    for p_data in platform_breakdown.values():
        total = p_data["total"]
        if total > 0:
            score = (p_data["pos"] - p_data["neg"]) / total * 100
            scores.append(score)

    median_sentiment = round(statistics.median(scores)) if scores else 0

    return {
        "median_sentiment": median_sentiment,
        "platform_breakdown": platform_breakdown,
        "total_volume": len(articles),
        "articles": articles,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def get_competitor_scores(competitor: str) -> dict:
    """
    Fetch real competitor data: Google rating, news count, sentiment.
    Returns a dict with scores sub-dict (same 6 keys as our indicators).
    """
    try:
        rating_data = get_brand_google_rating(competitor)
        rating = rating_data.get("rating")
        time.sleep(0.3)

        news = fetch_google_news(competitor, num=20)
        news_count = len(news)
        time.sleep(0.3)

        sentiment_data = analyze_brand_sentiment([competitor])
        total_sent = sentiment_data.get("total", 0)
        positive_sent = sentiment_data.get("positive", 0)

        if total_sent > 0:
            sentiment_score = round(positive_sent / total_sent * 100) - 50
        else:
            sentiment_score = 0

        scores = {
            "搜尋熱度":   None,
            "口碑聲量":   min(100, news_count * 5),
            "情感分數":   round(positive_sent / total_sent * 100) if total_sent > 0 else 50,
            "競品對比":   None,
            "關鍵字覆蓋": None,
            "評分指數":   round(rating / 5.0 * 100) if rating else None,
        }

        return {
            "name": competitor,
            "rating": rating,
            "news_count": news_count,
            "sentiment_score": sentiment_score,
            "scores": scores,
            "available": True,
        }
    except Exception as e:
        return {
            "name": competitor,
            "rating": None,
            "news_count": 0,
            "sentiment_score": 0,
            "scores": {},
            "available": False,
            "error": str(e),
        }


@st.cache_data(ttl=3600, show_spinner=False)
def get_search_suggestions(keyword: str, geo: str = "TW") -> dict:
    """Get Google autocomplete search suggestions — no API key required."""
    suggestions_top = []
    suggestions_rising = []
    try:
        # Primary: Google autocomplete
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={requests.utils.quote(keyword)}&hl=zh-TW&gl={geo}"
        resp = requests.get(url, headers=HEADERS, timeout=8)
        data = resp.json()
        raw = data[1] if len(data) > 1 else []
        suggestions_top = [{"query": s, "value": 100 - i * 8} for i, s in enumerate(raw[:12])]
    except Exception:
        pass

    try:
        # Secondary: extended autocomplete with suffix hints
        for suffix in [" 推薦", " 評價", " 菜單", " 訂位"]:
            q = requests.utils.quote(keyword + suffix)
            url2 = f"https://suggestqueries.google.com/complete/search?client=firefox&q={q}&hl=zh-TW"
            resp2 = requests.get(url2, headers=HEADERS, timeout=6)
            data2 = resp2.json()
            raw2 = data2[1] if len(data2) > 1 else []
            for s in raw2[:3]:
                if not any(x["query"] == s for x in suggestions_top + suggestions_rising):
                    suggestions_rising.append({"query": s, "value": "+熱搜"})
            time.sleep(0.15)
    except Exception:
        pass

    return {
        "top": suggestions_top[:12],
        "rising": suggestions_rising[:8],
        "available": bool(suggestions_top or suggestions_rising),
        "source": "Google搜尋建議",
        "keyword": keyword,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_news_volume_trend(keywords: list, months: int = 6) -> dict:
    """
    Build brand mention volume trend from Google News pub_dates.
    Returns monthly counts for the past N months as a time series.
    """
    import calendar
    from email.utils import parsedate_to_datetime
    from collections import defaultdict

    keyword = keywords[0] if keywords else ""
    if not keyword:
        return {"available": False, "data": [], "keyword": keyword}

    # Fetch a large batch of recent articles
    all_articles = []
    for kw in keywords[:2]:
        arts = fetch_google_news(kw, num=20)
        all_articles.extend(arts)
        time.sleep(0.2)

    # Group articles by YYYY/MM
    monthly_counts: dict = defaultdict(int)

    today = date.today()
    # Pre-fill last N months with 0
    for i in range(months - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        monthly_counts[f"{y}/{m:02d}"] = 0

    for art in all_articles:
        try:
            dt = parsedate_to_datetime(art.get("pub_date", ""))
            key = f"{dt.year}/{dt.month:02d}"
            if key in monthly_counts:
                monthly_counts[key] += 1
        except Exception:
            pass

    data = [{"month": k, "count": v} for k, v in sorted(monthly_counts.items())]

    return {
        "available": True,
        "data": data,
        "keyword": keyword,
        "total": sum(d["count"] for d in data),
        "source": "Google News RSS",
    }


@st.cache_data(ttl=7200, show_spinner=False)
def fetch_youtube_brand_presence(brand_name: str) -> dict:
    """Fetch brand mentions on YouTube via RSS search feed."""
    try:
        encoded = requests.utils.quote(brand_name)
        url = f"https://www.youtube.com/feeds/videos.xml?search_query={encoded}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return {"available": False, "videos": [], "count": 0}

        videos = []
        if HAS_BS4:
            soup = BeautifulSoup(resp.content, "xml")
            entries = soup.find_all("entry")[:10]
            for entry in entries:
                title = entry.find("title")
                link_tag = entry.find("link")
                published = entry.find("published")
                videos.append({
                    "title": title.get_text(strip=True) if title else "",
                    "link": link_tag.get("href", "") if link_tag else "",
                    "published": (published.get_text(strip=True) or "")[:10] if published else "",
                })
        else:
            import re as _re
            titles = _re.findall(r'<title>(.*?)</title>', resp.text)[1:11]
            videos = [{"title": t, "link": "", "published": ""} for t in titles]

        return {"available": True, "videos": videos, "count": len(videos)}
    except Exception as e:
        return {"available": False, "videos": [], "count": 0, "error": str(e)}


def generate_ai_keywords(brand_name: str, brand_kws: list, geo: str = "TW") -> dict:
    """
    Generate related keywords when Google Trends is unavailable.
    Tries Claude API first, falls back to rule-based generation.
    NOT cached — intended to be called once per session.
    """
    # Rule-based fallback data (always available)
    kws_top = [
        {"query": f"{brand_name} 菜單", "value": 100},
        {"query": f"{brand_name} 訂位", "value": 95},
        {"query": f"{brand_name} 評價", "value": 90},
        {"query": f"{brand_name} 優惠", "value": 85},
        {"query": "韓式石鍋料理", "value": 80},
        {"query": "台灣韓式餐廳推薦", "value": 75},
        {"query": "石鍋定食推薦", "value": 70},
        {"query": "韓式料理外帶", "value": 65},
        {"query": "韓式料理台北", "value": 60},
        {"query": "平價韓式料理", "value": 55},
        {"query": "韓食推薦 2025", "value": 50},
        {"query": "石鍋料理 台灣", "value": 45},
    ]
    kws_rising = [
        {"query": f"{brand_name} 打卡", "value": "Breakout"},
        {"query": f"{brand_name} 網美", "value": "Breakout"},
        {"query": "韓式料理外送", "value": "+500%"},
        {"query": "韓式炸雞", "value": "+300%"},
        {"query": "石鍋料理推薦", "value": "+200%"},
        {"query": "韓食 IG", "value": "+150%"},
        {"query": "韓式套餐", "value": "+100%"},
        {"query": "石鍋飯", "value": "+80%"},
    ]

    # Insert brand_kws at the front of top_list
    brand_top = [{"query": kw, "value": 100} for kw in brand_kws if kw]
    top_list = brand_top + [k for k in kws_top if k["query"] not in {b["query"] for b in brand_top}]

    # Try Claude API
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key and HAS_ANTHROPIC:
        try:
            client = _anthropic_mod.Anthropic(api_key=api_key)
            prompt = (
                f"你是台灣餐飲品牌SEO顧問。品牌「{brand_name}」是台灣的韓式石鍋料理連鎖餐廳。"
                f"現有關鍵字：{', '.join(brand_kws[:5])}。"
                f"請生成與此品牌高度相關的搜尋關鍵字，回傳純 JSON（不要 markdown code block），格式："
                f'{{"top": [{{"query": "...", "value": 數字}}], "rising": [{{"query": "...", "value": "..."}}]}}'
                f"top 最多 12 個（value 為 0-100 整數），rising 最多 8 個（value 為百分比字串或 Breakout）。"
            )
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            # Strip markdown code block if present
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip("`").strip()
            data = json.loads(raw)
            ai_top = data.get("top", [])
            ai_rising = data.get("rising", [])
            if ai_top or ai_rising:
                # Prepend brand_kws
                final_top = brand_top + [k for k in ai_top if k.get("query") not in {b["query"] for b in brand_top}]
                return {
                    "top": final_top[:15],
                    "rising": ai_rising[:10],
                    "available": True,
                    "ai_generated": True,
                    "source": "AI生成",
                }
        except Exception:
            pass

    # Rule-based fallback
    return {
        "top": top_list[:15],
        "rising": kws_rising,
        "available": True,
        "ai_generated": True,
        "source": "規則引擎生成",
    }


def _call_claude_diagnosis(
    brand_name: str,
    scores_summary: str,
    platform_summary: str,
    comp_summary: str,
) -> Optional[dict]:
    """Call Claude API for AI-powered brand diagnosis. Returns dict or None."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not HAS_ANTHROPIC:
        return None
    try:
        client = _anthropic_mod.Anthropic(api_key=api_key)
        prompt = (
            f"你是台灣餐飲品牌數位行銷顧問。請根據以下實際數據生成品牌健康診斷報告。\n\n"
            f"品牌：{brand_name}\n"
            f"六項健康指標（0-100分）：{scores_summary}\n"
            f"台灣各平台口碑：{platform_summary}\n"
            f"競品動態：{comp_summary}\n\n"
            f"請以資深行銷主管思維，提供具體可操作的建議，避免空泛通則。\n"
            f'回傳純 JSON（不要 markdown code block），格式：\n'
            f'{{"summary": ["...","..."], "warnings": ["..."], "opportunities": ["..."], "discussion_topics": ["..."]}}'
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip("`").strip()
        data = json.loads(raw)
        required_keys = {"summary", "warnings", "opportunities", "discussion_topics"}
        if required_keys.issubset(data.keys()):
            return data
        return None
    except Exception:
        return None


def generate_ai_diagnosis(
    brand_name: str,
    six_indicators: dict,
    platform_stats: dict,
    trends_data: dict,
    competitor_data: list,
    use_ai: bool = True,
) -> dict:
    """
    AI-powered (or rule-based fallback) diagnosis engine for brand health.
    Returns structured warnings and discussion topics.
    """
    warnings_list = []
    opportunities = []
    discussion_topics = []
    summary_lines = []

    # Analyze six indicators
    scores = {k: v.get("score", 0) for k, v in six_indicators.items()}
    avg_score = sum(scores.values()) / len(scores) if scores else 0

    # Try Claude AI diagnosis first
    if use_ai:
        scores_summary = ", ".join(f"{k}:{v}" for k, v in scores.items())
        pb = platform_stats.get("platform_breakdown", {})
        platform_summary = f"總聲量 {platform_stats.get('total_volume', 0)} 篇，中位數情感 {platform_stats.get('median_sentiment', 0)}，平台數 {len(pb)}"
        comp_brands = list({a.get("brand") for a in competitor_data if a.get("brand")})[:5]
        comp_summary = f"監控競品：{', '.join(comp_brands)}，共 {len(competitor_data)} 則競品動態"
        ai_result = _call_claude_diagnosis(brand_name, scores_summary, platform_summary, comp_summary)
        if ai_result:
            return {
                "summary": ai_result.get("summary", []),
                "warnings": ai_result.get("warnings", []),
                "opportunities": ai_result.get("opportunities", []),
                "discussion_topics": ai_result.get("discussion_topics", []),
                "avg_score": round(avg_score),
                "available": True,
                "ai_powered": True,
            }

    # Search heat analysis
    heat = scores.get("搜尋熱度", 50)
    if heat < 30:
        warnings_list.append(f"搜尋熱度偏低（{heat}分），品牌在搜尋引擎曝光不足，建議強化 SEO 與關鍵字投放")
        discussion_topics.append("【SEO策略】如何提升品牌在 Google 搜尋的曝光度？")
    elif heat > 70:
        opportunities.append(f"搜尋熱度良好（{heat}分），維持搜尋聲量優勢")

    # Sentiment analysis
    sentiment = scores.get("情感分數", 60)
    if sentiment < 40:
        warnings_list.append(f"情感分數偏低（{sentiment}分），網路負評比例偏高，需即時處理客訴議題")
        discussion_topics.append("【危機公關】負評原因分析與應對話術準備")
    elif sentiment < 60:
        warnings_list.append(f"情感分數中等（{sentiment}分），有改善空間")
        discussion_topics.append("【口碑提升】如何將中性評價轉化為正面口碑？")
    else:
        opportunities.append(f"品牌情感氛圍正向（{sentiment}分），繼續維持服務品質")

    # Competitor analysis
    comp_score = scores.get("競品對比", 50)
    if comp_score < 35:
        warnings_list.append(f"競品對比劣勢明顯（{comp_score}分），主要競品搜尋聲量遠超本品牌")
        discussion_topics.append("【競品分析】競品最近有哪些大型行銷活動？我們如何差異化？")
    elif comp_score < 50:
        warnings_list.append(f"競品壓力中等（{comp_score}分），需加強品牌差異化行銷")
        discussion_topics.append("【市場定位】嗑肉石鍋核心差異化優勢如何強化傳播？")

    # Platform volume analysis
    total_volume = platform_stats.get("total_volume", 0)
    median_sentiment = platform_stats.get("median_sentiment", 0)
    platform_breakdown = platform_stats.get("platform_breakdown", {})

    if total_volume < 10:
        warnings_list.append(f"各平台口碑聲量偏低（共 {total_volume} 篇），品牌在社群平台存在感不足")
        discussion_topics.append("【社群策略】如何增加 PTT、Dcard 等平台的品牌討論聲量？")
    else:
        opportunities.append(f"台灣各平台共有 {total_volume} 篇相關討論，口碑聲量具一定基礎")

    if median_sentiment < 0:
        warnings_list.append(f"跨平台中位數情感分數為負（{median_sentiment}），整體網路風評需要緊急干預")
        discussion_topics.append("【輿情危機】哪些平台負評最集中？如何展開針對性回應？")

    # Check for active platforms with high negative ratio
    for platform, p_data in platform_breakdown.items():
        total_p = p_data.get("total", 0)
        neg_p = p_data.get("neg", 0)
        if total_p >= 3 and neg_p / total_p > 0.5:
            warnings_list.append(f"{platform} 平台負評比例高達 {round(neg_p/total_p*100)}%，建議優先處理")
            discussion_topics.append(f"【{platform}平台】負評集中原因追查與回應策略")

    # Keyword coverage
    kw_coverage = scores.get("關鍵字覆蓋", 40)
    if kw_coverage < 40:
        opportunities.append(f"關鍵字覆蓋率（{kw_coverage}分）有提升空間，可新增長尾關鍵字投放")
        discussion_topics.append("【關鍵字策略】哪些長尾關鍵字最適合嗑肉石鍋目前的行銷目標？")

    # Rating index
    rating_idx = scores.get("評分指數", 70)
    if rating_idx < 60:
        warnings_list.append(f"Google 評分指數偏低（{rating_idx}分），消費者體驗評分需提升")
        discussion_topics.append("【顧客體驗】哪些門店評分最低？如何針對性改善？")

    # Competitor activity
    comp_brands_active = set(a.get("brand") for a in competitor_data if a.get("brand"))
    if len(comp_brands_active) >= 3:
        discussion_topics.append(f"【競品監控】{', '.join(list(comp_brands_active)[:3])} 近期有新活動，建議行銷部研究借鏡")

    # Build overall summary
    if avg_score >= 70:
        summary_lines.append(f"品牌整體健康度良好（六項平均 {round(avg_score)} 分），繼續維持競爭優勢")
    elif avg_score >= 50:
        summary_lines.append(f"品牌健康度中等（六項平均 {round(avg_score)} 分），有多項指標需要改善")
    else:
        summary_lines.append(f"品牌健康度警示（六項平均 {round(avg_score)} 分），建議召開緊急行銷策略會議")

    if len(warnings_list) == 0:
        summary_lines.append("目前無重大風險警示，持續監控即可")
    else:
        summary_lines.append(f"共發現 {len(warnings_list)} 項警示，{len(discussion_topics)} 個可討論議題")

    return {
        "summary": summary_lines,
        "warnings": warnings_list,
        "opportunities": opportunities,
        "discussion_topics": discussion_topics,
        "avg_score": round(avg_score),
        "available": True,
    }
