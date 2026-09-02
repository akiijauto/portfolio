"""ホストに入っている言語だけ、実装の検査を走らせる。

検査は2段ある。

  1. ロジック一致テスト  — tests/golden.json と一致するか
  2. HTTP層の構文/ビルド — HTTP層が壊れていないか

2 が要るのは、ロジックテストが core だけを読むためで、Go / TypeScript /
Java / Rust は言語の仕組み上テストがHTTP層まで巻き込んでコンパイルするが、
Python / Ruby / PHP / C# は core だけ通してHTTP層に一切触れない。
実機で `docker compose build` して初めて落ちる、という最悪の気づき方をする。

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

# --- 1. ロジック一致テスト -------------------------------------------------
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

# --- 2. HTTP層の構文/ビルド検査 --------------------------------------------
# 上のロジックテストが HTTP層まで巻き込む言語（Go / TypeScript / Java / Rust）は
# ここに載せない。二重に時間をかける意味がないため。
HTTP_CHECKS = [
    ("Python HTTP層", "python3",
     [sys.executable, "-m", "py_compile", "app.py", "core.py"], ROOT / "services" / "python"),
    ("Ruby HTTP層", "ruby",
     ["ruby", "-c", "app.rb"], ROOT / "services" / "ruby"),
    ("PHP HTTP層", "php",
     ["php", "-l", "public/index.php"], ROOT / "services" / "php"),
    ("C# HTTP層", "dotnet",
     ["dotnet", "build", "lang-bench-csharp.csproj", "-c", "Release", "--nologo"],
     ROOT / "services" / "csharp"),
]


def run_group(title, entries, passed, failed, skipped):
    print(f"\n--- {title} ---", flush=True)
    for name, binary, cmd, cwd in entries:
        if shutil.which(binary) is None:
            skipped.append((name, f"{binary} がホストに無い"))
            print(f"[SKIP] {name:<14} {binary} がホストに無い", flush=True)
            continue

        print(f"[RUN ] {name}", flush=True)
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if proc.returncode == 0:
            passed.append(name)
            print(f"[ OK ] {name}", flush=True)
        else:
            failed.append(name)
            print(f"[FAIL] {name}\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}", flush=True)


def main() -> int:
    passed, failed, skipped = [], [], []

    run_group("ロジック一致テスト", SUITES, passed, failed, skipped)
    run_group("HTTP層の構文/ビルド検査", HTTP_CHECKS, passed, failed, skipped)

    print("\n" + "=" * 60)
    print(f"OK: {len(passed)}  FAIL: {len(failed)}  SKIP: {len(skipped)}")
    if passed:
        print(f"  検証済み : {', '.join(passed)}")
    if skipped:
        print(f"  未検証   : {', '.join(f'{n}（{why}）' for n, why in skipped)}")
    if failed:
        print(f"  失敗     : {', '.join(failed)}")
        print("\n実装が壊れている。性能比較の前提が崩れているので先に直すこと。")
        return 1
    if skipped:
        print("\n未検証の言語がある。CI（GitHub Actions）が全言語を検証するので、そちらの結果も確認すること。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
