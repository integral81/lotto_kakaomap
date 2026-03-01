import json, os, re, time, sys, random
from pathlib import Path
import pandas as pd
import requests

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not available, using requests fallback")

JSON_FILE = "lotto_data.json"
JS_FILE = "lotto_data.js"
EXCEL_FILE = "temp_data.xlsx"
CACHE_FILE = "geocoded_cache_healthy.xlsx"
HISTORIC_FILE = "lotto_historic_numbers_1_1209_Final.xlsx"
KAKAO_API_KEY = os.environ.get("KAKAO_REST_API_KEY")

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.dhlottery.co.kr/",
}

def normalize_address(addr):
    if not isinstance(addr, str): return addr
    addr = addr.strip()
    addr = re.sub(r"(\d+)\uc5b5?", r"\1", addr)
    return addr.rstrip("., ")

def geocode(address, api_key, cache):
    if address in cache: return cache[address]
    if not api_key: return None, None
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": "KakaoAK " + api_key}
    try:
        r = requests.get(url, headers=headers, params={"query": address}, timeout=10)
        data = r.json()
        if data.get("documents"):
            pos = data["documents"][0]
            lat, lng = float(pos["y"]), float(pos["x"])
            cache[address] = (lat, lng)
            return lat, lng
    except: pass
    return None, None

def human_interaction(page):
    try:
        for _ in range(random.randint(2, 4)):
            page.mouse.move(random.randint(100, 700), random.randint(100, 500), steps=10)
            time.sleep(random.uniform(0.1, 0.3))
        page.mouse.wheel(0, random.randint(100, 300))
        time.sleep(0.5)
        page.mouse.wheel(0, -100)
    except: pass

def scrape_super_human(draw_no):
    """Mimic a human: visit main, click menus, type round number manually"""
    print(f"[Playwright] Super Human Mode: Manually searching for round {draw_no}...")
    records, winning_numbers = [], None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36", locale="ko-KR")
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")

        try:
            # 1. Main Page
            print("[SuperHuman] Navigating to main page...")
            page.goto("https://www.dhlottery.co.kr/main", timeout=60000, wait_until="networkidle")
            time.sleep(2)
            
            # Close Popups
            pop_btns = page.query_selector_all("a[href*='close'], button[class*='close'], .btn_close")
            for b in pop_btns:
                if b.is_visible(): b.click()

            # 2. Hover and Click '당첨결과' -> '로또6/45 당첨결과'
            print("[SuperHuman] Navigating through menus...")
            page.hover("a:has-text('당첨결과')")
            time.sleep(1)
            page.click("a:has-text('로또6/45')") # Should lead to win result page
            page.wait_for_load_state("networkidle")
            
            # 3. Handle Round Entry (Manual Typing)
            print(f"[SuperHuman] Typing round {draw_no} manually...")
            # On result page, there's usually a select or input for round. 
            # Often it's an <input id="crntDrawNo"> or <select id="drwNo">.
            # We'll try to find the input/select and type.
            input_box = page.query_selector("input#drwNo, select#drwNo")
            if input_box:
                input_box.focus()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(str(draw_no), delay=100)
                time.sleep(1)
                page.keyboard.press("Enter")
                # Alternatively find and click '조회' button
                search_btn = page.query_selector("a#searchBtn, button#searchBtn, input[value='조회']")
                if search_btn: search_btn.click()
                page.wait_for_load_state("networkidle")

            time.sleep(3) # Wait for page update
            human_interaction(page)

            # 4. Extract Numbers
            win_div = page.query_selector("div.win_result")
            if win_div:
                nd = win_div.query_selector("div.num.win")
                if nd:
                    spans = nd.query_selector_all("span.ball_645")
                    nums = [int(s.inner_text().strip()) for s in spans][:6]
                    bonus_div = win_div.query_selector("div.num.bonus")
                    if bonus_div:
                        bspan = bonus_div.query_selector("span.ball_645")
                        if bspan: nums.append(int(bspan.inner_text().strip()))
                    winning_numbers = nums
                    print(f"[SuperHuman] Extracted numbers: {winning_numbers}")

            # 5. Extract Stores
            table = page.query_selector("table.tbl_data")
            if table:
                rows = table.query_selector_all("tbody tr")
                for row in rows:
                    cols = row.query_selector_all("td")
                    if len(cols) >= 4:
                        name = cols[1].inner_text().strip()
                        method = cols[2].inner_text().strip()
                        address = normalize_address(cols[3].inner_text().strip())
                        if "dhlottery" in name.lower():
                             name = "\ub3d9\ud589\ubcf5\uac7c(dhlottery.co.kr)"
                             address = "\uc41c\uc6b8 \uc11c\uc108\uad6c \ub128\ubd80\uc21c\ud644\ub85c 2423 \ud55c\ube5b\ud0c0\uc6cc"
                        records.append({"r": draw_no, "n": name, "m": method, "a": address})

        except Exception as e: print(f"[SuperHuman] Error: {e}")
        finally: browser.close()
    return records, winning_numbers

