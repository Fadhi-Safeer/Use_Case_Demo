import cv2
import ollama
import base64
import re
import time
import threading
import queue
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import uvicorn

MODELS = {
    "qwen3-vl:4b":      {"label": "Qwen3-VL 4B",    "desc": "Accurate, slower"},
    "moondream:latest": {"label": "Moondream",        "desc": "Fast, lightweight"},
}
DEFAULT_MODEL = "qwen3-vl:4b"
CAMERA_INDEX  = 0

app = FastAPI()

# ── Camera ────────────────────────────────────────────────────────────────────
camera_lock = threading.Lock()
cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

latest_frame = None
frame_lock   = threading.Lock()

def camera_loop():
    global latest_frame
    while True:
        with camera_lock:
            ret, frame = cap.read()
        if ret:
            with frame_lock:
                latest_frame = frame.copy()
        time.sleep(0.03)

threading.Thread(target=camera_loop, daemon=True).start()

# ── Analysis queue ─────────────────────────────────────────────────────────────
job_queue   = queue.Queue()
history     = []          # list of completed result dicts
history_lock = threading.Lock()
current_job  = {"status": "idle", "id": None}
current_lock = threading.Lock()
job_counter  = 0
job_counter_lock = threading.Lock()

def next_job_id():
    global job_counter
    with job_counter_lock:
        job_counter += 1
        return job_counter

def encode_b64(frame, size=(800, 600), quality=85):
    resized = cv2.resize(frame, size)
    _, buf = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf).decode('utf-8')

def encode_bytes(frame, size=(960, 540), quality=78):
    resized = cv2.resize(frame, size)
    _, buf = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()

def strip_think(text):
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

