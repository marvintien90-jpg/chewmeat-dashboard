import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import warnings
import re
import calendar
import io

warnings.filterwarnings("ignore")

# ============================================================
# 基本設定
# ============================================================
SHEET_ID = "1NZQEJgL-HkB08JSW6zsVHRSyl_XgwLc5etUqSF0O9ow"

SHEET_GIDS = {
    "2025-01": "672482866", "2025-02": "1943981506", "2025-03": "847955849",
    "2025-04": "591730250", "2025-05": "695013616", "2025-06": "897256004",
    "2025-07": "593028448", "2025-08": "836455215", "2025-09": "1728608975",
    "2025-10": "2043079442", "2025-11": "1307429413", "2025-12": "1838876978",
    "2026-01": "872131612", "2026-02": "162899314", "2026-03": "1575135129",
    "2026-04": "1702412906", "2026-05": "1499115222", "2026-06": "467088033",
}

WEEKDAY_MAP = {0: "週一", 1: "週二", 2: "週三", 3: "週四", 4: "週五", 5: "週六", 6: "週日"}
QUARTER_MAP = {1: "Q1", 2: "Q1", 3: "Q1", 4: "Q2", 5: "Q2", 6: "Q2",
               7: "Q3", 8: "Q3", 9: "Q3", 10: "Q4", 11: "Q4", 12: "Q4"}

# 已結村門店清單（有歷史資料但已不在營業）
CLOSED_STORES = {"北屯軍福店", "犝犝楠梓店", "高雄大順店", "高雄自由店", "高雄鼎強店", "鳳山文中店"}

# 手機 RWD：圖表設定（禁用縮放、拖曳；保留 tooltip）
MOBILE_CHART_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "displaylogo": False,
    "staticPlot": False,  # 保留 hover/tooltip
}

st.set_page_config(
    page_title="嗑肉石鍋 營收儀表板",
    page_icon="🍲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 全新設計系統 CSS（Premium 50萬級）
# ============================================================
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<style>
/* ── CSS Variables ── */
:root {
  --brand:        #FF6B35;
  --brand-dark:   #E0551F;
  --brand-light:  #FF8F5E;
  --brand-glow:   rgba(255,107,53,.18);
  --accent:       #3B82F6;
  --success:      #10B981;
  --warning:      #F59E0B;
  --danger:       #EF4444;
  --bg:           #F4F6FA;
  --surface:      #FFFFFF;
  --surface-2:    #F8FAFC;
  --surface-3:    #EFF3F8;
  --text-1:       #0F172A;
  --text-2:       #475569;
  --text-3:       #94A3B8;
  --border:       #E2E8F0;
  --border-2:     #CBD5E1;
  --r:            14px;
  --r-sm:         8px;
  --r-lg:         20px;
  --shadow-xs:    0 1px 3px rgba(15,23,42,.06);
  --shadow-sm:    0 2px 8px rgba(15,23,42,.07), 0 1px 2px rgba(15,23,42,.04);
  --shadow:       0 4px 20px rgba(15,23,42,.09), 0 1px 4px rgba(15,23,42,.05);
  --shadow-lg:    0 12px 40px rgba(15,23,42,.13), 0 4px 8px rgba(15,23,42,.05);
  --shadow-brand: 0 6px 24px rgba(255,107,53,.32);
}

/* ── Base ── */
html, body, [class*="st-"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  -webkit-font-smoothing: antialiased;
}
.stApp { background: var(--bg); }
.main .block-container {
  padding-top: 1.5rem;
  padding-bottom: 3rem;
  max-width: 1440px;
}
header[data-testid="stHeader"] { display: none; }
#MainMenu { display: none; }
footer { display: none; }

/* ── KPI Cards ── */
[data-testid="stMetric"] {
  background: var(--surface);
  border-radius: var(--r);
  padding: 22px 24px 18px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
  transition: box-shadow .2s ease, transform .2s ease;
  position: relative;
  overflow: hidden;
}
[data-testid="stMetric"]::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--brand), var(--brand-light));
  border-radius: var(--r) var(--r) 0 0;
}
[data-testid="stMetric"]:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow);
}
[data-testid="stMetricLabel"] {
  font-size: .78rem !important;
  font-weight: 700 !important;
  color: var(--text-3) !important;
  letter-spacing: .06em;
  text-transform: uppercase;
}
[data-testid="stMetricValue"] {
  font-size: 1.8rem !important;
  font-weight: 800 !important;
  color: var(--text-1) !important;
  letter-spacing: -.03em;
  line-height: 1.15;
}
[data-testid="stMetricDelta"] {
  font-size: .8rem !important;
  font-weight: 600 !important;
}
[data-testid="stMetricDelta"] > div { border-radius: 20px; padding: 1px 8px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] > div { gap: 2px !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  padding: 9px 14px !important;
  border-radius: var(--r-sm) !important;
  cursor: pointer !important;
  transition: all .14s ease !important;
  font-size: .875rem !important;
  font-weight: 500 !important;
  color: var(--text-2) !important;
  border: 1px solid transparent !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
  background: var(--surface-3) !important;
  color: var(--text-1) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"] ~ div label,
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"] {
  background: linear-gradient(135deg,#FFF2EC,#FFF7F4) !important;
  color: var(--brand) !important;
  font-weight: 700 !important;
  border-color: rgba(255,107,53,.2) !important;
}

/* ── Buttons ── */
.stButton > button {
  border-radius: var(--r-sm) !important;
  font-weight: 600 !important;
  font-size: .875rem !important;
  transition: all .15s ease !important;
  letter-spacing: .01em;
}
.stButton > button[data-testid="baseButton-primary"],
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--brand), var(--brand-light)) !important;
  border: none !important;
  color: white !important;
  box-shadow: var(--shadow-brand) !important;
}
.stButton > button[data-testid="baseButton-primary"]:hover,
.stButton > button[kind="primary"]:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 28px rgba(255,107,53,.4) !important;
}
.stButton > button[data-testid="baseButton-secondary"],
.stButton > button[kind="secondary"] {
  background: var(--surface) !important;
  border: 1.5px solid var(--border-2) !important;
  color: var(--text-2) !important;
}
.stButton > button[data-testid="baseButton-secondary"]:hover,
.stButton > button[kind="secondary"]:hover {
  border-color: var(--brand) !important;
  color: var(--brand) !important;
  background: #FFF2EC !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"] {
  border-bottom: 2px solid var(--border);
  gap: 0;
  background: transparent;
}
[data-testid="stTabs"] [role="tab"] {
  border-radius: var(--r-sm) var(--r-sm) 0 0 !important;
  font-weight: 600 !important;
  font-size: .875rem !important;
  padding: 10px 20px !important;
  color: var(--text-2) !important;
  border: none !important;
  background: transparent !important;
  transition: all .15s ease !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: var(--brand) !important;
  background: #FFF2EC !important;
  border-bottom: 2px solid var(--brand) !important;
}
[data-testid="stTabs"] [role="tab"]:hover { background: var(--surface-3) !important; }

/* ── Expander ── */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  background: var(--surface) !important;
  box-shadow: var(--shadow-xs) !important;
}
[data-testid="stExpander"] summary {
  font-weight: 600 !important;
  color: var(--text-1) !important;
  padding: 12px 16px !important;
}

/* ── DataFrame ── */
[data-testid="stDataFrame"] {
  border-radius: var(--r) !important;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border) !important;
}

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 1.25rem 0 !important; }

/* ── Selectbox & Inputs ── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextInput"] > div > div,
[data-testid="stTextArea"] textarea {
  border-radius: var(--r-sm) !important;
  border-color: var(--border) !important;
  font-size: .875rem !important;
}
[data-testid="stSelectbox"] > div > div:focus-within,
[data-testid="stTextInput"] > div > div:focus-within {
  border-color: var(--brand) !important;
  box-shadow: 0 0 0 3px var(--brand-glow) !important;
}

/* ── Chat Interface ── */
.chat-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 8px 0 16px;
}
.chat-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.chat-row.user-row { flex-direction: row-reverse; }
.chat-avatar {
  width: 34px; height: 34px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: .95rem;
  flex-shrink: 0;
  font-weight: 700;
}
.chat-avatar.ai-av {
  background: linear-gradient(135deg, var(--brand), var(--brand-light));
  color: #fff;
  box-shadow: var(--shadow-brand);
}
.chat-avatar.user-av {
  background: linear-gradient(135deg,#3B82F6,#60A5FA);
  color: #fff;
}
.chat-bubble {
  max-width: 78%;
  border-radius: 0 var(--r) var(--r) var(--r);
  padding: 12px 16px;
  font-size: .875rem;
  line-height: 1.65;
  box-shadow: var(--shadow-xs);
}
.chat-bubble.ai-bubble {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-1);
}
.chat-bubble.user-bubble {
  background: linear-gradient(135deg, var(--brand), var(--brand-light));
  color: #fff;
  border-radius: var(--r) 0 var(--r) var(--r);
  box-shadow: var(--shadow-brand);
}
.chat-meta {
  font-size: .7rem;
  color: var(--text-3);
  margin-top: 5px;
  text-align: left;
}
.chat-row.user-row .chat-meta { text-align: right; }

