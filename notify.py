import requests


def send_discord_notification(webhook_url, keyword, item):
    """1商品につき1つのEmbedメッセージをDiscordに送る。"""
    if not webhook_url or "ここに" in webhook_url:
        print("  [注意] Discord Webhook URLが未設定のため通知をスキップしました。")
        return False

    price_text = f"¥{item['price']:,}" if item.get("price") else "価格不明"

    payload = {
        "embeds": [
            {
                "title": item.get("title", "新着商品"),
                "url": item.get("url"),
                "description": f"**{price_text}**\nキーワード: {keyword}",
                "footer": {"text": item.get("site", "")},
                "color": 5814783,
            }
        ]
    }

    try:
        res = requests.post(webhook_url, json=payload, timeout=10)
        return res.status_code in (200, 204)
    except requests.RequestException as e:
        print(f"  [エラー] Discord通知失敗: {e}")
        return False
