# frozen_string_literal: true

# Python実装（リファレンス）と同じ結果を返すことを検証する。
# 性能比較は3実装が同じ仕事をしていることが前提なので、これが落ちたら計測しない。

require 'minitest/autorun'
require 'json'
require_relative 'core'

class TestGoldenParity < Minitest::Test
  GOLDEN_PATH = File.expand_path('../../tests/golden.json', __dir__)

  def setup
    skip "golden.json が無い（harness/gen_golden.py で生成する）" unless File.exist?(GOLDEN_PATH)
    @golden = JSON.parse(File.read(GOLDEN_PATH))
  end

  def test_golden_parity
    refute_empty @golden['cases'], 'golden.json にケースが無い'
    @golden['cases'].each do |tc|
      # lang フィールドは実装ごとに異なって当然なので比較から外す
      got = Score.compute(tc['request']).reject { |k, _| k == 'lang' }
      assert_equal tc['expect'], got, "Python実装と不一致: #{tc['name']}"
    end
  end

  # 不正入力が計算に進まないことを見る。バリデーションをすり抜けると
  # 言語ごとに異なるエラー経路に入り、負荷試験のレイテンシに再現性が無くなる。
  def test_validation
    invalid = {
      'order_id無し' => { 'items' => [{ 'sku' => 'A', 'qty' => 1, 'unit_price' => 1 }] },
      '明細が空' => { 'order_id' => 'X', 'items' => [] },
      '数量ゼロ' => { 'order_id' => 'X', 'items' => [{ 'sku' => 'A', 'qty' => 0, 'unit_price' => 1 }] },
      '負の単価' => { 'order_id' => 'X', 'items' => [{ 'sku' => 'A', 'qty' => 1, 'unit_price' => -1 }] }
    }
    invalid.each do |name, req|
      assert_raises(Score::ValidationError, name) { Score.compute(req) }
    end
  end
end
