package main

import (
	"encoding/json"
	"os"
	"reflect"
	"testing"
)

// golden は tests/golden.json の構造。3言語のテストが同じファイルを読む。
type golden struct {
	Cases []struct {
		Name    string          `json:"name"`
		Request scoreRequest    `json:"request"`
		Expect  json.RawMessage `json:"expect"`
	} `json:"cases"`
}

// TestGoldenParity は Python実装（リファレンス）と同じ結果を返すことを検証する。
// 性能比較は3実装が同じ仕事をしていることが前提なので、これが落ちたら計測しない。
func TestGoldenParity(t *testing.T) {
	raw, err := os.ReadFile("../../tests/golden.json")
	if err != nil {
		t.Fatalf("golden.json が読めない: %v (harness/gen_golden.py で生成する)", err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatalf("golden.json のパースに失敗: %v", err)
	}
	if len(g.Cases) == 0 {
		t.Fatal("golden.json にケースが無い")
	}

	for _, tc := range g.Cases {
		t.Run(tc.Name, func(t *testing.T) {
			got, err := compute(tc.Request)
			if err != nil {
				t.Fatalf("compute が失敗: %v", err)
			}
			// lang フィールドは実装ごとに異なって当然なので比較から外す
			var gotMap, wantMap map[string]any
			gotJSON, _ := json.Marshal(got)
			json.Unmarshal(gotJSON, &gotMap)
			delete(gotMap, "lang")
			json.Unmarshal(tc.Expect, &wantMap)

			if !reflect.DeepEqual(gotMap, wantMap) {
				t.Errorf("Python実装と不一致\n got=%v\nwant=%v", gotMap, wantMap)
			}
		})
	}
}

// TestValidation は不正入力が計算に進まないことを見る。
// バリデーションをすり抜けると言語ごとに異なるエラー経路に入り、
// 負荷試験のレイテンシに再現性が無くなる。
func TestValidation(t *testing.T) {
	cases := map[string]scoreRequest{
		"order_id無し": {Items: []item{{SKU: "A", Qty: 1, UnitPrice: 1}}},
		"明細が空":       {OrderID: "X"},
		"数量ゼロ":       {OrderID: "X", Items: []item{{SKU: "A", Qty: 0, UnitPrice: 1}}},
		"負の単価":       {OrderID: "X", Items: []item{{SKU: "A", Qty: 1, UnitPrice: -1}}},
	}
	for name, req := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := compute(req); err == nil {
				t.Error("エラーになるべきだが成功した")
			}
		})
	}
}
