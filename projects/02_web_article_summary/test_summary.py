import requests

BASE = "http://127.0.0.1:5002"
TEST_URL = "https://ja.wikipedia.org/wiki/人工知能"

fd = {"url": TEST_URL}
r  = requests.post(f"{BASE}/summarize", data=fd)
d  = r.json()

if d["ok"]:
    data = d["data"]
    print("タイトル:", data["title"])
    print(f"本文文字数: {data['char_len']}文字\n")
    print("【3行要約】")
    for s in data["summary_3"]:
        print(f"  ▸ {s}")
    print("\n【5行要約】")
    for s in data["summary_5"]:
        print(f"  ▸ {s}")
    print("\n【SNS用】")
    print(data["sns"])
else:
    print("エラー:", d["error"])
    # NHKが取得できない場合はWikipediaでテスト
    print("\nWikipediaでテスト中...")
    fd2 = {"url": "https://ja.wikipedia.org/wiki/人工知能"}
    r2  = requests.post(f"{BASE}/summarize", data=fd2)
    d2  = r2.json()
    if d2["ok"]:
        data = d2["data"]
        print("タイトル:", data["title"])
        print("\n【3行要約】")
        for s in data["summary_3"]:
            print(f"  ▸ {s}")
        print("\n【SNS用】")
        print(data["sns"])
    else:
        print("エラー:", d2["error"])
