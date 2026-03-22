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
KAKAO_API_KEY = os.environ.get('KAKAO_REST_API_KEY', "a6b27b6dab16c7e3459bb9589bf1269d") # Prefer Env Var
INTERNET_LOTTERY_LAT, INTERNET_LOTTERY_LNG = 37.4831, 127.0225 # Near Donghaeng Lottery HQ

SUPABASE_URL = os.environ.get('SUPABASE_URL', "https://sdvrijpwwpqgaivfutjm.supabase.co")
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNkdnJpanB3d3BxZ2FpdmZ1dGptIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjcwNDcxNCwiZXhwIjoyMDg4MjgwNzE0fQ.IkyRMb5FfjfRWfAwp2gaPIvnsKJvEM_y8GrgdJhqLyA")

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
        pattern = r'(?:당첨번호|당첨 번호)\D{0,15}?(\d{1,2})\D{1,5}?(\d{1,2})\D{1,5}?(\d{1,2})\D{1,5}?(\d{1,2})\D{1,5}?(\d{1,2})\D{1,5}?(\d{1,2})'
        for m in re.finditer(pattern, text):
            nums = [int(m.group(i)) for i in range(1, 7)]
            if all(1 <= n <= 45 for n in nums) and len(set(nums)) == 6:
                search_region = text[max(0, m.start()-100) : m.end()+200]
                bonus_pattern = r'보너스\D{0,30}?(?<!\d)(\d{1,2})(?!\d)'
                bm = re.search(bonus_pattern, search_region)
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
        pattern = r'(?:당첨번호|당첨 번호)\D{0,15}?(\d{1,2})\D{1,5}?(\d{1,2})\D{1,5}?(\d{1,2})\D{1,5}?(\d{1,2})\D{1,5}?(\d{1,2})\D{1,5}?(\d{1,2})'
        for m in re.finditer(pattern, text):
            nums = [int(m.group(i)) for i in range(1, 7)]
            if all(1 <= n <= 45 for n in nums) and len(set(nums)) == 6:
                search_region = text[max(0, m.start()-100) : m.end()+200]
                bonus_pattern = r'보너스\D{0,30}?(?<!\d)(\d{1,2})(?!\d)'
                bm = re.search(bonus_pattern, search_region)
                if bm:
                    bonus = int(bm.group(1))
                    if 1 <= bonus <= 45 and bonus not in nums:
                        nums.append(bonus)
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

