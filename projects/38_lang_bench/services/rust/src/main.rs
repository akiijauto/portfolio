//! 共通仕様のスコアリングAPI（Rust実装・HTTP層）。計算ロジックは score.rs。
//!
//! 他実装が手動でJSONを解釈しているため、公平性の観点からここでも
//! extractor による自動バリデーションには頼らず、Bytes を受けて自前で解釈する。

mod score;

use axum::{
    body::Bytes,
    http::StatusCode,
    response::{IntoResponse, Json},
    routing::{get, post},
    Router,
};
use serde_json::json;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

struct AppState {
    processed: AtomicU64,
}

async fn handle_score(
    axum::extract::State(state): axum::extract::State<Arc<AppState>>,
    body: Bytes,
) -> impl IntoResponse {
    let req: score::ScoreRequest = match serde_json::from_slice(&body) {
        Ok(value) => value,
        Err(_) => return (StatusCode::BAD_REQUEST, Json(json!({"error": "invalid_json"}))).into_response(),
    };

    match score::compute(&req) {
        Ok(res) => {
            state.processed.fetch_add(1, Ordering::Relaxed);
            Json(res).into_response()
        }
        Err(_) => (
            StatusCode::BAD_REQUEST,
            Json(json!({"error": "validation_failed"})),
        )
            .into_response(),
    }
}

fn main() {
    // ワーカースレッド数を他言語のワーカー数と揃える。既定の
    // available_parallelism 任せにすると、cgroup 制限の読み取り可否で
    // 並列度が変わり、条件を揃えたつもりが揃っていない事故になる。
    let workers: usize = std::env::var("WORKERS")
        .ok()
        .and_then(|v| v.parse().ok())
        .filter(|n| *n > 0)
        .unwrap_or(2);

    tokio::runtime::Builder::new_multi_thread()
        .worker_threads(workers)
        .enable_all()
        .build()
        .expect("tokio ランタイムを構築できない")
        .block_on(serve(workers));
}

async fn serve(workers: usize) {
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(8000);

    let state = Arc::new(AppState {
        processed: AtomicU64::new(0),
    });

    let metrics_state = state.clone();
    let app = Router::new()
        .route("/api/v1/score", post(handle_score))
        .route("/healthz", get(|| async { Json(json!({"status": "ok", "lang": "rust"})) }))
        .route(
            "/metrics",
            get(move || {
                let state = metrics_state.clone();
                async move {
                    Json(json!({
                        "lang": "rust",
                        "processed": state.processed.load(Ordering::Relaxed),
                        "worker_threads": workers,
                    }))
                }
            }),
        )
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port))
        .await
        .expect("ポートにバインドできない");
    eprintln!("rust service listening on :{port} (worker_threads={workers})");
    axum::serve(listener, app).await.expect("サーバが停止した");
}
