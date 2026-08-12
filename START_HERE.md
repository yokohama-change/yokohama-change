# START HERE — 0円で自動運転を開始する

このフォルダはアップロード準備済みです。

## GitHubで1回だけ必要な操作

1. 新しい **Public repository** を作る（推奨名 `yokohama-change`）。README等はGitHub側で追加せず空で作成。
2. このZIPを展開し、`japan-change-zero` フォルダ**の中身**をすべてリポジトリへアップロード。
3. GitHubの `Actions` → `collect-public-changes` → `Run workflow` を1回実行。
4. `Settings` → `Pages` → `Deploy from a branch` → `main` / `/docs` を選択。

以後、3時間ごとに自動巡回します。

## 自動で生成される商品候補データ

- `docs/data/latest.json` — API向けJSON
- `docs/data/leads.csv` — 商用スコア50以上の候補CSV
- `docs/data/summary.json` — 顧客層別・機会別の件数
- `docs/data/status.json` — データ源の稼働状況

## 重要

通常WebサイトRSSは本文を転載せず、変化検知・分類・原典リンク中心です。オープンデータはライセンス条件に従って扱います。詳細は `LICENSES_AND_LEGAL.md` を参照してください。
