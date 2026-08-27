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

from scrapers import search_all_sites
from notify import send_discord_notification

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SEEN_PATH = os.path.join(BASE_DIR, "seen_ids.json")


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

        for item in results:
            if item["id"] in seen_ids:
                continue
            if max_price and item.get("price") and item["price"] > max_price:
                continue

            print(f"  [新着] {item['site']} / {item['title']} / {item.get('price')}")
            ok = send_discord_notification(webhook_url, keyword, item)
            if ok:
                new_count += 1

            seen_ids.add(item["id"])

    save_json(SEEN_PATH, sorted(seen_ids))
    print(f"\n完了: 新着 {new_count} 件を通知しました。")


if __name__ == "__main__":
    main()
