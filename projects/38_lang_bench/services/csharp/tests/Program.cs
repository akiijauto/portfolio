// Python実装（リファレンス）と同じ結果を返すことを検証する。
// 性能比較は全実装が同じ仕事をしていることが前提なので、これが落ちたら計測しない。

using System.Text.Json;
using Bench;

var failures = 0;
var assertions = 0;

void Check(bool ok, string label)
{
    assertions++;
    if (ok) return;
    failures++;
    Console.Error.WriteLine($"  [NG] {label}");
}

// --- golden parity ---
var goldenPath = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "../../../../../../tests/golden.json"));
if (!File.Exists(goldenPath))
{
    // ビルド出力の深さは構成によって変わるので、見つからなければ上に辿って探す
    var dir = new DirectoryInfo(AppContext.BaseDirectory);
    goldenPath = "";
    for (var i = 0; i < 10 && dir is not null; i++, dir = dir.Parent)
    {
        var candidate = Path.Combine(dir.FullName, "tests", "golden.json");
        if (File.Exists(candidate)) { goldenPath = candidate; break; }
    }
}
if (string.IsNullOrEmpty(goldenPath))
{
    Console.Error.WriteLine("golden.json が見つからない（harness/gen_golden.py で生成する）");
    return 1;
}

using var golden = JsonDocument.Parse(File.ReadAllText(goldenPath));
var cases = golden.RootElement.GetProperty("cases");
Check(cases.GetArrayLength() > 0, "golden.json にケースがある");

foreach (var tc in cases.EnumerateArray())
{
    var name = tc.GetProperty("name").GetString() ?? "?";
    var reqNode = tc.GetProperty("request");

    var items = new List<Item>();
    if (reqNode.TryGetProperty("items", out var itemsNode))
    {
        foreach (var it in itemsNode.EnumerateArray())
        {
            items.Add(new Item(
                it.GetProperty("sku").GetString() ?? "",
                it.GetProperty("qty").GetInt32(),
                it.GetProperty("unit_price").GetDouble()));
        }
    }

    var tier = "";
    var historyDays = 0;
    if (reqNode.TryGetProperty("customer", out var customer))
    {
        if (customer.TryGetProperty("tier", out var t)) tier = t.GetString() ?? "";
        if (customer.TryGetProperty("history_days", out var h)) historyDays = h.GetInt32();
    }

    var got = Score.Compute(new ScoreRequest(
        reqNode.GetProperty("order_id").GetString() ?? "",
        items, tier, historyDays,
        reqNode.TryGetProperty("rounds", out var r) ? r.GetInt32() : 0));

    var want = tc.GetProperty("expect");
    // lang フィールドは実装ごとに異なって当然なので比較から外す
    Check(want.GetProperty("item_count").GetInt32() == got.ItemCount, $"{name}: item_count");
    Check(want.GetProperty("subtotal").GetDouble() == got.Subtotal, $"{name}: subtotal");
    Check(want.GetProperty("discount").GetDouble() == got.Discount, $"{name}: discount");
    Check(want.GetProperty("tax").GetDouble() == got.Tax, $"{name}: tax");
    Check(want.GetProperty("total").GetDouble() == got.Total, $"{name}: total");
    Check(want.GetProperty("signature").GetString() == got.Signature, $"{name}: signature");
    Check(want.GetProperty("rounds").GetInt32() == got.Rounds, $"{name}: rounds");

    var wantSkus = want.GetProperty("top_skus").EnumerateArray().Select(x => x.GetString()).ToList();
    Check(wantSkus.SequenceEqual(got.TopSkus), $"{name}: top_skus");
}

// --- 丸め ---
// .NET の Math.Round は既定が偶数丸めなので、Go/Ruby と揃うことを明示的に固定する
Check(Score.Round2(2.675) == 2.68, "round2(2.675) == 2.68");
Check(Score.Round2(0.125) == 0.13, "round2(0.125) == 0.13");
Check(Score.Round2(-0.125) == -0.13, "round2(-0.125) == -0.13");

// --- 割引表 ---
Check(Score.DiscountRate("gold", 0) == 0.12, "gold");
Check(Score.DiscountRate("silver", 0) == 0.07, "silver");
Check(Score.DiscountRate("platinum", 0) == 0.02, "未知tierは既定割引");
Check(Math.Abs(Score.DiscountRate("gold", 365) - 0.15) < 1e-9, "長期顧客ボーナス");
Check(Score.DiscountRate("gold", 100000) <= 0.20, "割引上限");

// --- バリデーション ---
var invalid = new (string Name, ScoreRequest Req)[]
{
    ("order_id無し", new ScoreRequest("", new[] { new Item("A", 1, 1.0) }, "gold", 0, 16)),
    ("明細が空", new ScoreRequest("X", Array.Empty<Item>(), "gold", 0, 16)),
    ("数量ゼロ", new ScoreRequest("X", new[] { new Item("A", 0, 1.0) }, "gold", 0, 16)),
    ("負の単価", new ScoreRequest("X", new[] { new Item("A", 1, -1.0) }, "gold", 0, 16)),
};
foreach (var (name, req) in invalid)
{
    var threw = false;
    try { Score.Compute(req); } catch (ValidationException) { threw = true; }
    Check(threw, $"バリデーション: {name}");
}

Console.WriteLine($"C#: {assertions} assertions, {failures} failures");
return failures == 0 ? 0 : 1;
