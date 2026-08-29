# ブラウザ拡張連携 クリップボード自動整形

Chrome拡張からコピーしたテキストを送信し、AIで整形（誤字修正・箇条書き変換・要約・
丁寧語変換）して結果を受け取るツールです。バックエンド（Flask）とChrome拡張の2つから
構成されます。

> 詳細な仕様は [要件定義.md](要件定義.md) を参照してください。

## 構成

```
projects/36_clipboard_formatter/   ← バックエンド（このフォルダ）
extensions/project36/              ← Chrome拡張（Manifest V3）
```

## バックエンドのセットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # GEMINI_API_KEYを設定
python app.py
```

`http://localhost:5036/` でダッシュボードが、`/api/format`でAPIが起動します。

## Chrome拡張のインストール（開発時）

1. Chromeで `chrome://extensions` を開く
2. 右上の「デベロッパーモード」をONにする
3. 「パッケージ化されていない拡張機能を読み込む」から `extensions/project36/` を選択する
4. ツールバーの拡張機能アイコンからポップアップを開き、テキストを入力して「整形する」を押す

ローカル開発では`popup.js`内の`API_BASE`が`http://localhost:5036`を指しているため、
バックエンドをローカルで起動しておく必要があります。本番公開時はこの値をRenderの
URLに変更してください。

## 環境変数（バックエンド）

`.env.example` をコピーして `.env` を作成し、値を設定してください。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 必須 | テキスト整形に使用 |
| `SECRET_KEY` | 任意 | Flaskセッション用。未設定時は起動ごとに自動生成 |

## テスト

```bash
python -m pytest projects/36_clipboard_formatter/tests/test_app.py -v
```

実機では`/api/format`に丁寧語変換モードでリクエストを送り、Gemini APIによる
実際の変換結果が返ることを確認済みです。

## デプロイ（Render）

このフォルダの `render.yaml` を使い、Renderサービス名 `project36-clipboard-formatter` として
バックエンドのみを個別デプロイします（Chrome拡張はストアまたは手動配布）。
本番URLが確定したら、`extensions/project36/popup.js`の`API_BASE`と
`manifest.json`の`host_permissions`を本番URLに更新してください。
