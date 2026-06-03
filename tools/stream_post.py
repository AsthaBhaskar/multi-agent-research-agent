import http.client
import json

conn = http.client.HTTPConnection('127.0.0.1', 8000, timeout=300)
body = json.dumps({"topic": "test pipeline run", "max_revisions": 2, "score_threshold": 6})
headers = {'Content-Type': 'application/json'}
conn.request('POST', '/api/research', body=body, headers=headers)
resp = conn.getresponse()
print('status', resp.status)
for k, v in resp.getheaders():
    print(k, v)

try:
    while True:
        line = resp.readline()
        if not line:
            break
        print('LINE:', line.decode('utf-8', errors='replace').rstrip())
except KeyboardInterrupt:
    pass
