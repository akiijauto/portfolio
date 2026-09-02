<?php

declare(strict_types=1);

namespace Bench;

/**
 * SPEC-API-v1 のスコアリング計算（PHP実装）。
 *
 * HTTP層から意図的に切り離してある。全実装が「同じ仕事」をしていることを
 * テストで機械的に保証するのがこのクラスの役割で、ここが食い違うと
 * 性能比較の数値そのものが無意味になる。変更時は必ず全実装を同時に直し、
 * tests/golden.json での検証を通すこと。
 */
final class Score
{
    /**
     * 「0.5は絶対値の大きい側へ」の丸め。
     * PHP の round() は既定でこの挙動だが、実装の意図を明示するため
     * 他言語と同じ式で書いて仕様として固定する。
     */
    public static function round2(float $value): float
    {
        return $value >= 0
            ? floor($value * 100 + 0.5) / 100
            : -(floor(-$value * 100 + 0.5) / 100);
    }

    /** SPEC-API-v1の割引表。全実装で同一の値を返さなければならない。 */
    public static function discountRate(string $tier, int $historyDays): float
    {
        $rate = match ($tier) {
            'gold' => 0.12,
            'silver' => 0.07,
            default => 0.02,
        };
        if ($historyDays >= 365) {
            $rate += 0.03;
        }

        return min($rate, 0.20);
    }

    /**
     * 注文の改ざん検知署名を模したCPU負荷。SHA-256をrounds回チェーンする。
     * rounds を上げるとCPU比重が、明細数を上げるとJSON/メモリ比重が増える。
     */
    public static function signature(string $orderId, float $subtotal, int $rounds): string
    {
        $digest = hash('sha256', sprintf('%s|%.2f', $orderId, $subtotal), true);
        for ($i = 0; $i < $rounds; $i++) {
            $digest = hash('sha256', $digest, true);
        }

        return bin2hex($digest);
    }

    /**
     * @param  array<string, mixed>  $req
     * @return array<string, mixed>
     *
     * @throws ValidationException
     */
    public static function compute(array $req): array
    {
        $orderId = (string) ($req['order_id'] ?? '');
        $items = $req['items'] ?? [];
        if ($orderId === '' || !is_array($items) || count($items) === 0) {
            throw new ValidationException();
        }

        $subtotal = 0.0;
        foreach ($items as $it) {
            $qty = (int) ($it['qty'] ?? 0);
            $unitPrice = (float) ($it['unit_price'] ?? 0.0);
            if ($qty <= 0 || $unitPrice < 0) {
                throw new ValidationException();
            }
            $subtotal += $qty * $unitPrice;
        }
        $subtotal = self::round2($subtotal);

        $customer = $req['customer'] ?? [];
        $rate = self::discountRate((string) ($customer['tier'] ?? ''), (int) ($customer['history_days'] ?? 0));
        $discount = self::round2($subtotal * $rate);
        $tax = self::round2(($subtotal - $discount) * 0.10);
        $total = self::round2($subtotal - $discount + $tax);

        // 上位SKU抽出。金額降順、同額はSKU昇順で全実装の結果を一致させる。
        $ranked = $items;
        usort($ranked, static function (array $a, array $b): int {
            $av = (int) $a['qty'] * (float) $a['unit_price'];
            $bv = (int) $b['qty'] * (float) $b['unit_price'];

            return $av === $bv ? strcmp((string) $a['sku'], (string) $b['sku']) : ($bv <=> $av);
        });
        $topSkus = array_map(static fn (array $it): string => (string) $it['sku'], array_slice($ranked, 0, 5));

        $rounds = (int) ($req['rounds'] ?? 0);
        if ($rounds <= 0) {
            $rounds = 200;
        }

        return [
            'order_id' => $orderId,
            'lang' => 'php',
            'item_count' => count($items),
            'subtotal' => $subtotal,
            'discount' => $discount,
            'tax' => $tax,
            'total' => $total,
            'signature' => self::signature($orderId, $subtotal, $rounds),
            'top_skus' => $topSkus,
            'rounds' => $rounds,
        ];
    }
}
