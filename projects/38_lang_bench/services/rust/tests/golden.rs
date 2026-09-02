//! Python実装（リファレンス）と同じ結果を返すことを検証する。
//! 性能比較は全実装が同じ仕事をしていることが前提なので、これが落ちたら計測しない。

use serde_json::Value;

// score.rs をテストから使うためにソースを直接取り込む。
// バイナリクレート（main.rs）のモジュールは統合テストから参照できないため。
#[path = "../src/score.rs"]
mod score;

fn load_golden() -> Value {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../tests/golden.json");
    let raw = std::fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("golden.json が読めない（harness/gen_golden.py で生成する）: {path}: {e}"));
    serde_json::from_str(&raw).expect("golden.json のパースに失敗")
}

#[test]
fn golden_parity() {
    let golden = load_golden();
    let cases = golden["cases"].as_array().expect("cases が配列でない");
    assert!(!cases.is_empty(), "golden.json にケースが無い");

    for tc in cases {
        let name = tc["name"].as_str().unwrap_or("?");
        let req: score::ScoreRequest =
            serde_json::from_value(tc["request"].clone()).expect("request のパースに失敗");
        let got = score::compute(&req).expect("compute が失敗");

        // lang フィールドは実装ごとに異なって当然なので比較から外す
        let mut got_value = serde_json::to_value(&got).unwrap();
        got_value.as_object_mut().unwrap().remove("lang");

        assert_eq!(tc["expect"], got_value, "Python実装と不一致: {name}");
    }
}

#[test]
fn rounding_is_half_away_from_zero() {
    assert_eq!(score::round2(2.675), 2.68);
    assert_eq!(score::round2(0.125), 0.13);
    assert_eq!(score::round2(-0.125), -0.13);
}

#[test]
fn discount_table() {
    assert_eq!(score::discount_rate("gold", 0), 0.12);
    assert_eq!(score::discount_rate("silver", 0), 0.07);
    assert_eq!(score::discount_rate("platinum", 0), 0.02);
    assert!((score::discount_rate("gold", 365) - 0.15).abs() < 1e-9);
    assert!(score::discount_rate("gold", 100_000) <= 0.20);
}

#[test]
fn rejects_bad_input() {
    let cases = [
        ("order_id無し", serde_json::json!({"items": [{"sku": "A", "qty": 1, "unit_price": 1}]})),
        ("明細が空", serde_json::json!({"order_id": "X", "items": []})),
        ("数量ゼロ", serde_json::json!({"order_id": "X", "items": [{"sku": "A", "qty": 0, "unit_price": 1}]})),
        ("負の単価", serde_json::json!({"order_id": "X", "items": [{"sku": "A", "qty": 1, "unit_price": -1}]})),
    ];
    for (name, body) in cases {
        let req: score::ScoreRequest = serde_json::from_value(body).expect("request のパースに失敗");
        assert!(score::compute(&req).is_err(), "エラーになるべきだが成功した: {name}");
    }
}