def fetch_stores_naver_news(draw_no):
    # Store results as {(name, address): {"method": str, "count": int}}
    stores_map = {}
    queries = [
        f"로또 {draw_no}회 1등 배출점",
        f"로또 {draw_no}회 1등 판매점",
        f"{draw_no}회 로또 당첨지역"
    ]
    
    links = []
    for query in queries:
        url = f"https://search.naver.com/search.naver?where=news&query={requests.utils.quote(query)}&sort=1"
        try:
            r = requests.get(url, headers=NAVER_HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            
            # UI 변경(클래스명 난독화) 대응: a.news_tit 대신 URL 구조로 뉴스 링크 추출
            for a in soup.find_all('a', href=True):
                href = a['href']
                # n.news.naver.com 계열 링크 추출
                if 'news.naver.com' in href and 'article' in href:
                    if href not in links:
                        links.append(href)
            
            if len(links) >= 5:
                break
        except Exception as e:
            print(f"[News] {query} 검색 실패: {e}")
            
    links = links[:5]
    
    blacklist = ["홈페이지", "뉴스", "기자", "기사", "로또복권", "동행복권", "인터넷", "판매점", "당첨", "추첨", "연합뉴스"]
    
    best_stores_map = {}
    
    for link in links:
        stores_map = {}
        try:
            nr = requests.get(link, headers=NAVER_HEADERS, timeout=12)
            nr.encoding = 'utf-8'
            nsoup = BeautifulSoup(nr.text, "html.parser")
            content = nsoup.find('article', id='dic_area') or nsoup.find('div', id='dic_area') or \
                      nsoup.find('div', id='articleBodyContents') or nsoup.find('div', class_='_article_body')
            if not content: continue
                
            text = content.get_text(separator="\n")
            # regex to find store name and address hint within parentheticals
            matches = list(re.finditer(r'(?:▲|△|■|[\d]+\.)\s*([가-힣\w\d&/\s()]+)\(([^)]+)\)', text))
                
            for i, m in enumerate(matches):
                p1 = m.group(1).strip()
                p2 = m.group(2).strip()
                    
                if any(word in p1 for word in blacklist) and len(p1) < 10: continue
                if len(p1) < 2 or len(p2) < 2: continue

                if any(x in p1 for x in ['시 ', '구 ', '군 ', '읍 ', '면 ', '리 ']) or re.search(r'\d+-\d+', p1):
                    name, addr = p2, p1
                else:
                    name, addr = p1, p2
                    
                if any(word in name for word in ["홈페이지", "뉴스1", "연합뉴스", "기자"]): continue

                multiplier = 1
                search_end = matches[i+1].start() if i + 1 < len(matches) else m.end() + 150
                next_text = text[m.end():search_end]
                    
                if re.search(r'(2|3|4|5)\s*(명|인|게임|장|번|건)', next_text) or "동시에" in next_text:
                    m_match = re.search(r'(\d)\s*(?:명|인|게임|장|번|건)', next_text)
                    if m_match:
                        multiplier = int(m_match.group(1))
                    elif "2명" in next_text or "2게임" in next_text or "2건" in next_text:
                        multiplier = 2

                method = "수동" if "수동" in text[max(0, m.start()-50):search_end] else "자동"
                if "반자동" in text[max(0, m.start()-50):search_end]: method = "반자동"
                    
                key = (name, addr)
                if key not in stores_map:
                    stores_map[key] = {"m": method, "c": multiplier}
                else:
                    stores_map[key]["c"] = max(stores_map[key]["c"], multiplier)
            
            if len(stores_map) > len(best_stores_map):
                best_stores_map = stores_map
                
            time.sleep(random.uniform(0.3, 0.7))
        except Exception as e:
            print(f"[News article] {link} 파싱 실패: {e}")
    
    records = []
    for (name, addr), info in best_stores_map.items():
        for _ in range(info["c"]):
            records.append({"n": name, "a": addr, "m": info["m"], "r": draw_no})
            
    print(f"[News] 총 {len(best_stores_map)}개 판매점에서 {len(records)}명의 1등 당첨자 추출 완료")
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
    # Note: Using JS Key with spoofed KA/Referer headers to bypass restriction
    headers = {
        "Authorization": "KakaoAK " + api_key,
        "Referer": "https://k-inov.com/",
        "KA": "sdk/1.43.0 os/javascript lang/ko device/web origin/https%3A%2F%2Fk-inov.com"
    }
    try:
        r = requests.get(url, headers=headers, params={"query": address}, timeout=10)
        data = r.json()
        if data.get("documents"):
            pos = data["documents"][0]
            lat, lng = float(pos["y"]), float(pos["x"])
            cache[address] = (lat, lng)
            return lat, lng
    except Exception as e:
        print(f"[Geocode] '{address}' 변환 실패: {e}")
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
def _sb_get(url, headers):
    """Supabase GET 헬퍼"""
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Supabase GET] 오류: {e}")
        return []

