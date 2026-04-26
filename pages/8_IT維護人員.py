"""pages/8_IT維護人員.py — 24 小時 IT 自動維護人員"""
import streamlit as st
import json
from datetime import datetime

# ── 頁面設定 ──────────────────────────────────────────────────────
st.set_page_config(page_title="IT維護人員", page_icon="🖥️", layout="wide")

# ── 認證守衛 ──────────────────────────────────────────────────────
if not st.session_state.get("authenticated", False):
    st.error("🔒 尚未通過身份驗證，請返回總部登入")
    st.page_link("app.py", label="← 返回數位總部大門")
    st.stop()

from utils.icons import icon_svg
from utils.ui_helpers import inject_global_css
inject_global_css()

from utils import health_monitor, edge_store

# ── 跑馬燈 ───────────────────────────────────────────────────────
try:
    latest = health_monitor.get_latest_status()
    ok_cnt  = sum(1 for v in latest.values() if v.get("status") == "ok")
    bad_cnt = len(latest) - ok_cnt
    if bad_cnt == 0 and latest:
        ticker_msg = f"✅ 所有服務運作正常 ({len(latest)}/{len(latest)}) ｜ 上次檢查：{list(latest.values())[0].get('check_time','')[:16]}"
        ticker_color = "#15803d"
    elif latest:
        bad_svcs = [v["service"] for v in latest.values() if v.get("status") != "ok"]
        ticker_msg = f"🚨 {bad_cnt} 個服務異常：{' · '.join(bad_svcs)} ｜ 請立即處理！"
        ticker_color = "#dc2626"
    else:
        ticker_msg = "⏳ 尚無檢查記錄，請執行健康檢查"
        ticker_color = "#9ca3af"
except Exception:
    ticker_msg = "⏳ 載入中…"
    ticker_color = "#9ca3af"

