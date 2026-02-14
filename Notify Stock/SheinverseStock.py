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
    try:
        r = requests.get(URL, impersonate="chrome110", timeout=30)
        if r.status_code != 200:
            print(f"[{time.strftime('%H:%M:%S')}] Fetch failed: {r.status_code}")
            return None, None
            
        html = r.text
        
        # Accurate extraction using JSON patterns
        women_match = re.search(r'"name"\s*:\s*"Women"\s*,\s*"count"\s*:\s*(\d+)', html)
        men_match = re.search(r'"name"\s*:\s*"Men"\s*,\s*"count"\s*:\s*(\d+)', html)
        
        women = int(women_match.group(1)) if women_match else 0
        men = int(men_match.group(1)) if men_match else 0
        
        return women, men
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error: {e}")
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
    print("--- SHEINVERSE LIVE STOCK MONITOR ---")
    
    # Start dummy server for hosting port check
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # Load last seen state
    state = load_state()
    
    if state is None:
        print("Fetching initial state...")
        w, m = get_stock()
        if w is not None:
            save_state(w, m)
            state = {"women": w, "men": m}
        else:
            state = {"women": 0, "men": 0}

    print(f"Initial State: Women={state['women']}, Men={state['men']}")
    print(f"Monitoring started at {time.strftime('%H:%M:%S')}")

    while True:
        print(f"[{time.strftime('%H:%M:%S')}] --- Refreshing Website Data ---")
        women, men = get_stock()
        if women is None:
            time.sleep(30)
            continue

        old_women = state["women"]
        old_men = state["men"]

        # Alert ONLY if stock INCREASED
        if women > old_women or men > old_men:
            
            # Use OLD value as "Current"
            cur_w = old_women
            cur_m = old_men
            
            # Calculate exactly what was ADDED
            diff_w = women - cur_w
            diff_m = men - cur_m
            
            message = "<b>✨ SHEINVERSE STOCK ALERT ✨</b>\n\n"
            message += f"👗 Women: {cur_w} ➜ <b>Now {women}</b> (+{max(0, diff_w)}) 📦\n"
            message += f"👕 Men: {cur_m} ➜ <b>Now {men}</b> (+{max(0, diff_m)}) 📦\n"
            message += f"\n<a href='{URL}'>Visit Store</a>"
            
            print(f"[{time.strftime('%H:%M:%S')}] STOCK INCREASE DETECTED! Sending alert...")
            send_telegram(message)
            
            # UPDATE state so the next 'Current' is this new 'Now'
            state["women"] = women
            state["men"] = men
            save_state(women, men)
            
        elif women < old_women or men < old_men:
            # If stock decreases, update state SILENTLY (No message)
            print(f"[{time.strftime('%H:%M:%S')}] Stock decreased. Updated baseline to W:{women}, M:{men}")
            state["women"] = women
            state["men"] = men
            save_state(women, men)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Checked Website. Current Stock: W:{women}, M:{men}")

        time.sleep(20) 

if __name__ == "__main__":
    main()
