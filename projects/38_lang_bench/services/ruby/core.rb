# frozen_string_literal: true

# SPEC-API-v1 のスコアリング計算（Ruby実装）。
#
# HTTP層から意図的に切り離してある。3言語が「同じ仕事」をしていることを
# テストで機械的に保証するのがこのファイルの役割で、ここが食い違うと
# 性能比較の数値そのものが無意味になる。変更時は必ず3実装を同時に直し、
# tests/golden.json での検証を通すこと。

require 'digest'

module Score
  # リクエスト内容の不備。HTTP層で400に変換する。
  class ValidationError < StandardError; end

  module_function

  # SPEC-API-v1の割引表。3実装で同一の値を返さなければならない。
  def discount_rate(tier, history_days)
    rate = { 'gold' => 0.12, 'silver' => 0.07 }.fetch(tier, 0.02)
    rate += 0.03 if history_days >= 365
    [rate, 0.20].min
  end

  # 注文の改ざん検知署名を模したCPU負荷。SHA-256をrounds回チェーンする。
  # rounds を上げるとCPU比重が、明細数を上げるとJSON/メモリ比重が増える。
  def signature(order_id, subtotal, rounds)
    digest = Digest::SHA256.digest(format('%s|%.2f', order_id, subtotal))
    rounds.times { digest = Digest::SHA256.digest(digest) }
    digest.unpack1('H*')
  end

  def compute(req)
    order_id = req['order_id'].to_s
    items = req['items'] || []
    raise ValidationError if order_id.empty? || items.empty?

    subtotal = 0.0
    items.each do |it|
      qty = it['qty'].to_i
      unit_price = it['unit_price'].to_f
      raise ValidationError if qty <= 0 || unit_price.negative?

      subtotal += qty * unit_price
    end
    subtotal = subtotal.round(2)

    customer = req['customer'] || {}
    rate = discount_rate(customer['tier'].to_s, customer['history_days'].to_i)
    discount = (subtotal * rate).round(2)
    tax = ((subtotal - discount) * 0.10).round(2)
    total = (subtotal - discount + tax).round(2)

    # 上位SKU抽出。金額降順、同額はSKU昇順で3実装の結果を一致させる。
    ranked = items.sort_by { |it| [-(it['qty'].to_i * it['unit_price'].to_f), it['sku'].to_s] }

    rounds = req['rounds'].to_i
    rounds = 200 if rounds <= 0

    {
      'order_id' => order_id,
      'lang' => 'ruby',
      'item_count' => items.length,
      'subtotal' => subtotal,
      'discount' => discount,
      'tax' => tax,
      'total' => total,
      'signature' => signature(order_id, subtotal, rounds),
      'top_skus' => ranked.first(5).map { |it| it['sku'] },
      'rounds' => rounds
    }
  end
end
