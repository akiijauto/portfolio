// 共通仕様のスコアリングAPI（C#実装・HTTP層）。計算ロジックは Score.cs。
//
// 他実装が手動でJSONを解釈しているため、公平性の観点からここでも
// モデルバインドと DataAnnotations の自動検証は使わず、JsonDocument を自前で解釈する。

using System.Text.Json;
using Bench;

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders();
builder.WebHost.UseUrls($"http://0.0.0.0:{Environment.GetEnvironmentVariable("PORT") ?? "8000"}");

var app = builder.Build();
var processed = 0L;

app.MapPost("/api/v1/score", async (HttpRequest request) =>
{
    JsonDocument doc;
    try
    {
        doc = await JsonDocument.ParseAsync(request.Body);
    }
    catch (JsonException)
    {
        return Results.BadRequest(new { error = "invalid_json" });
    }

    using (doc)
    {
        ScoreRequest req;
        try
        {
            req = Parse(doc.RootElement);
        }
        catch (Exception e) when (e is InvalidOperationException or FormatException or KeyNotFoundException)
        {
            return Results.BadRequest(new { error = "validation_failed" });
        }

        try
        {
            var res = Score.Compute(req);
            Interlocked.Increment(ref processed);
            // キー名と順序を他実装に合わせる（C#のプロパティ名は PascalCase のため）。
            return Results.Ok(new Dictionary<string, object>
            {
                ["order_id"] = res.OrderId,
                ["lang"] = res.Lang,
                ["item_count"] = res.ItemCount,
                ["subtotal"] = res.Subtotal,
                ["discount"] = res.Discount,
                ["tax"] = res.Tax,
                ["total"] = res.Total,
                ["signature"] = res.Signature,
                ["top_skus"] = res.TopSkus,
                ["rounds"] = res.Rounds,
            });
        }
        catch (ValidationException)
        {
            return Results.BadRequest(new { error = "validation_failed" });
        }
    }
});

app.MapGet("/healthz", () => Results.Ok(new { status = "ok", lang = "csharp" }));
app.MapGet("/metrics", () => Results.Ok(new
{
    lang = "csharp",
    processed = Interlocked.Read(ref processed),
    pid = Environment.ProcessId,
}));

app.Run();

static ScoreRequest Parse(JsonElement root)
{
    var items = new List<Item>();
    if (root.TryGetProperty("items", out var itemsNode) && itemsNode.ValueKind == JsonValueKind.Array)
    {
        foreach (var it in itemsNode.EnumerateArray())
        {
            items.Add(new Item(
                it.TryGetProperty("sku", out var sku) ? sku.GetString() ?? "" : "",
                it.TryGetProperty("qty", out var qty) ? qty.GetInt32() : 0,
                it.TryGetProperty("unit_price", out var price) ? price.GetDouble() : 0.0));
        }
    }

    var tier = "";
    var historyDays = 0;
    if (root.TryGetProperty("customer", out var customer) && customer.ValueKind == JsonValueKind.Object)
    {
        if (customer.TryGetProperty("tier", out var t)) tier = t.GetString() ?? "";
        if (customer.TryGetProperty("history_days", out var h)) historyDays = h.GetInt32();
    }

    return new ScoreRequest(
        root.TryGetProperty("order_id", out var id) ? id.GetString() ?? "" : "",
        items,
        tier,
        historyDays,
        root.TryGetProperty("rounds", out var r) ? r.GetInt32() : 0);
}
