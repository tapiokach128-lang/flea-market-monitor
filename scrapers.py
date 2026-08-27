"""
各フリマ・中古サイトの「キーワード検索結果」を取得するモジュール。

■ 設計方針
サイトのHTML/CSSクラス名は頻繁に変わるため、特定のクラス名に依存しすぎない
「商品リンクのURLパターン + 近傍テキストから価格を正規表現で抜き出す」方式を
採用しています。これにより多少のデザイン変更には耐えられますが、サイト側の
大規模リニューアルがあった場合は動かなくなることがあります。

その場合は、該当ページのHTML(ブラウザの「検証」→ Elements の該当箇所)を
私(Claude)に見せてもらえれば、パーサーを修正します。
"""

import re
import time
import random
import requests
from urllib.parse import quote

# 人間がブラウザで見ているのと同じヘッダーを送る(ブロック回避と最低限のマナー)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
}

REQUEST_TIMEOUT = 15


def _get(url):
    """共通GETリクエスト。失敗時はNoneを返す(全体を止めない)。"""
    try:
        res = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if res.status_code != 200:
            print(f"  [警告] {url} -> HTTP {res.status_code}")
            return None
        return res.text
    except requests.RequestException as e:
        print(f"  [警告] リクエスト失敗: {url} ({e})")
        return None


def _find_items(html, link_pattern, price_window=400):
    """
    HTML全体から `link_pattern` に一致する商品URLを探し、
    そのURL出現位置の直後 `price_window` 文字以内にある
    最初の「¥ or 円」表記を価格として拾う汎用パーサー。
    """
    if not html:
        return []

    items = {}
    for m in re.finditer(link_pattern, html):
        url = m.group(0)
        item_id = m.group(1) if m.groups() else url
        if item_id in items:
            continue

        window = html[m.end(): m.end() + price_window]
        price_match = re.search(r"[¥￥]\s?([\d,]{3,9})", window)
        price = int(price_match.group(1).replace(",", "")) if price_match else None

        # タイトルらしき文字列(直前のalt属性)を拾う
        prefix = html[max(0, m.start() - 300): m.start()]
        alt_match = re.findall(r'alt="([^"]{2,80})"', prefix)
        title = alt_match[-1] if alt_match else "(タイトル取得失敗)"

        # サムネイル画像らしきURLを拾う(直前のimg src / data-src)
        img_match = re.findall(
            r'(?:src|data-src)="(https://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', prefix
        )
        image = img_match[-1] if img_match else None

        items[item_id] = {
            "id": item_id,
            "title": title,
            "price": price,
            "url": url,
            "image": image,
        }

    return list(items.values())


def search_mercari(keyword, max_results=20):
    url = f"https://jp.mercari.com/search?keyword={quote(keyword)}&status=on_sale"
    html = _get(url)
    results = _find_items(
        html,
        r"https://jp\.mercari\.com/item/(m\d+)",
    )
    for r in results:
        r["site"] = "メルカリ"
        r["id"] = "mercari_" + r["id"]
    return results[:max_results]


def search_rakuma(keyword, max_results=20):
    url = f"https://fril.jp/s?query={quote(keyword)}&transaction=selling"
    html = _get(url)
    results = _find_items(
        html,
        r"https://fril\.jp/([a-f0-9]{20,40})",
    )
    for r in results:
        r["site"] = "ラクマ"
        r["url"] = "https://fril.jp/" + r["id"]
        r["id"] = "rakuma_" + r["id"]
    return results[:max_results]


def search_2ndstreet(keyword, max_results=20):
    url = f"https://www.2ndstreet.jp/search?keyword={quote(keyword)}"
    html = _get(url)
    results = _find_items(
        html,
        r"https://www\.2ndstreet\.jp/goods/detail/(\d+)",
    )
    for r in results:
        r["site"] = "2nd STREET"
        r["id"] = "2ndstreet_" + r["id"]
    return results[:max_results]


def search_bookoff(keyword, max_results=20):
    url = f"https://shopping.bookoff.co.jp/search/?keyword={quote(keyword)}"
    html = _get(url)
    results = _find_items(
        html,
        r"https://shopping\.bookoff\.co\.jp/[a-zA-Z0-9\-_/]*?/(\d{6,})/?",
    )
    for r in results:
        r["site"] = "BOOKOFF"
        r["id"] = "bookoff_" + r["id"]
    return results[:max_results]


SCRAPERS = {
    "mercari": search_mercari,
    "rakuma": search_rakuma,
    "2ndstreet": search_2ndstreet,
    "bookoff": search_bookoff,
}


def search_all_sites(keyword, enabled_sites, max_results=20):
    """有効なサイトすべてでkeyword検索し、結果をまとめて返す。"""
    all_results = []
    for site_key, is_enabled in enabled_sites.items():
        if not is_enabled or site_key not in SCRAPERS:
            continue
        try:
            results = SCRAPERS[site_key](keyword, max_results=max_results)
            print(f"  {site_key}: {len(results)}件取得")
            all_results.extend(results)
        except Exception as e:
            print(f"  [エラー] {site_key} の検索に失敗: {e}")
        # サイトに負荷をかけすぎないよう毎回ランダムに待つ
        time.sleep(random.uniform(1.5, 3.0))
    return all_results
