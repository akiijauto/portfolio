package bench;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.File;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * Python実装（リファレンス）と同じ結果を返すことを検証する。
 * 性能比較は全実装が同じ仕事をしていることが前提なので、これが落ちたら計測しない。
 */
class ScoreTest {

    /** Maven の実行ディレクトリが services/java なので、そこから2階層上る。 */
    private static JsonNode loadGolden() throws Exception {
        File path = new File("../../tests/golden.json");
        assertTrue(path.exists(), "golden.json が無い（harness/gen_golden.py で生成する）: " + path.getAbsolutePath());
        return new ObjectMapper().readTree(path);
    }

    @Test
    void goldenParity() throws Exception {
        JsonNode golden = loadGolden();
        JsonNode cases = golden.get("cases");
        assertTrue(cases.size() > 0, "golden.json にケースが無い");

        for (JsonNode tc : cases) {
            JsonNode reqNode = tc.get("request");
            List<Score.Item> items = new ArrayList<>();
            for (JsonNode it : reqNode.path("items")) {
                items.add(new Score.Item(
                        it.path("sku").asText(""), it.path("qty").asInt(0), it.path("unit_price").asDouble(0)));
            }
            JsonNode customer = reqNode.path("customer");
            Score.Response got = Score.compute(new Score.Request(
                    reqNode.path("order_id").asText(""), items,
                    customer.path("tier").asText(""), customer.path("history_days").asInt(0),
                    reqNode.path("rounds").asInt(0)));

            JsonNode want = tc.get("expect");
            String label = tc.get("name").asText();
            // lang フィールドは実装ごとに異なって当然なので比較から外す
            assertEquals(want.get("item_count").asInt(), got.itemCount(), label);
            assertEquals(want.get("subtotal").asDouble(), got.subtotal(), 0.0, label);
            assertEquals(want.get("discount").asDouble(), got.discount(), 0.0, label);
            assertEquals(want.get("tax").asDouble(), got.tax(), 0.0, label);
            assertEquals(want.get("total").asDouble(), got.total(), 0.0, label);
            assertEquals(want.get("signature").asText(), got.signature(), label);
            assertEquals(want.get("rounds").asInt(), got.rounds(), label);

            List<String> wantSkus = new ArrayList<>();
            want.get("top_skus").forEach(n -> wantSkus.add(n.asText()));
            assertEquals(wantSkus, got.topSkus(), label);
        }
    }

    @Test
    void roundingIsHalfAwayFromZero() {
        // Math.round は 0.5 を常に +∞ 側へ倒すため、負値で Go/Ruby とずれる
        assertEquals(2.68, Score.round2(2.675), 0.0);
        assertEquals(0.13, Score.round2(0.125), 0.0);
        assertEquals(-0.13, Score.round2(-0.125), 0.0);
    }

    @Test
    void discountTable() {
        assertEquals(0.12, Score.discountRate("gold", 0), 0.0);
        assertEquals(0.07, Score.discountRate("silver", 0), 0.0);
        assertEquals(0.02, Score.discountRate("platinum", 0), 0.0);
        assertEquals(0.15, Score.discountRate("gold", 365), 1e-9);
        assertTrue(Score.discountRate("gold", 100000) <= 0.20);
    }

    @Test
    void rejectsBadInput() {
        List<Score.Item> ok = List.of(new Score.Item("A", 1, 1.0));
        assertThrows(Score.ValidationException.class,
                () -> Score.compute(new Score.Request("", ok, "gold", 0, 16)), "order_id無し");
        assertThrows(Score.ValidationException.class,
                () -> Score.compute(new Score.Request("X", List.of(), "gold", 0, 16)), "明細が空");
        assertThrows(Score.ValidationException.class,
                () -> Score.compute(new Score.Request("X", List.of(new Score.Item("A", 0, 1.0)), "gold", 0, 16)), "数量ゼロ");
        assertThrows(Score.ValidationException.class,
                () -> Score.compute(new Score.Request("X", List.of(new Score.Item("A", 1, -1.0)), "gold", 0, 16)), "負の単価");
    }
}
