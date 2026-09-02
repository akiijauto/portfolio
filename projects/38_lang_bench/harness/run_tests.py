"""ホストに入っている言語だけロジック一致テストを走らせる。

`make test` は全8言語のツールチェーンが揃っている前提で、1つでも欠けると
そこで止まる。ローカルには普通そこまで揃っていないので、開発中はこちらを使う。
欠けている言語は「未検証」として明示的に報告する。黙って飛ばすと
「テストが通った」と誤解して、壊れた実装のまま計測に進む事故になる。

CI（.github/workflows/lang-bench.yml）では全ツールチェーンを用意した上で
これを実行するため、SKIP が出たらCI設定側の不備を意味する。
"""

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# (表示名, 必要なコマンド, 実行コマンド, 実行ディレクトリ)
SUITES = [
    ("Python", "python3", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], ROOT),
    ("Go", "go", ["go", "test", "./..."], ROOT / "services" / "go"),
    ("Ruby", "ruby", ["ruby", "test_core.rb"], ROOT / "services" / "ruby"),
    ("TypeScript", "npm", ["npm", "test", "--silent"], ROOT / "services" / "node"),
    ("Java", "mvn", ["mvn", "-B", "-q", "test"], ROOT / "services" / "java"),
    ("PHP", "php", ["php", "tests/core_test.php"], ROOT / "services" / "php"),
    ("Rust", "cargo", ["cargo", "test", "--quiet"], ROOT / "services" / "rust"),
    ("C#", "dotnet", ["dotnet", "run", "--configuration", "Release"], ROOT / "services" / "csharp" / "tests"),
]


def main() -> int:
    passed, failed, skipped = [], [], []

    for name, binary, cmd, cwd in SUITES:
        if shutil.which(binary) is None:
            skipped.append((name, f"{binary} がホストに無い"))
            print(f"[SKIP] {name:<11} {binary} がホストに無い", flush=True)
            continue

        print(f"[RUN ] {name}", flush=True)
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if proc.returncode == 0:
            passed.append(name)
            print(f"[ OK ] {name}", flush=True)
        else:
            failed.append(name)
            print(f"[FAIL] {name}\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}", flush=True)

    print("\n" + "=" * 60)
    print(f"OK: {len(passed)}  FAIL: {len(failed)}  SKIP: {len(skipped)}")
    if passed:
        print(f"  検証済み : {', '.join(passed)}")
    if skipped:
        print(f"  未検証   : {', '.join(f'{n}（{why}）' for n, why in skipped)}")
    if failed:
        print(f"  失敗     : {', '.join(failed)}")
        print("\n実装間でロジックが食い違っている。性能比較の前提が崩れているので先に直すこと。")
        return 1
    if skipped:
        print("\n未検証の言語がある。CI（GitHub Actions）が全言語を検証するので、そちらの結果も確認すること。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
