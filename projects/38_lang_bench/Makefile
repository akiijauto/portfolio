# 使い方は README.html を参照。すべて docker compose 経由で完結する。
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help test golden build up down verify bench quick concurrent console report clean

help: ## このヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

test: ## 3言語のロジック一致テスト（Docker不要。コード変更時は必ず実行）
	python3 -m unittest discover -s tests -p 'test_*.py'
	cd services/go && go test ./...
	ruby services/ruby/test_core.rb

golden: ## 期待値 tests/golden.json を再生成（仕様を変えたときだけ）
	python3 harness/gen_golden.py

build: ## 3言語のイメージをビルド
	$(COMPOSE) build

up: ## 3サービスを起動（手動確認用）
	$(COMPOSE) up -d py go rb

down: ## 全コンテナを停止・削除
	$(COMPOSE) --profile tools down --remove-orphans

verify: ## 3実装が同じ計算結果を返すか検証（bench の前に必ず実行）
	python3 harness/verify_parity.py

bench: ## 本計測（単独 + 同時実行の両方、約8分）
	python3 harness/bench.py --mode both

quick: ## 短縮計測（動作確認用、約2分）
	python3 harness/bench.py --mode both --warmup 5s --steady 20s --vus 20

concurrent: ## 3言語同時実行だけを計測
	python3 harness/bench.py --mode concurrent

console: ## ブラウザ実行テスト用コンソールを起動（http://localhost:18080）
	$(COMPOSE) --profile tools up -d py go rb console

report: ## 最新の計測結果から report.html を再生成
	python3 harness/report.py

clean: ## 計測結果を削除（results/ 配下）※実行前に中身を確認すること
	@echo "results/ を削除します。必要な結果は退避済みか確認してください。" && read -p "続行 [y/N]: " a && [ "$$a" = "y" ] && rm -rf results/2* || echo "中止しました"
