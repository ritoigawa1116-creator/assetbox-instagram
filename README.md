# アセットボックス Instagram 自動投稿

- 毎朝7:30（日本時間）に GitHub Actions が動き、投稿管理表（Googleスプレッドシート）の「今日」の行を投稿します。
- ステータスが「保留」「修正依頼」「投稿済」の行は投稿しません。
- 画像は `images/` にあればそれを使い、無ければカード設定(JSON)から自動で作ります。
- 投稿した記録は `posted.json` に残ります。
- 失敗すると GitHub からメールが届きます。

設定値（Settings → Secrets and variables → Actions）
- Variables（任意）: `SHEET_CSV_URL`, `IG_USER_ID`（未設定ならワークフロー内の既定値を使用）
- Secrets: `IG_TOKEN`（Instagramアクセストークン）, 任意で `GH_PAT`
