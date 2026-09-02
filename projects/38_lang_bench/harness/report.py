"""results/<timestamp>/ の生データから比較レポート report.html を生成する。

入力は bench.py が残した3種類。
  manifest.json              : 実行パラメータと壁時計時間
  k6-<lang>.json             : レイテンシ/スループット（isolated）
  concurrent/k6-<lang>.json  : 同上（3言語同時実行）
  resource-*.csv             : コンテナ資源使用量の時系列

外部CDNに依存しないよう、グラフはインラインSVGとCSSバーだけで描く。
計測結果はオフラインのPCで開くことが多く、読めないレポートは無価値なため。
"""

import csv
import html
import json
import pathlib
import statistics
import sys

LANG_LABEL = {
    "py": "Python", "go": "Go", "rb": "Ruby", "ts": "TypeScript",
    "java": "Java", "cs": "C#", "php": "PHP", "rs": "Rust",
}
LANG_COLOR = {
    "py": "#3572A5", "go": "#00ADD8", "rb": "#CC342D", "ts": "#3178C6",
    "java": "#E76F00", "cs": "#68217A", "php": "#777BB4", "rs": "#B7410E",
}
CONTAINER_LANG = {f"bench-{k}": k for k in LANG_LABEL}


def load_k6(path):
    """k6 サマリから必要な指標だけ取り出す。欠損は None にして表で 'n/a' と出す。"""
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    metrics = data.get("metrics", {})

    def value(name, field):
        entry = metrics.get(name) or {}
        values = entry.get("values") or entry
        got = values.get(field)
        return round(got, 2) if isinstance(got, (int, float)) else None

    return {
        "lang": data.get("lang"),
        "rps": value("http_reqs{phase:steady}", "rate"),
        "count": value("http_reqs{phase:steady}", "count"),
        "p50": value("http_req_duration{phase:steady}", "p(50)") or value("http_req_duration{phase:steady}", "med"),
        "p90": value("http_req_duration{phase:steady}", "p(90)"),
        "p95": value("http_req_duration{phase:steady}", "p(95)"),
        "max": value("http_req_duration{phase:steady}", "max"),
        "fail_rate": value("http_req_failed{phase:steady}", "rate"),
        "spike_p95": value("http_req_duration{phase:spike}", "p(95)"),
        "spike_fail": value("http_req_failed{phase:spike}", "rate"),
    }


