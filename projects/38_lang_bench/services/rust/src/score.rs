//! SPEC-API-v1 のスコアリング計算（Rust実装）。
//!
//! HTTP層から意図的に切り離してある。全実装が「同じ仕事」をしていることを
//! テストで機械的に保証するのがこのモジュールの役割で、ここが食い違うと
//! 性能比較の数値そのものが無意味になる。変更時は必ず全実装を同時に直し、
//! tests/golden.json での検証を通すこと。

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, Deserialize)]
pub struct Item {
    pub sku: String,
    #[serde(default)]
    pub qty: i64,
    #[serde(default)]
    pub unit_price: f64,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct Customer {
    #[serde(default)]
    pub tier: String,
    #[serde(default)]
    pub history_days: i64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ScoreRequest {
    #[serde(default)]
    pub order_id: String,
    #[serde(default)]
    pub items: Vec<Item>,
    #[serde(default)]
    pub customer: Customer,
    #[serde(default)]
    pub rounds: i64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScoreResponse {
    pub order_id: String,
    pub lang: &'static str,
    pub item_count: usize,
    pub subtotal: f64,
    pub discount: f64,
    pub tax: f64,
    pub total: f64,
    pub signature: String,
    pub top_skus: Vec<String>,
    pub rounds: i64,
}

/// リクエスト内容の不備。HTTP層で400に変換する。
#[derive(Debug)]
pub struct ValidationError;

/// 「0.5は絶対値の大きい側へ」の丸め。
/// Rust の f64::round は既にこの挙動だが、他言語と同じ式で書いて仕様として固定する。
pub fn round2(value: f64) -> f64 {
    if value >= 0.0 {
        (value * 100.0 + 0.5).floor() / 100.0
    } else {
        -((-value * 100.0 + 0.5).floor() / 100.0)
    }
}

/// SPEC-API-v1の割引表。全実装で同一の値を返さなければならない。
pub fn discount_rate(tier: &str, history_days: i64) -> f64 {
    let mut rate: f64 = match tier {
        "gold" => 0.12,
        "silver" => 0.07,
        _ => 0.02,
    };
    if history_days >= 365 {
        rate += 0.03;
    }
    rate.min(0.20)
}

/// 注文の改ざん検知署名を模したCPU負荷。SHA-256をrounds回チェーンする。
/// rounds を上げるとCPU比重が、明細数を上げるとJSON/メモリ比重が増える。
pub fn signature(order_id: &str, subtotal: f64, rounds: i64) -> String {
    let seed = format!("{}|{:.2}", order_id, subtotal);
    let mut digest = Sha256::digest(seed.as_bytes());
    for _ in 0..rounds {
        digest = Sha256::digest(digest);
    }
    hex::encode(digest)
}

pub fn compute(req: &ScoreRequest) -> Result<ScoreResponse, ValidationError> {
    if req.order_id.is_empty() || req.items.is_empty() {
        return Err(ValidationError);
    }

    let mut subtotal = 0.0_f64;
    for it in &req.items {
        if it.qty <= 0 || it.unit_price < 0.0 {
            return Err(ValidationError);
        }
        subtotal += it.qty as f64 * it.unit_price;
    }
    subtotal = round2(subtotal);

    let rate = discount_rate(&req.customer.tier, req.customer.history_days);
    let discount = round2(subtotal * rate);
    let tax = round2((subtotal - discount) * 0.10);
    let total = round2(subtotal - discount + tax);

    // 上位SKU抽出。金額降順、同額はSKU昇順で全実装の結果を一致させる。
    let mut ranked: Vec<&Item> = req.items.iter().collect();
    ranked.sort_by(|a, b| {
        let av = a.qty as f64 * a.unit_price;
        let bv = b.qty as f64 * b.unit_price;
        bv.partial_cmp(&av)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.sku.cmp(&b.sku))
    });
    let top_skus: Vec<String> = ranked.iter().take(5).map(|it| it.sku.clone()).collect();

    let rounds = if req.rounds <= 0 { 200 } else { req.rounds };

    Ok(ScoreResponse {
        order_id: req.order_id.clone(),
        lang: "rust",
        item_count: req.items.len(),
        subtotal,
        discount,
        tax,
        total,
        signature: signature(&req.order_id, subtotal, rounds),
        top_skus,
        rounds,
    })
}
