// SPEC-API-v1 のスコアリング計算（TypeScript実装）。
//
// HTTP層から意図的に切り離してある。8言語が「同じ仕事」をしていることを
// テストで機械的に保証するのがこのファイルの役割で、ここが食い違うと
// 性能比較の数値そのものが無意味になる。変更時は必ず全実装を同時に直し、
// tests/golden.json での検証を通すこと。

import { createHash } from 'node:crypto';

export interface Item {
  sku: string;
  qty: number;
  unit_price: number;
}

export interface ScoreRequest {
  order_id?: string;
  items?: Item[];
  customer?: { tier?: string; history_days?: number };
  rounds?: number;
}

export interface ScoreResponse {
  order_id: string;
  lang: string;
  item_count: number;
  subtotal: number;
  discount: number;
  tax: number;
  total: number;
  signature: string;
  top_skus: string[];
  rounds: number;
}

/** リクエスト内容の不備。HTTP層で400に変換する。 */
export class ValidationError extends Error {}

/**
 * 「0.5は絶対値の大きい側へ」の丸め。
 * JS の Math.round は 0.5 を常に +∞ 側へ倒すため、負値で Go/Ruby とずれる。
 * 小計は非負だが、仕様として符号を明示的に扱っておく。
 */
export function round2(value: number): number {
  return value >= 0 ? Math.floor(value * 100 + 0.5) / 100 : -(Math.floor(-value * 100 + 0.5) / 100);
}

/** SPEC-API-v1の割引表。全実装で同一の値を返さなければならない。 */
export function discountRate(tier: string, historyDays: number): number {
  let rate = tier === 'gold' ? 0.12 : tier === 'silver' ? 0.07 : 0.02;
  if (historyDays >= 365) rate += 0.03;
  return Math.min(rate, 0.2);
}

/**
 * 注文の改ざん検知署名を模したCPU負荷。SHA-256をrounds回チェーンする。
 * rounds を上げるとCPU比重が、明細数を上げるとJSON/メモリ比重が増える。
 */
export function signature(orderId: string, subtotal: number, rounds: number): string {
  let digest = createHash('sha256').update(`${orderId}|${subtotal.toFixed(2)}`).digest();
  for (let i = 0; i < rounds; i++) {
    digest = createHash('sha256').update(digest).digest();
  }
  return digest.toString('hex');
}

export function compute(req: ScoreRequest): ScoreResponse {
  const orderId = req.order_id ?? '';
  const items = req.items ?? [];
  if (orderId === '' || items.length === 0) throw new ValidationError('validation_failed');

  let subtotal = 0;
  for (const it of items) {
    if (it.qty <= 0 || it.unit_price < 0) throw new ValidationError('validation_failed');
    subtotal += it.qty * it.unit_price;
  }
  subtotal = round2(subtotal);

  const customer = req.customer ?? {};
  const rate = discountRate(customer.tier ?? '', customer.history_days ?? 0);
  const discount = round2(subtotal * rate);
  const tax = round2((subtotal - discount) * 0.1);
  const total = round2(subtotal - discount + tax);

  // 上位SKU抽出。金額降順、同額はSKU昇順で全実装の結果を一致させる。
  const ranked = [...items].sort((a, b) => {
    const av = a.qty * a.unit_price;
    const bv = b.qty * b.unit_price;
    return av === bv ? (a.sku < b.sku ? -1 : a.sku > b.sku ? 1 : 0) : bv - av;
  });

  const rounds = !req.rounds || req.rounds <= 0 ? 200 : req.rounds;

  return {
    order_id: orderId,
    lang: 'typescript',
    item_count: items.length,
    subtotal,
    discount,
    tax,
    total,
    signature: signature(orderId, subtotal, rounds),
    top_skus: ranked.slice(0, 5).map((it) => it.sku),
    rounds,
  };
}