def load_resource(path):
    """資源CSVをコンテナ別に集計する。平均CPUとピークメモリが比較の主眼。"""
    if not path.exists():
        return {}
    buckets = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            lang = CONTAINER_LANG.get(row["container"])
            if not lang:
                continue
            buckets.setdefault(lang, {"cpu": [], "mem": []})
            buckets[lang]["cpu"].append(float(row["cpu_pct"]))
            buckets[lang]["mem"].append(float(row["mem_used_mb"]))
    summary = {}
    for lang, series in buckets.items():
        # 起動直後のアイドル区間が平均を押し下げるので、CPUは上位50%だけを平均する
        cpu_sorted = sorted(series["cpu"], reverse=True)
        active = cpu_sorted[: max(1, len(cpu_sorted) // 2)]
        summary[lang] = {
            "cpu_avg": round(statistics.fmean(active), 1),
            "cpu_max": round(max(series["cpu"]), 1),
            "mem_avg": round(statistics.fmean(series["mem"]), 1),
            "mem_max": round(max(series["mem"]), 1),
            "samples": len(series["cpu"]),
        }
    return summary


def fmt(value, unit=""):
    return "n/a" if value is None else f"{value:,.2f}{unit}".replace(".00", "")


def bar(value, peak, color):
    """CSSバー。値が大きいほど良い/悪いは列見出し側で説明する。"""
    if value is None or not peak:
        return '<span class="na">n/a</span>'
    width = max(1.0, min(100.0, value / peak * 100))
    return (f'<span class="bar"><span class="fill" style="width:{width:.1f}%;background:{color}"></span></span>'
            f'<span class="v">{value:,.1f}</span>')


def table(rows, resources, title, note):
    """1シナリオ分の比較表。langごとに1行。"""
    present = [r for r in rows if r]
    if not present:
        return f"<h3>{html.escape(title)}</h3><p class='na'>データなし</p>"
    peak_rps = max((r["rps"] or 0) for r in present) or 1
    peak_p95 = max((r["p95"] or 0) for r in present) or 1

    body = []
    for r in present:
        lang = r["lang"]
        color = LANG_COLOR.get(lang, "#888")
        res = resources.get(lang, {})
        body.append(f"""    <tr>
      <th scope="row"><span class="dot" style="background:{color}"></span>{html.escape(LANG_LABEL.get(lang, lang))}</th>
      <td class="num">{bar(r['rps'], peak_rps, color)}</td>
      <td class="num">{fmt(r['p50'])}</td>
      <td class="num">{fmt(r['p95'])}</td>
      <td class="num">{bar(r['p95'], peak_p95, color)}</td>
      <td class="num">{fmt(r['max'])}</td>
      <td class="num">{fmt((r['fail_rate'] or 0) * 100, '%')}</td>
      <td class="num">{fmt(r['spike_p95'])}</td>
      <td class="num">{fmt(res.get('cpu_avg'), '%')}</td>
      <td class="num">{fmt(res.get('mem_max'), 'MB')}</td>
    </tr>""")

    return f"""<h3>{html.escape(title)}</h3>
<p class="note">{html.escape(note)}</p>
<div class="scroll"><table>
  <thead><tr>
    <th scope="col">言語</th><th scope="col">スループット RPS<br><small>高いほど良い</small></th>
    <th scope="col">p50 ms</th><th scope="col">p95 ms</th>
    <th scope="col">p95 相対<br><small>短いほど良い</small></th>
    <th scope="col">最大 ms</th><th scope="col">失敗率</th>
    <th scope="col">スパイク p95 ms</th><th scope="col">CPU 平均</th><th scope="col">メモリ最大</th>
  </tr></thead>
  <tbody>
{chr(10).join(body)}
  </tbody>
</table></div>"""


def build(out_dir: pathlib.Path) -> pathlib.Path:
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    langs = manifest["params"]["langs"]

    iso_rows, iso_res = [], {}
    for lang in langs:
        iso_rows.append(load_k6(out_dir / f"k6-{lang}.json"))
        iso_res.update(load_resource(out_dir / f"resource-isolated-{lang}.csv"))

    con_rows = [load_k6(out_dir / "concurrent" / f"k6-{lang}.json") for lang in langs]
    con_res = load_resource(out_dir / "resource-concurrent.csv")

    params = manifest["params"]
    conditions = (
        f"VU={params['vus']} / SHA-256反復={params['rounds']}回 / 明細={params['items']}件 / "
        f"ウォームアップ={params['warmup']} / 定常={params['steady']} / "
        f"コンテナ上限 CPU={manifest['host']['cpu_limit_per_container']} "
        f"メモリ={manifest['host']['mem_limit_per_container']}"
    )

    return_path = out_dir / "report.html"
    return_path.write_text(f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>バックエンド言語 性能比較レポート {html.escape(manifest['started_at'])}</title>
<style>
  :root {{ color-scheme: light dark; --fg:#1a1a1a; --bg:#fff; --line:#d8d8d8; --muted:#666; --panel:#f7f7f8; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fg:#e8e8e8; --bg:#16181c; --line:#333; --muted:#9aa0a6; --panel:#1e2126; }}
  }}
  body {{ margin:0; padding:2rem 1.25rem; background:var(--bg); color:var(--fg);
         font-family:system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif; line-height:1.7; }}
  main {{ max-width:1080px; margin:0 auto; }}
  h1 {{ font-size:1.6rem; margin:0 0 .25rem; }}
  h2 {{ font-size:1.2rem; margin:2.5rem 0 .5rem; padding-bottom:.3rem; border-bottom:2px solid var(--line); }}
  h3 {{ font-size:1rem; margin:1.75rem 0 .25rem; }}
  .meta {{ color:var(--muted); font-size:.9rem; }}
  .cond {{ background:var(--panel); border:1px solid var(--line); border-radius:8px;
           padding:.75rem 1rem; font-size:.88rem; margin:1rem 0; }}
  .note {{ color:var(--muted); font-size:.85rem; margin:.1rem 0 .6rem; }}
  .scroll {{ overflow-x:auto; }}
  table {{ border-collapse:collapse; width:100%; font-size:.88rem; }}
  th, td {{ border-bottom:1px solid var(--line); padding:.5rem .6rem; text-align:left; white-space:nowrap; }}
  thead th {{ font-weight:600; vertical-align:bottom; }}
  thead small {{ color:var(--muted); font-weight:400; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .dot {{ display:inline-block; width:.65rem; height:.65rem; border-radius:50%; margin-right:.4rem; }}
  .bar {{ display:inline-block; width:90px; height:.55rem; background:var(--line);
          border-radius:3px; overflow:hidden; vertical-align:middle; margin-right:.4rem; }}
  .bar .fill {{ display:block; height:100%; }}
  .v {{ font-variant-numeric:tabular-nums; }}
  .na {{ color:var(--muted); }}
  ul {{ padding-left:1.2rem; }}
</style>
</head>
<body>
<main>
  <h1>バックエンド言語 性能比較レポート</h1>
  <p class="meta">計測開始 {html.escape(manifest['started_at'])} ／ 終了 {html.escape(manifest.get('finished_at', '-'))}
     ／ ホスト論理CPU {manifest['host']['cpus']}</p>

  <div class="cond"><strong>計測条件</strong><br>{html.escape(conditions)}</div>

  <h2>1. 単独実行（言語間の素の比較）</h2>
  {table(iso_rows, iso_res, "isolated — 1言語ずつ単独で起動", "他コンテナがCPUを奪わない条件。言語選定の主データはこちら。")}

  <h2>2. 同時実行（リソース競合下の比較）</h2>
  {table(con_rows, con_res, "concurrent — 全言語を共通タイマーで一斉起動", "全コンテナがホストCPUを奪い合う。単独実行より必ず悪化する。悪化の「幅」が本番同居時のリスク。")}

  <h2>3. 読み方</h2>
  <ul>
    <li><strong>RPS</strong> は同じVU数で捌けた秒間リクエスト数。処理1件あたりの所要時間の逆数に近い。</li>
    <li><strong>p95 / 最大</strong> が平均より重要。商用SLAは平均ではなく裾で切られる。</li>
    <li><strong>スパイク p95</strong> が定常p95から跳ね上がる言語は、突発トラフィックに弱い。</li>
    <li><strong>CPU平均</strong> は上位50%サンプルの平均（アイドル区間を除外）。同じRPSならCPUが低い方が単価が安い。</li>
    <li>単独と同時の差が小さい言語ほど、1台に複数サービスを同居させる構成に向く。</li>
  </ul>

  <h2>4. 生データ</h2>
  <ul>
    <li><code>manifest.json</code> — 実行パラメータ</li>
    <li><code>k6-*.json</code> / <code>concurrent/k6-*.json</code> — レイテンシとスループットの全指標</li>
    <li><code>resource-*.csv</code> — 1秒刻みのCPU・メモリ・ネットワーク時系列</li>
  </ul>
</main>
</body>
</html>
""", encoding="utf-8")
    return return_path


if __name__ == "__main__":
    target = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if target is None:
        results = pathlib.Path(__file__).resolve().parent.parent / "results"
        candidates = sorted(p for p in results.glob("*/manifest.json"))
        if not candidates:
            sys.exit("results/ に manifest.json が無い。先に bench.py を実行すること。")
        target = candidates[-1].parent
    print(f"[report] {build(target)}")
