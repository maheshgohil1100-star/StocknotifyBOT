from curl_cffi import requests
import time
import json
import re
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# =========================
# TELEGRAM SETTINGS
# =========================
BOT_TOKEN = "8516981172:AAGkcqkpq5J4DrTHPfCDVcgpAoklT9Q8aZ4"
CHANNEL_ID = "-1003710871914" 

# Render/Hosting Port Binding (Dummy server to keep hosting alive)
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # Silence the "GET / HTTP/1.1" noise in console
        return

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    print(f"Dummy server started on port {port}")
    server.serve_forever()

# =========================
# SETTINGS & FILES
# =========================
URL = "https://www.sheinindia.in/c/sverse-5939-37961"
STATE_FILE = "stock_state_live.json"

def get_stock():
    # Try multiple times if fetch fails
    for attempt in range(3):
        try:
            r = requests.get(URL, impersonate="chrome110", timeout=30)
            if r.status_code != 200:
                print(f"[{time.strftime('%H:%M:%S')}] Attempt {attempt+1} failed: {r.status_code}")
                continue
                
            html = r.text
            
            # Target the Gender Filter specifically for better accuracy
            # These are usually inside the filter search results JSON
            women_match = re.search(r'"genderfilter-Women".*?"count"\s*:\s*(\d+)', html)
            men_match = re.search(r'"genderfilter-Men".*?"count"\s*:\s*(\d+)', html)
            
            # Fallback to old regex if specific one fails
            if not women_match:
                women_match = re.search(r'"name"\s*:\s*"Women"\s*,\s*"count"\s*:\s*(\d+)', html)
            if not men_match:
                men_match = re.search(r'"name"\s*:\s*"Men"\s*,\s*"count"\s*:\s*(\d+)', html)
            
            women = int(women_match.group(1)) if women_match else 0
            men = int(men_match.group(1)) if men_match else 0
            
            if women > 0 or men > 0: # Ensure we got something
                return women, men
                
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Attempt {attempt+1} Error: {e}")
            time.sleep(2)
            
    return None, None

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHANNEL_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, impersonate="chrome110")
        print(f"[{time.strftime('%H:%M:%S')}] Alert sent to Channel!")
    except Exception as e:
        print(f"Failed to send to Channel: {e}")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return None

def save_state(women, men):
    with open(STATE_FILE, "w") as f:
        json.dump({"women": women, "men": men}, f)

def main():
    # Start dummy server for hosting port check
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    print("--- SHEINVERSE LIVE STOCK MONITOR ---")
    
    # Random startup delay to prevent synchronized duplicates on Render
    import random
    startup_wait = random.randint(2, 8)
    print(f"Starting in {startup_wait}s (Anti-collision delay)...")
    time.sleep(startup_wait)

    # SYSTEM SYNC: On startup, we ALWAYS get the latest stock 
    # and set it as the starting point. This stops DUPLICATE alerts on restarts.
    print("Syncing with website for the first time...")
    w_start, m_start = get_stock()
    
    if w_start is not None:
        state = {"women": w_start, "men": m_start}
        save_state(w_start, m_start)
        print(f"Starting Baseline Set: Women={w_start}, Men={m_start}")
    else:
        # If website fetch fails on start, try loading from file or use 0
        saved = load_state()
        state = saved if saved else {"women": 0, "men": 0}
        print("Starting with last known or zero state.")

    print(f"Monitoring active. Refresh: 20s. Started at {time.strftime('%H:%M:%S')}")

    while True:
        # 1. Refresh Website
        women, men = get_stock()
        if women is None:
            time.sleep(20)
            continue

        old_w = state["women"]
        old_m = state["men"]

        # 2. Check for INCREASE ONLY
        if women > old_w or men > old_m:
            
            # Amount BEFORE the stock addition
            before_w = old_w
            before_m = old_m
            
            # Amount ADDED
            added_w = max(0, women - before_w)
            added_m = max(0, men - before_m)
            
            # 3. Update the baseline IMMEDIATELY (Before sending telegram)
            # This is CRITICAL to prevent duplicate messages if the telegram call lags.
            state["women"] = women
            state["men"] = men
            save_state(women, men)
            
            # 4. Create Alert Message
            message = "<b>✨ SHEINVERSE STOCK ALERT ✨</b>\n\n"
            message += f"👗 <b>Women:</b> {before_w} ➜ <b>Now {women}</b> (+{added_w}) 📦\n"
            message += f"👕 <b>Men:</b> {before_m} ➜ <b>Now {men}</b> (+{added_m}) 📦\n"
            message += f"\n<a href='{URL}'>Visit Store</a>"
            
            print(f"[{time.strftime('%H:%M:%S')}] New Stock! W:{women}, M:{men}. Sending alert...")
            send_telegram(message)
            
        elif women < old_w or men < old_m:
            # Silent update for decreases (keeps 'Before' accurate for next refill)
            print(f"[{time.strftime('%H:%M:%S')}] Stock sold/decreased. New base: W:{women}, M:{men}")
            state["women"] = women
            state["men"] = men
            save_state(women, men)
        else:
            # LIVE MONITORING HEARTBEAT (Shows on Render console)
            print(f"[{time.strftime('%H:%M:%S')}] Active & Monitoring... Current Stock: W:{women}, M:{men}")

        time.sleep(20) 

if __name__ == "__main__":
    main()
