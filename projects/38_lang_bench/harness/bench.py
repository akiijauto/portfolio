"""3言語ベンチマークのオーケストレータ。

実行モードは2つある。両方を1回の run で走らせるのが既定。

  isolated   : 1言語ずつ単独で起動して負荷をかける。他コンテナがCPUを奪わないので
               「その言語の素の性能」が出る。言語間比較の主データはこちら。
  concurrent : 全言語を同時に起動し、共通の開始時刻（スタートバリア）で一斉に
               負荷をかける。ホストのCPUを奪い合う状況での劣化の仕方を見る。
               「複数のDockerを同時に動かすタイマー」はここ。

concurrent の数値は isolated より必ず悪くなる。両者を並べて初めて
「この言語は混み合うとどれだけ崩れるか」が読める。
"""

import argparse
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collector import Collector  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

# service名 -> (コンテナ名, ホスト公開ポート, 表示名)
TARGETS = {
    "py": ("bench-py", 18001, "Python 3.12 / FastAPI+uvicorn"),
    "go": ("bench-go", 18002, "Go 1.22 / net_http"),
    "rb": ("bench-rb", 18003, "Ruby 3.3 / Sinatra+Puma"),
    "ts": ("bench-ts", 18004, "TypeScript / Node 22 + Fastify"),
    "java": ("bench-java", 18005, "Java 21 / Spring Boot 3 + 仮想スレッド"),
    "cs": ("bench-cs", 18006, "C# / .NET 9 Minimal API"),
    "php": ("bench-php", 18007, "PHP 8.4 / nginx + php-fpm + JIT"),
    "rs": ("bench-rs", 18008, "Rust / Axum + Tokio"),
}

K6_IMAGE = "grafana/k6:0.54.0"


def run(cmd, **kwargs):
    print(f"  $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=ROOT, **kwargs)


def compose(*args, **kwargs):
    return run(["docker", "compose", *args], **kwargs)


def preflight():
    """前提が崩れたまま走らせると無意味な数値が出るので、ここで必ず止める。"""
    if sys.platform == "win32":
        # Windows ネイティブでも docker -v は通るが、Makefile が Unix ツールに
        # 依存しており、結果ディレクトリのパス変換でも事故りやすい。
        # 計測対象は Linux コンテナなので、WSL2 で走らせても数値の意味は変わらない。
        print("[WARN] Windows ネイティブで実行している。WSL2 上での実行を推奨"
              "（README.html の「Windows での実行」を参照）。", flush=True)

    for binary in ("docker",):
        if shutil.which(binary) is None:
            sys.exit(f"[FATAL] {binary} が見つからない。README.html の前提条件を参照。")
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode != 0:
        sys.exit("[FATAL] docker compose v2 が必要。")
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        sys.exit("[FATAL] docker デーモンに接続できない。")


def wait_healthy(services, timeout=300):
    """healthz が通るまで待つ。ここを省くと起動直後の遅さを計測してしまう。"""
    deadline = time.time() + timeout
    pending = set(services)
    while pending and time.time() < deadline:
        for svc in list(pending):
            container = TARGETS[svc][0]
            probe = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Health.Status}}", container],
                capture_output=True, text=True,
            )
            if probe.stdout.strip() == "healthy":
                pending.discard(svc)
        if pending:
            time.sleep(2)
    if pending:
        sys.exit(f"[FATAL] 起動待ちタイムアウト: {sorted(pending)}")
    print(f"  healthy: {sorted(services)}", flush=True)


def k6_command(svc, out_dir, start_at_ms, args, detach):
    """k6 コンテナ1本分のコマンドを組み立てる。

    負荷元も同じ bench ネットワークに入れ、コンテナ名:8000 を直接叩く。
    ホスト側の公開ポート経由にすると docker-proxy がボトルネックになり、
    言語差ではなくポートフォワードの詰まりを測ることになる。
    """
    container, _, _ = TARGETS[svc]
    return [
        "docker", "run", "--rm", "-i",
        *(["-d"] if detach else []),
        "--name", f"k6-{svc}",
        "--network", "lang-bench-net",
        # Windows では pathlib がバックスラッシュ区切りを返す。docker -v の
        # 区切り文字と衝突して壊れるため、as_posix() でスラッシュに統一する。
        "-v", f"{(ROOT / 'loadgen').as_posix()}:/scripts:ro",
        "-v", f"{out_dir.as_posix()}:/out",
        "-e", f"TARGET_URL=http://{container}:8000",
        "-e", f"LANG={svc}",
        "-e", f"START_AT={start_at_ms}",
        "-e", f"ROUNDS={args.rounds}",
        "-e", f"ITEMS={args.items}",
        "-e", f"VUS={args.vus}",
        "-e", f"WARMUP={args.warmup}",
        "-e", f"STEADY={args.steady}",
        "-e", f"OUT_JSON=/out/k6-{svc}.json",
        K6_IMAGE, "run",
        "--no-usage-report",
        "/scripts/scenario.js",
    ]


