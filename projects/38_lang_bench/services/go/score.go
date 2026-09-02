// SPEC-API-v1 のスコアリング計算（Go実装）。
//
// HTTP層から意図的に切り離してある。3言語が「同じ仕事」をしていることを
// テストで機械的に保証するのがこのファイルの役割で、ここが食い違うと
// 性能比較の数値そのものが無意味になる。変更時は必ず3実装を同時に直し、
// tests/golden.json での検証を通すこと。
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"math"
	"sort"
)

type item struct {
	SKU       string  `json:"sku"`
	Qty       int     `json:"qty"`
	UnitPrice float64 `json:"unit_price"`
}

type customer struct {
	Tier        string `json:"tier"`
	HistoryDays int    `json:"history_days"`
}

type scoreRequest struct {
	OrderID  string   `json:"order_id"`
	Items    []item   `json:"items"`
	Customer customer `json:"customer"`
	Rounds   int      `json:"rounds"`
}

type scoreResponse struct {
	OrderID   string   `json:"order_id"`
	Lang      string   `json:"lang"`
	ItemCount int      `json:"item_count"`
	Subtotal  float64  `json:"subtotal"`
	Discount  float64  `json:"discount"`
	Tax       float64  `json:"tax"`
	Total     float64  `json:"total"`
	Signature string   `json:"signature"`
	TopSKUs   []string `json:"top_skus"`
	Rounds    int      `json:"rounds"`
}

// errValidation はリクエスト内容の不備。HTTP層で400に変換する。
var errValidation = errors.New("validation_failed")

// round2 は「0.5は絶対値の大きい側へ」の丸め。Python/Ruby実装と揃えてある。
func round2(v float64) float64 { return math.Round(v*100) / 100 }

// discountRate はSPEC-API-v1の割引表。3実装で同一の値を返さなければならない。
func discountRate(tier string, historyDays int) float64 {
	var rate float64
	switch tier {
	case "gold":
		rate = 0.12
	case "silver":
		rate = 0.07
	default:
		rate = 0.02
	}
	if historyDays >= 365 {
		rate += 0.03
	}
	if rate > 0.20 {
		rate = 0.20
	}
	return rate
}

// signature は注文の改ざん検知署名を模したCPU負荷。SHA-256をrounds回チェーンする。
// rounds を上げるとCPU比重が、明細数を上げるとJSON/メモリ比重が増える。
func signature(orderID string, subtotal float64, rounds int) string {
	seed := fmt.Sprintf("%s|%.2f", orderID, subtotal)
	digest := sha256.Sum256([]byte(seed))
	for i := 0; i < rounds; i++ {
		digest = sha256.Sum256(digest[:])
	}
	return hex.EncodeToString(digest[:])
}

func compute(req scoreRequest) (scoreResponse, error) {
	if req.OrderID == "" || len(req.Items) == 0 {
		return scoreResponse{}, errValidation
	}

	subtotal := 0.0
	for _, it := range req.Items {
		if it.Qty <= 0 || it.UnitPrice < 0 {
			return scoreResponse{}, errValidation
		}
		subtotal += float64(it.Qty) * it.UnitPrice
	}
	subtotal = round2(subtotal)

	discount := round2(subtotal * discountRate(req.Customer.Tier, req.Customer.HistoryDays))
	tax := round2((subtotal - discount) * 0.10)
	total := round2(subtotal - discount + tax)

	// 上位SKU抽出。金額降順、同額はSKU昇順で3実装の結果を一致させる。
	ranked := make([]item, len(req.Items))
	copy(ranked, req.Items)
	sort.SliceStable(ranked, func(i, j int) bool {
		a := float64(ranked[i].Qty) * ranked[i].UnitPrice
		b := float64(ranked[j].Qty) * ranked[j].UnitPrice
		if a == b {
			return ranked[i].SKU < ranked[j].SKU
		}
		return a > b
	})
	top := make([]string, 0, 5)
	for i := 0; i < len(ranked) && i < 5; i++ {
		top = append(top, ranked[i].SKU)
	}

	rounds := req.Rounds
	if rounds <= 0 {
		rounds = 200
	}

	return scoreResponse{
		OrderID:   req.OrderID,
		Lang:      "go",
		ItemCount: len(req.Items),
		Subtotal:  subtotal,
		Discount:  discount,
		Tax:       tax,
		Total:     total,
		Signature: signature(req.OrderID, subtotal, rounds),
		TopSKUs:   top,
		Rounds:    rounds,
	}, nil
}
