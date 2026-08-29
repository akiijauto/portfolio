import requests

fd = {
    "name":      "iPhone 15 Pro 256GB ブラック",
    "condition": "やや傷や汚れあり",
    "category":  "スマートフォン",
    "features":  "純正ケース・充電ケーブル付属、画面に小傷数箇所、バッテリー残量85%"
}
r = requests.post("http://127.0.0.1:5004/generate", data=fd)
d = r.json()

if d["ok"]:
    data = d["data"]
    title_len = len(data["title"])
    print(f"タイトル ({title_len}文字): {data['title']}")
    print(f"カテゴリ: {data['category']}")
    print(f"推奨価格: {data['price_min']:,}円 〜 {data['price_max']:,}円")
    print()
    print("【説明文】")
    print(data["description"])
    print()
    print("【売るためのコツ】")
    for t in data["tips"]:
        print(f"  💡 {t}")
else:
    print("エラー:", d["error"])
