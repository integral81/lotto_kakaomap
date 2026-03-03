"""
로또 자동 업데이트 스크립트 v3.0
방식: 네이버/구글 검색 기반 (동행복권 직접 스크래핑 제거)
스케줄:
  - 1214회: 2026-03-07 22:50 KST (UTC 13:50) - 워크플로우에서 단 1회 트리거
  - 1215회~: 매주 토요일 21:10 KST (UTC 12:10) 시작, 10분 간격 재시도
지연 감지: 1시간 실패 시 TV편성표 검색으로 발표 지연 여부 확인
"""

import json
import os
import re
import time
import sys
import random
from pathlib import Path
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

JSON_FILE = "lotto_data.json"
JS_FILE = "lotto_data.js"
CACHE_FILE = "geocoded_cache_healthy.xlsx"
HISTORIC_FILE = "lotto_historic_numbers_1_1209_Final.xlsx"
KAKAO_API_KEY = os.environ.get("KAKAO_REST_API_KEY")

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
    """네이버에서 N회 로또 당첨번호 검색"""
    query = f"로또 {draw_no}회 당첨번호"
    url = f"https://search.naver.com/search.naver?query={requests.utils.quote(query)}"
    try:
        r = requests.get(url, headers=NAVER_HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # 네이버 로또 전용 결과 파싱 (숫자 볼 형태)
        text = soup.get_text(separator=" ")
        
        # 패턴: "1등 N1 N2 N3 N4 N5 N6 + 보너스 N7"
        pattern = r'당첨번호[^\d]*(\d{1,2})[^\d]+(\d{1,2})[^\d]+(\d{1,2})[^\d]+(\d{1,2})[^\d]+(\d{1,2})[^\d]+(\d{1,2})'
        m = re.search(pattern, text)
        if m:
            nums = [int(m.group(i)) for i in range(1, 7)]
            if all(1 <= n <= 45 for n in nums) and len(set(nums)) == 6:
                # 보너스 번호 추출 시도
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
    """구글에서 N회 로또 당첨번호 검색 (더블체크)"""
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
    """네이버에서 N회 로또 1등 판매점 검색"""
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
            
            # 패턴: 판매점 이름 + 구/시 지역명 + "자동"/"수동"/"반자동"
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
    """동행복권 공식 JSON API 시도 (블록될 수 있음)"""
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
    except Exception as e:
        print(f"[DH API] 실패 (예상됨): {e}")
    return None


def fetch_stores_naver_news(draw_no):
    """네이버 뉴스 기사에서 판매점 정보 추출"""
    records = []
    query = f"로또 {draw_no}회 1등 판매점 당첨"
    url = f"https://search.naver.com/search.naver?where=news&query={requests.utils.quote(query)}&sort=1"
    try:
        r = requests.get(url, headers=NAVER_HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # 뉴스 기사 링크 추출
        news_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "news.naver.com" in href or "n.news.naver.com" in href:
                news_links.append(href)
        
        print(f"[News] {len(news_links)}개 기사 링크 발견")
        
        # 첫 3개 기사 내용에서 판매점 파싱
        for link in news_links[:3]:
            try:
                nr = requests.get(link, headers=NAVER_HEADERS, timeout=10)
                nsoup = BeautifulSoup(nr.text, "html.parser")
                article_text = nsoup.get_text(separator="\n")
                
                # 기사에서 "판매점명 + 지역 (방식)" 패턴 추출
                lines = article_text.split("\n")
                for line in lines:
                    line = line.strip()
                    method = None
                    if "자동" in line:
                        method = "자동"
                    elif "수동" in line:
                        method = "수동"
                    elif "반자동" in line:
                        method = "반자동"
                    elif "사이트" in line or "인터넷" in line:
                        method = "사이트"
                    
                    if method and len(line) > 5 and len(line) < 80:
                        # 지역명이 포함된 줄에서 판매점 이름 추출
                        region_match = re.search(r'([가-힣]+(?:시|구|군))', line)
                        if region_match:
                            name_part = line[:region_match.start()].strip()
                            addr_part = region_match.group(0)
                            if len(name_part) >= 2 and name_part not in [rec["n"] for rec in records]:
                                records.append({
                                    "n": name_part,
                                    "a": addr_part,
                                    "m": method,
                                    "r": draw_no
                                })
                
                if len(records) >= 10:
                    break
                time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                print(f"[News article] 파싱 실패: {e}")
    except Exception as e:
        print(f"[News] 검색 실패: {e}")
    
    print(f"[News] {len(records)}개 판매점 추출")
    return records


# ===================================================================
# 3. TV편성표 기반 로또 발표 지연 감지
# ===================================================================
def check_tv_schedule_delay():
    """
    네이버 TV편성표 검색으로 로또 1등 발표 시간 지연 여부 확인
    Returns: (is_delayed: bool, expected_time: str or None)
    """
    today = datetime.now().strftime("%Y%m%d")
    query = f"KBS2 TV편성표 {today}"
    url = f"https://search.naver.com/search.naver?query={requests.utils.quote(query)}"
    
    try:
        r = requests.get(url, headers=NAVER_HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ")
        
        # KBS2 토요일 21:05 전후 스포츠 중계 감지
        delay_keywords = ["중계", "올림픽", "월드컵", "야구", "축구", "농구", "스포츠", "특집"]
        
        # 21:00~21:30 시간대에 중계 프로그램 있는지 확인
        time_range_pattern = r'21[:\s]*0[0-9][^\n]{0,100}'
        time_matches = re.findall(time_range_pattern, text)
        
        for match in time_matches:
            for keyword in delay_keywords:
                if keyword in match:
                    print(f"[TV Schedule] 지연 감지! 21시대 중계방송: {match[:80]}")
                    # 지연이 감지되면 22:30 이후를 기준으로 설정
                    return True, "22:30"
        
        # 로또 당첨자 발표 지연 관련 뉴스 검색
        delay_query = f"로또 {datetime.now().strftime('%Y년 %m월')} 발표 지연 연기"
        delay_url = f"https://search.naver.com/search.naver?where=news&query={requests.utils.quote(delay_query)}&sort=1"
        dr = requests.get(delay_url, headers=NAVER_HEADERS, timeout=10)
        dsoup = BeautifulSoup(dr.text, "html.parser")
        dtext = dsoup.get_text(separator=" ")
        
        if "발표 지연" in dtext or "연기" in dtext or "특집" in dtext:
            print("[TV Schedule] 뉴스에서 발표 지연 정보 감지")
            return True, "22:30"
    except Exception as e:
        print(f"[TV Schedule] 확인 실패 (기본 스케줄 유지): {e}")
    
    return False, None


# ===================================================================
# 4. 보조 함수들
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


def update_history_json(draw_no, numbers):
    """lotto_history.json 업데이트"""
    hist_path = "lotto_history.json"
    try:
        if Path(hist_path).exists():
            with open(hist_path, encoding="utf-8") as f:
                hist = json.load(f)
        else:
            hist = {}
        
        key = str(draw_no)
        if key not in hist:
            hist[key] = numbers
            with open(hist_path, "w", encoding="utf-8") as f:
                json.dump(hist, f, ensure_ascii=False, separators=(',', ':'))
            print(f"[History] {draw_no}회 번호 {numbers} 저장 완료")
        else:
            print(f"[History] {draw_no}회 이미 존재, 스킵")
    except Exception as e:
        print(f"[History] 업데이트 실패: {e}")


def get_current_round_from_json():
    """lotto_data.json에서 가장 최신 회차 반환"""
    try:
        with open(JSON_FILE, encoding="utf-8") as f:
            all_data = json.load(f)
        rounds = [d.get("r", 0) for d in all_data]
        return max(rounds) if rounds else 0
    except:
        return 0


# ===================================================================
# 5. 메인 업데이트 로직
# ===================================================================
def run_update(target_round):
    """
    네이버/구글에서 target_round 회차 당첨 정보 수집 및 업데이트
    Returns: True (성공), False (실패)
    """
    print(f"\n{'='*50}")
    print(f"[Update] {target_round}회 업데이트 시작 - {datetime.now().strftime('%H:%M:%S KST')}")
    print(f"{'='*50}")
    
    # --- Step 1: 당첨번호 수집 (3가지 방법 시도) ---
    winning_nums = None
    
    # 방법 1: 동행복권 공식 JSON API (간단, 가끔 됨)
    winning_nums = fetch_stores_from_dhlottery_api(target_round)
    
    # 방법 2: 네이버 검색
    if not winning_nums:
        time.sleep(random.uniform(2, 4))
        winning_nums = fetch_winning_numbers_naver(target_round)
    
    # 방법 3: 구글 검색
    if not winning_nums:
        time.sleep(random.uniform(2, 4))
        winning_nums = fetch_winning_numbers_google(target_round)
    
    if not winning_nums:
        print(f"[Update] ❌ {target_round}회 당첨번호 수집 실패 - 아직 발표 전이거나 검색 불가")
        return False
    
    print(f"[Update] ✅ 당첨번호: {winning_nums[:6]} (보너스: {winning_nums[6] if len(winning_nums) > 6 else 'N/A'})")
    
    # --- Step 2: 판매점 정보 수집 ---
    records = []
    
    # 방법 1: 네이버 뉴스 기사
    time.sleep(random.uniform(2, 4))
    records = fetch_stores_naver_news(target_round)
    
    # 방법 2: 네이버 일반 검색
    if len(records) < 3:
        time.sleep(random.uniform(2, 4))
        records += fetch_stores_naver(target_round)
    
    # 인터넷 복권판매사이트 항목 처리
    for rec in records:
        if "인터넷" in rec.get("n", "") or "사이트" in rec.get("m", ""):
            rec["n"] = "인터넷 복권판매사이트"
            rec["a"] = "인터넷 복권 판매사이트 (동행복권 온라인)"
            rec["isOnline"] = True
    
    if not records:
        print(f"[Update] ❌ {target_round}회 판매점 정보 수집 실패")
        return False
    
    print(f"[Update] 수집된 판매점: {len(records)}개")
    
    # --- Step 3: 좌표 변환 ---
    try:
        import pandas as pd
        cache = {}
        if Path(CACHE_FILE).exists():
            cdf = pd.read_excel(CACHE_FILE)
            cache = {row["a"]: (row["lat"], row["lng"]) for _, row in cdf.iterrows() if pd.notna(row.get("a"))}
        print(f"[Geocode] 캐시 {len(cache)}개 로드")
    except:
        cache = {}
    
    INTERNET_LOTTERY_LAT = 37.56358
    INTERNET_LOTTERY_LNG = 126.97923
    
    for rec in records:
        if rec.get("isOnline"):
            rec["lat"] = INTERNET_LOTTERY_LAT
            rec["lng"] = INTERNET_LOTTERY_LNG
            rec["verified"] = True
        else:
            lat, lng = geocode(normalize_address(rec.get("a", "")), KAKAO_API_KEY, cache)
            rec["lat"] = lat
            rec["lng"] = lng
    
    # --- Step 4: 인터넷 복권판매사이트를 동행복권(dhlottery) 마스터 항목에 추가 ---
    try:
        with open(JSON_FILE, encoding="utf-8") as f:
            all_data = json.load(f)
        
        # 동행복권 마스터 항목 찾아서 1등 추가
        dh_main = next((x for x in all_data if "dhlottery" in str(x.get("n","")).lower()), None)
        
        has_internet = any("인터넷" in rec.get("n","") for rec in records)
        if has_internet and dh_main:
            existing_rounds = dh_main.get("rounds", [])
            existing_round_nums = set(item["r"] for item in existing_rounds)
            if target_round not in existing_round_nums:
                existing_rounds.insert(0, {"r": target_round, "m": "사이트"})
                existing_rounds_sorted = sorted(existing_rounds, key=lambda x: x["r"], reverse=True)
                dh_main["rounds"] = existing_rounds_sorted
                dh_main["totalWins"] = len(existing_rounds_sorted)
                dh_main["w"] = dh_main["totalWins"]
                dh_main["r"] = target_round
                print(f"[DH] 동행복권 마스터에 {target_round}회 추가 → 총 {dh_main['totalWins']}회")
            
            # 인터넷 복권판매사이트 별도 항목은 추가하지 않음
            records = [rec for rec in records if "인터넷" not in rec.get("n","")]
        
        all_data = records + all_data
        all_data.sort(key=lambda x: x.get("r", 0), reverse=True)
        
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, separators=(',', ':'))
        with open(JS_FILE, "w", encoding="utf-8") as f:
            f.write("const lottoData = " + json.dumps(all_data, ensure_ascii=False, separators=(',', ':')) + ";")
        
        print(f"[Update] ✅ {JSON_FILE} 업데이트 완료 (총 {len(all_data)}개)")
    except Exception as e:
        print(f"[Update] ❌ 데이터 저장 실패: {e}")
        return False
    
    # --- Step 5: lotto_history.json 업데이트 ---
    update_history_json(target_round, winning_nums)
    
    # --- Step 6: 캐시 저장 ---
    try:
        if cache:
            import pandas as pd
            pd.DataFrame([{"a": k, "lat": v[0], "lng": v[1]} for k, v in cache.items()]).to_excel(CACHE_FILE, index=False)
    except: pass
    
    print(f"\n[Update] 🎉 {target_round}회 업데이트 성공!")
    return True


# ===================================================================
# 6. 메인 진입점
# ===================================================================
def main():
    last_round = get_current_round_from_json()
    target_round = last_round + 1
    
    print(f"[Main] 현재 최신 회차: {last_round}회 → 목표: {target_round}회 업데이트")
    
    result = run_update(target_round)
    
    if result:
        print(f"[Main] ✅ {target_round}회 업데이트 완료!")
        sys.exit(0)
    else:
        print(f"[Main] ❌ {target_round}회 업데이트 실패 - 아직 발표 전이거나 데이터 없음")
        sys.exit(1)


if __name__ == "__main__":
    main()
