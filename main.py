"""
新着出品監視ツール - メイン実行スクリプト

使い方:
    python main.py

  1回実行するごとに、config.json のキーワード×サイトで検索し、
  前回まで通知していない新着商品だけをDiscordに通知します。
  常時監視したい場合は、この script を Windows タスクスケジューラ /
  cron / GitHub Actions などで定期的に(例: 10〜15分おき)実行してください。
"""

import json
import os
from datetime import datetime, timezone

from scrapers import search_all_sites
from notify import send_discord_notification

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SEEN_PATH = os.path.join(BASE_DIR, "seen_ids.json")
FEED_PATH = os.path.join(BASE_DIR, "docs", "feed.json")

# ダッシュボードに残す最大件数(古いものは自動的に切り捨て)
FEED_MAX_ITEMS = 300


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    config = load_json(CONFIG_PATH, {})
    seen_ids = set(load_json(SEEN_PATH, []))
    existing_feed = load_json(FEED_PATH, {"items": []})
    if isinstance(existing_feed, list):  # 旧形式との互換
        existing_feed = {"items": existing_feed}
    feed_items = {item["id"]: item for item in existing_feed.get("items", [])}

    keywords = config.get("keywords", [])
    sites = config.get("sites", {})
    webhook_url = config.get("discord_webhook_url", "")
    max_price = config.get("max_price")
    max_results = config.get("max_results_per_keyword", 20)

    if not keywords:
        print("config.json に keywords が設定されていません。")
        return

    new_count = 0

    for keyword in keywords:
        print(f"\n=== 検索: 「{keyword}」 ===")
        results = search_all_sites(keyword, sites, max_results=max_results)

        now_iso = datetime.now(timezone.utc).isoformat()

        for item in results:
            if max_price and item.get("price") and item["price"] > max_price:
                continue

            is_new = item["id"] not in seen_ids

            if is_new:
                print(f"  [新着] {item['site']} / {item['title']} / {item.get('price')}")
                ok = send_discord_notification(webhook_url, keyword, item)
                if ok:
                    new_count += 1
                seen_ids.add(item["id"])

            # ダッシュボード用フィード: 初回発見時刻は保持し、キーワードを記録
            existing = feed_items.get(item["id"])
            feed_items[item["id"]] = {
                **item,
                "keyword": keyword,
                "found_at": existing["found_at"] if existing else now_iso,
            }

    save_json(SEEN_PATH, sorted(seen_ids))

    # 新しい発見順に並べ替えて、上限件数だけ残す
    sorted_feed = sorted(
        feed_items.values(), key=lambda x: x["found_at"], reverse=True
    )[:FEED_MAX_ITEMS]
    os.makedirs(os.path.dirname(FEED_PATH), exist_ok=True)
    save_json(FEED_PATH, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": sorted_feed,
    })

    print(f"\n完了: 新着 {new_count} 件を通知しました。(ダッシュボード掲載: {len(sorted_feed)}件)")


if __name__ == "__main__":
    main()
