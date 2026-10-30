# 本番デプロイガイド（DEPLOYMENT_GUIDE.md）

本ドキュメントは、**GitHub Description Generator** を本番環境（Linux / Docker / Reverse Proxy）に安全かつ再現性高くデプロイするためのガイドです。

---

## 📋 アーキテクチャ概要

```
[クライアント / ブラウザ]
       │
       ▼ (HTTPS: 443)
[リバースプロキシ (Apache2 / Nginx)]
       │
       ▼ (HTTP: 127.0.0.1:8085)
[Docker Container: github-description]
       │  - FastAPI / Uvicorn (非root実行: appuser)
       │  - ログ自動ローテーション
       └─ Docker Compose 一元管理
```

- **待受ポート**: `127.0.0.1:8085` (ホスト側のループバックにのみバインド)
- **プロセス管理**: Docker Compose (`compose.yaml`)、`restart: unless-stopped`
- **コンテナ設計**: マルチステージビルド、`python:3.12-slim`、非rootユーザー実行

---

## 目次
- [STEP 1: 前提要件と準備](#step-1-前提要件と準備)
- [STEP 2: ソースコードの配置と環境設定](#step-2-ソースコードの配置と環境設定)
- [STEP 3: Docker Compose による起動](#step-3-docker-compose-による起動)
- [STEP 4: リバースプロキシ設定 (Apache2 / Nginx)](#step-4-リバースプロキシ設定-apache2--nginx)
- [STEP 5: 動作確認とヘルスチェック](#step-5-動作確認とヘルスチェック)
- [STEP 6: セキュリティと運用保守](#step-6-セキュリティと運用保守)

---

## STEP 1: 前提要件と準備

- **ホストOS**: Ubuntu 22.04 LTS / Debian 12 などの Linux ディストリビューション
- **必須ソフトウェア**:
  - Docker Engine 24.0+
  - Docker Compose v2 (Compose Plugin)
  - リバースプロキシ (Apache2 または Nginx)
  - SSL証明書 (Certbot / Let's Encrypt または Cloudflare)

---

## STEP 2: ソースコードの配置と環境設定

### 2-1. リポジトリのクローン
```bash
# 作業ディレクトリの作成
mkdir -p /opt/apps/github-description
cd /opt/apps/github-description

# リポジトリのクローン
git clone https://github.com/zyuuuukak1n/github-description-generator.git .
```

### 2-2. 環境変数ファイル（`.env`）の作成
`.env.example` をコピーして `.env` を作成し、必要に応じて設定を編集します。

```bash
cp .env.example .env
chmod 600 .env
```

**【設定例】**
```env
APP_ENV=production
HOST=0.0.0.0
PORT=8085

# サブディレクトリで配信する場合はパスを指定 (例: /tools/github-description)
# ドメイン直下で配信する場合は空欄
ROOT_PATH=/tools/github-description

CORS_ORIGINS=*
LOG_LEVEL=INFO
RATE_LIMIT_PER_MINUTE=60

# 任意設定
GITHUB_DEFAULT_TOKEN=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

---

## STEP 3: Docker Compose による起動

`compose.yaml` を使用してコンテナをビルド・起動します。

```bash
# コンテナのビルドとバックグラウンド起動
docker compose up -d --build

# 起動ステータスの確認
docker compose ps
```

---

## STEP 4: リバースプロキシ設定

外部からのHTTPSリクエストを受け、ローカルコンテナ（`http://127.0.0.1:8085/`）へ転送します。

### 構成例A: Apache2 (サブパス配信: `/tools/github-description/`)

`/etc/apache2/sites-available/github-description.conf` を作成:

```apache
<IfModule mod_proxy.c>
    ProxyPreserveHost On
    ProxyRequests Off

    <Proxy *>
        Require all granted
    </Proxy>

    # コンテナへの転送
    ProxyPass /tools/github-description/ http://127.0.0.1:8085/ connectiontimeout=10 timeout=60
    ProxyPassReverse /tools/github-description/ http://127.0.0.1:8085/

    # 末尾スラッシュ補正
    <IfModule mod_rewrite.c>
        RewriteEngine On
        RewriteRule ^/tools/github-description$ /tools/github-description/ [R=301,L]
    </IfModule>

    RequestHeader set X-Forwarded-Prefix "/tools/github-description"
    RequestHeader set X-Forwarded-Proto "https"
</IfModule>
```

有効化と反映:
```bash
sudo a2enmod proxy proxy_http rewrite headers
sudo a2ensite github-description.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

---

### 構成例B: Nginx (サブパス配信: `/tools/github-description/`)

`/etc/nginx/conf.d/github-description.conf` または既存の `server` ブロック内:

```nginx
location /tools/github-description/ {
    proxy_pass http://127.0.0.1:8085/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /tools/github-description;

    proxy_connect_timeout 10s;
    proxy_read_timeout 60s;
}
```

反映:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## STEP 5: 動作確認とヘルスチェック

### 5-1. ローカルヘルスチェック
```bash
curl -i http://127.0.0.1:8085/health
```

### 5-2. コンテナログの確認
```bash
docker compose logs -f
```

### 5-3. ブラウザでの確認
`https://your-domain.com/tools/github-description/` にアクセスし、正常にUIが表示され、解析および生成が行えることを確認します。

---

## STEP 6: セキュリティと運用保守

- **シークレット保護**:
  `.env` ファイルには適切なパーミッション（`600`）を設定し、Gitリポジトリには絶対にコミットしないでください。
- **ログ管理**:
  `compose.yaml` でログローテーション（`max-size: 10m`, `max-file: 3`）が設定されているため、ディスク枯渇のリスクを未然に防止します。
- **コンテナ更新**:
  ```bash
  git pull origin main
  docker compose up -d --build
  ```
