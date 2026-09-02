<?php

declare(strict_types=1);

// 共通仕様のスコアリングAPI（PHP実装・HTTP層）。計算ロジックは src/Score.php。
//
// Composer は使わない。依存は無く、オートローダを挟む必要が無いため。
// 他実装が手動でJSONを解釈しているのに合わせ、ここでもフレームワークの
// 自動バリデーションは使わず、生のリクエストボディを自前で解釈する。

require_once __DIR__ . '/../src/ValidationException.php';
require_once __DIR__ . '/../src/Score.php';

use Bench\Score;
use Bench\ValidationException;

header('Content-Type: application/json');

$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

function send(int $status, array $body): never
{
    http_response_code($status);
    // JSON_PRESERVE_ZERO_FRACTION を付けないと 3755.00 が 3755 になり、
    // 他実装との応答比較（make verify / ブラウザのパリティ検証）が落ちる。
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION);
    exit;
}

if ($path === '/healthz') {
    send(200, ['status' => 'ok', 'lang' => 'php']);
}

if ($path === '/metrics') {
    // PHP はリクエストごとにプロセス状態が消えるため、他実装のような
    // 累積カウンタは持てない。opcache 統計で代用する。
    $status = function_exists('opcache_get_status') ? @opcache_get_status(false) : false;
    send(200, [
        'lang' => 'php',
        'processed' => -1,
        'pid' => getmypid(),
        'opcache_hits' => is_array($status) ? ($status['opcache_statistics']['hits'] ?? 0) : 0,
    ]);
}

if ($path !== '/api/v1/score') {
    send(404, ['error' => 'not_found']);
}

if ($method !== 'POST') {
    send(405, ['error' => 'method_not_allowed']);
}

$raw = file_get_contents('php://input');
$req = json_decode($raw === false ? '' : $raw, true);
if (!is_array($req)) {
    send(400, ['error' => 'invalid_json']);
}

try {
    send(200, Score::compute($req));
} catch (ValidationException | \TypeError) {
    send(400, ['error' => 'validation_failed']);
}
