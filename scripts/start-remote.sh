#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  E-YAY BrainChain — Remote Access Launcher                  ║
# ║  Kullanım: bash scripts/start-remote.sh                     ║
# ║                                                              ║
# ║  Açar: Backend :8000 + Frontend :3000 + Cloudflare Tunnel   ║
# ║  Tünel URL'si terminalde görünür — telefona kopyala          ║
# ║  Ctrl+C → tüm servisler temiz kapatılır                      ║
# ╚══════════════════════════════════════════════════════════════╝

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_LOG="/tmp/eyay_backend_remote.log"
FRONTEND_LOG="/tmp/eyay_frontend_remote.log"
BACKEND_PID=""
FRONTEND_PID=""

# ── Renkler ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

# ── Cleanup ────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo -e "${YELLOW}⏹  Servisler durduruluyor...${RESET}"
  [[ -n "$BACKEND_PID" ]]  && kill "$BACKEND_PID"  2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  echo -e "${GREEN}✅ Temiz kapandı.${RESET}"
}
trap cleanup SIGINT SIGTERM EXIT

echo ""
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}${CYAN}   E-YAY BrainChain  ·  Remote Access${RESET}"
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

# ── Backend ────────────────────────────────────────────────────
echo -e "${GREEN}▶  Backend başlatılıyor (port 8000)...${RESET}"
cd "$ROOT/backend"
VENV_UVICORN=""
if [[ -f "$ROOT/.venv/bin/uvicorn" ]]; then
  VENV_UVICORN="$ROOT/.venv/bin/uvicorn"
elif [[ -f ".venv/bin/uvicorn" ]]; then
  VENV_UVICORN=".venv/bin/uvicorn"
else
  VENV_UVICORN="$(python3 -m uvicorn --version 2>/dev/null | head -1 && echo python3 -m uvicorn || echo '')"
  VENV_UVICORN="python3 -m uvicorn"
fi
$VENV_UVICORN app.main:app --host 127.0.0.1 --port 8000 \
  > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo -e "   PID: ${BOLD}$BACKEND_PID${RESET}  |  Log: $BACKEND_LOG"

# ── Frontend ───────────────────────────────────────────────────
echo -e "${GREEN}▶  Frontend başlatılıyor (port 3000)...${RESET}"
cd "$ROOT/frontend"
if [[ ! -d "node_modules" ]]; then
  echo -e "${YELLOW}   node_modules yok, npm install çalışıyor...${RESET}"
  npm install --silent
fi
npm run dev \
  > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo -e "   PID: ${BOLD}$FRONTEND_PID${RESET}  |  Log: $FRONTEND_LOG"

# ── Servisler hazır olana kadar bekle ─────────────────────────
echo ""
echo -e "${YELLOW}⏳  Servisler ısınıyor (12 saniye)...${RESET}"
for i in {1..12}; do
  sleep 1
  # Backend hazır mı?
  if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1 || \
     curl -sf http://localhost:8000/ > /dev/null 2>&1; then
    echo -e "   Backend: ${GREEN}✓${RESET}"
    break
  fi
  [[ $i -eq 12 ]] && echo -e "   Backend: ${YELLOW}başlatılıyor...${RESET}"
done

# ── Cloudflare Tunnel ─────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}   🌐  Cloudflare Tunnel açılıyor...${RESET}"
echo -e "${BOLD}   ↓  Aşağıdaki URL'yi telefona kopyala${RESET}"
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "${YELLOW}   ⚠  PAPER_SAFE · NO_EXECUTION${RESET}"
echo -e "${YELLOW}   Bu URL herkese açık — Ctrl+C ile kapatmayı unutma${RESET}"
echo ""

# cloudflared tunnel çalışıyor (foreground) — URL burada çıkar
cloudflared tunnel --url http://localhost:3000
