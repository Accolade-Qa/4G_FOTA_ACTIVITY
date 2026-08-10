import json
import os
from pathlib import Path
import requests

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

def load_env():
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

load_env()

user = os.getenv("PORTAL_USER")
pwd = os.getenv("PORTAL_PASS")
login_url = os.getenv("PORTAL_LOGIN_URL", "https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/user/login")
list_url = os.getenv("FETCH_SERVERS_API_URL", "https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/server/getServerData?page=1&size=100&search=")
by_id_template = os.getenv("FETCH_SERVER_DATA_BY_ID", "https://aepl-tcu4g-qa.accoladeelectronics.com:6101/api/server/getServerDataByUId?id={id}")

print(f"--- API TEST DIAGNOSTICS ---")
print(f"User: {user}")
print(f"Login URL: {login_url}")
print(f"List URL: {list_url}")

session = requests.Session()
session.verify = False

# 1. Authenticate
login_res = session.post(login_url, json={"userEmail": user, "password": pwd}, timeout=8)
print(f"Login Response Code: {login_res.status_code}")
login_json = login_res.json()
print("Login Response JSON:", json.dumps(login_json, indent=2)[:400])

token = login_json.get("data", {}).get("token") or login_json.get("token") or login_json.get("data", {}).get("accessToken")
if token:
    session.headers.update({"Authorization": f"Bearer {token}"})
    print(f"\nToken Acquired: {token[:20]}...")
else:
    print("\nFAILED TO GET TOKEN!")
    exit(1)

# 2. Get Servers Data List
res = session.get(list_url, timeout=8)
print(f"\nGetServerData Status: {res.status_code}")
res_json = res.json()
print("GetServerData JSON Keys:", list(res_json.keys()))
print("GetServerData Response Preview:", json.dumps(res_json, indent=2)[:800])

# Inspect Data Structure
data_field = res_json.get("data")
print("\nType of 'data' field:", type(data_field))
if isinstance(data_field, dict):
    print("Keys in 'data' dict:", list(data_field.keys()))
    state_list = data_field.get("data") or data_field.get("stateServers") or data_field.get("servers") or []
elif isinstance(data_field, list):
    state_list = data_field
else:
    state_list = []

print(f"\nParsed State List Length: {len(state_list)}")
if state_list:
    first_item = state_list[0]
    print("First Item Sample:", json.dumps(first_item, indent=2))
    state_id = first_item.get("_id") or first_item.get("id")
    state_name = first_item.get("state") or first_item.get("stateName") or first_item.get("stateServerName")
    print(f"First State -> Name: '{state_name}', ID: '{state_id}'")

    if state_id:
        detail_url = by_id_template.format(id=state_id)
        print(f"\nTesting Detail URL: {detail_url}")
        d_res = session.get(detail_url, timeout=6)
        print(f"Detail Response Status: {d_res.status_code}")
        print("Detail Response JSON Preview:", json.dumps(d_res.json(), indent=2)[:600])
