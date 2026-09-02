// SPEC-API-v1 のスコアリング計算（C#実装）。
//
// HTTP層から意図的に切り離してある。全実装が「同じ仕事」をしていることを
// テストで機械的に保証するのがこのクラスの役割で、ここが食い違うと
// 性能比較の数値そのものが無意味になる。変更時は必ず全実装を同時に直し、
// tests/golden.json での検証を通すこと。

using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace Bench;

/// <summary>リクエスト内容の不備。HTTP層で400に変換する。</summary>
public sealed class ValidationException : Exception
{
    public ValidationException() : base("validation_failed") { }
}

public sealed record Item(string Sku, int Qty, double UnitPrice);

public sealed record ScoreRequest(string OrderId, IReadOnlyList<Item> Items, string Tier, int HistoryDays, int Rounds);

public sealed record ScoreResponse(
    string OrderId,
    string Lang,
    int ItemCount,
    double Subtotal,
    double Discount,
    double Tax,
    double Total,
    string Signature,
    IReadOnlyList<string> TopSkus,
    int Rounds);

public static class Score
{
    /// <summary>
    /// 「0.5は絶対値の大きい側へ」の丸め。
    /// .NET の Math.Round は既定が偶数丸めなので、そのまま使うと Go/Ruby と金額が食い違う。
    /// </summary>
    public static double Round2(double value) =>
        value >= 0
            ? Math.Floor(value * 100 + 0.5) / 100
            : -(Math.Floor(-value * 100 + 0.5) / 100);

    /// <summary>SPEC-API-v1の割引表。全実装で同一の値を返さなければならない。</summary>
    public static double DiscountRate(string tier, int historyDays)
    {
        var rate = tier switch
        {
            "gold" => 0.12,
            "silver" => 0.07,
            _ => 0.02,
        };
        if (historyDays >= 365) rate += 0.03;
        return Math.Min(rate, 0.20);
    }

    /// <summary>
    /// 注文の改ざん検知署名を模したCPU負荷。SHA-256をrounds回チェーンする。
    /// rounds を上げるとCPU比重が、明細数を上げるとJSON/メモリ比重が増える。
    /// </summary>
    public static string Signature(string orderId, double subtotal, int rounds)
    {
        var seed = string.Format(CultureInfo.InvariantCulture, "{0}|{1:F2}", orderId, subtotal);
        var digest = SHA256.HashData(Encoding.UTF8.GetBytes(seed));
        for (var i = 0; i < rounds; i++)
        {
            digest = SHA256.HashData(digest);
        }
        return Convert.ToHexStringLower(digest);
    }

    public static ScoreResponse Compute(ScoreRequest req)
    {
        if (string.IsNullOrEmpty(req.OrderId) || req.Items.Count == 0) throw new ValidationException();

        var subtotal = 0.0;
        foreach (var it in req.Items)
        {
            if (it.Qty <= 0 || it.UnitPrice < 0) throw new ValidationException();
            subtotal += it.Qty * it.UnitPrice;
        }
        subtotal = Round2(subtotal);

        var discount = Round2(subtotal * DiscountRate(req.Tier, req.HistoryDays));
        var tax = Round2((subtotal - discount) * 0.10);
        var total = Round2(subtotal - discount + tax);

        // 上位SKU抽出。金額降順、同額はSKU昇順で全実装の結果を一致させる。
        var topSkus = req.Items
            .OrderByDescending(it => it.Qty * it.UnitPrice)
            .ThenBy(it => it.Sku, StringComparer.Ordinal)
            .Take(5)
            .Select(it => it.Sku)
            .ToList();

        var rounds = req.Rounds <= 0 ? 200 : req.Rounds;

        return new ScoreResponse(
            req.OrderId, "csharp", req.Items.Count,
            subtotal, discount, tax, total,
            Signature(req.OrderId, subtotal, rounds), topSkus, rounds);
    }
}
