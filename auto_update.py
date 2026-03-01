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
    if not isinstance(addr, str):
        return addr
    addr = addr.strip()
    addr = re.sub(r"(\d+)\uc5b5?", r"\1", addr)
    addr = re.sub(r"\s+(\d+)\ud638?$", "", addr)
    addr = addr.rstrip("., ")
    return addr


def geocode(address, api_key, cache):
    if address in cache:
        return cache[address]
    if not api_key:
        return None, None
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": "KakaoAK " + api_key}
    params = {"query": address}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        if data.get("documents"):
            pos = data["documents"][0]
            lat, lng = float(pos["y"]), float(pos["x"])
            cache[address] = (lat, lng)
            return lat, lng
    except Exception as e:
        print("Geocoding error:", e)
    return None, None

def human_interaction(page):
    """Simulate basic human-like behavior like mouse movement and scrolling"""
    try:
        # Move mouse to random spots
        for _ in range(random.randint(2, 4)):
            x, y = random.randint(100, 700), random.randint(100, 500)
            page.mouse.move(x, y, steps=10)
            time.sleep(random.uniform(0.2, 0.5))
        
        # Random scroll
        page.mouse.wheel(0, random.randint(200, 500))
        time.sleep(random.uniform(0.5, 1.0))
        page.mouse.wheel(0, -random.randint(100, 200))
    except: pass

