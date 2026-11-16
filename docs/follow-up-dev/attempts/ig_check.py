import sys, requests, truststore; truststore.inject_into_ssl()
from hanip.config import load_settings
s = load_settings()
mid = sys.argv[1]; method = sys.argv[2] if len(sys.argv) > 2 else "GET"
url = f"https://{s.ig_graph_host}/{s.ig_api_version}/{mid}"
if method == "GET":
    r = requests.get(url, params={"fields": "id,permalink,timestamp", "access_token": s.ig_access_token}, timeout=30)
else:
    r = requests.delete(url, params={"access_token": s.ig_access_token}, timeout=30)
print(r.status_code, r.text[:400])