/* ── Quick Actions ── */
.qa-wrap { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 18px; }
.qa-pill {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: 20px;
  padding: 7px 14px;
  font-size: .8rem;
  font-weight: 600;
  color: var(--text-2);
  cursor: pointer;
  transition: all .15s ease;
  white-space: nowrap;
}
.qa-pill:hover {
  border-color: var(--brand);
  color: var(--brand);
  background: #FFF2EC;
  box-shadow: 0 2px 10px var(--brand-glow);
}

/* ── Page Banner ── */
.page-banner {
  background: linear-gradient(135deg,#0F172A 0%,#1E293B 60%,#0F3460 100%);
  border-radius: var(--r-lg);
  padding: 22px 28px;
  margin-bottom: 22px;
  position: relative;
  overflow: hidden;
}
.page-banner::before {
  content: '';
  position: absolute;
  top: -40%; right: -8%;
  width: 240px; height: 240px;
  background: radial-gradient(circle, rgba(255,107,53,.35), transparent 68%);
  border-radius: 50%;
  pointer-events: none;
}
.page-banner::after {
  content: '';
  position: absolute;
  bottom: -30%; left: 30%;
  width: 160px; height: 160px;
  background: radial-gradient(circle, rgba(59,130,246,.2), transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}
.page-banner h2 {
  color: #fff !important;
  margin: 0 0 4px;
  font-size: 1.45rem !important;
  font-weight: 800 !important;
  letter-spacing: -.02em;
  position: relative;
}
.page-banner p {
  color: rgba(255,255,255,.65);
  margin: 0;
  font-size: .85rem;
  position: relative;
}

/* ── Insight Cards ── */
.insight-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 15px 18px;
  margin-bottom: 10px;
  display: flex;
  gap: 14px;
  align-items: flex-start;
  box-shadow: var(--shadow-xs);
  transition: all .2s ease;
}
.insight-card:hover {
  box-shadow: var(--shadow);
  transform: translateX(3px);
}
.insight-icon {
  width: 42px; height: 42px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem;
  flex-shrink: 0;
}
.insight-body { flex: 1; min-width: 0; }
.insight-cat {
  font-size: .68rem; font-weight: 800;
  text-transform: uppercase; letter-spacing: .1em;
  margin-bottom: 3px;
}
.insight-title {
  font-size: .93rem; font-weight: 700;
  color: var(--text-1); margin-bottom: 3px;
  line-height: 1.4;
}
.insight-detail { font-size: .8rem; color: var(--text-2); line-height: 1.5; }

/* ── Sidebar Brand ── */
.sb-brand {
  background: linear-gradient(135deg,#FF6B35 0%,#FF8F5E 100%);
  margin: -1rem -1rem 1rem;
  padding: 18px 18px 16px;
  position: relative;
  overflow: hidden;
}
.sb-brand::after {
  content: '';
  position: absolute;
  bottom: -24px; right: -16px;
  width: 90px; height: 90px;
  background: rgba(255,255,255,.14);
  border-radius: 50%;
  pointer-events: none;
}
.sb-brand-name { font-size: 1.05rem; font-weight: 800; color: #fff; letter-spacing: -.01em; }
.sb-brand-sub { font-size: .73rem; color: rgba(255,255,255,.8); margin-top: 1px; }

/* ── Yesterday Summary ── */
.yd-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 13px 15px;
  margin-top: 2px;
}
.yd-title { font-size: .75rem; font-weight: 800; color: var(--text-1); margin-bottom: 6px; }
.yd-row { display: flex; align-items: center; gap: 6px; font-size: .83rem; color: var(--text-2); margin: 3px 0; }
.yd-val { font-weight: 700; color: var(--text-1); }
.up { color: var(--success) !important; font-weight: 700; }
.dn { color: var(--danger)  !important; font-weight: 700; }

/* ── AI Assistant Header ── */
.ai-header {
  background: linear-gradient(135deg,#667EEA,#764BA2,#F64F59);
  border-radius: var(--r-lg);
  padding: 20px 24px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.ai-header-icon {
  width: 52px; height: 52px;
  background: rgba(255,255,255,.2);
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.5rem;
  flex-shrink: 0;
  backdrop-filter: blur(4px);
}
.ai-header-text h3 { color: #fff; margin: 0; font-size: 1.2rem; font-weight: 800; }
.ai-header-text p  { color: rgba(255,255,255,.75); margin: 3px 0 0; font-size: .82rem; }

/* ── Chat Panel ── */
.chat-panel {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 16px;
  min-height: 280px;
  max-height: 520px;
  overflow-y: auto;
  margin-bottom: 12px;
}
.empty-chat {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 220px; gap: 10px; color: var(--text-3);
}
.empty-chat i { font-size: 2.5rem; opacity: .4; }
.empty-chat p { font-size: .88rem; font-weight: 500; margin: 0; }

/* ── Section Header ── */
.section-header {
  display: flex; align-items: center; gap: 8px;
  margin: 1.5rem 0 .8rem;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--border);
}
.section-header i { color: var(--brand); font-size: 1.1rem; }
.section-header span { font-size: 1rem; font-weight: 700; color: var(--text-1); }

/* ── Badges ── */
.badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px; border-radius: 20px;
  font-size: .72rem; font-weight: 700;
}
.badge-success { background:#D1FAE5; color:#065F46; }
.badge-warning { background:#FEF3C7; color:#92400E; }
.badge-danger  { background:#FEE2E2; color:#991B1B; }
.badge-info    { background:#DBEAFE; color:#1E40AF; }
.badge-purple  { background:#EDE9FE; color:#5B21B6; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-3); }

/* ── Animations ── */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
[data-testid="stMetric"] { animation: fadeUp .35s ease both; }

/* ── Mobile RWD ── */
@media (max-width: 768px) {
  .main .block-container { padding: .75rem .75rem 5rem !important; }
  [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
  [data-testid="stMetricLabel"] { font-size: .72rem !important; }
  .page-banner { padding: 14px 16px; margin-bottom: 14px; }
  .page-banner h2 { font-size: 1.15rem !important; }
  .chat-bubble { max-width: 92%; font-size: .82rem; }
  .ai-header { padding: 14px 16px; gap: 12px; }
  .ai-header-icon { width: 42px; height: 42px; font-size: 1.2rem; }
}
@media (max-width: 480px) {
  [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
  .chat-bubble { max-width: 96%; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 資料讀取
# ============================================================
@st.cache_data(ttl=3600)
def load_sheet(year_month, gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    try:
        raw = pd.read_csv(url, header=None)
    except Exception:
        return pd.DataFrame()

    year, month = year_month.split("-")
    year, month = int(year), int(month)

    date_row = raw.iloc[1, 7:]
    dates = []
    for val in date_row:
        s = str(val).strip()
        if s == "nan" or s == "合計":
            continue
        m_ = re.match(r"(\d+)/(\d+)", s)
        if m_:
            m, d = int(m_.group(1)), int(m_.group(2))
            if m != month:
                continue
            try:
                dates.append(date(year, m, d))
            except ValueError:
                continue

    if not dates:
        return pd.DataFrame()

    rows = []
    cur_region = cur_store = cur_target = cur_rate = None

    for i in range(2, len(raw)):
        row = raw.iloc[i]
        if pd.notna(row.iloc[0]) and str(row.iloc[0]).strip():
            cur_region = str(row.iloc[0]).strip()
        if pd.notna(row.iloc[1]) and str(row.iloc[1]).strip():
            cur_store = str(row.iloc[1]).strip()
        if pd.notna(row.iloc[2]) and str(row.iloc[2]).strip():
            t = str(row.iloc[2]).replace(",", "").strip()
            try:
                cur_target = float(t)
            except ValueError:
                cur_target = None
        if pd.notna(row.iloc[3]) and str(row.iloc[3]).strip():
            r = str(row.iloc[3]).replace("%", "").strip()
            try:
                cur_rate = float(r) / 100
            except ValueError:
                cur_rate = None

        metric = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else ""
        if metric not in ["業績合計", "人數合計", "平均客單"]:
            continue
        if not cur_store:
            continue

        vals = []
        for val in row.iloc[7:]:
            s = str(val).strip().replace(",", "").replace(" ", "")
            if s in ["nan", "", "#DIV/0!", "\\#DIV/0\\!", "#DIV/0!"]:
                vals.append(None)
            else:
                try:
                    vals.append(float(s))
                except ValueError:
                    vals.append(None)

        day_vals = []
        for idx in range(0, len(vals), 2):
            if idx // 2 < len(dates):
                day_vals.append(vals[idx])

        for di, dt in enumerate(dates):
            v = day_vals[di] if di < len(day_vals) else None
            rows.append({
                "日期": dt, "區域": cur_region, "門店": cur_store,
                "本月目標": cur_target, "達成率": cur_rate,
                "指標": metric, "數值": v,
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    pivot = df.pivot_table(
        index=["日期", "區域", "門店"],
        columns="指標", values="數值", aggfunc="first",
    ).reset_index()
    pivot.columns.name = None

    # 本月目標/達成率單獨 join，避免 NaN index 導致門店被 pivot_table 過濾掉
    tr = df.groupby(["日期", "區域", "門店"])[["本月目標", "達成率"]].first().reset_index()
    pivot = pivot.merge(tr, on=["日期", "區域", "門店"], how="left")

    ren = {}
    if "業績合計" in pivot.columns: ren["業績合計"] = "營業額"
    if "人數合計" in pivot.columns: ren["人數合計"] = "來客數"
    if "平均客單" in pivot.columns: ren["平均客單"] = "客單價"
    pivot = pivot.rename(columns=ren)

    for col in ["營業額", "來客數", "客單價"]:
        if col not in pivot.columns:
            pivot[col] = None
    return pivot


@st.cache_data(ttl=3600)
def load_all_data():
    dfs = []
    for ym, gid in SHEET_GIDS.items():
        df = load_sheet(ym, gid)
        if not df.empty:
            dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    data = pd.concat(dfs, ignore_index=True)
    # 資料清洗：犝犝楠梓店保留為獨立門店（已結村）
    data["日期"] = pd.to_datetime(data["日期"])
    data["年份"] = data["日期"].dt.year
    data["月份"] = data["日期"].dt.month
    data["年月"] = data["日期"].dt.to_period("M").astype(str)
    data["季"] = data["月份"].map(QUARTER_MAP)
    data["年季"] = data["年份"].astype(str) + " " + data["季"]
    data["週次"] = data["日期"].dt.isocalendar().week.astype(int)
    data["年週"] = data["日期"].dt.strftime("%G-W%V")
    data["星期"] = data["日期"].dt.dayofweek
    data["星期名"] = data["星期"].map(WEEKDAY_MAP)
    data["已結村"] = data["門店"].isin(CLOSED_STORES)
    return data


# ============================================================
# 工具函數
# ============================================================
def fmt_num(x):
    if pd.isna(x) or x == 0:
        return "—"
    return f"{x:,.0f}"


def fmt_pct(x):
    if pd.isna(x):
        return "—"
    return f"{x:+.1f}%"


def plotly_chart(fig, key=None):
    """統一 Plotly 圖表渲染：禁用縮放拖曳、保留 tooltip"""
    st.plotly_chart(fig, use_container_width=True, config=MOBILE_CHART_CONFIG, key=key)


def bsh(icon, text, level=2):
    if level == 2:
        st.markdown(
            f'<div class="page-banner"><h2><i class="bi {icon}" style="opacity:.85"></i> {text}</h2>'
            f'<p>即時數據・智慧洞察・協助您做出最佳決策</p></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="section-header"><i class="bi {icon}"></i><span>{text}</span></div>',
            unsafe_allow_html=True,
        )


def get_date_filter(data, key_prefix="", active_stores=None):
    """展開式篩選器 - 每頁通用"""
    with st.expander("篩選條件", expanded=False):
        c1, c2, c3 = st.columns([2, 1, 1])
        min_date = data["日期"].min().date()
        max_date = data["日期"].max().date()

        with c1:
            date_range = st.date_input(
                "日期範圍", value=(min_date, max_date),
                min_value=min_date, max_value=max_date,
                key=f"{key_prefix}_date",
            )
        with c2:
            regions = sorted(data["區域"].dropna().unique().tolist())
            sel_regions = st.multiselect(
                "區域", regions, default=regions,
                key=f"{key_prefix}_region",
            )
        with c3:
            store_pool = active_stores if active_stores else sorted(
                data[data["區域"].isin(sel_regions)]["門店"].dropna().unique().tolist()
            )
            sel_stores = st.multiselect(
                "門店", store_pool, default=store_pool,
                key=f"{key_prefix}_store",
            )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
    else:
        start_d, end_d = min_date, max_date

    mask = (
        (data["日期"].dt.date >= start_d) & (data["日期"].dt.date <= end_d)
        & (data["區域"].isin(sel_regions)) & (data["門店"].isin(sel_stores))
    )
    return data[mask].copy(), start_d, end_d, sel_regions, sel_stores


def calc_kpi_card(data, period_label, start_d, end_d, compare_start=None, compare_end=None):
    """計算累計卡片的三合一指標：本期金額、同期比、達成率"""
    period_data = data[(data["日期"].dt.date >= start_d) & (data["日期"].dt.date <= end_d)]
    period_data = period_data[period_data["營業額"].notna() & (period_data["營業額"] > 0)]
    total = period_data["營業額"].sum()

    delta = None
    if compare_start and compare_end:
        cmp_data = data[(data["日期"].dt.date >= compare_start) & (data["日期"].dt.date <= compare_end)]
        cmp_data = cmp_data[cmp_data["營業額"].notna() & (cmp_data["營業額"] > 0)]
        cmp_total = cmp_data["營業額"].sum()
        if cmp_total > 0:
            delta = (total - cmp_total) / cmp_total * 100

    return total, delta


# ============================================================
# 分頁函數
# ============================================================
def page_overview(data):
    """總覽（四大累計）"""
    bsh("bi-bar-chart-line", "總覽", level=2)

    filtered, start_d, end_d, sel_regions, sel_stores = get_date_filter(data, "ov")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    # 計算基準日（資料最新一天）
    today = valid["日期"].max().date()
    yr, mn = today.year, today.month

    # ========== 四大累計卡片 ==========
    bsh("bi-gem", "四大累計分析", level=3)

    # 曆年累計（所有歷史資料至最新日）
    yoy_total = data[data["營業額"].notna() & (data["營業額"] > 0)]["營業額"].sum()

    # 今年累計
    y_start = date(yr, 1, 1)
    y_ly_start = date(yr - 1, 1, 1)
    y_ly_end = date(yr - 1, today.month, today.day) if today.month <= 12 else date(yr - 1, 12, 31)
    y_total, y_delta = calc_kpi_card(data, "今年", y_start, today, y_ly_start, y_ly_end)

    # 本季累計
    q_start_month = ((mn - 1) // 3) * 3 + 1
    q_start = date(yr, q_start_month, 1)
    q_ly_start = date(yr - 1, q_start_month, 1)
    q_ly_end = date(yr - 1, mn, today.day) if today.day <= calendar.monthrange(yr - 1, mn)[1] else date(yr - 1, mn, calendar.monthrange(yr - 1, mn)[1])
    q_total, q_delta = calc_kpi_card(data, "本季", q_start, today, q_ly_start, q_ly_end)

    # 本月累計
    m_start = date(yr, mn, 1)
    try:
        m_ly_start = date(yr - 1, mn, 1)
        ly_last_day = calendar.monthrange(yr - 1, mn)[1]
        m_ly_end = date(yr - 1, mn, min(today.day, ly_last_day))
    except ValueError:
        m_ly_start = m_ly_end = None
    m_total, m_delta = calc_kpi_card(data, "本月", m_start, today, m_ly_start, m_ly_end)

    # 本月目標達成率
    cur_month_target = data[
        (data["日期"].dt.year == yr) & (data["日期"].dt.month == mn)
    ].groupby("門店")["本月目標"].first().sum()
    m_rate = (m_total / cur_month_target * 100) if cur_month_target > 0 else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("曆年累計", f"{yoy_total:,.0f} 元")
    c2.metric("今年累計", f"{y_total:,.0f} 元",
              delta=f"{y_delta:+.1f}% vs 去年同期" if y_delta is not None else None)
    c3.metric("本季累計", f"{q_total:,.0f} 元",
              delta=f"{q_delta:+.1f}% vs 去年同期" if q_delta is not None else None)
    c4.metric("本月累計", f"{m_total:,.0f} 元",
              delta=f"達成 {m_rate:.1f}%" if m_rate else None)

    st.divider()

    # ========== 每日營收趨勢 ==========
    bsh("bi-graph-up-arrow", "每日營收趨勢", level=3)
    daily = valid.groupby("日期").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    daily["客單價"] = (daily["營業額"] / daily["來客數"]).round(0)

    fig = make_revenue_bar(daily)
    plotly_chart(fig, key="ov_daily")

    # 來客數 + 客單價雙軸
    fig2 = make_dual_axis(daily)
    plotly_chart(fig2, key="ov_dual")

    # ========== 區域營收佔比 Sunburst ==========
    bsh("bi-pie-chart", "區域 / 門店營收結構", level=3)
    sunburst_data = valid.groupby(["區域", "門店"])["營業額"].sum().reset_index()
    fig_sb = px.sunburst(
        sunburst_data, path=["區域", "門店"], values="營業額",
        color="營業額", color_continuous_scale="RdYlGn",
        title="區域 → 門店 營收佔比",
    )
    fig_sb.update_layout(height=500)
    plotly_chart(fig_sb, key="ov_sunburst")


def page_store_rank(data):
    """門店排行"""
    bsh("bi-shop", "門店排行")
    filtered, _, _, _, sel_stores = get_date_filter(data, "rk")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    store_sum = valid.groupby(["區域", "門店"]).agg({
        "營業額": "sum", "來客數": "sum",
        "本月目標": "first", "達成率": "first",
    }).reset_index()
    store_sum["客單價"] = (store_sum["營業額"] / store_sum["來客數"]).round(0)
    store_sum = store_sum.sort_values("營業額", ascending=False)

    # 排行圖
    fig = px.bar(
        store_sum, x="門店", y="營業額", color="區域",
        title="各門店營業額排行", height=450,
    )
    fig.update_layout(xaxis_tickangle=-45)
    fig.update_traces(hovertemplate="%{x}<br>營業額：%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="rk_bar")

    # 達成率儀表板（選前 6 名）
    if store_sum["達成率"].notna().any():
        bsh("bi-bullseye", "前六店達成率儀表板", level=3)
        top6 = store_sum[store_sum["達成率"].notna()].head(6)
        cols = st.columns(3)
        for i, (_, row) in enumerate(top6.iterrows()):
            with cols[i % 3]:
                fig_g = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=row["達成率"] * 100,
                    title={"text": row["門店"]},
                    number={"suffix": "%"},
                    gauge={
                        "axis": {"range": [0, 130]},
                        "bar": {"color": "#4ECDC4"},
                        "steps": [
                            {"range": [0, 50], "color": "#FFD6D6"},
                            {"range": [50, 80], "color": "#FFF3C4"},
                            {"range": [80, 130], "color": "#C4F0C4"},
                        ],
                        "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 100},
                    },
                ))
                fig_g.update_layout(height=200, margin=dict(t=30, b=10, l=10, r=10))
                plotly_chart(fig_g, key=f"gauge_{i}")

    # 明細表
    bsh("bi-table", "明細表", level=3)
    disp = store_sum[["區域", "門店", "營業額", "來客數", "客單價", "達成率"]].copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["達成率"] = disp["達成率"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_store_compare(data):
    """店對店比較"""
    bsh("bi-arrow-left-right", "店對店比較")
    filtered, _, _, _, sel_stores = get_date_filter(data, "cmp")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    compare_stores = st.multiselect(
        "選擇 2～4 間門店比較", sel_stores,
        default=sel_stores[:min(2, len(sel_stores))],
        max_selections=4,
        key="cmp_select",
    )
    if len(compare_stores) < 2:
        st.info("請至少選擇 2 間門店")
        return

    comp = valid[valid["門店"].isin(compare_stores)]

    # 每日營業額對比
    pivot = comp.pivot_table(index="日期", columns="門店", values="營業額", aggfunc="sum").reset_index()
    fig = go.Figure()
    colors = ["#4ECDC4", "#FF6B6B", "#45B7D1", "#FFA726"]
    for i, s in enumerate(compare_stores):
        if s in pivot.columns:
            fig.add_trace(go.Scatter(
                x=pivot["日期"], y=pivot[s], mode="lines+markers", name=s,
                line=dict(color=colors[i % 4], width=2),
                hovertemplate=f"{s}<br>%{{x|%m/%d}}<br>%{{y:,.0f}} 元<extra></extra>",
            ))
    fig.update_layout(title="每日營業額對比", height=400, hovermode="x unified",
                      xaxis_title="日期", yaxis_title="營業額（元）")
    plotly_chart(fig, key="cmp_line")

    # 雷達圖
    radar = comp.groupby("門店").agg({"營業額": "sum", "來客數": "sum", "客單價": "mean"}).reset_index()
    cats = ["營業額", "來客數", "客單價"]
    fig_r = go.Figure()
    for i, s in enumerate(compare_stores):
        row = radar[radar["門店"] == s]
        if row.empty: continue
        vals = [row[c].values[0] / radar[c].max() * 100 if radar[c].max() > 0 else 0 for c in cats]
        vals.append(vals[0])
        fig_r.add_trace(go.Scatterpolar(
            r=vals, theta=cats + [cats[0]], fill="toself", name=s,
            line=dict(color=colors[i % 4]),
        ))
    fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                        title="綜合指標雷達圖（標準化%）", height=450)
    plotly_chart(fig_r, key="cmp_radar")


def page_cycle_week(data):
    """週循環分析"""
    bsh("bi-calendar-week", "週循環分析")
    filtered, _, _, _, sel_stores = get_date_filter(data, "wk")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    weeks = sorted(valid["年週"].unique(), reverse=True)
    sel_weeks = st.multiselect(
        "選擇要比較的週次（預設最新 3 週）",
        weeks, default=weeks[:min(3, len(weeks))], key="wk_sel",
    )
    if not sel_weeks:
        st.info("請至少選擇一週")
        return

    wk_data = valid[valid["年週"].isin(sel_weeks)]

    # 週彙總
    wk_sum = wk_data.groupby("年週").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    wk_sum["客單價"] = (wk_sum["營業額"] / wk_sum["來客數"]).round(0)
    wk_sum = wk_sum.sort_values("年週")

    st.subheader("週摘要")
    disp = wk_sum.copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    st.dataframe(disp, use_container_width=True, hide_index=True)

    # 週內日別對比
    st.subheader("各週 × 星期 營業額")
    wd = wk_data.groupby(["年週", "星期", "星期名"])["營業額"].sum().reset_index().sort_values("星期")
    fig = px.bar(wd, x="星期名", y="營業額", color="年週", barmode="group", height=400)
    fig.update_layout(xaxis_title="星期", yaxis_title="營業額（元）")
    fig.update_traces(hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="wk_weekday")

    # 熱力圖：日 × 門店
    bsh("bi-fire", "熱力圖：選定期間各門店每日營業額", level=3)
    heat = wk_data.pivot_table(index="門店", columns="日期", values="營業額", aggfunc="sum")
    if not heat.empty:
        fig_h = px.imshow(
            heat.values,
            labels=dict(x="日期", y="門店", color="營業額"),
            x=[d.strftime("%m/%d") for d in heat.columns],
            y=heat.index.tolist(),
            color_continuous_scale="YlOrRd", aspect="auto",
        )
        fig_h.update_layout(height=max(400, len(heat) * 25))
        plotly_chart(fig_h, key="wk_heat")


def page_cycle_month(data):
    """月循環比較"""
    bsh("bi-calendar-month", "月循環比較")
    filtered, _, _, _, sel_stores = get_date_filter(data, "mo")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    months = sorted(valid["年月"].unique(), reverse=True)
    sel_months = st.multiselect(
        "選擇要比較的月份（預設最新 3 個月）",
        months, default=months[:min(3, len(months))], key="mo_sel",
    )
    if not sel_months:
        st.info("請至少選擇一個月")
        return

    mo_data = valid[valid["年月"].isin(sel_months)]

    # 月度趨勢
    monthly = mo_data.groupby("年月").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    monthly["客單價"] = (monthly["營業額"] / monthly["來客數"]).round(0)
    monthly["營業額成長率"] = monthly["營業額"].pct_change() * 100
    monthly = monthly.sort_values("年月")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=monthly["年月"], y=monthly["營業額"], name="營業額",
                        marker_color="#4ECDC4",
                        hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>"))
    fig.add_trace(go.Scatter(x=monthly["年月"], y=monthly["客單價"], name="客單價",
                             mode="lines+markers", line=dict(color="#FF6B6B", width=2),
                             yaxis="y2",
                             hovertemplate="客單價：%{y:,.0f} 元<extra></extra>"))
    fig.update_layout(title="月度趨勢", height=400, hovermode="x unified",
                      yaxis=dict(title="營業額（元）"),
                      yaxis2=dict(title="客單價（元）", side="right", overlaying="y"))
    plotly_chart(fig, key="mo_trend")

    # 成長率表格
    st.subheader("月度成長率")
    disp = monthly.copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["營業額成長率"] = disp["營業額成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    disp = disp.rename(columns={"年月": "月份"})
    st.dataframe(disp[["月份", "營業額", "來客數", "客單價", "營業額成長率"]],
                 use_container_width=True, hide_index=True)


def page_cycle_quarter(data):
    """季循環分析"""
    bsh("bi-calendar3-range", "季循環分析")
    filtered, _, _, _, _ = get_date_filter(data, "qt")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    quarters = sorted(valid["年季"].unique(), reverse=True)
    sel_q = st.multiselect(
        "選擇要比較的季度（預設最新 4 季）",
        quarters, default=quarters[:min(4, len(quarters))], key="qt_sel",
    )
    if not sel_q:
        st.info("請至少選擇一季")
        return

    q_data = valid[valid["年季"].isin(sel_q)]
    q_sum = q_data.groupby("年季").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    q_sum["客單價"] = (q_sum["營業額"] / q_sum["來客數"]).round(0)
    q_sum["成長率"] = q_sum["營業額"].pct_change() * 100

    fig = px.bar(q_sum.sort_values("年季"), x="年季", y="營業額",
                 color="營業額", color_continuous_scale="Blues",
                 title="季度營業額", height=400)
    fig.update_traces(hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="qt_bar")

    disp = q_sum.sort_values("年季").copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["成長率"] = disp["成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_cycle_year(data):
    """年循環比較"""
    bsh("bi-calendar3", "年循環比較")
    filtered, _, _, _, _ = get_date_filter(data, "yr")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    years = sorted(valid["年份"].unique())
    if len(years) < 1:
        st.info("資料年份不足")
        return

    # 年度彙總
    yr_sum = valid.groupby("年份").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    yr_sum["客單價"] = (yr_sum["營業額"] / yr_sum["來客數"]).round(0)
    yr_sum["成長率"] = yr_sum["營業額"].pct_change() * 100

    fig = px.bar(yr_sum, x="年份", y="營業額", text=yr_sum["營業額"].apply(lambda x: f"{x/10000:,.0f}萬"),
                 color="年份", title="年度營業額", height=400)
    fig.update_traces(textposition="outside", hovertemplate="%{x}年<br>%{y:,.0f} 元<extra></extra>")
    plotly_chart(fig, key="yr_bar")

    # 年度同月對比
    if len(years) > 1:
        st.subheader("年度同月營業額對比")
        ym = valid.groupby(["年份", "月份"]).agg({"營業額": "sum"}).reset_index()
        fig_y = go.Figure()
        year_colors = ["#4ECDC4", "#FF6B6B", "#45B7D1"]
        for i, yr in enumerate(years):
            yd = ym[ym["年份"] == yr].sort_values("月份")
            fig_y.add_trace(go.Bar(
                x=[f"{m}月" for m in yd["月份"]], y=yd["營業額"],
                name=f"{yr}年", marker_color=year_colors[i % 3],
                hovertemplate=f"{yr}年 %{{x}}<br>%{{y:,.0f}} 元<extra></extra>",
            ))
        fig_y.update_layout(barmode="group", height=400, xaxis_title="月份", yaxis_title="營業額（元）")
        plotly_chart(fig_y, key="yr_yoy")

    # 明細
    disp = yr_sum.copy()
    disp["年份"] = disp["年份"].astype(str) + "年"
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["成長率"] = disp["成長率"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_region(data):
    """商圈分析"""
    bsh("bi-buildings", "商圈 / 區域競爭分析")
    filtered, _, _, _, _ = get_date_filter(data, "rg")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if valid.empty:
        st.warning("篩選後無資料")
        return

    # 區域總覽
    rg_sum = valid.groupby("區域").agg({"營業額": "sum", "來客數": "sum"}).reset_index()
    rg_sum["客單價"] = (rg_sum["營業額"] / rg_sum["來客數"]).round(0)
    rg_sum["門店數"] = valid.groupby("區域")["門店"].nunique().values
    rg_sum = rg_sum.sort_values("營業額", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(rg_sum, x="區域", y="營業額", color="區域",
                     text=rg_sum["營業額"].apply(lambda x: f"{x/10000:,.0f}萬"),
                     title="各區域總營業額", height=350)
        fig.update_traces(textposition="outside", hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>")
        fig.update_layout(showlegend=False)
        plotly_chart(fig, key="rg_bar")

    with c2:
        fig_pie = px.pie(rg_sum, values="營業額", names="區域", title="區域營收佔比", hole=0.4)
        fig_pie.update_traces(hovertemplate="%{label}<br>%{value:,.0f} 元<br>%{percent}<extra></extra>")
        fig_pie.update_layout(height=350)
        plotly_chart(fig_pie, key="rg_pie")

    # 選區域看內部
    sel_region = st.selectbox("選擇區域查看內部競爭", sorted(valid["區域"].dropna().unique()))
    rg_stores = valid[valid["區域"] == sel_region].groupby("門店").agg({
        "營業額": "sum", "來客數": "sum", "達成率": "first",
    }).reset_index()
    rg_stores["客單價"] = (rg_stores["營業額"] / rg_stores["來客數"]).round(0)
    rg_stores = rg_stores.sort_values("營業額", ascending=False)
    avg_rev = rg_stores["營業額"].mean()

    fig = go.Figure()
    colors = ["#44BB44" if r > avg_rev else "#FF6B6B" for r in rg_stores["營業額"]]
    fig.add_trace(go.Bar(x=rg_stores["門店"], y=rg_stores["營業額"], marker_color=colors,
                        hovertemplate="%{x}<br>%{y:,.0f} 元<extra></extra>"))
    fig.add_hline(y=avg_rev, line_dash="dash", line_color="blue",
                  annotation_text=f"區域平均 {avg_rev:,.0f} 元")
    fig.update_layout(title=f"【{sel_region}】門店營業額（綠=高於平均）",
                      height=350, xaxis_tickangle=-45)
    plotly_chart(fig, key="rg_inner")

    # 明細
    disp = rg_stores.copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["來客數"] = disp["來客數"].apply(lambda x: f"{x:,.0f} 人")
    disp["客單價"] = disp["客單價"].apply(lambda x: f"{x:,.0f} 元")
    disp["達成率"] = disp["達成率"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_target(data):
    """達標追蹤"""
    bsh("bi-bullseye", "本月達標進度追蹤")

    today = data["日期"].max().date()
    yr, mn = today.year, today.month
    days_in_month = calendar.monthrange(yr, mn)[1]
    day_of_month = today.day

    st.info(f"基準日：{today.strftime('%Y-%m-%d')}（資料最新日） ｜ 進度 {day_of_month}/{days_in_month} 天（{day_of_month/days_in_month*100:.0f}%）")

    # 所有歷史資料中出現過的非結村門店 → 主控清單（不因月份缺資料而消失）
    master = (data[~data["門店"].isin(CLOSED_STORES)]
              .groupby("門店")["區域"].first()
              .reset_index())

    cur = data[
        (data["日期"].dt.year == yr) & (data["日期"].dt.month == mn)
        & ~data["門店"].isin(CLOSED_STORES)
    ]
    cur_valid = cur[cur["營業額"].notna() & (cur["營業額"] > 0)]

    if not cur_valid.empty:
        sp = cur_valid.groupby("門店").agg(
            營業額=("營業額", "sum"),
            來客數=("來客數", "sum"),
            本月目標=("本月目標", "first"),
        ).reset_index()
        day_cnt = cur_valid.groupby("門店")["日期"].nunique().rename("已營業天數").reset_index()
        sp = sp.merge(day_cnt, on="門店", how="left")
    else:
        sp = pd.DataFrame(columns=["門店", "營業額", "來客數", "本月目標", "已營業天數"])

    # left join：所有門店皆出現，缺資料者填 0 / NaN
    store_progress = master.merge(sp, on="門店", how="left")
    store_progress["已營業天數"] = store_progress["已營業天數"].fillna(0).astype(int)
    store_progress["營業額"] = store_progress["營業額"].fillna(0)
    store_progress["來客數"] = store_progress["來客數"].fillna(0)

    store_progress["日均實際"] = store_progress.apply(
        lambda r: round(r["營業額"] / r["已營業天數"], 0) if r["已營業天數"] > 0 else 0, axis=1
    )
    store_progress["預估月營收"] = (store_progress["日均實際"] * days_in_month).round(0)
    store_progress["預估達成率"] = store_progress.apply(
        lambda r: round(r["預估月營收"] / r["本月目標"] * 100, 1)
        if pd.notna(r["本月目標"]) and r["本月目標"] > 0 else None, axis=1
    )
    store_progress["目前達成率"] = store_progress.apply(
        lambda r: round(r["營業額"] / r["本月目標"] * 100, 1)
        if pd.notna(r["本月目標"]) and r["本月目標"] > 0 else None, axis=1
    )
    store_progress["狀態"] = store_progress["預估達成率"].apply(
        lambda x: "可達標" if pd.notna(x) and x >= 100 else ("略低" if pd.notna(x) and x >= 85 else "危險")
    )
    store_progress = store_progress.sort_values("預估達成率", ascending=False, na_position="last")

    ok_mask = store_progress["預估達成率"].notna()
    c1, c2, c3 = st.columns(3)
    c1.metric("預估可達標", f"{(ok_mask & (store_progress['預估達成率'] >= 100)).sum()} 店")
    c2.metric("預估危險",
              f"{(ok_mask & (store_progress['預估達成率'] < 85)).sum() + (~ok_mask).sum()} 店")
    c3.metric("本月剩餘天數", f"{days_in_month - day_of_month} 天")

    rates = store_progress["預估達成率"].fillna(0)
    colors = ["#44BB44" if r >= 100 else ("#FFaa00" if r >= 85 else "#FF4444") for r in rates]
    labels = [
        f"{r_orig:.0f}%" if pd.notna(r_orig) else "無資料"
        for r_orig in store_progress["預估達成率"]
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=store_progress["門店"], y=rates,
        marker_color=colors, text=labels, textposition="outside",
        hovertemplate="%{x}<br>預估達成率：%{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="目標 100%")
    fig.update_layout(
        title=f"{yr}年{mn}月 各門店預估達成率（{len(store_progress)} 間）",
        height=480, xaxis_tickangle=-45, yaxis_title="預估達成率（%）",
    )
    plotly_chart(fig, key="tg_bar")

    disp = store_progress[["區域", "門店", "營業額", "本月目標", "目前達成率",
                            "日均實際", "預估月營收", "預估達成率", "狀態"]].copy()
    disp["營業額"] = disp["營業額"].apply(lambda x: f"{x:,.0f} 元" if x > 0 else "—")
    disp["本月目標"] = disp["本月目標"].apply(lambda x: f"{x:,.0f} 元" if pd.notna(x) else "—")
    disp["日均實際"] = disp["日均實際"].apply(lambda x: f"{x:,.0f} 元" if x > 0 else "—")
    disp["預估月營收"] = disp["預估月營收"].apply(lambda x: f"{x:,.0f} 元" if x > 0 else "—")
    disp["目前達成率"] = disp["目前達成率"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
    disp["預估達成率"] = disp["預估達成率"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_drill(data):
    """單店下鑽"""
    bsh("bi-search", "單店下鑽分析")
    filtered, _, _, _, sel_stores = get_date_filter(data, "dr")
    valid = filtered[filtered["營業額"].notna() & (filtered["營業額"] > 0)]

    if not sel_stores:
        st.warning("請在篩選條件中至少選擇 1 間門店")
        return

    store = st.selectbox("選擇門店", sel_stores, key="dr_drill_store")
    sd = valid[valid["門店"] == store].sort_values("日期")

    if sd.empty:
        st.warning("此門店在選定期間無資料")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("總營業額", f"{sd['營業額'].sum():,.0f} 元")
    c2.metric("總來客數", f"{sd['來客數'].sum():,.0f} 人")
    avg = sd["營業額"].sum() / sd["來客數"].sum() if sd["來客數"].sum() > 0 else 0
    c3.metric("平均客單價", f"{avg:,.0f} 元")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sd["日期"], y=sd["營業額"], mode="lines+markers",
                              line=dict(color="#4ECDC4", width=2), fill="tozeroy",
                              hovertemplate="%{x|%m/%d}<br>%{y:,.0f} 元<extra></extra>"))
    fig.update_layout(title=f"{store} — 每日營業額走勢", height=350,
                      xaxis_title="日期", yaxis_title="營業額（元）")
    plotly_chart(fig, key="dr_line")

    # 星期分析
    wd = sd.groupby(["星期", "星期名"]).agg({"營業額": "mean"}).reset_index().sort_values("星期")
    fig_w = px.bar(wd, x="星期名", y="營業額", color="營業額",
                   color_continuous_scale="Viridis",
                   title=f"{store} — 平均營業額（按星期）", height=300)
    fig_w.update_traces(hovertemplate="%{x}<br>平均 %{y:,.0f} 元<extra></extra>")
    plotly_chart(fig_w, key="dr_weekday")


def page_alert(data):
    """異常警示"""
    bsh("bi-exclamation-triangle", "未達日均目標警示")
    filtered, _, _, _, _ = get_date_filter(data, "al")
    alert_data = filtered.copy()
    alert_data["當月天數"] = alert_data["日期"].apply(
        lambda x: calendar.monthrange(x.year, x.month)[1]
    )
    alert_data["日均目標"] = alert_data["本月目標"] / alert_data["當月天數"]
    hs = alert_data[alert_data["日均目標"].notna() & (alert_data["日均目標"] > 0)
                    & alert_data["營業額"].notna()].copy()

    if hs.empty:
        st.warning("無足夠資料")
        return

    hs["未達標"] = hs["營業額"] < hs["日均目標"]
    hs["差額"] = hs["日均目標"] - hs["營業額"]
    hs.loc[~hs["未達標"], "差額"] = 0

    sa = hs.groupby(["區域", "門店"]).agg(
        有效天數=("營業額", "count"),
        未達標次數=("未達標", "sum"),
        損失營業額=("差額", "sum"),
        日均目標=("日均目標", "mean"),
        實際日均=("營業額", "mean"),
    ).reset_index()
    sa["未達標率"] = (sa["未達標次數"] / sa["有效天數"] * 100).round(1)
    sa = sa.sort_values("損失營業額", ascending=False)

    total_miss = int(sa["未達標次數"].sum())
    total_loss = sa["損失營業額"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("全店未達標次數", f"{total_miss} 次")
    c2.metric("累計損失營業額", f"{total_loss:,.0f} 元")
    c3.metric("損失最多門店", sa.iloc[0]["門店"] if len(sa) else "—")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sa["門店"], y=sa["損失營業額"],
        marker_color=["#FF4444" if r > 50 else "#FFaa00" for r in sa["未達標率"]],
        hovertemplate="%{x}<br>損失：%{y:,.0f} 元<extra></extra>",
    ))
    fig.update_layout(title="各門店累計損失營業額", height=400, xaxis_tickangle=-45,
                      yaxis_title="損失營業額（元）")
    plotly_chart(fig, key="al_loss")

    disp = sa[["區域", "門店", "有效天數", "未達標次數", "未達標率", "日均目標", "實際日均", "損失營業額"]].copy()
    disp["日均目標"] = disp["日均目標"].apply(lambda x: f"{x:,.0f} 元")
    disp["實際日均"] = disp["實際日均"].apply(lambda x: f"{x:,.0f} 元")
    disp["損失營業額"] = disp["損失營業額"].apply(lambda x: f"{x:,.0f} 元")
    disp["未達標次數"] = disp["未達標次數"].astype(int).astype(str) + " 次"
    disp["未達標率"] = disp["未達標率"].apply(lambda x: f"{x:.1f}%")
    disp["有效天數"] = disp["有效天數"].astype(int).astype(str) + " 天"
    st.dataframe(disp, use_container_width=True, hide_index=True)


# ============================================================
# 共用圖表函數
# ============================================================
def make_revenue_bar(daily):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["日期"], y=daily["營業額"], name="營業額",
        marker_color="#4ECDC4",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f} 元<extra></extra>",
    ))
    # 標記峰值
    if not daily.empty:
        peak_idx = daily["營業額"].idxmax()
        peak = daily.loc[peak_idx]
        fig.add_annotation(
            x=peak["日期"], y=peak["營業額"],
            text=f"峰值 {peak['營業額']:,.0f}",
            showarrow=True, arrowhead=2, bgcolor="#FFF3C4",
        )
    fig.update_layout(title="全店每日營業額", height=400, hovermode="x unified",
                      xaxis_title="日期", yaxis_title="營業額（元）")
    return fig


def make_dual_axis(daily):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["日期"], y=daily["來客數"], name="來客數", marker_color="#45B7D1",
        hovertemplate="%{x|%Y-%m-%d}<br>來客數：%{y:,.0f} 人<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=daily["日期"], y=daily["客單價"], name="客單價",
        mode="lines+markers", line=dict(color="#FF6B6B", width=2), yaxis="y2",
        hovertemplate="客單價：%{y:,.0f} 元<extra></extra>",
    ))
    fig.update_layout(
        title="來客數 與 客單價", height=400, hovermode="x unified",
        xaxis_title="日期",
        yaxis=dict(title="來客數（人）", side="left"),
        yaxis2=dict(title="客單價（元）", side="right", overlaying="y"),
    )
    return fig


# ============================================================
# AI 洞察：規則引擎
# ============================================================
def generate_rule_insights(data):
    """規則引擎：分析數據並生成文字洞察列表"""
    insights = []
    valid = data[data["營業額"].notna() & (data["營業額"] > 0)]
    if valid.empty:
        return insights

    today = valid["日期"].max().date()
    yesterday = today - timedelta(days=1)
    yr, mn = today.year, today.month
    days_in_month = calendar.monthrange(yr, mn)[1]
    day_of_month = today.day

    # 1. 昨日摘要
    yd = valid[valid["日期"].dt.date == yesterday]
    if not yd.empty:
        yd_rev = yd["營業額"].sum()
        yd_cust = yd["來客數"].sum()
        yd_stores = yd["門店"].nunique()
        day_before = yesterday - timedelta(days=1)
        db = valid[valid["日期"].dt.date == day_before]
        db_rev = db["營業額"].sum() if not db.empty else 0
        change = (yd_rev - db_rev) / db_rev * 100 if db_rev > 0 else None
        change_text = f"，較前日 {change:+.1f}%" if change is not None else ""
        insights.append({
            "category": "昨日摘要", "icon": '<i class="bi bi-bar-chart-line"></i>', "level": "info",
            "title": f"昨日（{yesterday.strftime('%m/%d')}）全店營業額 {yd_rev/10000:.1f} 萬元",
            "detail": f"來客 {yd_cust:,.0f} 人，{yd_stores} 間門店有營業紀錄{change_text}",
        })
        top_store_s = yd.groupby("門店")["營業額"].sum()
        top_store = top_store_s.idxmax()
        top_rev = top_store_s.max()
        insights.append({
            "category": "昨日之星", "icon": '<i class="bi bi-trophy"></i>', "level": "success",
            "title": f"昨日冠軍：{top_store}",
            "detail": f"營業額 {top_rev:,.0f} 元",
        })

    # 2. 本月達標概況
    cur = valid[(valid["日期"].dt.year == yr) & (valid["日期"].dt.month == mn)]
    cur_active = cur[~cur["門店"].isin(CLOSED_STORES)]
    if not cur_active.empty:
        sp = cur_active.groupby("門店").agg(
            actual=("營業額", "sum"),
            days=("日期", "nunique"),
            target=("本月目標", "first"),
        ).reset_index()
        sp = sp[sp["target"].notna() & (sp["target"] > 0)]
        if not sp.empty:
            sp["projected"] = sp["actual"] / sp["days"] * days_in_month
            sp["proj_rate"] = sp["projected"] / sp["target"] * 100
            danger = sp[sp["proj_rate"] < 85]
            on_track = sp[sp["proj_rate"] >= 100]
            insights.append({
                "category": "達標概況", "icon": '<i class="bi bi-bullseye"></i>', "level": "info",
                "title": f"本月預估：{len(on_track)} 間可達標 / {len(danger)} 間高風險",
                "detail": f"月份進度 {day_of_month}/{days_in_month} 天（{day_of_month/days_in_month*100:.0f}%）",
            })
            if not danger.empty:
                names = "、".join(danger.sort_values("proj_rate")["門店"].tolist())
                insights.append({
                    "category": "達標預警", "icon": '<i class="bi bi-exclamation-circle"></i>', "level": "error",
                    "title": f"以下 {len(danger)} 間門店達標率預估不足 85%",
                    "detail": names,
                })

    # 3. 連續 3 天低於日均目標
    recent = valid[valid["日期"].dt.date >= (today - timedelta(days=6))].copy()
    if not recent.empty:
        recent["日均目標"] = recent["本月目標"] / recent["日期"].apply(
            lambda x: calendar.monthrange(x.year, x.month)[1]
        )
        recent = recent[recent["日均目標"].notna() & (recent["日均目標"] > 0)]
        recent["未達標"] = recent["營業額"] < recent["日均目標"]
        cons = (
            recent.sort_values("日期")
            .groupby("門店")["未達標"]
            .apply(lambda s: s.tail(3).all())
            .reset_index(name="連續未達")
        )
        bad = cons[cons["連續未達"]]["門店"].tolist()
        if bad:
            insights.append({
                "category": "連續警示", "icon": '<i class="bi bi-exclamation-triangle"></i>', "level": "warning",
                "title": f"{len(bad)} 間門店連續 3 天低於日均目標",
                "detail": "、".join(bad),
            })

    # 4. 週環比
    week_sum = valid.groupby("年週")["營業額"].sum().reset_index().sort_values("年週")
    if len(week_sum) >= 2:
        this_w = week_sum.iloc[-1]["營業額"]
        last_w = week_sum.iloc[-2]["營業額"]
        wow = (this_w - last_w) / last_w * 100 if last_w > 0 else 0
        insights.append({
            "category": "週環比", "icon": '<i class="bi bi-graph-up-arrow"></i>' if wow >= 0 else '<i class="bi bi-graph-down-arrow"></i>',
            "level": "success" if wow >= 0 else "warning",
            "title": f"本週較上週 {wow:+.1f}%",
            "detail": f"本週 {this_w/10000:.1f} 萬 vs 上週 {last_w/10000:.1f} 萬",
        })

    # 5. 客單價異常（低於近 30 日平均 15%）
    recent30 = valid[valid["日期"].dt.date >= (today - timedelta(days=30))]
    if not recent30.empty and not yd.empty:
        avg_aov = recent30["客單價"].mean()
        yd_aov = yd["客單價"].mean()
        if pd.notna(avg_aov) and pd.notna(yd_aov) and avg_aov > 0:
            drop = (avg_aov - yd_aov) / avg_aov * 100
            if drop > 15:
                insights.append({
                    "category": "客單價警示", "icon": '<i class="bi bi-cash-coin"></i>', "level": "warning",
                    "title": f"昨日客單價較近 30 日均低 {drop:.1f}%",
                    "detail": f"昨日 {yd_aov:,.0f} 元 vs 近期均值 {avg_aov:,.0f} 元",
                })

    return insights


def _insight_card(ins):
    """渲染單張洞察卡片（Premium 版）"""
    palette = {
        "success": ("#D1FAE5", "#10B981", "#065F46"),
        "error":   ("#FEE2E2", "#EF4444", "#991B1B"),
        "warning": ("#FEF3C7", "#F59E0B", "#92400E"),
        "info":    ("#DBEAFE", "#3B82F6", "#1E40AF"),
    }
    bg, icon_bg, text_col = palette.get(ins["level"], ("#F1F5F9", "#64748B", "#334155"))
    st.markdown(f"""
<div class="insight-card">
  <div class="insight-icon" style="background:{bg}">
    <span style="color:{icon_bg}">{ins['icon']}</span>
  </div>
  <div class="insight-body">
    <div class="insight-cat" style="color:{icon_bg}">{ins['category']}</div>
    <div class="insight-title">{ins['title']}</div>
    <div class="insight-detail">{ins['detail']}</div>
  </div>
</div>""", unsafe_allow_html=True)


def _build_data_context(data):
    """建立 AI 分析用的資料摘要字串"""
    valid = data[data["營業額"].notna() & (data["營業額"] > 0)]
    today = valid["日期"].max().date()
    yr, mn = today.year, today.month

    monthly = valid[(valid["日期"].dt.year == yr) & (valid["日期"].dt.month == mn)]
    sp = monthly.groupby("門店").agg(
        營業額=("營業額", "sum"), 來客數=("來客數", "sum"), 本月目標=("本月目標", "first"),
    ).reset_index()
    sp["達成率%"] = (sp["營業額"] / sp["本月目標"] * 100).round(1)

    week_sum = valid.groupby("年週")["營業額"].sum().reset_index().sort_values("年週")
    wow_text = ""
    if len(week_sum) >= 2:
        this_w = week_sum.iloc[-1]["營業額"]
        last_w = week_sum.iloc[-2]["營業額"]
        wow = (this_w - last_w) / last_w * 100 if last_w > 0 else 0
        wow_text = f"\n最新週環比：{wow:+.1f}%（本週 {this_w/10000:.1f} 萬 vs 上週 {last_w/10000:.1f} 萬）"

    return f"""=== 嗑肉石鍋 {yr}年{mn}月 門店數據（截至 {today}）===
{sp.to_string(index=False)}
{wow_text}
"""


def call_claude_api_stream(data, api_key, messages_history):
    """Claude API 串流介面，支援多輪對話；generator 形式"""
    try:
        import anthropic
    except ImportError:
        yield "請先安裝套件：`pip install anthropic`"
        return

    context = _build_data_context(data)
    system_prompt = (
        "你是嗑肉石鍋火鍋連鎖餐飲業的專屬數據分析顧問，擁有豐富的餐飲業 KPI 分析與門店管理經驗。"
        "請用繁體中文回覆，語氣專業但親切，善用條列格式，給出具體可行的建議。\n\n"
        f"以下是最新營業數據供參考：\n{context}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        with client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=2000,
            system=system_prompt,
            messages=messages_history,
        ) as stream:
            for text in stream.text_stream:
                yield text
    except Exception as e:
        yield f"\n\n⚠️ API 呼叫失敗：{e}"


# 快速問題清單
_QUICK_QUESTIONS = [
    "本月哪間門店表現最亮眼？原因為何？",
    "哪些門店達標風險最高？給我具體改善行動清單",
    "用表格幫我比較各區域本月業績",
    "本週和上週相比，趨勢如何？",
    "客單價最低的門店，如何提升？",
    "請幫我寫一份給老闆的本月簡報摘要",
]


def page_ai_insights(data):
    """AI 洞察 — 升級版"""

    # ── AI 助理 Header ──
    st.markdown("""
<div class="ai-header">
  <div class="ai-header-icon"><i class="bi bi-robot"></i></div>
  <div class="ai-header-text">
    <h3>AI 數據分析助理</h3>
    <p>由 Claude Opus 驅動・嗑肉石鍋專屬顧問・支援多輪對話</p>
  </div>
</div>""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🤖 AI 智慧對話", "📊 規則引擎洞察"])

    with tab1:
        # ── API Key ──
        secret_key = ""
        try:
            secret_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass

        if secret_key:
            api_key = secret_key
            st.success("✅ API Key 已從 Streamlit Secrets 自動載入，可直接開始對話。", icon=None)
        else:
            with st.expander("🔑 設定 API Key", expanded=True):
                st.info(
                    "請至 Streamlit Cloud → Settings → Secrets 新增：\n"
                    "`ANTHROPIC_API_KEY = \"sk-ant-...\"`，或在下方手動輸入。"
                )
                api_key = st.text_input(
                    "Anthropic API Key", type="password",
                    placeholder="sk-ant-...", key="claude_key",
                )

        st.markdown('<div class="section-header"><i class="bi bi-lightning-charge-fill"></i><span>快速提問</span></div>', unsafe_allow_html=True)

        # 快速問題按鈕（用 columns 排列）
        if "pending_question" not in st.session_state:
            st.session_state.pending_question = ""

        cols_q = st.columns(3)
        for i, q in enumerate(_QUICK_QUESTIONS):
            with cols_q[i % 3]:
                if st.button(q, key=f"qq_{i}", use_container_width=True):
                    st.session_state.pending_question = q

        st.markdown('<div class="section-header"><i class="bi bi-chat-dots-fill"></i><span>對話記錄</span></div>', unsafe_allow_html=True)

        # ── 對話歷史 ──
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # 渲染對話氣泡
        chat_html = '<div class="chat-wrap">'
        if not st.session_state.chat_history:
            chat_html += """
<div class="empty-chat">
  <i class="bi bi-chat-dots"></i>
  <p>選擇快速提問或在下方輸入問題，開始與 AI 顧問對話</p>
</div>"""
        else:
            for msg in st.session_state.chat_history:
                role = msg["role"]
                content = msg["content"].replace("\n", "<br>")
                ts = msg.get("ts", "")
                if role == "user":
                    chat_html += f"""
<div class="chat-row user-row">
  <div class="chat-avatar user-av"><i class="bi bi-person-fill"></i></div>
  <div>
    <div class="chat-bubble user-bubble">{content}</div>
    <div class="chat-meta">{ts}</div>
  </div>
</div>"""
                else:
                    chat_html += f"""
<div class="chat-row">
  <div class="chat-avatar ai-av"><i class="bi bi-robot"></i></div>
  <div>
    <div class="chat-bubble ai-bubble">{content}</div>
    <div class="chat-meta">Claude Opus・{ts}</div>
  </div>
</div>"""
        chat_html += "</div>"
        st.markdown(f'<div class="chat-panel">{chat_html}</div>', unsafe_allow_html=True)

        # ── 輸入區 ──
        c_input, c_send, c_clear = st.columns([6, 1, 1])
        with c_input:
            default_val = st.session_state.pop("pending_question", "") if st.session_state.get("pending_question") else ""
            user_input = st.text_input(
                "問題", value=default_val,
                placeholder="輸入你的問題，例如：本月哪間門店最需要立即關注？",
                label_visibility="collapsed", key="chat_input",
            )
        with c_send:
            send = st.button("送出", type="primary", use_container_width=True, key="chat_send")
        with c_clear:
            if st.button("清除", use_container_width=True, key="chat_clear"):
                st.session_state.chat_history = []
                st.rerun()

        if send and user_input.strip():
            if not api_key:
                st.error("請先設定 API Key")
            else:
                now_str = datetime.now().strftime("%H:%M")
                st.session_state.chat_history.append({"role": "user", "content": user_input.strip(), "ts": now_str})

                api_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history]

                with st.spinner("AI 顧問思考中…"):
                    full_reply = ""
                    try:
                        for chunk in call_claude_api_stream(data, api_key, api_messages):
                            full_reply += chunk
                    except Exception as e:
                        full_reply = f"發生錯誤：{e}"

                st.session_state.chat_history.append({"role": "assistant", "content": full_reply, "ts": now_str})
                st.rerun()

    with tab2:
        c_refresh, _ = st.columns([1, 4])
        with c_refresh:
            if st.button("重新分析", key="ai_refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        insights = generate_rule_insights(data)
        if not insights:
            st.info("資料不足，無法產生洞察")
            return
        for ins in insights:
            _insight_card(ins)


# ============================================================
# 主程式
# ============================================================
def main():
    # 載入資料
    with st.spinner("載入資料中..."):
        data = load_all_data()

    if data.empty:
        st.error("無法載入資料")
        return

    # 側邊欄：品牌 Banner
    st.sidebar.markdown(f"""
<div class="sb-brand">
  <div style="display:flex;align-items:center;gap:10px;position:relative;z-index:1">
    <i class="bi bi-cup-hot-fill" style="font-size:1.6rem;color:#fff;opacity:.9"></i>
    <div>
      <div class="sb-brand-name">嗑肉石鍋</div>
      <div class="sb-brand-sub">營收儀表板 · 即時數據</div>
    </div>
  </div>
  <div style="margin-top:10px;font-size:.7rem;color:rgba(255,255,255,.6);position:relative;z-index:1">
    <i class="bi bi-clock"></i> {datetime.now().strftime('%Y/%m/%d %H:%M')} 更新
  </div>
</div>""", unsafe_allow_html=True)
    st.sidebar.divider()

    pages = {
        "總覽": page_overview,
        "AI 洞察": page_ai_insights,
        "門店排行": page_store_rank,
        "店對店比較": page_store_compare,
        "週循環分析": page_cycle_week,
        "月循環比較": page_cycle_month,
        "季循環分析": page_cycle_quarter,
        "年循環比較": page_cycle_year,
        "商圈分析": page_region,
        "達標追蹤": page_target,
        "單店下鑽": page_drill,
        "異常警示": page_alert,
    }

    selected = st.sidebar.radio("功能選單", list(pages.keys()), label_visibility="collapsed")

    st.sidebar.divider()

    # 昨日摘要 sidebar widget
    valid_all = data[data["營業額"].notna() & (data["營業額"] > 0)]
    if not valid_all.empty:
        latest = valid_all["日期"].max().date()
        yesterday = latest - timedelta(days=1)
        yd = valid_all[valid_all["日期"].dt.date == yesterday]
        if not yd.empty:
            yd_rev = yd["營業額"].sum()
            yd_cust = yd["來客數"].sum()
            db = valid_all[valid_all["日期"].dt.date == (yesterday - timedelta(days=1))]
            db_rev = db["營業額"].sum() if not db.empty else 0
            wow = (yd_rev - db_rev) / db_rev * 100 if db_rev > 0 else 0
            arrow = "▲" if wow >= 0 else "▼"
            color = "#28a745" if wow >= 0 else "#dc3545"
            wow_cls = "up" if wow >= 0 else "dn"
            wow_icon = "bi-arrow-up-short" if wow >= 0 else "bi-arrow-down-short"
            st.sidebar.markdown(f"""
<div style="font-size:.75rem;font-weight:800;color:#94A3B8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">
  <i class="bi bi-calendar-check-fill" style="color:#FF6B35"></i> 昨日摘要
</div>
<div class="yd-card">
  <div class="yd-title">{yesterday.strftime('%m/%d')}（{WEEKDAY_MAP.get(yesterday.weekday(), '')}）全店</div>
  <div class="yd-row">
    <i class="bi bi-cash-coin" style="color:#FF6B35"></i>
    <span class="yd-val">{yd_rev/10000:.1f} 萬元</span>
    <span class="{wow_cls}"><i class="bi {wow_icon}"></i>{abs(wow):.1f}%</span>
  </div>
  <div class="yd-row">
    <i class="bi bi-people-fill" style="color:#3B82F6"></i>
    <span class="yd-val">{yd_cust:,.0f} 人</span>
    <span style="color:#94A3B8;font-size:.75rem">{yd['門店'].nunique()} 間門店</span>
  </div>
</div>""", unsafe_allow_html=True)
            st.sidebar.divider()

    # 工具列
    st.sidebar.markdown('<div style="font-size:.75rem;font-weight:800;color:#94A3B8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">工具</div>', unsafe_allow_html=True)
    if st.sidebar.button("🔄 重新載入資料", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    valid_all = data[data["營業額"].notna() & (data["營業額"] > 0)]
    export_df = valid_all[["日期", "區域", "門店", "營業額", "來客數", "客單價", "本月目標", "達成率"]].copy()
    export_df["日期"] = export_df["日期"].dt.strftime("%Y-%m-%d")

    def to_excel(df):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="營收資料")
        return out.getvalue()

    st.sidebar.download_button(
        label="📥 匯出 Excel",
        data=to_excel(export_df),
        file_name=f"嗑肉石鍋_營收_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    # 版本資訊
    st.sidebar.divider()
    st.sidebar.markdown(
        '<div style="font-size:.7rem;color:#CBD5E1;text-align:center;line-height:1.8">'
        'Powered by <strong>Claude Opus</strong><br>'
        '嗑肉石鍋 Dashboard v6.0<br>'
        '<span style="color:#FF6B35">★ Premium Edition</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # 執行選中的分頁
    pages[selected](data)


if __name__ == "__main__":
    main()
