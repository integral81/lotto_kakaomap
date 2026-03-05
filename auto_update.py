"""
로또 자동 업데이트 스크립트 v4.0 (Supabase 연동 버전)
방식: 네이버/구글 검색 기반 (동행복권 직접 스크래핑 제거)
스케줄: 매주 토요일 21:10 KST (UTC 12:10) 시작, 10분 간격 재시도
"""

import os
import re
import time
import sys
import random
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import certifi

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CACHE_FILE = "geocoded_cache_healthy.xlsx"
KAKAO_API_KEY = os.environ.get("KAKAO_REST_API_KEY")

SUPABASE_URL = "https://sdvrijpwwpqgaivfutjm.supabase.co"
# Service Role Key for Insert capability (You might want to put this in OS env var)
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNkdnJpanB3d3BxZ2FpdmZ1dGptIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjcwNDcxNCwiZXhwIjoyMDg4MjgwNzE0fQ.IkyRMb5FfjfRWfAwp2gaPIvnsKJvEM_y8GrgdJhqLyA")

NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.naver.com",
}

INTERNET_LOTTERY_LAT = 37.56358
INTERNET_LOTTERY_LNG = 126.97923

# ===================================================================
# 1. 네이버 검색 기반 당첨번호 추출
# ===================================================================
def fetch_winning_numbers_naver(draw_no):
    query = f"로또 {draw_no}회 당첨번호"
    url = f"https://search.naver.com/search.naver?query={requests.utils.quote(query)}"
    try:
        r = requests.get(url, headers=NAVER_HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ")
        pattern = r'당첨번호[^\d]*(\d{1,2})[^\d]+(\d{1,2})[^\d]+(\d{1,2})[^\d]+(\d{1,2})[^\d]+(\d{1,2})[^\d]+(\d{1,2})'
        m = re.search(pattern, text)
        if m:
            nums = [int(m.group(i)) for i in range(1, 7)]
            if all(1 <= n <= 45 for n in nums) and len(set(nums)) == 6:
                bonus_pattern = r'보너스[^\d]*(\d{1,2})'
                bm = re.search(bonus_pattern, text[m.start():m.start()+200])
                if bm:
                    bonus = int(bm.group(1))
                    if 1 <= bonus <= 45 and bonus not in nums:
                        nums.append(bonus)
                print(f"[Naver] 당첨번호 추출 성공: {nums}")
                return nums
    except Exception as e:
        print(f"[Naver] 당첨번호 검색 실패: {e}")
    return None

def fetch_winning_numbers_google(draw_no):
    query = f"로또 {draw_no}회차 당첨번호 1등"
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&hl=ko"
    google_headers = dict(NAVER_HEADERS)
    google_headers["Referer"] = "https://www.google.com"
    try:
        r = requests.get(url, headers=google_headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ")
        pattern = r'(\d{1,2})[,\s]+(\d{1,2})[,\s]+(\d{1,2})[,\s]+(\d{1,2})[,\s]+(\d{1,2})[,\s]+(\d{1,2})'
        for m in re.finditer(pattern, text):
            nums = [int(m.group(i)) for i in range(1, 7)]
            if all(1 <= n <= 45 for n in nums) and len(set(nums)) == 6:
                print(f"[Google] 당첨번호 추출 성공: {nums}")
                return nums
    except Exception as e:
        print(f"[Google] 당첨번호 검색 실패: {e}")
    return None

# ===================================================================
# 2. 네이버/구글 검색 기반 1등 판매점 추출
# ===================================================================
def fetch_stores_naver(draw_no):
    records = []
    queries = [
        f"로또 {draw_no}회 1등 판매점",
        f"{draw_no}회 로또 1등 당첨점",
    ]
    for query in queries:
        url = f"https://search.naver.com/search.naver?query={requests.utils.quote(query)}"
        try:
            r = requests.get(url, headers=NAVER_HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(separator="\n")
            store_pattern = r'([가-힣\w]+(?:복권|로또|행운|황금|대박|꿈|이월|기쁨|대성|미래|우리|희망|나눔|행복|\w{1,6})?(?:방|점|샵|마트|편의점|슈퍼)?)\s+([가-힣]+(?:시|구|군|동|읍|면|리)\s*[가-힣\d-]*)\s+(자동|수동|반자동|사이트)'
            for m in re.finditer(store_pattern, text):
                name = m.group(1).strip()
                addr_hint = m.group(2).strip()
                method = m.group(3).strip()
                if len(name) >= 2 and name not in [r['n'] for r in records]:
                    records.append({"n": name, "a": addr_hint, "m": method, "r": draw_no})
            if records:
                print(f"[Naver stores] {len(records)}개 판매점 추출 (쿼리: {query})")
                break
        except Exception as e:
            print(f"[Naver stores] 검색 실패: {e}")
        time.sleep(random.uniform(1.5, 3.0))
    return records

def fetch_stores_from_dhlottery_api(draw_no):
    url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={draw_no}"
    try:
        r = requests.get(url, headers=NAVER_HEADERS, timeout=10)
        data = r.json()
        if data.get("returnValue") == "success":
            nums = [data.get(f"drwtNo{i}") for i in range(1, 7)]
            bonus = data.get("bnusNo")
            if bonus:
                nums.append(bonus)
            print(f"[DH API] 당첨번호 추출 성공: {nums}")
            return nums
    except: pass
    return None

def fetch_stores_naver_news(draw_no):
    records = []
    query = f"로또 {draw_no}회 1등 판매점 당첨"
    url = f"https://search.naver.com/search.naver?where=news&query={requests.utils.quote(query)}&sort=1"
    try:
        r = requests.get(url, headers=NAVER_HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        news_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "news.naver.com" in href or "n.news.naver.com" in href:
                news_links.append(href)
        print(f"[News] {len(news_links)}개 기사 링크 발견")
        for link in news_links[:3]:
            try:
                nr = requests.get(link, headers=NAVER_HEADERS, timeout=10)
                nsoup = BeautifulSoup(nr.text, "html.parser")
                article_text = nsoup.get_text(separator="\n")
                lines = article_text.split("\n")
                for line in lines:
                    line = line.strip()
                    method = None
                    if "자동" in line: method = "자동"
                    elif "수동" in line: method = "수동"
                    elif "반자동" in line: method = "반자동"
                    elif "사이트" in line or "인터넷" in line: method = "사이트"
                    if method and len(line) > 5 and len(line) < 80:
                        region_match = re.search(r'([가-힣]+(?:시|구|군))', line)
                        if region_match:
                            name_part = line[:region_match.start()].strip()
                            addr_part = region_match.group(0)
                            if len(name_part) >= 2 and name_part not in [rec["n"] for rec in records]:
                                records.append({"n": name_part, "a": addr_part, "m": method, "r": draw_no})
                if len(records) >= 10: break
                time.sleep(random.uniform(0.5, 1.5))
            except Exception as e: print(f"[News article] 파싱 실패: {e}")
    except Exception as e: print(f"[News] 검색 실패: {e}")
    print(f"[News] {len(records)}개 판매점 추출")
    return records

# ===================================================================
# 3. 보조 함수들
# ===================================================================
def normalize_address(addr):
    if not isinstance(addr, str): return addr
    addr = addr.strip()
    addr = re.sub(r"(\d+)억?", r"\1", addr)
    return addr.rstrip("., ")

def geocode(address, api_key, cache):
    if not address or address in cache: 
        return cache.get(address, (None, None))
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

def get_current_round_from_supabase():
    url = f"{SUPABASE_URL}/rest/v1/lotto_rounds?select=round&order=round.desc&limit=1"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if data: return data[0]['round']
    except Exception as e:
        print(f"[Supabase] 데이터베이스 회차 확인 실패 (0으로 간주): {e}")
    return 0

# ===================================================================
# 4. Supabase 저장 로직
# ===================================================================
def save_to_supabase(target_round, winning_nums, records):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation"
    }
    
    # 1. lotto_rounds 업로드
    if winning_nums and len(winning_nums) >= 7:
        round_data = {
            "round": target_round, "num1": winning_nums[0], "num2": winning_nums[1],
            "num3": winning_nums[2], "num4": winning_nums[3], "num5": winning_nums[4],
            "num6": winning_nums[5], "bonus": winning_nums[6]
        }
        url = f"{SUPABASE_URL}/rest/v1/lotto_rounds?on_conflict=round"
        try:
            requests.post(url, headers=headers, json=round_data, verify=certifi.where()).raise_for_status()
            print(f"[Supabase] {target_round}회 당첨번호 (lotto_rounds) 업로드 성공")
        except Exception as e:
            print(f"[Supabase] 당첨번호 업로드 실패: {e}")
            return False

    # 2. lotto_stores 및 lotto_winners 등록
    for rec in records:
        address = rec.get("a", "").strip()
        if not address: address = rec["n"]
            
        store_data = {
            "name": rec["n"], "address": address,
            "lat": float(rec.get("lat", 0)), "lng": float(rec.get("lng", 0)),
            "is_online": rec.get("isOnline", False), "verified": rec.get("verified", False)
        }
        url = f"{SUPABASE_URL}/rest/v1/lotto_stores?on_conflict=name,address"
        try:
            r = requests.post(url, headers=headers, json=store_data, verify=certifi.where())
            r.raise_for_status()
            res_data = r.json()
            if res_data:
                store_id = res_data[0]['id']
                # 3. lotto_winners 업로드
                winner_data = {"store_id": store_id, "round": target_round, "method": rec.get("m", "자동")}
                w_url = f"{SUPABASE_URL}/rest/v1/lotto_winners"
                w_headers = dict(headers)
                if 'Prefer' in w_headers: del w_headers['Prefer'] # Return is not needed for winners
                requests.post(w_url, headers=w_headers, json=winner_data, verify=certifi.where()).raise_for_status()
        except Exception as e:
            print(f"[Supabase] 상점/당첨자 전송 실패 ({rec['n']}): {e}")
            
    print(f"[Supabase] {len(records)}개의 1등 매장 정보(lotto_stores/winners) 등록 완료")
    return True

# ===================================================================
# 5. 메인 업데이트 로직
# ===================================================================
def run_update(target_round):
    print(f"\n{'='*50}")
    print(f"[Update] {target_round}회 업데이트 시작 - {datetime.now().strftime('%H:%M:%S KST')}")
    print(f"{'='*50}")
    
    winning_nums = fetch_stores_from_dhlottery_api(target_round)
    if not winning_nums:
        time.sleep(random.uniform(2, 4))
        winning_nums = fetch_winning_numbers_naver(target_round)
    if not winning_nums:
        time.sleep(random.uniform(2, 4))
        winning_nums = fetch_winning_numbers_google(target_round)
    
    if not winning_nums:
        print(f"[Update] ❌ {target_round}회 당첨번호 수집 실패 (미발표 상태 의심)")
        return False
        
    records = []
    time.sleep(random.uniform(2, 4))
    records = fetch_stores_naver_news(target_round)
    if len(records) < 3:
        time.sleep(random.uniform(2, 4))
        records += fetch_stores_naver(target_round)
        
    for rec in records:
        if "인터넷" in rec.get("n", "") or "사이트" in rec.get("m", ""):
            rec["n"] = "인터넷 복권판매사이트"
            rec["a"] = "인터넷 복권 판매사이트 (동행복권 온라인)"
            rec["isOnline"] = True
            
    if not records:
        print(f"[Update] ❌ {target_round}회 판매점 정보 생략/조회 불가")
        return False
        
    try:
        import pandas as pd
        cache = {}
        if Path(CACHE_FILE).exists():
            cdf = pd.read_excel(CACHE_FILE)
            cache = {row["a"]: (row["lat"], row["lng"]) for _, row in cdf.iterrows() if pd.notna(row.get("a"))}
    except: cache = {}
    
    for rec in records:
        if rec.get("isOnline"):
            rec["lat"], rec["lng"], rec["verified"] = INTERNET_LOTTERY_LAT, INTERNET_LOTTERY_LNG, True
        else:
            lat, lng = geocode(normalize_address(rec.get("a", "")), KAKAO_API_KEY, cache)
            rec["lat"], rec["lng"] = lat, lng
            
    try:
        if cache:
            import pandas as pd
            pd.DataFrame([{"a": k, "lat": v[0], "lng": v[1]} for k, v in cache.items()]).to_excel(CACHE_FILE, index=False)
    except: pass
    
    # Supabase로 모든 데이터를 업로드합니다.
    if save_to_supabase(target_round, winning_nums, records):
        print(f"\n[Update] 🎉 {target_round}회 Supabase 업데이트 성공!")
        return True
    return False

def main():
    last_round = get_current_round_from_supabase()
    if last_round == 0:
        print("[Main] ❌ Supabase DB 연동 또는 읽기 에러. 안전을 위해 스크립트를 중지합니다.")
        sys.exit(1)
        
    target_round = last_round + 1
    print(f"[Main] 현재 DB 최신 회차: {last_round}회 → 목표: {target_round}회 추출 및 DB Push 시작")
    
    if run_update(target_round): sys.exit(0)
    else: sys.exit(1)

if __name__ == "__main__":
    main()
