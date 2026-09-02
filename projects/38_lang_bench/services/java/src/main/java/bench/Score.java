package bench;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

/**
 * SPEC-API-v1 のスコアリング計算（Java実装）。
 *
 * <p>HTTP層から意図的に切り離してある。全実装が「同じ仕事」をしていることを
 * テストで機械的に保証するのがこのクラスの役割で、ここが食い違うと
 * 性能比較の数値そのものが無意味になる。変更時は必ず全実装を同時に直し、
 * tests/golden.json での検証を通すこと。
 */
public final class Score {

    private Score() {}

    /** リクエスト内容の不備。HTTP層で400に変換する。 */
    public static class ValidationException extends RuntimeException {
        public ValidationException() {
            super("validation_failed");
        }
    }

    public record Item(String sku, int qty, double unitPrice) {}

    public record Request(String orderId, List<Item> items, String tier, int historyDays, int rounds) {}

    public record Response(
            String orderId,
            String lang,
            int itemCount,
            double subtotal,
            double discount,
            double tax,
            double total,
            String signature,
            List<String> topSkus,
            int rounds) {}

    /**
     * 「0.5は絶対値の大きい側へ」の丸め。
     * Math.round は 0.5 を常に +∞ 側へ倒すため、負値で Go/Ruby とずれる。
     * 小計は非負だが、仕様として符号を明示的に扱っておく。
     */
    public static double round2(double value) {
        return value >= 0
                ? Math.floor(value * 100 + 0.5) / 100
                : -(Math.floor(-value * 100 + 0.5) / 100);
    }

    /** SPEC-API-v1の割引表。全実装で同一の値を返さなければならない。 */
    public static double discountRate(String tier, int historyDays) {
        double rate = switch (tier == null ? "" : tier) {
            case "gold" -> 0.12;
            case "silver" -> 0.07;
            default -> 0.02;
        };
        if (historyDays >= 365) {
            rate += 0.03;
        }
        return Math.min(rate, 0.20);
    }

    /**
     * 注文の改ざん検知署名を模したCPU負荷。SHA-256をrounds回チェーンする。
     * rounds を上げるとCPU比重が、明細数を上げるとJSON/メモリ比重が増える。
     */
    public static String signature(String orderId, double subtotal, int rounds) {
        MessageDigest sha256;
        try {
            sha256 = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 が利用できない", e);
        }
        String seed = String.format(Locale.ROOT, "%s|%.2f", orderId, subtotal);
        byte[] digest = sha256.digest(seed.getBytes(StandardCharsets.UTF_8));
        for (int i = 0; i < rounds; i++) {
            digest = sha256.digest(digest);
        }
        StringBuilder hex = new StringBuilder(digest.length * 2);
        for (byte b : digest) {
            hex.append(Character.forDigit((b >> 4) & 0xF, 16)).append(Character.forDigit(b & 0xF, 16));
        }
        return hex.toString();
    }

    public static Response compute(Request req) {
        if (req.orderId() == null || req.orderId().isEmpty() || req.items() == null || req.items().isEmpty()) {
            throw new ValidationException();
        }

        double subtotal = 0.0;
        for (Item it : req.items()) {
            if (it.qty() <= 0 || it.unitPrice() < 0) {
                throw new ValidationException();
            }
            subtotal += it.qty() * it.unitPrice();
        }
        subtotal = round2(subtotal);

        double discount = round2(subtotal * discountRate(req.tier(), req.historyDays()));
        double tax = round2((subtotal - discount) * 0.10);
        double total = round2(subtotal - discount + tax);

        // 上位SKU抽出。金額降順、同額はSKU昇順で全実装の結果を一致させる。
        List<Item> ranked = new ArrayList<>(req.items());
        ranked.sort(Comparator
                .comparingDouble((Item it) -> -(it.qty() * it.unitPrice()))
                .thenComparing(Item::sku));
        List<String> topSkus = ranked.stream().limit(5).map(Item::sku).toList();

        int rounds = req.rounds() <= 0 ? 200 : req.rounds();

        return new Response(
                req.orderId(), "java", req.items().size(),
                subtotal, discount, tax, total,
                signature(req.orderId(), subtotal, rounds), topSkus, rounds);
    }
}
