import subprocess, json, urllib.request, time, sys

result = subprocess.run(
    ['git', 'credential', 'fill'],
    input='protocol=https\nhost=github.com\n',
    capture_output=True, text=True
)
lines = result.stdout.strip().split('\n')
creds = {l.split('=')[0]: l.split('=',1)[1] for l in lines if '=' in l}
token = creds.get('password','')

run_id = 22544371970
url = 'https://api.github.com/repos/integral81/lottomap/actions/runs/' + str(run_id)

print("완료 대기 중... (5분 간격, 최대 3시간 추가 폴링)")
for i in range(36):
    req = urllib.request.Request(url)
    req.add_header('Authorization', 'token ' + token)
    req.add_header('Accept', 'application/vnd.github.v3+json')
    resp = urllib.request.urlopen(req, timeout=15)
    run = json.loads(resp.read())
    status = run['status']
    conclusion = run['conclusion']
    updated = run['updated_at']
    print("[" + str(i+1) + "/36] Status:", status, "| Conclusion:", conclusion, "| Updated:", updated)
    if status == 'completed':
        print("\n===== 완료 =====")
        print("결과:", conclusion)
        print("URL:", run['html_url'])
        sys.exit(0 if conclusion == 'success' else 1)
    time.sleep(300)

print("타임아웃: 3시간 추가 폴링 완료, 아직 실행 중.")
