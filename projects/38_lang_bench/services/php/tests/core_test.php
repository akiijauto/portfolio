<?php

declare(strict_types=1);

// Python実装（リファレンス）と同じ結果を返すことを検証する。
// 性能比較は全実装が同じ仕事をしていることが前提なので、これが落ちたら計測しない。
//
// PHPUnit ではなく素のPHPで書いてある。この検証に必要なのは
// 「golden.json と一致するか」だけで、そのために composer の依存解決を
// CI とローカルの両方に持ち込む価値が無いため。

require_once __DIR__ . '/../src/ValidationException.php';
require_once __DIR__ . '/../src/Score.php';

use Bench\Score;
use Bench\ValidationException;

$failures = 0;
$assertions = 0;

function check(bool $ok, string $label): void
{
    global $failures, $assertions;
    $assertions++;
    if (!$ok) {
        $failures++;
        fwrite(STDERR, "  [NG] {$label}\n");
    }
}

// --- golden parity ---
$goldenPath = __DIR__ . '/../../../tests/golden.json';
if (!file_exists($goldenPath)) {
    fwrite(STDERR, "golden.json が無い（harness/gen_golden.py で生成する）: {$goldenPath}\n");
    exit(1);
}
$golden = json_decode((string) file_get_contents($goldenPath), true);
check(count($golden['cases']) > 0, 'golden.json にケースがある');

foreach ($golden['cases'] as $tc) {
    $got = Score::compute($tc['request']);
    // lang フィールドは実装ごとに異なって当然なので比較から外す
    unset($got['lang']);
    $same = $got == $tc['expect'];
    check($same, "golden parity: {$tc['name']}");
    if (!$same) {
        fwrite(STDERR, '   got=' . json_encode($got, JSON_UNESCAPED_UNICODE) . "\n");
        fwrite(STDERR, '  want=' . json_encode($tc['expect'], JSON_UNESCAPED_UNICODE) . "\n");
    }
}

// --- 丸め ---
check(Score::round2(2.675) === 2.68, 'round2(2.675) == 2.68');
check(Score::round2(0.125) === 0.13, 'round2(0.125) == 0.13');
check(Score::round2(-0.125) === -0.13, 'round2(-0.125) == -0.13');

// --- 割引表 ---
check(Score::discountRate('gold', 0) === 0.12, 'gold');
check(Score::discountRate('silver', 0) === 0.07, 'silver');
check(Score::discountRate('platinum', 0) === 0.02, '未知tierは既定割引');
check(abs(Score::discountRate('gold', 365) - 0.15) < 1e-9, '長期顧客ボーナス');
check(Score::discountRate('gold', 100000) <= 0.20, '割引上限');

// --- バリデーション ---
$invalid = [
    'order_id無し' => ['items' => [['sku' => 'A', 'qty' => 1, 'unit_price' => 1]]],
    '明細が空' => ['order_id' => 'X', 'items' => []],
    '数量ゼロ' => ['order_id' => 'X', 'items' => [['sku' => 'A', 'qty' => 0, 'unit_price' => 1]]],
    '負の単価' => ['order_id' => 'X', 'items' => [['sku' => 'A', 'qty' => 1, 'unit_price' => -1]]],
];
foreach ($invalid as $name => $req) {
    $threw = false;
    try {
        Score::compute($req);
    } catch (ValidationException) {
        $threw = true;
    }
    check($threw, "バリデーション: {$name}");
}

echo "PHP: {$assertions} assertions, {$failures} failures\n";
exit($failures === 0 ? 0 : 1);