st.markdown(f"""
<div style="background:{ticker_color};color:white;padding:8px 16px;border-radius:8px;
     font-size:.9rem;font-weight:600;overflow:hidden;white-space:nowrap;
     text-overflow:ellipsis;margin-bottom:1rem">
  📡 IT 維護跑馬燈：{ticker_msg}
</div>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────
st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;padding:4px 0 12px">
  {icon_svg("server",36,"#0ea5e9")}
  <div>
    <h2 style="margin:0;font-size:1.5rem;font-weight:700">24 小時 IT 維護人員</h2>
    <p style="margin:0;font-size:.85rem;color:#888">全服務健康監控・自動修復・資安偵測</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 功能列（指標卡）────────────────────────────────────────────────
latest = health_monitor.get_latest_status()
recent_log = health_monitor.get_recent_log(200)

total_checks   = len(recent_log)
fail_checks    = sum(1 for r in recent_log if r.get("status") == "fail")
auto_repaired  = sum(1 for r in recent_log if r.get("auto_repaired"))
svc_count      = len(latest)
ok_count       = sum(1 for v in latest.values() if v.get("status") == "ok")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("監控服務數", svc_count, help="目前監控中的服務總數")
c2.metric("目前正常", ok_count, delta=f"異常 {svc_count-ok_count}" if svc_count else None,
          delta_color="inverse")
c3.metric("歷史檢查次數", total_checks)
c4.metric("歷史異常次數", fail_checks, delta_color="inverse")
c5.metric("自動修復次數", auto_repaired)

st.divider()

# ── AI 狀態徽章 ───────────────────────────────────────────────────
import os
has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY",""))
ai_status_html = (
    '<span style="background:#dcfce7;color:#15803d;padding:3px 10px;border-radius:20px;'
    'font-size:.8rem;font-weight:600">✅ Claude AI 連線正常</span>'
    if has_anthropic else
    '<span style="background:#fee2e2;color:#dc2626;padding:3px 10px;border-radius:20px;'
    'font-size:.8rem;font-weight:600">❌ Claude AI API Key 未設定</span>'
)
st.markdown(f"**AI 狀態：** {ai_status_html}", unsafe_allow_html=True)
st.markdown("")

# ── Tabs ─────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["🖥️ 服務狀態看板", "🔧 手動操作", "🔐 資安示警", "📜 健康歷史"])

# ══════════════════════════════════════════════════════════════════
# Tab 1：服務狀態看板
# ══════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("#### 各服務即時狀態")
    if not latest:
        st.info("尚無健康檢查記錄。請至「手動操作」標籤執行首次健康檢查。")
    else:
        SERVICES = ["Render Webhook","Claude AI","LINE API","Google Sheets","Streamlit Cloud"]
        for svc in SERVICES:
            entry = latest.get(svc)
            if not entry:
                st.markdown(f"""
<div style="background:#f3f4f6;border-left:4px solid #9ca3af;padding:12px 16px;
     border-radius:6px;margin-bottom:8px">
  ⬜ <strong>{svc}</strong> — 尚未檢查
</div>""", unsafe_allow_html=True)
                continue
            ok      = entry.get("status") == "ok"
            lat_ms  = entry.get("latency_ms", 0)
            detail  = entry.get("detail", "")
            ts      = str(entry.get("check_time",""))[:16]
            color   = "#15803d" if ok else "#dc2626"
            bg      = "#f0fdf4" if ok else "#fef2f2"
            border  = "#86efac" if ok else "#fca5a5"
            icon    = "✅" if ok else "❌"
            lat_str = f" · 延遲 {lat_ms}ms" if lat_ms else ""
            repaired_badge = (
                ' <span style="background:#fef9c3;color:#854d0e;padding:1px 7px;'
                'border-radius:10px;font-size:.75rem">🔧 已自動修復</span>'
                if entry.get("auto_repaired") else ""
            )
            st.markdown(f"""
<div style="background:{bg};border-left:4px solid {border};padding:12px 16px;
     border-radius:6px;margin-bottom:8px">
  {icon} <strong style="color:{color}">{svc}</strong>{repaired_badge}
  <span style="float:right;color:#6b7280;font-size:.8rem">{ts}</span><br>
  <span style="font-size:.85rem;color:#374151">{detail}{lat_str}</span>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# Tab 2：手動操作
# ══════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("#### 手動 IT 操作")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**🔍 健康檢查**")
        st.caption("立即執行一次全服務健康檢查，並記錄結果")
        if st.button("▶️ 立即執行健康檢查", use_container_width=True, type="primary",
                     key="btn_health_check"):
            with st.spinner("檢查中，請稍候（最多 30 秒）…"):
                try:
                    results = health_monitor.run_all_checks()
                    failed  = [r for r in results if not r["ok"]]
                    repaired = health_monitor.auto_repair(failed) if failed else []
                    health_monitor.log_results(results, auto_repaired=bool(repaired))
                    ok_n  = sum(1 for r in results if r["ok"])
                    fail_n = len(results) - ok_n
                    if fail_n == 0:
                        st.success(f"✅ 全部 {ok_n} 個服務正常！")
                    else:
                        st.error(f"❌ {fail_n} 個服務異常，{ok_n} 個正常")
                        for r in [x for x in results if not x["ok"]]:
                            st.warning(f"⚠️ {r['service']}：{r['detail']}")
                    if repaired:
                        st.info("🔧 自動修復動作：")
                        for a in repaired:
                            st.caption(a)
                    st.rerun()
                except Exception as e:
                    st.error(f"健康檢查失敗：{e}")

    with col_b:
        st.markdown("**🚀 強制 Render 重新部署**")
        st.caption("觸發 Render Webhook 服務重新部署（自動修復離線）")
        if st.button("🔄 強制重新部署 Webhook", use_container_width=True, key="btn_redeploy"):
            import requests, os
            api_key = os.environ.get("RENDER_API_KEY","")
            svc_id  = os.environ.get("RENDER_SERVICE_ID","srv-d7m2qre7r5hc73fvaetg")
            if not api_key:
                st.error("❌ RENDER_API_KEY 未設定，請至 Render 新增環境變數")
            else:
                try:
                    resp = requests.post(
                        f"https://api.render.com/v1/services/{svc_id}/deploys",
                        headers={"Authorization":f"Bearer {api_key}",
                                 "Content-Type":"application/json"},
                        json={"clearCache":"do_not_clear"}, timeout=15
                    )
                    if resp.status_code < 300:
                        st.success(f"✅ 重新部署已觸發！(HTTP {resp.status_code})")
                    else:
                        st.error(f"❌ Render API 回傳 HTTP {resp.status_code}：{resp.text[:100]}")
                except Exception as e:
                    st.error(f"❌ 連線失敗：{e}")

    st.divider()
    st.markdown("**📲 傳送 IT 狀態到 LINE**")
    st.caption("立即推播一份簡短的服務狀態摘要到指揮官 LINE")
    if st.button("📨 推播 IT 狀態摘要", use_container_width=True, key="btn_push_status"):
        try:
            results = health_monitor.run_all_checks()
            health_monitor.log_results(results)
            now_str = datetime.now().strftime("%m/%d %H:%M")
            ok_n  = sum(1 for r in results if r["ok"])
            fail_n = len(results) - ok_n
            lines = [f"📊 【IT 狀態報告】{now_str}"]
            for r in results:
                icon = "✅" if r["ok"] else "❌"
                lines.append(f"{icon} {r['service']}：{r['detail']}")
            lines.append(f"\n{'🎉 全部服務正常！' if fail_n==0 else f'⚠️ {fail_n} 個服務異常'}")
            health_monitor.push_alert("\n".join(lines))
            st.success("✅ 已推播 IT 狀態到 LINE")
        except Exception as e:
            st.error(f"推播失敗：{e}")

# ══════════════════════════════════════════════════════════════════
# Tab 3：資安示警
# ══════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### 資安偵測結果")

    if st.button("🔐 立即執行資安掃描", type="primary", key="btn_security"):
        with st.spinner("掃描中…"):
            threats = health_monitor.check_security()
            st.session_state["_security_scan"] = threats

    threats = st.session_state.get("_security_scan", None)
    if threats is None:
        st.info("點擊上方按鈕執行資安掃描")
    elif not threats:
        st.success("✅ 未偵測到資安威脅")
    else:
        for t in threats:
            sev = t.get("severity","info")
            color = "#dc2626" if sev == "high" else "#d97706"
            bg    = "#fef2f2" if sev == "high" else "#fffbeb"
            st.markdown(f"""
<div style="background:{bg};border-left:4px solid {color};padding:12px 16px;
     border-radius:6px;margin-bottom:8px">
  ⚠️ <strong style="color:{color}">[{sev.upper()}]</strong> {t['detail']}
</div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("#### 資安說明")
    st.markdown("""
- **異常登入偵測**：同一帳號 1 小時內連續失敗登入 ≥ 3 次，自動觸發示警
- **API Key 缺失**：ANTHROPIC_API_KEY / LINE 金鑰 / GCP 憑證任一缺失即警示
- **自動推播**：資安威脅偵測後自動推播 LINE 通知指揮官
- **每小時掃描**：排程系統每小時自動執行一次，無需手動觸發
""")

# ══════════════════════════════════════════════════════════════════
# Tab 4：健康歷史
# ══════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("#### 健康檢查歷史記錄")
    import pandas as pd

    filter_svc = st.selectbox(
        "篩選服務",
        ["全部","Render Webhook","Claude AI","LINE API","Google Sheets","Streamlit Cloud"],
        key="it_log_filter"
    )
    logs = health_monitor.get_recent_log(300)
    if filter_svc != "全部":
        logs = [l for l in logs if l.get("service") == filter_svc]

    if not logs:
        st.info("尚無健康檢查記錄")
    else:
        df = pd.DataFrame(logs)[["check_time","service","status","latency_ms","detail","auto_repaired"]]
        df.columns = ["時間","服務","狀態","延遲(ms)","詳情","已修復"]
        df["狀態"]  = df["狀態"].map({"ok":"✅ 正常","fail":"❌ 異常"})
        df["已修復"] = df["已修復"].map({0:"",1:"🔧"})
        df["時間"]  = df["時間"].str[:19]
        st.dataframe(df, use_container_width=True, hide_index=True, height=400)
        st.caption(f"共 {len(df)} 筆記錄（最多顯示 300 筆）")
