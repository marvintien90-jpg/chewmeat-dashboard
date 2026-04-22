#!/usr/bin/env bash
# start_webhook.sh — 一鍵啟動本機 Line Webhook 服務
# 使用方式：
#   chmod +x start_webhook.sh
#   ./start_webhook.sh
#
# 可選環境變數（或在 .env 中設定）：
#   LINE_CHANNEL_SECRET       - Line Channel Secret
#   LINE_CHANNEL_ACCESS_TOKEN - Line Channel Access Token
#   LINE_GROUP_STORE_MAP      - JSON 群組→門店對應
#   NGROK_AUTHTOKEN           - ngrok 帳號 Token（取自 https://dashboard.ngrok.com/get-started/your-authtoken）
#   EDGE_DB_PATH              - SQLite 路徑（預設 /tmp/edge_agent.db）
#   PORT                      - Webhook 伺服器 Port（預設 8765）

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 載入 .env（若存在）──────────────────────────────────────────
if [ -f .env ]; then
    echo "📄 載入 .env 設定..."
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

PORT="${PORT:-8765}"
EDGE_DB_PATH="${EDGE_DB_PATH:-/tmp/edge_agent.db}"
export EDGE_DB_PATH

# ── 檢查依賴 ────────────────────────────────────────────────────
echo "🔍 檢查 Python 依賴..."
python3 -c "import fastapi, uvicorn" 2>/dev/null || {
    echo "📦 安裝 fastapi / uvicorn..."
    pip3 install fastapi "uvicorn[standard]" --quiet
}
python3 -c "import pyngrok" 2>/dev/null || {
    echo "📦 安裝 pyngrok..."
    pip3 install pyngrok --quiet
}

# ── 啟動 Webhook 伺服器 ──────────────────────────────────────────
echo ""
echo "🚀 啟動 Line Webhook 伺服器（Port $PORT）..."
WEBHOOK_PID_FILE="/tmp/line_webhook_${PORT}.pid"

# 結束舊程序
if [ -f "$WEBHOOK_PID_FILE" ]; then
    OLD_PID=$(cat "$WEBHOOK_PID_FILE")
    kill "$OLD_PID" 2>/dev/null && echo "   ✓ 舊程序 (PID $OLD_PID) 已終止"
    rm -f "$WEBHOOK_PID_FILE"
fi

python3 -m uvicorn line_webhook:app --host 0.0.0.0 --port "$PORT" \
    > /tmp/line_webhook.log 2>&1 &
WEBHOOK_PID=$!
echo "$WEBHOOK_PID" > "$WEBHOOK_PID_FILE"
echo "   PID: $WEBHOOK_PID  Log: /tmp/line_webhook.log"

# 等待伺服器就緒
sleep 2
HEALTH=$(curl -s "http://localhost:${PORT}/health" 2>/dev/null)
if echo "$HEALTH" | grep -q '"status": "ok"'; then
    echo "   ✅ 伺服器健康檢查通過"
else
    echo "   ❌ 伺服器啟動失敗，查看 log："
    tail -20 /tmp/line_webhook.log
    exit 1
fi

# ── ngrok 暴露 ──────────────────────────────────────────────────
echo ""
echo "🌐 啟動 ngrok 通道..."

if [ -z "$NGROK_AUTHTOKEN" ]; then
    echo "⚠️  未設定 NGROK_AUTHTOKEN"
    echo ""
    echo "   請依以下步驟取得免費 Token："
    echo "   1. 前往 https://dashboard.ngrok.com/signup 註冊免費帳號"
    echo "   2. 登入後至 https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "   3. 複製 Authtoken"
    echo "   4. 在此專案建立 .env 檔案，加入："
    echo "      NGROK_AUTHTOKEN=your_token_here"
    echo "      LINE_CHANNEL_SECRET=your_secret"
    echo "      LINE_CHANNEL_ACCESS_TOKEN=your_token"
    echo ""
    echo "   本機伺服器已在 http://localhost:${PORT} 運行"
    echo "   設定 NGROK_AUTHTOKEN 後重新執行此腳本即可取得公開網址"
    echo ""
    echo "📋 Webhook 伺服器日誌："
    tail -5 /tmp/line_webhook.log
    exit 0
fi

# 設定 ngrok authtoken 並啟動
python3 - <<PYEOF
import sys
from pyngrok import ngrok, conf

# 設定 authtoken
conf.get_default().auth_token = "$NGROK_AUTHTOKEN"

try:
    tunnel = ngrok.connect($PORT, "http")
    public_url = tunnel.public_url.replace("http://", "https://")
    webhook_url = public_url + "/webhook"

    print("")
    print("=" * 60)
    print("✅ ngrok 通道已建立！")
    print(f"   公開網址：{public_url}")
    print(f"   Webhook URL：{webhook_url}")
    print("=" * 60)
    print("")
    print("📋 接下來請完成 Line Developer Console 設定：")
    print(f"   1. 前往 https://developers.line.biz/console/")
    print(f"   2. 選擇您的 Messaging API Channel")
    print(f"   3. Webhook settings > Webhook URL > 貼入：")
    print(f"      {webhook_url}")
    print(f"   4. 點擊 Verify → 應顯示 Success")
    print(f"   5. 開啟 Use webhook 開關")
    print("")
    print("⏳ 伺服器持續運行中，按 Ctrl+C 停止...")
    print("")

    # 寫入 webhook URL 到暫存檔案（供其他腳本讀取）
    with open("/tmp/ngrok_webhook_url.txt", "w") as f:
        f.write(webhook_url)

    # 保持 ngrok 運行
    import signal, time
    signal.pause()

except Exception as e:
    print(f"❌ ngrok 啟動失敗：{e}")
    sys.exit(1)
PYEOF
