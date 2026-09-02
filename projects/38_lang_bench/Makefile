# 使い方は README.html を参照。すべて docker compose 経由で完結する。
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help test test-quick golden build up down verify bench quick concurrent console report clean

help: ## このヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

test: ## 全言語の検査（ロジック一致 + HTTP層のビルド。Docker不要。コード変更時は必ず実行）
	python3 -m unittest discover -s tests -p 'test_*.py'
	cd services/go && go test ./...
	ruby services/ruby/test_core.rb
	cd services/node && npm ci --no-audit --no-fund && npm test
	cd services/java && mvn -B -q test
	php services/php/tests/core_test.php
	cd services/rust && cargo test --quiet
	cd services/csharp/tests && dotnet run --configuration Release
	python3 -m py_compile services/python/app.py services/python/core.py
	ruby -c services/ruby/app.rb
	php -l services/php/public/index.php
	cd services/csharp && dotnet build lang-bench-csharp.csproj -c Release --nologo

test-quick: ## ホストに入っている言語だけ検査する（ロジック一致 + HTTP層）
	@python3 harness/run_tests.py

golden: ## 期待値 tests/golden.json を再生成（仕様を変えたときだけ）
	python3 harness/gen_golden.py

build: ## 全言語のイメージをビルド
	$(COMPOSE) build

up: ## 全サービスを起動（手動確認用）
	$(COMPOSE) up -d py go rb ts java cs php rs

down: ## 全コンテナを停止・削除
	$(COMPOSE) --profile tools down --remove-orphans

verify: ## 全実装が同じ計算結果を返すか検証（bench の前に必ず実行）
	python3 harness/verify_parity.py

bench: ## 本計測（単独 + 同時実行の両方、8言語で約20分）
	python3 harness/bench.py --mode both

quick: ## 短縮計測（動作確認用、約5分）
	python3 harness/bench.py --mode both --warmup 5s --steady 20s --vus 20

concurrent: ## 全言語同時実行だけを計測
	python3 harness/bench.py --mode concurrent

console: ## ブラウザ実行テスト用コンソールを起動（http://localhost:18080）
	$(COMPOSE) --profile tools up -d py go rb ts java cs php rs console

report: ## 最新の計測結果から report.html を再生成
	python3 harness/report.py

clean: ## 計測結果を削除（results/ 配下）※実行前に中身を確認すること
	@echo "results/ を削除します。必要な結果は退避済みか確認してください。" && read -p "続行 [y/N]: " a && [ "$$a" = "y" ] && rm -rf results/2* || echo "中止しました"
