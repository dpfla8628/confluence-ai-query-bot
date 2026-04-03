from flask import Flask, jsonify
import requests
import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

CONFLUENCE_URL = "wiki"
USERNAME = "id"
PASSWORD = "pw"
ROOT_PAGE_ID = "pageId"

headers = {"Accept": "application/json"}

# 모든 요청을 이 세션으로 통일
session = requests.Session()
session.trust_env = False


def strip_html(html):
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def safe_get(url, params=None):
    """Confluence 요청 공통 함수"""
    res = session.get(
        url,
        auth=(USERNAME, PASSWORD),
        headers=headers,
        params=params,
        verify=False,
        proxies={"http": None, "https": None},
        timeout=15,
    )
    res.raise_for_status()
    return res


def get_all_child_pages(page_id, depth=0, max_depth=3):
    """하위 페이지 재귀적으로 전부 수집"""
    if depth > max_depth:
        return []

    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}/child/page"
    res = safe_get(url, params={"limit": 50})

    pages = []
    for p in res.json().get("results", []):
        pages.append(p["id"])
        pages.extend(get_all_child_pages(p["id"], depth + 1, max_depth))

    return pages


def get_page_content(page_id):
    """페이지 제목 + 본문 조회"""
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}"
    res = safe_get(url, params={"expand": "body.storage,title"})

    data = res.json()
    title = data.get("title", "")
    body = data.get("body", {}).get("storage", {}).get("value", "")
    return title, strip_html(body)


@app.route("/get_schema")
def get_schema():
    try:
        page_ids = [ROOT_PAGE_ID] + get_all_child_pages(ROOT_PAGE_ID)

        results = []
        for pid in page_ids:
            title, body = get_page_content(pid)
            results.append({
                "page_id": pid,
                "title": title,
                "content": body
            })

        return jsonify({
            "success": True,
            "count": len(results),
            "pages": results
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