def update_historic_file(draw_no, numbers):
    if not Path(HISTORIC_FILE).exists(): return
    try:
        df = pd.read_excel(HISTORIC_FILE)
        rcol = df.columns[0]
        if draw_no in df[rcol].values: return
        new_row = {rcol: draw_no}
        for i, val in enumerate(numbers[:6]):
            col = [c for c in df.columns[1:] if "\ubcf4\ub108\uc2a4" not in str(c)][i]
            new_row[col] = val
        if len(numbers) > 6:
            new_row[[c for c in df.columns[1:] if "\ubcf4\ub108\uc2a4" in str(c)][0]] = numbers[6]
        df = pd.concat([pd.DataFrame([new_row]), df], ignore_index=True).sort_values(by=rcol, ascending=False)
        df.to_excel(HISTORIC_FILE, index=False)
    except: pass

def build_history_json():
    if not Path(HISTORIC_FILE).exists(): return
    try:
        df = pd.read_excel(HISTORIC_FILE)
        rcol = df.columns[0]
        data = {str(int(row[rcol])): [int(row[c]) for c in df.columns[1:] if pd.notna(row[c])] for _, row in df.iterrows()}
        with open("lotto_history.json", "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False)
    except: pass

def get_current_round():
    try:
        r = requests.get("https://www.dhlottery.co.kr/common.do?method=main", headers=BASE_HEADERS, timeout=10)
        from bs4 import BeautifulSoup
        el = BeautifulSoup(r.text, "html.parser").find("strong", id="lottoDrwNo")
        return int(el.get_text().strip())
    except: return None

def main():
    with open(JSON_FILE, "r", encoding="utf-8") as f: all_data = json.load(f)
    last_round = max([d["r"] for d in all_data]) if all_data else 0
    current_round = get_current_round() or (last_round + 1)
    if last_round >= current_round: return

    for r in range(last_round + 1, current_round + 1):
        recs, nums = scrape_super_human(r) if PLAYWRIGHT_AVAILABLE else ([], None)
        if not recs or not nums: sys.exit(1)
        update_historic_file(r, nums)
        
        # Geocode and Save
        cache = {}
        if Path(CACHE_FILE).exists():
            cdf = pd.read_excel(CACHE_FILE)
            cache = {row["a"]: (row["lat"], row["lng"]) for _, row in cdf.iterrows()}
        
        for rec in recs:
            lat, lng = geocode(rec["a"], KAKAO_API_KEY, cache)
            rec["lat"], rec["lng"] = lat, lng
        
        all_data = recs + all_data
        all_data.sort(key=lambda x: x["r"], reverse=True)
        with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump(all_data, f, ensure_ascii=False, indent=2)
        with open(JS_FILE, "w", encoding="utf-8") as f: f.write("const lottoData = " + json.dumps(all_data, ensure_ascii=False, indent=2) + ";")
        
        if Path(EXCEL_FILE).exists():
           try:
               df_old = pd.read_excel(EXCEL_FILE)
               pd.concat([pd.DataFrame([[r["r"], None, r["n"], r["m"], r["a"]] for r in recs], columns=df_old.columns[:5]), df_old], ignore_index=True).to_excel(EXCEL_FILE, index=False)
           except: pass
        
        if cache: pd.DataFrame([{"a": k, "lat": v[0], "lng": v[1]} for k, v in cache.items()]).to_excel(CACHE_FILE, index=False)
        build_history_json()
        print(f"DONE: Round {r} added.")

if __name__ == "__main__": main()
