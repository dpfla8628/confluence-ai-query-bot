from flask import Flask, request, jsonify
import requests, re

app = Flask(__name__)

CONFLUENCE_URL = "https://wiki.ktalpha.com"
USERNAME       = "dpfla8628"
PASSWORD       = "gzs173240!"
ROOT_PAGE_ID   = "186452952"

auth    = (USERNAME, PASSWORD)
headers = {"Accept": "application/json"}

def strip_html(html):
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def get_all_child_pages(page_id, depth=0, max_depth=3):
    """하위 페이지 재귀적으로 전부 수집"""
    if depth > max_depth:
        return []
    
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}/child/page"
    res = requests.get(url, auth=auth, headers=headers, params={"limit": 50})
    if res.status_code != 200:
        return []
    
    pages = []
    for p in res.json().get("results", []):
        pages.append(p["id"])
        pages.extend(get_all_child_pages(p["id"], depth+1, max_depth))
    return pages

def get_page_content(page_id):
    """페이지 내용 가져오기"""
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}"
    res = requests.get(url, auth=auth, headers=headers,
                      params={"expand": "body.storage,title"})
    if res.status_code != 200:
        return None, None
    data  = res.json()
    title = data.get("title", "")
    body  = strip_html(data["body"]["storage"]["value"])
    return title, body

@app.route("/get_schema", methods=["GET"])
def get_schema():
    # 최상단 페이지 + 모든 하위 페이지 ID 수집
    all_ids = [ROOT_PAGE_ID]
    all_ids.extend(get_all_child_pages(ROOT_PAGE_ID))
    
    combined = ""
    titles   = []
    
    for pid in all_ids:
        title, body = get_page_content(pid)
        if not title:
            continue
        # 내용이 너무 짧으면 스킵 (빈 페이지)
        if len(body) < 50:
            continue
        combined += f"\n\n### {title}\n{body}"
        titles.append(title)
    
    # 토큰 제한 위해 최대 15000자로 자르기
    if len(combined) > 15000:
        combined = combined[:15000] + "\n\n... (이하 생략)"
    
    return jsonify({
        "schema": combined,
        "pages_found": len(titles),
        "titles": titles
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    print("Confluence MCP 서버 시작 - http://localhost:5000")
    app.run(port=5000)