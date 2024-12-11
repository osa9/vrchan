# VRChan

VRChan は VRChat のグループインスタンスの状況を監視し、Discord に通知するアプリケーションです。

## 使い方

### 事前準備

事前に下記が必要です。

- Discord の Webhook URL を取得
- VRChat の TOTP シークレットを取得
- VRChat のグループ ID を取得
- Upstash の Redis の URL と API トークンを取得

### 実行/デプロイ

```bash
# このリポジトリをクローン
$ git clone https://github.com/osa9/vrchan.git
$ cd vrchan

# 環境変数を設定
$ cp .env.example .env

# ローカル実行
$ uv run python -m vrchan.app

# AWS Lambda にデプロイ
$ uv export -o requirements.txt --no-hashes
$ sls deploy
```
