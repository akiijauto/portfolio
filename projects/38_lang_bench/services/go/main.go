// 3言語共通仕様のスコアリングAPI（Go実装・HTTP層）。
// 計算ロジックは score.go に置いてある。
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"runtime"
	"sync/atomic"
)

var processed int64

func handleScore(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"method_not_allowed"}`, http.StatusMethodNotAllowed)
		return
	}
	var req scoreRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid_json"}`, http.StatusBadRequest)
		return
	}
	resp, err := compute(req)
	if errors.Is(err, errValidation) {
		http.Error(w, `{"error":"validation_failed"}`, http.StatusBadRequest)
		return
	}
	atomic.AddInt64(&processed, 1)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8000"
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/score", handleScore)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"status":"ok","lang":"go"}`)
	})
	mux.HandleFunc("/metrics", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"lang":"go","processed":%d,"gomaxprocs":%d}`,
			atomic.LoadInt64(&processed), runtime.GOMAXPROCS(0))
	})
	log.Printf("go service listening on :%s (GOMAXPROCS=%d)", port, runtime.GOMAXPROCS(0))
	log.Fatal(http.ListenAndServe(":"+port, mux))
}
