#!/bin/bash

echo ""
echo "  ┌─────────────────────────────────────┐"
echo "  │       USE CASE DEMO - DEPLOY        │"
echo "  └─────────────────────────────────────┘"
echo ""

echo "[1/5] Freeing RAM..."
sudo systemctl stop gdm3 snapd ModemManager bluetooth 2>/dev/null
sudo systemctl stop ollama 2>/dev/null          
pkill -f ollama 2>/dev/null                     
pkill -f vscode-server 2>/dev/null
pkill -f "server/node" 2>/dev/null
pkill -f gnome-software 2>/dev/null
pkill -f gnome-shell 2>/dev/null
pkill -f evolution-alarm 2>/dev/null
pkill -f evolution-data-server 2>/dev/null
pkill -f dockerd 2>/dev/null
pkill -f containerd 2>/dev/null
pkill -f packagekitd 2>/dev/null
pkill -f tracker-miner 2>/dev/null
pkill -f update-manager 2>/dev/null
pkill -f claude 2>/dev/null
pkill -f llama-server 2>/dev/null
sleep 3
sudo sysctl vm.drop_caches=3 2>/dev/null
echo "    RAM after cleanup:"
free -h | grep Mem
AVAIL=$(free -m | awk '/^Mem:/{print $7}')
if [ "$AVAIL" -lt 3000 ]; then
    echo "ERROR: Only ${AVAIL}MB available. Aborting."
    exit 1
fi
echo "    OK: ${AVAIL}MB available."

echo "[2/5] Setting max power mode..."
sudo nvpmodel -m 0 2>/dev/null
sudo jetson_clocks 2>/dev/null

echo "[3/5] Setting up environment..."
export LD_LIBRARY_PATH=~/Fadhi/Use_Case_Demo/bin:$LD_LIBRARY_PATH

echo "[4/5] Starting llama-server..."
~/Fadhi/Use_Case_Demo/bin/llama-server \
    -m ~/Fadhi/Use_Case_Demo/models/Qwen3VL-2B-Instruct-Q4_K_M.gguf \
    --mmproj ~/Fadhi/Use_Case_Demo/models/mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf \
    -ngl 99 -c 1024 --temp 0.1 --top-k 20 --top-p 0.8 \
    --presence-penalty 1.5 --jinja -np 1 \
    --cache-ram 0 \
    --log-disable \
    --port 8080 --host 127.0.0.1 &
for i in {1..30}; do
    curl -s http://127.0.0.1:8080/health > /dev/null 2>&1 && break
    sleep 1
done
echo "    llama-server ready."
echo "    RAM after model load:"
free -h | grep Mem

echo "[5/5] Starting web server..."
source ~/Fadhi/Use_Case_Demo/venv/bin/activate
cd ~/Fadhi/Use_Case_Demo
python main.py