def scrape_with_playwright(draw_no):
    """Use advanced human-like interaction to bypass dhlottery bot detection"""
    print(f"[Playwright] Advanced human-like scraping for round {draw_no}...")
    records = []
    winning_numbers = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1280,800"
            ],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1280, "height": 800},
            device_scale_factor=1,
            has_touch=False,
            is_mobile=False
        )
        
        # More advanced fingerprint evasion
        page = context.new_page()
        page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
            """
        )

        try:
            # Step 1: Visit main page
            print("[Playwright] Step 1: Warming up session on main page...")
            page.goto("https://www.dhlottery.co.kr/main", timeout=60000, wait_until="networkidle")
            time.sleep(random.uniform(2.0, 4.0)) # Humand-like pause
            human_interaction(page)

            # Step 2: Navigate to result page
            target_url = f"https://www.dhlottery.co.kr/gameResult.do?method=byWin765&drwNo={draw_no}"
            print(f"[Playwright] Step 2: Accessing: {target_url}")
            page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(random.uniform(3.0, 5.0))
            
            # Close popups
            try:
                popups = page.query_selector_all("div[id^='pop'], div[class*='popup'], a[href*='close'], .btn_close")
                for p_div in popups:
                    if p_div.is_visible():
                        p_div.click()
                        print("[Playwright] Popup/Overlay closed.")
            except: pass

            human_interaction(page)

            # Extract winning numbers
            print("[Playwright] Step 3: Extracting numbers...")
            win_div = page.query_selector("div.win_result")
            if win_div:
                num_div = win_div.query_selector("div.num.win")
                if num_div:
                    spans = num_div.query_selector_all("span.ball_645")
                    nums = [int(s.inner_text().strip()) for s in spans][:6]
                    bonus_div = win_div.query_selector("div.num.bonus")
                    if bonus_div:
                        bspan = bonus_div.query_selector("span.ball_645")
                        if bspan:
                            nums.append(int(bspan.inner_text().strip()))
                    winning_numbers = nums
                    print(f"[Playwright] Success! Raw numbers: {winning_numbers}")
            else:
                print("[Playwright] Round data not found. Current Title:", page.title())

            # Extract winner store table
            print("[Playwright] Step 4: Extracting store table...")
            table = page.query_selector("table.tbl_data")
            if table:
                rows = table.query_selector_all("tbody tr")
                print(f"[Playwright] Found {len(rows)} winner rows.")
                for row in rows:
                    cols = row.query_selector_all("td")
                    if len(cols) >= 4:
                        name = cols[1].inner_text().strip()
                        method = cols[2].inner_text().strip()
                        address = normalize_address(cols[3].inner_text().strip())
                        
                        # Special handling for online center
                        if "\ub3d9\ud589\ubcf5\uac7c" in name and "dhlottery" in name.lower():
                            name = "\ub3d9\ud589\ubcf5\uac7c(dhlottery.co.kr)"
                            address = "\uc41c\uc6b8 \uc11c\uc108\uad6c \ub128\ubd80\uc21c\ud644\ub85c 2423 \ud55c\ube5b\ud0c0\uc6cc"

                        records.append({"r": draw_no, "n": name, "m": method, "a": address})
            else:
                print("[Playwright] Winner table not located.")

        except Exception as e:
            print(f"[Playwright] Critical Error: {e}")
        finally:
            browser.close()

    return records, winning_numbers


def scrape_with_requests_fallback(draw_no):
    """Fallback: requests + BeautifulSoup (not human-like)"""
    from bs4 import BeautifulSoup
    print(f"[requests] Simple fallback for round {draw_no}")
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    try:
        session.get("https://www.dhlottery.co.kr/main", timeout=15)
        time.sleep(1)
        url = f"https://www.dhlottery.co.kr/gameResult.do?method=byWin765&drwNo={draw_no}"
        r = session.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        records = []
        winning_numbers = None

        div_win = soup.find("div", class_="win_result")
        if div_win:
            nd = div_win.find("div", class_="num win")
            if nd:
                nums = [int(s.get_text()) for s in nd.find_all("span", class_="ball_645")][:6]
                bd = div_win.find("div", class_="num bonus")
                if bd:
                    bs2 = bd.find("span", class_="ball_645")
                    if bs2:
                        nums.append(int(bs2.get_text()))
                winning_numbers = nums

        tbl = soup.find("table", {"class": "tbl_data"})
        if tbl:
            for row in tbl.find("tbody").find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 4:
                    records.append({
                        "r": draw_no,
                        "n": cols[1].get_text(strip=True),
                        "m": cols[2].get_text(strip=True),
                        "a": normalize_address(cols[3].get_text(strip=True)),
                    })
        return records, winning_numbers
    except Exception as e:
        print(f"[requests] Error: {e}")
        return [], None


def update_historic_file(draw_no, numbers):
    if not Path(HISTORIC_FILE).exists():
        return
    try:
        df = pd.read_excel(HISTORIC_FILE)
        rcol = df.columns[0]
        if draw_no in df[rcol].values:
            print(f"Round {draw_no} already exists.")
            return
        num_cols = [c for c in df.columns[1:] if "\ubcf4\ub108\uc2a4" not in str(c)]
        bonus_cols = [c for c in df.columns[1:] if "\ubcf4\ub108\uc2a4" in str(c)]
        new_row = {rcol: draw_no}
        for i, col in enumerate(num_cols[:6]):
            if i < len(numbers):
                new_row[col] = numbers[i]
        if bonus_cols and len(numbers) > 6:
            new_row[bonus_cols[0]] = numbers[6]
        df = pd.concat([pd.DataFrame([new_row]), df], ignore_index=True)
        df = df.sort_values(by=rcol, ascending=False)
        df.to_excel(HISTORIC_FILE, index=False)
        print(f"Historic data updated for round {draw_no}.")
    except Exception as e:
        print(f"Historic sync failed: {e}")


def build_history_json():
    OUTPUT_JSON = "lotto_history.json"
    if not Path(HISTORIC_FILE).exists():
        return
    try:
        df = pd.read_excel(HISTORIC_FILE)
        rcol = df.columns[0]
        history_map = {}
        for _, row in df.iterrows():
            rnum = int(row[rcol])
            num_cols = [c for c in df.columns[1:] if "\ubcf4\ub108\uc2a4" not in str(c)]
            bonus_cols = [c for c in df.columns[1:] if "\ubcf4\ub108\uc2a4" in str(c)]
            nums = [int(row[c]) for c in num_cols[:6] if pd.notna(row[c])]
            if bonus_cols and pd.notna(row[bonus_cols[0]]):
                nums.append(int(row[bonus_cols[0]]))
            history_map[str(rnum)] = nums
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(history_map, f, ensure_ascii=False)
        print(f"JSON rebuilt: {OUTPUT_JSON}")
    except Exception as e:
        print(f"JSON build error: {e}")


def get_current_round():
    """Detect current round by scraping the main page"""
    from bs4 import BeautifulSoup
    try:
        session = requests.Session()
        session.headers.update(BASE_HEADERS)
        session.get("https://www.dhlottery.co.kr/main", timeout=15)
        r = session.get("https://www.dhlottery.co.kr/common.do?method=main", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        el = soup.find("strong", id="lottoDrwNo")
        if el: return int(el.get_text().strip())
    except: pass
    return None


def main():
    if not Path(JSON_FILE).exists():
        sys.exit(1)

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    last_round = max([d["r"] for d in all_data]) if all_data else 0
    print(f"Current Max Round in Data: {last_round}")

    site_round = get_current_round()
    current_round = site_round if site_round else last_round + 1
    print(f"Determined Target Round: {current_round}")

    if last_round >= current_round:
        print("Everything is synchronized.")
        return

    new_records_base = []
    for r in range(last_round + 1, current_round + 1):
        if PLAYWRIGHT_AVAILABLE:
            recs, nums = scrape_with_playwright(r)
        else:
            recs, nums = scrape_with_requests_fallback(r)

        if not recs or not nums:
            print(f"Round {r} data not fully captured - Retrying soon.")
            sys.exit(1)

        if nums:
            update_historic_file(r, nums)
        if recs:
            new_records_base.extend(recs)
        time.sleep(2)

    if not new_records_base:
        sys.exit(1)

    # Cache geocode
    cache = {}
    if Path(CACHE_FILE).exists():
        try:
            cdf = pd.read_excel(CACHE_FILE)
            cache = {row["a"]: (row["lat"], row["lng"]) for _, row in cdf.iterrows()}
        except: pass

    final_new_records = []
    for rec in new_records_base:
        lat, lng = geocode(rec["a"], KAKAO_API_KEY, cache)
        rec["lat"], rec["lng"] = lat, lng
        final_new_records.append(rec)

    # Save
    combined = final_new_records + all_data
    combined.sort(key=lambda x: x["r"], reverse=True)

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    with open(JS_FILE, "w", encoding="utf-8") as f:
        f.write("const lottoData = " + json.dumps(combined, ensure_ascii=False, indent=2) + ";")

    if Path(EXCEL_FILE).exists():
        try:
            df_old = pd.read_excel(EXCEL_FILE)
            ndf = pd.DataFrame(
                [[r["r"], None, r["n"], r["m"], r["a"]] for r in final_new_records],
                columns=df_old.columns[:5],
            )
            pd.concat([ndf, df_old], ignore_index=True).to_excel(EXCEL_FILE, index=False)
        except: pass

    if cache:
        pd.DataFrame([{"a": k, "lat": v[0], "lng": v[1]} for k, v in cache.items()]).to_excel(
            CACHE_FILE, index=False
        )

    build_history_json()
    print(f"PROCESS COMPLETED. Round {current_round} integrated.")


if __name__ == "__main__":
    main()
