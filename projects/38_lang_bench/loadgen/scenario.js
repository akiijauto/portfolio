// k6 負荷シナリオ。3言語に対して完全に同一の条件で流す。
//
// TARGET_URL : 攻撃対象のURL
// LANG       : 結果ラベル（py / go / rb）
// START_AT   : 共通開始時刻（epoch ミリ秒）。同時実行モードで3コンテナの
//              スタートを揃えるためのバリア。単独実行時は 0 を渡す。
import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const TARGET = __ENV.TARGET_URL;
const LANG = __ENV.LANG || 'unknown';
const START_AT = parseInt(__ENV.START_AT || '0', 10);
const ROUNDS = parseInt(__ENV.ROUNDS || '200', 10);
const ITEMS = parseInt(__ENV.ITEMS || '12', 10);
const VUS = parseInt(__ENV.VUS || '50', 10);
const WARMUP = __ENV.WARMUP || '15s';
const STEADY = __ENV.STEADY || '60s';

export const bizLatency = new Trend('biz_latency', true);
export const bizErrors = new Counter('biz_errors');

export const options = {
  discardResponseBodies: false,
  scenarios: {
    // 1) ウォームアップ: JIT/YJIT・コネクションプール・ページキャッシュを温める。
    //    この区間の数値は集計から除外する（thresholds も掛けない）。
    warmup: {
      executor: 'constant-vus',
      vus: Math.max(1, Math.floor(VUS / 5)),
      duration: WARMUP,
      tags: { phase: 'warmup' },
      gracefulStop: '5s',
    },
    // 2) 定常負荷: 本計測。VU固定で「その言語が捌ける限界スループット」を見る。
    steady: {
      executor: 'constant-vus',
      vus: VUS,
      duration: STEADY,
      startTime: WARMUP,
      tags: { phase: 'steady' },
      gracefulStop: '10s',
    },
    // 3) スパイク: 商用で起きる突発トラフィック。飽和時の劣化の仕方を見る。
    spike: {
      executor: 'ramping-vus',
      startVUs: VUS,
      stages: [
        { duration: '5s', target: VUS * 4 },
        { duration: '15s', target: VUS * 4 },
        { duration: '5s', target: VUS },
      ],
      startTime: `${durationToSec(WARMUP) + durationToSec(STEADY) + 5}s`,
      tags: { phase: 'spike' },
      gracefulStop: '10s',
    },
  },
  // thresholds は受け入れ基準であると同時に「サブメトリクスの宣言」でもある。
  // ここに書いたタグ付きメトリクスだけが handleSummary の data.metrics に現れるため、
  // フェーズ別に集計したい指標は必ず1行足すこと（消すと report.html が空になる）。
  thresholds: {
    'http_req_failed{phase:steady}': ['rate<0.01'],
    'http_req_duration{phase:steady}': ['p(95)<1000'],
    'http_reqs{phase:steady}': ['count>0'],
    'http_req_failed{phase:spike}': ['rate<0.05'],
    'http_req_duration{phase:spike}': ['p(95)<5000'],
    'http_reqs{phase:spike}': ['count>0'],
  },
};

function durationToSec(s) {
  const m = /^(\d+)(ms|s|m)$/.exec(s);
  if (!m) return 0;
  const n = parseInt(m[1], 10);
  return m[2] === 'm' ? n * 60 : m[2] === 'ms' ? Math.ceil(n / 1000) : n;
}

// 決定論的な擬似乱数。3言語に同じ入力列を与えるためシード固定のLCGを使う。
function lcg(seed) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

// 事前生成した注文ペイロード群。VUごとに使い回してリクエスト生成コストを抑え、
// 測定対象がサーバ側処理になるようにする。
const PAYLOADS = (() => {
  const rnd = lcg(20260902);
  const tiers = ['gold', 'silver', 'bronze'];
  const list = [];
  for (let i = 0; i < 64; i++) {
    const items = [];
    for (let j = 0; j < ITEMS; j++) {
      items.push({
        sku: `SKU-${((i * ITEMS + j) % 9999).toString().padStart(4, '0')}`,
        qty: 1 + Math.floor(rnd() * 9),
        unit_price: Math.round(rnd() * 500000) / 100,
      });
    }
    list.push(
      JSON.stringify({
        order_id: `ORD-${(1000000 + i).toString()}`,
        items,
        customer: {
          tier: tiers[Math.floor(rnd() * tiers.length)],
          history_days: Math.floor(rnd() * 900),
        },
        rounds: ROUNDS,
      }),
    );
  }
  return list;
})();

export function setup() {
  if (START_AT > 0) {
    // 同時実行モードのスタートバリア。3コンテナが同じ壁時計時刻で走り出す。
    const waitMs = START_AT - Date.now();
    if (waitMs > 0) {
      const until = Date.now() + waitMs;
      while (Date.now() < until) {
        // k6 の sleep は秒単位なのでビジーウェイトで ms 精度に合わせる
      }
    }
  }
  return { startedAt: Date.now() };
}

export default function () {
  const body = PAYLOADS[(__VU * 7 + __ITER) % PAYLOADS.length];
  const res = http.post(`${TARGET}/api/v1/score`, body, {
    headers: { 'Content-Type': 'application/json' },
    tags: { lang: LANG },
  });
  const ok = check(res, {
    'status 200': (r) => r.status === 200,
    'has signature': (r) => r.body && r.body.indexOf('signature') !== -1,
  });
  if (!ok) bizErrors.add(1);
  bizLatency.add(res.timings.duration);
}

// 結果は report.html 生成用のJSONとして書き出す。テキスト要約は標準出力に残す。
export function handleSummary(data) {
  const out = __ENV.OUT_JSON || '/out/summary.json';
  return {
    [out]: JSON.stringify({ lang: LANG, vus: VUS, rounds: ROUNDS, items: ITEMS, metrics: data.metrics }, null, 2),
    stdout: `\n=== ${LANG} ===\n` +
      `steady p50=${fmt(data, 'http_req_duration{phase:steady}', 'p(50)')}ms ` +
      `p95=${fmt(data, 'http_req_duration{phase:steady}', 'p(95)')}ms ` +
      `rps=${fmt(data, 'http_reqs{phase:steady}', 'rate')}\n`,
  };
}

function fmt(data, metric, field) {
  const m = data.metrics[metric];
  if (!m || !m.values || m.values[field] === undefined) return 'n/a';
  return m.values[field].toFixed(1);
}
