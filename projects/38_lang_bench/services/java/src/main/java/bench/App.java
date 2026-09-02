package bench;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * 共通仕様のスコアリングAPI（Java実装・HTTP層）。計算ロジックは {@link Score}。
 *
 * <p>他実装が手動でJSONを解釈しているため、公平性の観点からここでも
 * Bean へのバインドと Bean Validation は使わず、JsonNode を自前で解釈する。
 */
@SpringBootApplication
@RestController
public class App {

    private final AtomicLong processed = new AtomicLong();

    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }

    @PostMapping("/api/v1/score")
    public ResponseEntity<?> score(@RequestBody JsonNode body) {
        Score.Request req;
        try {
            req = parse(body);
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(Map.of("error", "validation_failed"));
        }

        Score.Response res;
        try {
            res = Score.compute(req);
        } catch (Score.ValidationException e) {
            return ResponseEntity.badRequest().body(Map.of("error", "validation_failed"));
        }

        processed.incrementAndGet();
        return ResponseEntity.ok(toMap(res));
    }

    private static Score.Request parse(JsonNode body) {
        List<Score.Item> items = new ArrayList<>();
        JsonNode itemsNode = body.path("items");
        for (JsonNode it : itemsNode) {
            items.add(new Score.Item(
                    it.path("sku").asText(""),
                    it.path("qty").asInt(0),
                    it.path("unit_price").asDouble(0.0)));
        }
        JsonNode customer = body.path("customer");
        return new Score.Request(
                body.path("order_id").asText(""),
                items,
                customer.path("tier").asText(""),
                customer.path("history_days").asInt(0),
                body.path("rounds").asInt(0));
    }

    /** レスポンスのキー順と名前を他実装に合わせる（レコードのフィールド名は camelCase のため）。 */
    private static Map<String, Object> toMap(Score.Response r) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("order_id", r.orderId());
        out.put("lang", r.lang());
        out.put("item_count", r.itemCount());
        out.put("subtotal", r.subtotal());
        out.put("discount", r.discount());
        out.put("tax", r.tax());
        out.put("total", r.total());
        out.put("signature", r.signature());
        out.put("top_skus", r.topSkus());
        out.put("rounds", r.rounds());
        return out;
    }

    @GetMapping("/healthz")
    public Map<String, String> healthz() {
        return Map.of("status", "ok", "lang", "java");
    }

    @GetMapping("/metrics")
    public Map<String, Object> metrics() {
        return Map.of("lang", "java", "processed", processed.get());
    }
}