def run_isolated(out_dir, args):
    """1言語ずつ。対象以外は落としてCPUを解放してから測る。"""
    results = {}
    for svc in args.langs:
        print(f"\n[isolated] {svc}", flush=True)
        compose("down", "--remove-orphans", capture_output=True)
        compose("up", "-d", svc, check=True)
        wait_healthy([svc])
        time.sleep(args.settle)

        csv_path = out_dir / f"resource-isolated-{svc}.csv"
        collector = Collector(csv_path)
        collector.start()
        started = time.time()
        proc = run(k6_command(svc, out_dir, 0, args, detach=False))
        elapsed = time.time() - started
        collector.stop()

        results[svc] = {"wall_sec": round(elapsed, 2), "k6_exit": proc.returncode}
        print(f"  完了 {elapsed:.1f}s (k6 exit={proc.returncode})", flush=True)
    compose("down", "--remove-orphans", capture_output=True)
    return results


def run_concurrent(out_dir, args):
    """全言語同時。共通の壁時計時刻を渡して一斉スタートさせる。"""
    print(f"\n[concurrent] {len(args.langs)}言語同時実行", flush=True)
    compose("down", "--remove-orphans", capture_output=True)
    compose("up", "-d", *args.langs, check=True)
    wait_healthy(args.langs)
    time.sleep(args.settle)

    # スタートバリア。k6 コンテナの起動自体に数秒かかるので余裕を持たせる。
    start_at_ms = int((time.time() + args.barrier) * 1000)
    print(f"  スタートバリア: {datetime.datetime.fromtimestamp(start_at_ms / 1000).isoformat()}", flush=True)

    csv_path = out_dir / "resource-concurrent.csv"
    collector = Collector(csv_path)
    collector.start()

    for svc in args.langs:
        run(k6_command(svc, out_dir / "concurrent", start_at_ms, args, detach=True), check=True)

    started = time.time()
    exits = {}
    for svc in args.langs:
        proc = run(["docker", "wait", f"k6-{svc}"], capture_output=True, text=True)
        exits[svc] = proc.stdout.strip()
    elapsed = time.time() - started
    collector.stop()

    print(f"  完了 {elapsed:.1f}s exits={exits}", flush=True)
    return {"wall_sec": round(elapsed, 2), "k6_exits": exits}


def main():
    parser = argparse.ArgumentParser(description="Python/Go/Ruby HTTP APIベンチマーク")
    parser.add_argument("--mode", choices=["isolated", "concurrent", "both"], default="both")
    parser.add_argument("--langs", nargs="+", default=list(TARGETS), choices=list(TARGETS))
    parser.add_argument("--vus", type=int, default=50, help="定常負荷の同時接続数")
    parser.add_argument("--rounds", type=int, default=200, help="1リクエストあたりのSHA-256反復数（CPU比重）")
    parser.add_argument("--items", type=int, default=12, help="1注文あたりの明細数（JSON/メモリ比重）")
    parser.add_argument("--warmup", default="15s")
    parser.add_argument("--steady", default="60s")
    parser.add_argument("--settle", type=float, default=3.0, help="healthy後に待つ秒数")
    parser.add_argument("--barrier", type=float, default=15.0, help="同時実行のスタートバリアまでの猶予秒")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    preflight()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / stamp
    (out_dir / "concurrent").mkdir(parents=True, exist_ok=True)

    if not args.skip_build:
        print("[build] イメージをビルド", flush=True)
        compose("build", check=True)

    run(["docker", "pull", K6_IMAGE], check=True)

    manifest = {
        "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "params": vars(args),
        "targets": {k: v[2] for k, v in TARGETS.items()},
        "host": {
            "cpus": os.cpu_count(),
            "cpu_limit_per_container": os.environ.get("BENCH_CPUS", "2.0"),
            "mem_limit_per_container": os.environ.get("BENCH_MEMORY", "512m"),
        },
    }

    if args.mode in ("isolated", "both"):
        manifest["isolated"] = run_isolated(out_dir, args)
    if args.mode in ("concurrent", "both"):
        manifest["concurrent"] = run_concurrent(out_dir, args)

    compose("down", "--remove-orphans", capture_output=True)
    manifest["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[done] 生データ: {out_dir}", flush=True)
    subprocess.run([sys.executable, str(ROOT / "harness" / "report.py"), str(out_dir)], check=False)


if __name__ == "__main__":
    main()
