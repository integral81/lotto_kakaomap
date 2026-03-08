import json
import os
import certifi
import urllib.request
import requests
import time

# Disable basic proxy environments just in case
os.environ['HTTPS_PROXY'] = ""
os.environ['HTTP_PROXY'] = ""

SUPABASE_URL = "https://sdvrijpwwpqgaivfutjm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNkdnJpanB3d3BxZ2FpdmZ1dGptIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjcwNDcxNCwiZXhwIjoyMDg4MjgwNzE0fQ.IkyRMb5FfjfRWfAwp2gaPIvnsKJvEM_y8GrgdJhqLyA"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation"
}

def get_real_win_numbers(round_num):
    url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={round_num}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=urllib.request.ssl.create_default_context(cafile=certifi.where()), timeout=3) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data['returnValue'] == 'success':
                return {
                    'num1': data['drwtNo1'],
                    'num2': data['drwtNo2'],
                    'num3': data['drwtNo3'],
                    'num4': data['drwtNo4'],
                    'num5': data['drwtNo5'],
                    'num6': data['drwtNo6'],
                    'bonus': data['bnusNo']
                }
    except Exception as e:
        pass
    
    return {'num1': 0, 'num2': 0, 'num3': 0, 'num4': 0, 'num5': 0, 'num6': 0, 'bonus': 0}

def get_history_rounds():
    print("Reading lotto_history.json to fetch all historical winning numbers...")
    with open('lotto_history.json', 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    rounds = []
    for rnd_str, nums in history.items():
        if len(nums) == 7:
            rounds.append({
                'round': int(rnd_str),
                'num1': nums[0],
                'num2': nums[1],
                'num3': nums[2],
                'num4': nums[3],
                'num5': nums[4],
                'num6': nums[5],
                'bonus': nums[6]
            })
    return rounds

def upsert_table(table_name, data, on_conflict=None):
    url = f"{SUPABASE_URL}/rest/v1/{table_name}"
    headers = HEADERS.copy()
    if on_conflict:
        headers["Prefer"] = f"resolution=return=representation,resolution=merge-duplicates"
        url += f"?on_conflict={on_conflict}"
        
    try:
        response = requests.post(url, headers=headers, json=data, verify=certifi.where())
        response.raise_for_status()
        if response.text:
            return response.json()
        return []
    except Exception as e:
        print(f"Error {table_name}: {e}")
        return []

def migrate():
    print("Starting REST Api Migration to Supabase...")
   
    # 1. Migrate Rounds
    rounds = get_history_rounds()
    print(f"Found {len(rounds)} rounds in history file. Uploading to lotto_rounds table...")
    
    for i in range(0, len(rounds), 100):
        chunk = rounds[i:i+100]
        upsert_table('lotto_rounds', chunk, 'round')
        
    print("Rounds migration complete.\n")

    # 2. Extract Data
    print("Reading lotto_data.json...")
    with open('lotto_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    unique_stores_set = set() # (name, address, lat, lng, isOnline, verified)
    for item in data:
        name = item.get('n', '').strip()
        address = item.get('a', '').strip()
        if not address:
            address = name
        lat = item.get('lat')
        lng = item.get('lng')
        isOnline = item.get('isOnline', False)
        verified = item.get('verified', False)
        if (name, address) not in [(s[0], s[1]) for s in unique_stores_set]:
             unique_stores_set.add((name, address, lat, lng, isOnline, verified))
             
    unique_stores_payload = []
    for s in unique_stores_set:
        unique_stores_payload.append({
            'name': s[0], 'address': s[1],
            'lat': float(s[2]) if s[2] is not None else 0.0,
            'lng': float(s[3]) if s[3] is not None else 0.0,
            'is_online': s[4], 'verified': s[5]
        })
    
    print(f"Found {len(unique_stores_payload)} unique stores. Uploading...")
    
    for i in range(0, len(unique_stores_payload), 500):
        chunk = unique_stores_payload[i:i+500]
        upsert_table('lotto_stores', chunk, 'name,address')
            
    print("Fetching assigned Store UUIDs to map winners...")
    all_stores = []
    try:
        get_headers = HEADERS.copy()
        if 'Prefer' in get_headers:
            del get_headers['Prefer']
        
        limit = 1000
        for offset in range(0, 15000, limit):
            url = f"{SUPABASE_URL}/rest/v1/lotto_stores?select=id,name,address&limit={limit}&offset={offset}"
            response = requests.get(url, headers=get_headers, verify=certifi.where())
            response.raise_for_status()
            if response.text:
                 res_data = response.json()
                 all_stores.extend(res_data)
                 if len(res_data) < limit:
                     break
    except Exception as e:
        print(f"Error fetching stores: {e}")
            
    print(f"Total successful processed UUID Stores returned: {len(all_stores)}")
            
    name_addr_to_id = {}
    for st in all_stores:
        name_addr_to_id[(st['name'], st['address'])] = st['id']

    # 3. Migrate Winners
    print("Preparing Winners mapping...")
    winners_list = []
    for item in data:
        name = item.get('n', '').strip()
        address = item.get('a', '').strip()
        if not address:
            address = name
        
        store_uuid = name_addr_to_id.get((name, address))
        if not store_uuid:
            continue
            
        if 'rounds' in item:
            for r in item['rounds']:
                winners_list.append({
                    'store_id': store_uuid, 'round': int(r['r']), 'method': r.get('m', '자동')
                })
        else:
            if 'r' in item:
                 winners_list.append({
                    'store_id': store_uuid, 'round': int(item['r']), 'method': item.get('m', '자동')
                })

    print(f"Found {len(winners_list)} winning records. Uploading in chunks...")
    for i in range(0, len(winners_list), 500):
        chunk = winners_list[i:i+500]
        upsert_table('lotto_winners', chunk)

    print("Migration finished successfully!")

if __name__ == "__main__":
    migrate()
