"""全実装が同一の計算結果を返すことを検証する（CLI版）。

性能比較は「同じ仕事をさせている」ことが前提になる。片方だけ手抜きをしていれば
速いのは当たり前で、数値に意味がなくなる。bench.py の前に必ずこれを通すこと。
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

ENDPOINTS = {
    "py": "http://localhost:18001",
    "go": "http://localhost:18002",
    "rb": "http://localhost:18003",
    "ts": "http://localhost:18004",
    "java": "http://localhost:18005",
    "cs": "http://localhost:18006",
    "php": "http://localhost:18007",
    "rs": "http://localhost:18008",
}


def build_payload(rounds: int, items: int) -> dict:
    return {
        "order_id": "ORD-PARITY-0001",
        "items": [
            {"sku": f"SKU-{j:04d}", "qty": (j % 9) + 1, "unit_price": (j * 137 % 5000) + 0.5}
            for j in range(items)
        ],
        "customer": {"tier": "gold", "history_days": 400},
        "rounds": rounds,
    }


def call(base: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{base}/api/v1/score",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=200)
    parser.add_argument("--items", type=int, default=12)
    args = parser.parse_args()

    payload = build_payload(args.rounds, args.items)
    results = {}
    for lang, base in ENDPOINTS.items():
        try:
            results[lang] = call(base, payload)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"[NG] {lang}: 接続失敗 {exc}（make up で全サービスを起動しているか確認）")
            return 2

    # lang フィールドだけは実装ごとに異なって当然なので比較から外す
    def strip(body: dict) -> str:
        return json.dumps({k: v for k, v in body.items() if k != "lang"}, sort_keys=True)

    base_key = strip(results["py"])
    ok = True
    for lang, body in results.items():
        same = strip(body) == base_key
        ok &= same
        print(f"[{'OK' if same else 'NG'}] {lang}: total={body['total']} signature={body['signature'][:16]}…")

    if not ok:
        print("\n--- 全応答 ---")
        print(json.dumps(results, ensure_ascii=False, indent=2))
        print("\n実装間で計算結果が食い違っている。性能比較の前提が崩れているので先に直すこと。")
        return 1
    print(f"\n{len(results)}実装のパリティ確認OK。性能比較を実行してよい。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