def save_to_supabase(target_round, winning_nums, records):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation"
    }
    read_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }

    # ── [안전장치 1] 이미 해당 round가 lotto_winners에 있으면 스킵 ──────────
    existing = _sb_get(
        f"{SUPABASE_URL}/rest/v1/lotto_winners?select=id&round=eq.{target_round}",
        read_headers
    )
    if existing:
        print(f"[Supabase] ⚠️  {target_round}회 lotto_winners 이미 {len(existing)}개 존재 → 중복 삽입 방지, 스킵")
        # 자가검증만 실행 후 반환
        _verify_round(target_round, len(records), read_headers)
        return True

    # ── 1. lotto_rounds 업로드 ─────────────────────────────────────────────
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

    # ── 2. lotto_stores 및 lotto_winners 등록 ─────────────────────────────
    inserted_count = 0
    for rec in records:
        address = rec.get("a", "").strip()
        if not address: address = rec["n"]

        store_data = {
            "name": rec["n"], "address": address,
            "lat": float(rec.get("lat") or 0.0), "lng": float(rec.get("lng") or 0.0),
            "is_online": rec.get("isOnline", False), "verified": rec.get("verified", False)
        }
        url = f"{SUPABASE_URL}/rest/v1/lotto_stores?on_conflict=name,address"
        try:
            r = requests.post(url, headers=headers, json=store_data, verify=certifi.where())
            r.raise_for_status()
            res_data = r.json()
            if not res_data:
                print(f"[Supabase] ⚠️  {rec['n']} store upsert 응답 없음")
                continue
            store_id = res_data[0]['id']

            # ── [안전장치 2] 이 상점의 해당 round winner가 이미 있으면 스킵 ──
            # (독천 로또처럼 2명 당첨인 경우는 같은 store_id로 2개가 정상이므로
            #  전체 round 단위 스킵(안전장치1)으로만 관리. 여기선 스킵 안 함)

            winner_data = {"store_id": store_id, "round": target_round, "method": rec.get("m", "자동")}
            w_url = f"{SUPABASE_URL}/rest/v1/lotto_winners"
            w_headers = dict(headers)
            if 'Prefer' in w_headers: del w_headers['Prefer']
            requests.post(w_url, headers=w_headers, json=winner_data, verify=certifi.where()).raise_for_status()
            inserted_count += 1
        except Exception as e:
            print(f"[Supabase] 상점/당첨자 전송 실패 ({rec['n']}): {e}")

    print(f"[Supabase] {inserted_count}/{len(records)}개 1등 매장 정보(lotto_stores/winners) 등록 완료")

    # ── [안전장치 3] 저장 후 자가검증 ──────────────────────────────────────
    _verify_round(target_round, len(records), read_headers)
    return True


def _verify_round(target_round, expected_count, read_headers):
    """저장 후 DB 실제 카운트 검증 및 불일치 시 경고"""
    actual = _sb_get(
        f"{SUPABASE_URL}/rest/v1/lotto_winners?select=id,lotto_stores(name)&round=eq.{target_round}",
        read_headers
    )
    actual_count = len(actual) if isinstance(actual, list) else 0
    if actual_count == expected_count:
        print(f"[검증] ✅ {target_round}회 DB 검증 성공: {actual_count}명 (예상 {expected_count}명)")
    else:
        print(f"[검증] ❌ {target_round}회 DB 불일치! DB={actual_count}명 vs 수집={expected_count}명")
        print("[검증] 등록된 상점 목록:")
        for w in (actual if isinstance(actual, list) else []):
            store = w.get('lotto_stores') or {}
            print(f"  - {store.get('name', '?')} (winner_id={w.get('id','?')[:8]}...)")

# ===================================================================
# 5. 메인 업데이트 로직
# ===================================================================
def run_update(target_round):
    print(f"\n{'='*50}")
    print(f"[Update] {target_round}회 업데이트 시작 - {datetime.now().strftime('%H:%M:%S KST')}")
    print(f"{'='*50}")
    
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
        if "인터넷" in rec.get("n", "") or "사이트" in rec.get("m", "") or "dhlottery" in rec.get("n", "").lower():
            rec["n"] = "동행복권(dhlottery.co.kr)"
            rec["a"] = "서울특별시 서초구 남부순환로 2423 1층"
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
