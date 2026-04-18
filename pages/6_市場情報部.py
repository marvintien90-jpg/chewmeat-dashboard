import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="嗑肉石鍋 ｜ 市場情報部",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("app.py", label="← 返回數位總部大門", use_container_width=False)
    st.stop()

# ──────────────────────────────────────────────
# CSS（橘紅配色・扁平圓角・全中文）
# ──────────────────────────────────────────────
st.markdown("""
<style>
    .main .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    [data-testid="stSidebarNav"] {display: none !important;}
    [data-testid="stSidebar"] {background: #FAFAFA;}
    .section-header {
        background: #E63B1F; color: white;
        padding: 7px 16px; border-radius: 8px;
        margin: 1rem 0 0.5rem 0; font-weight: 700; font-size: 0.95rem;
    }
    [data-testid="stMetric"] {
        background: #FFFFFF; padding: 14px; border-radius: 10px;
        border: 1.5px solid #F0E8E5;
        box-shadow: 0 1px 4px rgba(230,59,31,0.07);
    }
    [data-testid="stMetricLabel"] {font-size: 0.85rem; color: #888;}
    [data-testid="stMetricValue"] {font-size: 1.5rem; font-weight: 700; color: #1A1A1A;}
    .intel-card {
        background: #FFFFFF; border: 1.5px solid #F0E8E5;
        border-radius: 12px; padding: 1rem 1.2rem;
        margin-bottom: 0.8rem; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .brand-tag {
        display: inline-block; padding: 3px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 700; margin-right: 6px;
    }
    .tag-self   { background: #FDECEC; color: #C0392B; }
    .tag-rival  { background: #EBF5FB; color: #1A5276; }
    .tag-market { background: #E9F7EF; color: #1E8449; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 側邊欄
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 市場情報部")
    st.caption("競品情報 × 服務品質雷達")
    st.divider()
    st.page_link("app.py",               label="🏢 返回總部大門")
    st.page_link("pages/1_營收看板.py",   label="📊 財務部 — 營收看板")
    st.page_link("pages/3_智能戰情室.py", label="🧠 智能戰情室")
    st.page_link("pages/5_品牌行銷部.py", label="🎨 品牌行銷部")
    st.divider()
    region_filter = st.selectbox("選擇商圈", ["全部商圈", "台中", "台北", "高雄", "彰化"])

# ──────────────────────────────────────────────
# 標題
# ──────────────────────────────────────────────
st.markdown("# 🔍 市場情報部")
st.markdown("**競品價格區間 × 服務星等雷達** — 掌握市場定位，強化競爭優勢")
st.divider()

# ──────────────────────────────────────────────
# 競品資料（靜態範例）
# ──────────────────────────────────────────────
competitors = pd.DataFrame([
    # 品牌, 類型, 商圈, 均價, 最低價, 最高價, 服務各維度
    {"品牌": "嗑肉石鍋（自家）", "類型": "石鍋", "商圈": "台中", "均價": 320, "最低價": 258, "最高價": 488,
     "服務品質": 4.2, "菜單多樣性": 3.8, "CP值": 4.5, "環境氛圍": 4.0, "等位體驗": 3.5, "品牌知名度": 3.6},
    {"品牌": "石二鍋", "類型": "石鍋", "商圈": "台中", "均價": 299, "最低價": 199, "最高價": 399,
     "服務品質": 3.8, "菜單多樣性": 3.5, "CP值": 4.2, "環境氛圍": 3.7, "等位體驗": 3.8, "品牌知名度": 4.5},
    {"品牌": "瓦城泰國料理", "類型": "中高價炒鍋", "商圈": "台中", "均價": 450, "最低價": 320, "最高價": 680,
     "服務品質": 4.5, "菜單多樣性": 4.3, "CP值": 3.5, "環境氛圍": 4.6, "等位體驗": 3.2, "品牌知名度": 4.8},
    {"品牌": "爭鮮迴轉壽司", "類型": "迴轉壽司", "商圈": "台中", "均價": 280, "最低價": 150, "最高價": 420,
     "服務品質": 3.6, "菜單多樣性": 4.0, "CP值": 4.0, "環境氛圍": 3.5, "等位體驗": 4.0, "品牌知名度": 4.3},
    {"品牌": "嗑肉石鍋（自家）", "類型": "石鍋", "商圈": "台北", "均價": 345, "最低價": 258, "最高價": 498,
     "服務品質": 4.3, "菜單多樣性": 3.9, "CP值": 4.3, "環境氛圍": 4.1, "等位體驗": 3.4, "品牌知名度": 3.5},
    {"品牌": "鼎泰豐", "類型": "中高價餐廳", "商圈": "台北", "均價": 580, "最低價": 380, "最高價": 900,
     "服務品質": 4.9, "菜單多樣性": 3.8, "CP值": 3.2, "環境氛圍": 4.8, "等位體驗": 2.8, "品牌知名度": 5.0},
    {"品牌": "胡同燒肉", "類型": "燒肉", "商圈": "台北", "均價": 680, "最低價": 480, "最高價": 1200,
     "服務品質": 4.6, "菜單多樣性": 4.2, "CP值": 3.0, "環境氛圍": 4.7, "等位體驗": 3.0, "品牌知名度": 4.2},
    {"品牌": "嗑肉石鍋（自家）", "類型": "石鍋", "商圈": "高雄", "均價": 298, "最低價": 238, "最高價": 458,
     "服務品質": 4.0, "菜單多樣性": 3.7, "CP值": 4.4, "環境氛圍": 3.9, "等位體驗": 3.8, "品牌知名度": 3.3},
    {"品牌": "漢來海港餐廳", "類型": "海鮮合菜", "商圈": "高雄", "均價": 780, "最低價": 580, "最高價": 1500,
     "服務品質": 4.7, "菜單多樣性": 4.6, "CP值": 3.3, "環境氛圍": 4.9, "等位體驗": 2.5, "品牌知名度": 4.6},
    {"品牌": "呷哺呷哺", "類型": "火鍋", "商圈": "高雄", "均價": 260, "最低價": 188, "最高價": 360,
     "服務品質": 3.7, "菜單多樣性": 3.9, "CP值": 4.3, "環境氛圍": 3.6, "等位體驗": 4.2, "品牌知名度": 3.8},
])

SERVICE_DIMS = ["服務品質", "菜單多樣性", "CP值", "環境氛圍", "等位體驗", "品牌知名度"]

if region_filter != "全部商圈":
    competitors_view = competitors[competitors["商圈"] == region_filter]
else:
    competitors_view = competitors.copy()

self_brand = "嗑肉石鍋（自家）"
rivals = competitors_view[competitors_view["品牌"] != self_brand]
self_data = competitors_view[competitors_view["品牌"] == self_brand]

# ──────────────────────────────────────────────
# KPI 列
# ──────────────────────────────────────────────
self_avg_price = self_data["均價"].mean() if not self_data.empty else 0
rival_avg_price = rivals["均價"].mean() if not rivals.empty else 0
self_cp = self_data["CP值"].mean() if not self_data.empty else 0
rival_cp = rivals["CP值"].mean() if not rivals.empty else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("🏷️ 嗑肉均價", f"${self_avg_price:.0f}", delta=f"競品均 ${rival_avg_price:.0f}")
c2.metric("⭐ 自家 CP 值評分", f"{self_cp:.1f} 分")
c3.metric("🏆 競品 CP 值均分", f"{rival_cp:.1f} 分")
c4.metric("🔎 監控競品數", len(rivals["品牌"].unique()))

st.divider()

# ──────────────────────────────────────────────
# 圖一：競品價格區間（箱型 + 散點）
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">💰 競品價格區間分佈（均價 / 最低 / 最高）</div>', unsafe_allow_html=True)

fig1 = go.Figure()

colors = {"嗑肉石鍋（自家）": "#E63B1F", "石二鍋": "#3498DB", "瓦城泰國料理": "#9B59B6",
          "爭鮮迴轉壽司": "#27AE60", "鼎泰豐": "#F39C12", "胡同燒肉": "#E74C3C",
          "漢來海港餐廳": "#1ABC9C", "呷哺呷哺": "#2ECC71"}

for _, row in competitors_view.drop_duplicates("品牌").iterrows():
    brand = row["品牌"]
    color = colors.get(brand, "#95A5A6")
    is_self = brand == self_brand
    fig1.add_trace(go.Scatter(
        x=[row["最低價"], row["均價"], row["最高價"]],
        y=[brand, brand, brand],
        mode="markers+lines",
        name=brand,
        line=dict(color=color, width=3 if is_self else 1.5),
        marker=dict(
            size=[10, 16, 10],
            color=[color, color, color],
            symbol=["circle-open", "diamond" if is_self else "circle", "circle-open"],
        ),
        showlegend=True,
    ))

fig1.update_layout(
    xaxis_title="價格（元）",
    xaxis=dict(gridcolor="#F5F5F5"),
    plot_bgcolor="white", paper_bgcolor="white",
    font_family="sans-serif", height=max(350, len(competitors_view["品牌"].unique()) * 48),
    showlegend=False,
    annotations=[dict(
        x=row["均價"], y=row["品牌"],
        text=f"均 ${row['均價']}",
        showarrow=False, xanchor="left", xshift=10,
        font=dict(size=11, color="#E63B1F" if row["品牌"] == self_brand else "#555"),
    ) for _, row in competitors_view.drop_duplicates("品牌").iterrows()],
)
st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

# ──────────────────────────────────────────────
# 圖二：服務星等雷達圖
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">⭐ 服務星等雷達圖（自家 vs 主要競品）</div>', unsafe_allow_html=True)

col_sel1, col_sel2 = st.columns([3, 1])
with col_sel1:
    rival_brands = rivals["品牌"].unique().tolist()
    selected_rivals = st.multiselect(
        "選擇對比競品（最多 3 個）", rival_brands,
        default=rival_brands[:min(2, len(rival_brands))],
        max_selections=3,
    )

radar_brands = [self_brand] + selected_rivals
radar_colors = ["#E63B1F", "#2C3E50", "#3498DB", "#27AE60"]

fig2 = go.Figure()
for i, brand in enumerate(radar_brands):
    brand_row = competitors_view[competitors_view["品牌"] == brand]
    if brand_row.empty:
        continue
    vals = brand_row[SERVICE_DIMS].mean().tolist()
    vals_closed = vals + [vals[0]]
    dims_closed = SERVICE_DIMS + [SERVICE_DIMS[0]]
    fig2.add_trace(go.Scatterpolar(
        r=vals_closed,
        theta=dims_closed,
        fill="toself",
        name=brand,
        line=dict(color=radar_colors[i % len(radar_colors)],
                  width=3 if brand == self_brand else 1.8),
        fillcolor=radar_colors[i % len(radar_colors)],
        opacity=0.25 if brand != self_brand else 0.35,
    ))

fig2.update_layout(
    polar=dict(
        radialaxis=dict(visible=True, range=[0, 5], tickvals=[1, 2, 3, 4, 5],
                        gridcolor="#EEE", linecolor="#DDD"),
        angularaxis=dict(gridcolor="#EEE"),
        bgcolor="white",
    ),
    showlegend=True,
    legend=dict(orientation="h", y=-0.15),
    plot_bgcolor="white", paper_bgcolor="white",
    font_family="sans-serif", height=480,
)
st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

# ──────────────────────────────────────────────
# 圖三：各維度差距條形圖（自家 vs 競品均分）
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">📊 各維度與競品均分差距分析</div>', unsafe_allow_html=True)

if not rivals.empty and not self_data.empty:
    self_scores  = self_data[SERVICE_DIMS].mean()
    rival_scores = rivals[SERVICE_DIMS].mean()
    diff         = (self_scores - rival_scores).round(2)

    diff_df = pd.DataFrame({
        "維度": SERVICE_DIMS,
        "差距": diff.values,
        "顏色": ["#27AE60" if v >= 0 else "#E63B1F" for v in diff.values],
    })

    fig3 = go.Figure(go.Bar(
        x=diff_df["差距"], y=diff_df["維度"],
        orientation="h",
        marker_color=diff_df["顏色"],
        text=diff_df["差距"].apply(lambda v: f"+{v:.2f}" if v >= 0 else f"{v:.2f}"),
        textposition="outside",
    ))
    fig3.add_vline(x=0, line_width=1.5, line_color="#95A5A6")
    fig3.update_layout(
        xaxis_title="分差（正=優於競品均值）",
        xaxis=dict(range=[-1.5, 1.5], gridcolor="#F5F5F5"),
        plot_bgcolor="white", paper_bgcolor="white",
        font_family="sans-serif", height=320,
    )
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

# ──────────────────────────────────────────────
# 競品資料明細
# ──────────────────────────────────────────────
st.markdown('<div class="section-header">📋 競品資料彙整表</div>', unsafe_allow_html=True)

show_cols = ["品牌", "類型", "商圈", "最低價", "均價", "最高價"] + SERVICE_DIMS
st.dataframe(
    competitors_view[show_cols].sort_values("均價"),
    use_container_width=True, hide_index=True,
)

# ──────────────────────────────────────────────
# 情報摘要
# ──────────────────────────────────────────────
st.divider()
st.markdown('<div class="section-header">🧭 情報研判摘要</div>', unsafe_allow_html=True)

if not self_data.empty and not rivals.empty:
    cp_advantage = self_scores["CP值"] - rival_scores["CP值"]
    price_pos = "低於" if self_avg_price < rival_avg_price else "高於"
    price_diff_pct = abs(self_avg_price - rival_avg_price) / rival_avg_price * 100

    weak_dims = diff_df[diff_df["差距"] < -0.1]["維度"].tolist()
    strong_dims = diff_df[diff_df["差距"] > 0.1]["維度"].tolist()

    summary = f"""
**嗑肉石鍋** 在本商圈的均價約 **${self_avg_price:.0f}**，{price_pos}競品均值 {price_diff_pct:.1f}%，
整體定位屬於 **中低價親民型** 餐飲品牌。

✅ **相對優勢**：{'、'.join(strong_dims) if strong_dims else '—'} 等維度優於競品均值，
顯示顧客對我們的 CP 值與服務有較高肯定。

⚠️ **待強化項目**：{'、'.join(weak_dims) if weak_dims else '—'} 等維度低於競品均值，
建議行銷部針對品牌知名度投入更多資源，並由研發部優化菜單多樣性。
"""
    st.markdown(summary)
