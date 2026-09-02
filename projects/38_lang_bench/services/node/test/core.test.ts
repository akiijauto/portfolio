// Python実装（リファレンス）と同じ結果を返すことを検証する。
// 性能比較は全実装が同じ仕事をしていることが前提なので、これが落ちたら計測しない。

import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { describe, it } from 'node:test';
import { ValidationError, compute, discountRate, round2 } from '../src/core.js';

// tsc の出力先（dist/test/）から実行されるため、ソース位置からの相対パスが使えない。
// プロジェクト直下の tests/golden.json を上に辿って探す。
function findGolden(): string {
  let dir = dirname(fileURLToPath(import.meta.url));
  for (let i = 0; i < 8; i++) {
    const candidate = resolve(dir, 'tests', 'golden.json');
    if (existsSync(candidate)) return candidate;
    dir = dirname(dir);
  }
  throw new Error('tests/golden.json が見つからない（harness/gen_golden.py で生成する）');
}
const goldenPath = findGolden();

describe('golden parity', () => {
  const golden = JSON.parse(readFileSync(goldenPath, 'utf-8'));

  it('全ケースで Python 実装と一致する', () => {
    assert.ok(golden.cases.length > 0, 'golden.json にケースが無い');
    for (const tc of golden.cases) {
      // lang フィールドは実装ごとに異なって当然なので比較から外す
      const { lang: _lang, ...got } = compute(tc.request);
      assert.deepEqual(got, tc.expect, `不一致: ${tc.name}`);
    }
  });
});

describe('rounding', () => {
  it('0.5は絶対値の大きい側へ倒す', () => {
    // JS の Math.round は 0.5 を常に +∞ 側へ倒すため、負値で Go/Ruby とずれる
    assert.equal(round2(2.675), 2.68);
    assert.equal(round2(0.125), 0.13);
    assert.equal(round2(-0.125), -0.13);
  });
});

describe('discount rate', () => {
  it('割引表どおりの値を返す', () => {
    assert.equal(discountRate('gold', 0), 0.12);
    assert.equal(discountRate('silver', 0), 0.07);
    assert.equal(discountRate('platinum', 0), 0.02);
  });
  it('長期顧客ボーナスと上限が効く', () => {
    assert.ok(Math.abs(discountRate('gold', 365) - 0.15) < 1e-9);
    assert.ok(discountRate('gold', 100000) <= 0.2);
  });
});

describe('validation', () => {
  it('不正入力を弾く', () => {
    const invalid: Record<string, unknown> = {
      'order_id無し': { items: [{ sku: 'A', qty: 1, unit_price: 1 }] },
      明細が空: { order_id: 'X', items: [] },
      数量ゼロ: { order_id: 'X', items: [{ sku: 'A', qty: 0, unit_price: 1 }] },
      負の単価: { order_id: 'X', items: [{ sku: 'A', qty: 1, unit_price: -1 }] },
    };
    for (const [name, req] of Object.entries(invalid)) {
      assert.throws(() => compute(req as never), ValidationError, name);
    }
  });
});
