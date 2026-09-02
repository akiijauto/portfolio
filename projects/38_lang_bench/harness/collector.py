"""ベンチ実行中のコンテナ資源使用量を1秒間隔でCSVに落とすサンプラ。

`docker stats` を定期実行するだけの薄い実装にしてある。Prometheus/cAdvisor を
立てるほうが精緻だが、監視スタック自身がホストのCPUを食って比較を歪めるため、
このプロジェクトでは意図的に最小構成を選んでいる（振り返り.html 参照）。
"""

import csv
import json
import subprocess
import sys
import threading
import time

CONTAINERS = ["bench-py", "bench-go", "bench-rb"]
FIELDS = ["ts", "elapsed_sec", "container", "cpu_pct", "mem_used_mb", "mem_limit_mb", "net_rx_mb", "net_tx_mb"]


def _to_mb(text: str) -> float:
    """docker stats の "123.4MiB" 形式をMB(10進)に直す。"""
    text = text.strip()
    units = {"B": 1e-6, "KB": 1e-3, "KIB": 1024 / 1e6, "MB": 1.0, "MIB": 1048576 / 1e6,
             "GB": 1e3, "GIB": 1073741824 / 1e6, "TB": 1e6, "TIB": 1099511627776 / 1e6}
    for suffix, factor in sorted(units.items(), key=lambda kv: -len(kv[0])):
        if text.upper().endswith(suffix):
            try:
                return float(text[: -len(suffix)]) * factor
            except ValueError:
                return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _sample():
    """1回分のスナップショットを取る。対象が落ちていても例外にせず空を返す。"""
    proc = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}", *CONTAINERS],
        capture_output=True, text=True,
    )
    rows = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        mem_used, _, mem_limit = raw.get("MemUsage", "0B / 0B").partition("/")
        net_rx, _, net_tx = raw.get("NetIO", "0B / 0B").partition("/")
        rows.append({
            "container": raw.get("Name", "?"),
            "cpu_pct": float(raw.get("CPUPerc", "0%").rstrip("%") or 0),
            "mem_used_mb": _to_mb(mem_used),
            "mem_limit_mb": _to_mb(mem_limit),
            "net_rx_mb": _to_mb(net_rx),
            "net_tx_mb": _to_mb(net_tx),
        })
    return rows


class Collector(threading.Thread):
    """with 文ではなく start()/stop() で使う。bench.py が負荷実行を挟んで囲む。"""

    def __init__(self, out_path, interval=1.0):
        super().__init__(daemon=True)
        self.out_path = out_path
        self.interval = interval
        self._stop = threading.Event()

    def run(self):
        started = time.time()
        with open(self.out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            while not self._stop.is_set():
                now = time.time()
                for row in _sample():
                    writer.writerow({"ts": round(now, 3), "elapsed_sec": round(now - started, 1), **row})
                fh.flush()
                # docker stats 自体に1秒近くかかるので、経過分を差し引いて刻みを保つ
                self._stop.wait(max(0.0, self.interval - (time.time() - now)))

    def stop(self):
        self._stop.set()
        self.join(timeout=10)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "resource.csv"
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    collector = Collector(out)
    collector.start()
    time.sleep(seconds)
    collector.stop()
    print(f"wrote {out}")