def worker():
    while True:
        job = job_queue.get()
        jid, frame, prompt, model = job['id'], job['frame'], job['prompt'], job['model']

        with current_lock:
            current_job['status'] = 'analyzing'
            current_job['id']     = jid

        t0 = time.time()
        thumb = encode_b64(frame)
        try:
            img_b64 = encode_b64(frame, size=(640, 480), quality=85)
            resp = ollama.generate(
                model=model,
                prompt=prompt,
                images=[img_b64],
                options={"temperature": 0.2}
            )
            text    = strip_think(resp['response'])
            elapsed = round(time.time() - t0, 1)
            entry = {
                "id":        jid,
                "status":    "done",
                "prompt":    prompt,
                "model":     model,
                "result":    text if text else "(no response)",
                "elapsed":   elapsed,
                "thumb":     thumb,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
        except Exception as e:
            entry = {
                "id":        jid,
                "status":    "error",
                "prompt":    prompt,
                "model":     model,
                "result":    str(e),
                "elapsed":   round(time.time() - t0, 1),
                "thumb":     thumb,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }

        with history_lock:
            history.insert(0, entry)   # newest first
            if len(history) > 20:
                history.pop()

        with current_lock:
            current_job['status'] = 'idle'
            current_job['id']     = None

        job_queue.task_done()

threading.Thread(target=worker, daemon=True).start()

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/video_feed")
def video_feed():
    def generate():
        while True:
            with frame_lock:
                f = latest_frame
            if f is None:
                time.sleep(0.05); continue
            jpg = encode_bytes(f)
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n'
            time.sleep(0.05)
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace;boundary=frame")

@app.post("/analyze")
async def analyze(data: dict):
    prompt = data.get("prompt", "").strip()
    model  = data.get("model", DEFAULT_MODEL)
    if not prompt:
        return JSONResponse({"error": "No prompt"}, status_code=400)
    if model not in MODELS:
        return JSONResponse({"error": "Unknown model"}, status_code=400)
    with frame_lock:
        frame = latest_frame.copy() if latest_frame is not None else None
    if frame is None:
        return JSONResponse({"error": "No camera frame"}, status_code=503)
    jid = next_job_id()
    job_queue.put({"id": jid, "frame": frame, "prompt": prompt, "model": model})
    return JSONResponse({"status": "queued", "id": jid, "queue_size": job_queue.qsize()})

@app.get("/status")
def status():
    with current_lock:
        cj = dict(current_job)
    return JSONResponse({
        "current":    cj,
        "queue_size": job_queue.qsize(),
    })

@app.get("/history")
def get_history():
    with history_lock:
        return JSONResponse({"history": list(history)})

@app.get("/models")
def get_models():
    return JSONResponse({"models": MODELS, "default": DEFAULT_MODEL})

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(HTML)

# ── UI ─────────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VLM Demo — Jetson</title>
<style>
:root {
  --bg0:#080b10; --bg1:#0d1117; --bg2:#161b24; --bg3:#1e2636;
  --border:#242d3e; --border2:#2e3a50;
  --text:#c9d1de; --text2:#7a8899; --text3:#4a5568;
  --blue:#3b82f6; --blue2:#1d4ed8; --blue-dim:#1e3a5f;
  --green:#22c55e; --green-dim:#14532d;
  --amber:#f59e0b; --amber-dim:#78350f;
  --red:#ef4444; --red-dim:#7f1d1d;
  --purple:#a855f7; --purple-dim:#4c1d95;
  --cyan:#06b6d4; --cyan-dim:#164e63;
  --radius:8px; --radius-sm:5px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg0);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* Header */
header{background:var(--bg1);border-bottom:1px solid var(--border);padding:10px 18px;display:flex;align-items:center;gap:12px;flex-shrink:0}
.logo{font-size:15px;font-weight:700;color:#fff;letter-spacing:2px;display:flex;align-items:center;gap:8px}
.logo-dot{width:8px;height:8px;border-radius:50%;background:var(--blue);box-shadow:0 0 8px var(--blue)}
.tag{font-size:10px;padding:2px 8px;border-radius:10px;border:1px solid;font-weight:500}
.tag-blue{background:var(--blue-dim);color:#93c5fd;border-color:#2563eb44}
.tag-gray{background:var(--bg3);color:var(--text2);border-color:var(--border2)}
.header-right{margin-left:auto;display:flex;align-items:center;gap:10px}
.status-pill{display:flex;align-items:center;gap:6px;font-size:11px;padding:4px 10px;border-radius:12px;border:1px solid var(--border2);background:var(--bg2)}
.dot{width:7px;height:7px;border-radius:50%}
.dot-idle{background:#3a4a5e}
.dot-busy{background:var(--amber);animation:glow 1s infinite}
.dot-done{background:var(--green)}
.dot-err{background:var(--red)}
@keyframes glow{0%,100%{opacity:1;box-shadow:0 0 6px var(--amber)}50%{opacity:.4;box-shadow:none}}
.queue-badge{font-size:10px;background:var(--blue-dim);color:#93c5fd;border:1px solid #2563eb44;border-radius:10px;padding:2px 8px}

/* Layout */
.main{display:flex;flex:1;overflow:hidden}
.left{flex:1;display:flex;flex-direction:column;border-right:1px solid var(--border)}
.right{width:460px;display:flex;flex-direction:column;background:var(--bg1)}

/* Camera */
.cam-box{flex:1;background:#000;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden}
.cam-box img{width:100%;height:100%;object-fit:contain}
.cam-overlay{position:absolute;bottom:0;left:0;right:0;padding:6px 12px;background:linear-gradient(transparent,rgba(0,0,0,.7));display:flex;justify-content:space-between;align-items:flex-end}
.cam-label{font-size:10px;color:#ffffff66;letter-spacing:1px}
.cam-live{font-size:9px;color:var(--green);letter-spacing:1px;display:flex;align-items:center;gap:4px}
.live-dot{width:5px;height:5px;border-radius:50%;background:var(--green);animation:glow2 2s infinite}
@keyframes glow2{0%,100%{opacity:1}50%{opacity:.3}}

/* Controls */
.controls{padding:14px;border-bottom:1px solid var(--border);flex-shrink:0}
.section-label{font-size:10px;color:var(--text3);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}

.model-row{display:flex;gap:6px;margin-bottom:12px}
.model-btn{flex:1;padding:7px 8px;border-radius:var(--radius-sm);border:1px solid var(--border2);background:var(--bg2);color:var(--text2);font-size:11px;cursor:pointer;transition:all .15s;text-align:center}
.model-btn:hover{border-color:var(--blue);color:var(--text)}
.model-btn.active{background:var(--blue-dim);border-color:var(--blue);color:#93c5fd;font-weight:600}

.presets{display:flex;gap:6px;margin-bottom:10px}
.preset{flex:1;padding:6px 4px;border-radius:var(--radius-sm);border:1px solid;font-size:11px;cursor:pointer;transition:all .15s;font-weight:500}
.preset:hover{filter:brightness(1.2)}
.p-desc{background:#0d2a1e;border-color:#16653a;color:var(--green)}
.p-read{background:#0d1e3a;border-color:#1d4ed8;color:#60a5fa}
.p-count{background:#2a1a0d;border-color:#92400e;color:var(--amber)}

.prompt-wrap{position:relative}
textarea{width:100%;background:var(--bg2);border:1px solid var(--border2);border-radius:var(--radius);color:var(--text);font-size:12px;padding:9px 11px;resize:none;height:58px;font-family:inherit;outline:none;line-height:1.5;transition:border .15s}
textarea:focus{border-color:var(--blue)}
textarea::placeholder{color:var(--text3)}
.btn-row{display:flex;gap:8px;margin-top:8px}
.btn-analyze{flex:1;background:var(--blue);color:#fff;border:none;border-radius:var(--radius);padding:9px;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s;letter-spacing:.3px}
.btn-analyze:hover{background:var(--blue2)}
.btn-analyze:disabled{background:var(--bg3);color:var(--text3);cursor:not-allowed}
.btn-clear{background:var(--bg2);color:var(--text2);border:1px solid var(--border2);border-radius:var(--radius);padding:9px 14px;font-size:12px;cursor:pointer;transition:all .15s}
.btn-clear:hover{border-color:var(--red);color:var(--red)}

/* Results panel */
.results{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px}
.results::-webkit-scrollbar{width:4px}
.results::-webkit-scrollbar-track{background:transparent}
.results::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px}

.result-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;transition:border .2s}
.result-card.analyzing{border-color:var(--amber)}
.result-card.done{border-color:var(--border2)}
.result-card.error{border-color:var(--red-dim)}

.card-top{display:flex;gap:10px;padding:10px}
.card-thumb{width:96px;height:64px;object-fit:cover;border-radius:4px;flex-shrink:0;background:var(--bg3)}
.card-thumb-ph{width:96px;height:64px;border-radius:4px;flex-shrink:0;background:var(--bg3);display:flex;align-items:center;justify-content:center;color:var(--text3);font-size:10px}
.card-meta{flex:1;min-width:0}
.card-prompt{font-size:11px;color:var(--text2);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card-tags{display:flex;gap:5px;flex-wrap:wrap}
.ctag{font-size:9px;padding:1px 6px;border-radius:8px;border:1px solid}
.ctag-model{background:var(--purple-dim);color:#d8b4fe;border-color:#7c3aed44}
.ctag-time{background:var(--bg3);color:var(--text2);border-color:var(--border2)}
.ctag-ts{background:var(--bg3);color:var(--text3);border-color:var(--border2)}

.card-body{padding:0 10px 10px}
.card-result{font-size:12px;line-height:1.7;color:var(--text);white-space:pre-wrap}
.card-result.analyzing{color:var(--amber);animation:pulse .8s infinite}
.card-result.error{color:var(--red)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}

.empty-state{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;color:var(--text3)}
.empty-icon{font-size:32px;opacity:.3}
.empty-text{font-size:12px}
</style>
</head>
<body>
<header>
  <div class="logo"><div class="logo-dot"></div>VLM DEMO</div>
  <span class="tag tag-gray">Jetson Orin Nano</span>
  <div class="header-right">
    <div class="queue-badge" id="queue-badge" style="display:none">Queue: <span id="q-num">0</span></div>
    <div class="status-pill">
      <div class="dot dot-idle" id="status-dot"></div>
      <span id="status-text">Idle</span>
    </div>
  </div>
</header>

<div class="main">
  <div class="left">
    <div class="cam-box">
      <img id="cam-img" alt="Live feed">
      <div class="cam-overlay">
        <span class="cam-label">CAMERA 0</span>
        <span class="cam-live"><div class="live-dot"></div>LIVE</span>
      </div>
    </div>
  </div>

  <div class="right">
    <div class="controls">
      <div class="section-label">Model</div>
      <div class="model-row" id="model-row"></div>

      <div class="section-label">Presets</div>
      <div class="presets">
        <button class="preset p-desc" onclick="setPrompt('Describe what you see in this scene in detail.')">Describe</button>
        <button class="preset p-read" onclick="setPrompt('Read and transcribe every text, label, sign, or writing visible. List each one exactly as written.')">Read Label</button>
        <button class="preset p-count" onclick="setPrompt('Count all distinct objects or people visible. Give a total number and a breakdown by category.')">Count</button>
      </div>

      <div class="section-label">Prompt</div>
      <textarea id="prompt" placeholder="Type a custom question or pick a preset…"></textarea>
      <div class="btn-row">
        <button class="btn-analyze" id="analyze-btn" onclick="triggerAnalysis()">Capture &amp; Analyze</button>
        <button class="btn-clear" onclick="clearHistory()">Clear</button>
      </div>
    </div>

    <div class="results" id="results">
      <div class="empty-state" id="empty-state">
        <div class="empty-icon">&#9633;</div>
        <div class="empty-text">Results will appear here</div>
      </div>
    </div>
  </div>
</div>

<script>
let selectedModel = null;
const models = {};

async function loadModels() {
  const res = await fetch('/models');
  const data = await res.json();
  selectedModel = data.default;
  const row = document.getElementById('model-row');
  for (const [key, info] of Object.entries(data.models)) {
    models[key] = info;
    const btn = document.createElement('button');
    btn.className = 'model-btn' + (key === selectedModel ? ' active' : '');
    btn.dataset.model = key;
    btn.innerHTML = `<div style="font-weight:600">${info.label}</div><div style="font-size:9px;opacity:.6;margin-top:1px">${info.desc}</div>`;
    btn.onclick = () => selectModel(key);
    row.appendChild(btn);
  }
}

function selectModel(key) {
  selectedModel = key;
  document.querySelectorAll('.model-btn').forEach(b => b.classList.toggle('active', b.dataset.model === key));
}

function setPrompt(text) {
  document.getElementById('prompt').value = text;
}

async function triggerAnalysis() {
  const prompt = document.getElementById('prompt').value.trim();
  if (!prompt) { alert('Enter a prompt first.'); return; }
  const res = await fetch('/analyze', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({prompt, model: selectedModel})
  });
  const data = await res.json();
  if (!res.ok) { alert(data.error || 'Failed'); return; }
  addPendingCard(data.id, prompt, selectedModel);
}

let pendingCards = {};

function addPendingCard(id, prompt, model) {
  const empty = document.getElementById('empty-state');
  if (empty) empty.remove();

  const card = document.createElement('div');
  card.className = 'result-card analyzing';
  card.id = 'card-' + id;
  card.innerHTML = `
    <div class="card-top">
      <div class="card-thumb-ph">...</div>
      <div class="card-meta">
        <div class="card-prompt">${escHtml(prompt)}</div>
        <div class="card-tags">
          <span class="ctag ctag-model">${escHtml(models[model]?.label || model)}</span>
          <span class="ctag ctag-ts">Queued</span>
        </div>
      </div>
    </div>
    <div class="card-body">
      <div class="card-result analyzing">Waiting in queue…</div>
    </div>`;
  const results = document.getElementById('results');
  results.insertBefore(card, results.firstChild);
  pendingCards[id] = true;
}

function updateCard(entry) {
  const card = document.getElementById('card-' + entry.id);
  if (!card) return;
  card.className = 'result-card ' + entry.status;
  card.innerHTML = `
    <div class="card-top">
      ${entry.thumb
        ? `<img class="card-thumb" src="data:image/jpeg;base64,${entry.thumb}" alt="frame">`
        : `<div class="card-thumb-ph">no img</div>`}
      <div class="card-meta">
        <div class="card-prompt">${escHtml(entry.prompt)}</div>
        <div class="card-tags">
          <span class="ctag ctag-model">${escHtml(models[entry.model]?.label || entry.model)}</span>
          <span class="ctag ctag-time">${entry.elapsed}s</span>
          <span class="ctag ctag-ts">${entry.timestamp}</span>
        </div>
      </div>
    </div>
    <div class="card-body">
      <div class="card-result ${entry.status === 'error' ? 'error' : ''}">${escHtml(entry.result)}</div>
    </div>`;
  delete pendingCards[entry.id];
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function clearHistory() {
  document.getElementById('results').innerHTML = '<div class="empty-state" id="empty-state"><div class="empty-icon">&#9633;</div><div class="empty-text">Results will appear here</div></div>';
  pendingCards = {};
}

// Poll status + history
async function poll() {
  try {
    const [sRes, hRes] = await Promise.all([fetch('/status'), fetch('/history')]);
    const s = await sRes.json();
    const h = await hRes.json();

    // Status dot
    const dot  = document.getElementById('status-dot');
    const stxt = document.getElementById('status-text');
    const qb   = document.getElementById('queue-badge');
    const qn   = document.getElementById('q-num');

    const busy = s.current.status === 'analyzing';
    dot.className = 'dot ' + (busy ? 'dot-busy' : 'dot-idle');
    stxt.textContent = busy ? 'Analyzing…' : 'Idle';

    const qs = s.queue_size + (busy ? 1 : 0);
    if (qs > 0) {
      qb.style.display = 'inline-block';
      qn.textContent = qs;
    } else {
      qb.style.display = 'none';
    }

    // Update cards from history
    for (const entry of h.history) {
      if (entry.id in pendingCards || document.getElementById('card-' + entry.id)) {
        updateCard(entry);
      }
    }

    // Mark currently-analyzing card
    if (busy && s.current.id) {
      const ac = document.getElementById('card-' + s.current.id);
      if (ac) {
        const rt = ac.querySelector('.card-result');
        if (rt) { rt.className = 'card-result analyzing'; rt.textContent = 'Analyzing…'; }
      }
    }
  } catch(e) {}
}

setInterval(poll, 1000);
loadModels();

window.addEventListener('load', () => {
  setTimeout(() => { document.getElementById('cam-img').src = '/video_feed'; }, 300);
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except:
        ip = "your-jetson-ip"
    print(f"\nVLM Demo ready")
    print(f"Open: http://{ip}:5000\n")
    uvicorn.run(app, host="0.0.0.0", port=5000)