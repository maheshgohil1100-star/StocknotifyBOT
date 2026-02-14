from curl_cffi import requests
import time
import json
import re
import os
import threading
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

# =========================
# CONFIGURATION
# =========================
BOT_TOKEN = "8516981172:AAGkcqkpq5J4DrTHPfCDVcgpAoklT9Q8aZ4"
CHANNEL_ID = "-1003710871914" 
URL = "https://www.sheinindia.in/c/sverse-5939-37961"
STATE_FILE = "stock_state_live.json"

# =========================
# DUMMY SERVER (FOR HOSTING)
# =========================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, format, *args):
        return # Silence all hosting logs

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

# =========================
# CORE FUNCTIONS
# =========================
def get_stock():
    """Fetches stock counts with highly restricted search to prevent mirroring."""
    for _ in range(3):
        try:
            r = requests.get(URL, impersonate="chrome110", timeout=30)
            if r.status_code != 200: continue
            html = r.text
            
            def find_absolute_count(key):
                idx = html.find(f'"{key}"')
                if idx == -1: return None
                # Only look at the next 500 characters after the key
                # This ensures we stay within the gender JSON block and don't jump to another
                chunk = html[idx:idx+500]
                m = re.search(r'"count"\s*:\s*(\d+)', chunk)
                return int(m.group(1)) if m else None

            women = find_absolute_count("genderfilter-Women")
            men = find_absolute_count("genderfilter-Men")
            
            if women is not None and men is not None:
                return women, men
                
            # Emergency Fallback (rarely hits)
            w_bak = re.search(r'"name"\s*:\s*"Women"\s*,\s*"count"\s*:\s*(\d+)', html)
            m_bak = re.search(r'"name"\s*:\s*"Men"\s*,\s*"count"\s*:\s*(\d+)', html)
            if w_bak and m_bak:
                return int(w_bak.group(1)), int(m_bak.group(1))
        except:
            time.sleep(2)
    return None, None

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHANNEL_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=20)
    except:
        pass

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: return json.load(f)
        except: pass
    return None

def save_state(women, men):
    try:
        with open(STATE_FILE, "w") as f: json.dump({"women": women, "men": men}, f)
    except: pass

def main():
    # Start hosting server
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # Startup Sync (Prevent duplicate alerts on restart)
    time.sleep(random.randint(2, 5))
    w_start, m_start = get_stock()
    
    if w_start is not None:
        state = {"women": w_start, "men": m_start}
        save_state(w_start, m_start)
    else:
        saved = load_state()
        state = saved if saved else {"women": 0, "men": 0}

    # Main Monitoring Loop (No silent prints to save load)
    while True:
        women, men = get_stock()
        if women is None:
            time.sleep(30)
            continue

        old_w, old_m = state["women"], state["men"]

        # TRIGGER ALERT ONLY ON INCREASE
        if women > old_w or men > old_m:
            
            # 1. Update memory IMMEDIATELY to prevent duplicate hits
            added_w, added_m = max(0, women - old_w), max(0, men - old_m)
            state["women"], state["men"] = women, men
            save_state(women, men)
            
            # 2. Construct Message
            msg = "<b>✨ SHEINVERSE STOCK ALERT ✨</b>\n\n"
            msg += f"👗 <b>Women:</b> {old_w} ➜ <b>Now {women}</b> (+{added_w}) 📦\n"
            msg += f"👕 <b>Men:</b> {old_m} ➜ <b>Now {men}</b> (+{added_m}) 📦\n"
            msg += f"\n<a href='{URL}'>Visit Store</a>"
            
            # 3. Send Alert
            send_telegram(msg)
            print(f"[{time.strftime('%H:%M:%S')}] ALERT SENT: W:{women}, M:{men}")
            
        elif women < old_w or men < old_m:
            # Silent update for decreases
            state["women"], state["men"] = women, men
            save_state(women, men)
        
        # 30 second cycle is perfect for stable monitoring
        time.sleep(30)

if __name__ == "__main__":
    main()
