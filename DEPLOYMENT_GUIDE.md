# 手動オペレーション手順書（DEPLOYMENT_GUIDE.md）

本ドキュメントは、**GitHub Description Generator** のコード生成完了状態から、GitHubへのPublic公開、自宅Ubuntu Server（Apache2環境）の `tool` ディレクトリへの配置、systemdによるデーモン化、**Cloudflare Tunnelを利用した独自ドメイン（`zyuuuukak1n.dev`）の `tool` 配下への安全な公開**、および動作確認・ヘルスチェックに至る全手順を解説したステップバイステップガイドです。

---

## 📋 システム構成の概要

```
[インターネット]
       │
       ▼ (HTTPS)
[Cloudflare Edge Network] (zyuuuukak1n.dev)
       │
       ▼ (Cloudflare Tunnel: cloudflared)
[自宅 Ubuntu Server]
       │
       ▼ (HTTP: ポート80 または 443)
[Apache2 リバースプロキシ]
       │  ※ /tool/github-description/ -> http://127.0.0.1:8085/
       ▼ (HTTP: 127.0.0.1:8085)
[FastAPI / Uvicorn (systemd デーモン)]
       │
       └─ 配置パス: /var/www/tool/github-description
```

- **公開URL**: `https://zyuuuukak1n.dev/tool/github-description/`
- **内部ポート**: `127.0.0.1:8085`（外部にはポート開放せず完全ローカル待機）
- **サーバー配置パス**: `/var/www/tool/github-description`

---

## 目次
- [STEP 1: GitHubリポジトリの初期化とPush](#step-1-githubリポジトリの初期化とpush)
- [STEP 2: アーキテクチャ判定結果と設計理由](#step-2-アーキテクチャ判定結果と設計理由)
- [STEP 3: 実行・ホスティング環境のセットアップ（Ubuntu Server + Apache2）](#step-3-実行ホスティング環境のセットアップubuntu-server--apache2)
- [STEP 4: 本番環境変数（.env）の配置とセキュリティ設定](#step-4-本番環境変数の配置とセキュリティ設定)
- [STEP 5: Cloudflare Tunnel によるドメイン公開設定（zyuuuukak1n.dev）](#step-5-cloudflare-tunnel-によるドメイン公開設定zyuuuukak1ndev)
- [STEP 6: CI/CD（GitHub Actions）の設定](#step-6-cicdgithub-actionsの設定)
- [STEP 7: 動作確認・ヘルスチェック・運用保守](#step-7-動作確認ヘルスチェック運用保守)

---

## STEP 1: GitHubリポジトリの初期化とPush

ローカル環境（Windows / PowerShell等）から作業を開始し、GitHub上に作成したPublicリポジトリへソースコードを初期Pushします。

### 1-1. リポジトリ設定情報の確認
- **リポジトリ名**: `github-description-generator` （または任意の英数字名）
- **公開設定**: **Public**
- **Description（概要文・350文字以内）**:
  ```text
  GitHubのパブリックリポジトリを自動解析し、上限350文字に最適化された高品質な説明文（Description）とトピックタグを生成・ワンクリックで直接更新するWebアプリ。Gemini/OpenAI連携に加え、APIキー不要のスマート抽出エンジンも搭載。Ubuntu+Apache2リバースプロキシ対応。
  ```
- **トピックタグ（Topics）**:
  `github`, `github-api`, `fastapi`, `python`, `description-generator`, `developer-tools`, `gemini-api`, `apache2`

### 1-2. .gitignore の確認とコミット
`.env` などの機密情報が含まれていないことを確実に確認してからコミットします。

```powershell
# 作業ディレクトリに移動
cd d:\02_work_04_開発リポジトリ\03_tool_04_github_description

# 除外対象の確認 (.env がステージング対象外であることを確認)
git status --ignored

# ステージングとコミット
git add .
git commit -m "feat: configure subpath support for /tool/github-description and cloudflare tunnel"
```

### 1-3. GitHub PublicリポジトリへのPush
```powershell
# mainブランチへPush
git push origin main
```

---

## STEP 2: アーキテクチャ判定結果と設計理由

### 2-1. 判定結果: 【区分4: Webアプリ（軽量〜中規模、API、セッション管理型）】
自宅Ubuntu Server（既存Apache2稼働機）配下の独立したWebアプリケーションとして構成します。

### 2-2. 設計理由と選定技術
1. **既存稼働保護とポート分離**:
   - 既存のWebサイトやサービスに一切干渉しないよう、独立した未使用ポート `8085` を割り当てます。
   - バックエンドプロセスは `127.0.0.1:8085`（ローカルループバック）にのみバインドし、自宅ルーターのポート開放（Port Forwarding）は行いません。
2. **Cloudflare Tunnel によるセキュア公開**:
   - 自宅サーバーのグローバルIPを完全に秘匿し、CloudflareのEdgeネットワーク（DDoS防御、常時SSL/TLS）経由で `https://zyuuuukak1n.dev/tool/github-description/` を安全に外部公開します。
3. **tool ディレクトリ配下（サブパス）への適応設計**:
   - アプリケーション側のフロントエンド（アセットリンク、APIエンドポイント呼び出し）を相対パスおよび動的ベースパス解決方式で実装。
   - `/tool/github-description/` という深い階層配下でも、ルーティングや画像・CSSの読み込みが一切壊れない設計を採用しています。
4. **systemd による自動再起動・クラッシュ対策**:
   - サーバー再起動時や不意のクラッシュ発生時にも自律復帰できるよう、systemdサービスユニット（`Restart=always`, `RestartSec=5s`）を作成してデーモン管理します。
5. **防御的設計と0コスト運用（ハイブリッドAI）**:
   - Google Gemini API / OpenAI API キーを設定すれば最新LLMで高精度な説明文が生成可能。
   - APIキー未設定やAPI障害時でも内蔵の「スマートヒューリスティック抽出エンジン」が自律動作し、完全無料・無停止での運用を実現します。

---

## STEP 3: 実行・ホスティング環境のセットアップ（Ubuntu Server + Apache2）

自宅のUbuntu ServerにSSH接続し、以下のコマンドを順次実行して環境を構築します。

### 3-1. 必要なパッケージのインストール
```bash
# パッケージリスト更新と必要ツールのインストール
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git apache2

# Apache2のリバースプロキシ用モジュールを有効化
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
sudo a2enmod rewrite

# Apache2の構文チェックとリロード
sudo apache2ctl configtest
sudo systemctl reload apache2
```

### 3-2. toolディレクトリの作成とソースコードの取得
ツール群の配置先として `/var/www/tool/github-description` を作成します。

```bash
# 親ディレクトリおよび配置ディレクトリの作成
sudo mkdir -p /var/www/tool/github-description
sudo chown -R $USER:$USER /var/www/tool

# リポジトリのクローン
git clone https://github.com/KeiStan26/github-description-generator.git /var/www/tool/github-description
cd /var/www/tool/github-description

# Python仮想環境 (venv) の作成
python3 -m venv venv

# 依存ライブラリのインストール
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

### 3-3. systemd サービスユニットの登録と起動
リポジトリ内に含まれる `deploy/github-description.service` をsystemdへ配置します。

```bash
# サービスファイルのコピー
sudo cp deploy/github-description.service /etc/systemd/system/github-description.service

# サービスファイル内のユーザー名（User=ubuntu 等）を確認・編集
sudo nano /etc/systemd/system/github-description.service

# systemd デーモンのリロード
sudo systemctl daemon-reload

# サービスの有効化（OS起動時の自動起動）と即時起動
sudo systemctl enable github-description.service
sudo systemctl start github-description.service

# 起動ステータスの確認 (active (running) になっていればOK)
sudo systemctl status github-description.service
```

### 3-4. Apache2 リバースプロキシの設定（/tool/github-description 配下）
既存の `zyuuuukak1n.dev` の設定方法に合わせて、以下の**いずれか**を選択して設定します。

#### 【設定方法A】既存の zyuuuukak1n.dev 用 VirtualHost 設定に追記する場合（推奨）
すでに `zyuuuukak1n.dev` 向けの設定ファイル（例: `/etc/apache2/sites-available/zyuuuukak1n.dev.conf` または `000-default.conf`）がある場合、その `<VirtualHost *:80>`（または `*:443`）ブロック内に以下を追記します。

```apache
    # --- GitHub Description Generator (ポート8085へのリバースプロキシ) ---
    ProxyPreserveHost On
    ProxyRequests Off

    <Proxy *>
        Require all granted
    </Proxy>

    # 末尾スラッシュを補正 (/tool/github-description -> /tool/github-description/)
    RewriteEngine On
    RewriteRule ^/tool/github-description$ /tool/github-description/ [R=301,L]

    # バックエンド (127.0.0.1:8085) へのフォワード
    ProxyPass /tool/github-description/ http://127.0.0.1:8085/ connectiontimeout=10 timeout=60
    ProxyPassReverse /tool/github-description/ http://127.0.0.1:8085/

    RequestHeader set X-Forwarded-Prefix "/tool/github-description"
    RequestHeader set X-Forwarded-Proto "https"
```

#### 【設定方法B】独立した設定ファイル（github-description.conf）として追加する場合
```bash
# 設定ファイルの配置
sudo cp deploy/apache2.conf /etc/apache2/sites-available/github-description.conf

# サイトの有効化
sudo a2ensite github-description.conf
```

#### 反映と構文チェック
```bash
# 構文チェック (Syntax OK を確認)
sudo apache2ctl configtest

# Apache2の再読み込み
sudo systemctl reload apache2
```

---

## STEP 4: 本番環境変数（.env）の配置とセキュリティ設定

### 4-1. .env ファイルの生成と権限保護
`.env.example` を元に、本番専用の `.env` ファイルを作成します。

```bash
cd /var/www/tool/github-description
cp .env.example .env

# パーミッションを厳格化 (所有者のみ読み書き可能に設定)
chmod 600 .env
```

### 4-2. パラメータの編集
```bash
nano .env
```

設定内容の確認・編集：
```ini
# 本番運用モード
APP_ENV=production

# サーバーバインド設定 (127.0.0.1で固定)
HOST=127.0.0.1
PORT=8085

# サブパス配信設定 (/tool/github-description を指定)
ROOT_PATH=/tool/github-description

# CORS設定 (公開ドメインを許可)
CORS_ORIGINS=https://zyuuuukak1n.dev,http://localhost:8085

# ログレベル
LOG_LEVEL=INFO

# レート制限 (1IPあたり毎分60リクエスト)
RATE_LIMIT_PER_MINUTE=60

# GitHubトークン (任意: 未認証レートリミット上限を緩和したい場合に設定)
GITHUB_DEFAULT_TOKEN=

# AIプロバイダー設定 (任意: 空欄の場合はビルトインのスマート分析エンジンが自動動作)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

編集完了後、サービスを再起動して設定を反映します。
```bash
sudo systemctl restart github-description.service
```

---

## STEP 5: Cloudflare Tunnel によるドメイン公開設定（zyuuuukak1n.dev）

お使いの Cloudflare Tunnel（`cloudflared`）の設定方式（**Webダッシュボード方式** または **設定ファイル config.yml 方式**）に合わせて確認・設定します。

### パターン1: Apache2経由でトンネル接続している場合（最も一般的・変更不要）
すでに Cloudflare Tunnel が `zyuuuukak1n.dev` 宛のトラフィック全体を自宅サーバーの Apache2（例: `http://localhost:80`）へ転送している場合：
- **Cloudflare側の追加設定は一切不要です！**
- STEP 3 で Apache2 に追加した `ProxyPass /tool/github-description/ http://127.0.0.1:8085/` により、ブラウザから `https://zyuuuukak1n.dev/tool/github-description/` にアクセスするだけで自動的に本アプリへ転送されます。

---

### パターン2: Cloudflare Zero Trust ダッシュボード（GUI）でパスマッピングする場合
Cloudflare Zero Trust ダッシュボードでホスト名ごとにルーティングを管理している場合の手順です。

1. **[Cloudflare Zero Trust ダッシュボード](https://one.dash.cloudflare.com/)** にログイン。
2. 左メニューの **Networks** > **Tunnels** を開く。
3. 稼働中のトンネルを選択し、**Configure** をクリック。
4. **Public Hostname** タブを開く。
5. **Add a public hostname** をクリックし、以下を入力：
   - **Subdomain**: （空欄のまま、またはルート）
   - **Domain**: `zyuuuukak1n.dev`
   - **Path**: `tool/github-description*`
   - **Type**: `HTTP`
   - **URL**: `localhost:8085` （または Apache経由の場合は `localhost:80`）
6. **Save hostname** をクリックして保存します。

---

### パターン3: ローカル設定ファイル（`config.yml`）で直接トンネルを管理している場合
サーバー上の `/etc/cloudflared/config.yml`（または `~/.cloudflared/config.yml`）に直接パスルーティングを追加する場合の手順です。

```yaml
# /etc/cloudflared/config.yml の編集例
tunnel: <TUNNEL-UUID>
credentials-file: /etc/cloudflared/<TUNNEL-UUID>.json

ingress:
  # GitHub Description Generator (ポート8085へ直接ルーティングする場合)
  - hostname: zyuuuukak1n.dev
    path: ^/tool/github-description.*
    service: http://127.0.0.1:8085

  # 既存のウェブサイト / Apache2 へのルーティング
  - hostname: zyuuuukak1n.dev
    service: http://127.0.0.1:80

  # Catch-all ルール (必須)
  - service: http_status:404
```

設定を更新後、cloudflaredサービスを再起動します。
```bash
sudo systemctl restart cloudflared
```

---

## STEP 6: CI/CD（GitHub Actions）の設定

リポジトリの `.github/workflows/main.yml` により、コミットがPushされるたびに自動で構文チェック（Ruff）とテスト（Pytest）が実行されます。

### 6-1. GitHub Secrets の登録（任意）
本アプリは防御的設計により、シークレットなしでもヒューリスティックエンジンでテストが100%通過するように設計されています。
もしCI上で本物のGemini APIテスト等を実施したい場合のみ、GitHubリポジトリ画面で以下を登録します。

1. GitHubリポジトリ画面の **Settings** > **Secrets and variables** > **Actions** を開く。
2. **New repository secret** をクリック。
   - `GEMINI_API_KEY`: Google AI Studioで取得したAPIキー（任意）
   - `GITHUB_DEFAULT_TOKEN`: GitHub Personal Access Token（任意）

### 6-2. CIパイプラインの動作確認
1. コードをPushした後、GitHubの **Actions** タブを開きます。
2. `CI / Test and Code Quality` ワークフローが自動トリガーされ、Lint（Ruff）およびPython 3.10/3.11/3.12でのテストがすべてグリーン（Pass）になることを確認します。

---

## STEP 7: 動作確認・ヘルスチェック・運用保守

サーバー上およびインターネット（Cloudflare経由）から正常に動作しているか、包括的に検証します。

### 7-1. ローカルバックエンドの直接ヘルスチェック
まず、FastAPI (ポート8085) が内部で正常に応答しているか確認します。

```bash
curl -s http://127.0.0.1:8085/health | jq .
```
**期待される出力例:**
```json
{
  "status": "healthy",
  "app": "GitHub Description Generator",
  "version": "1.0.0",
  "environment": "production",
  "ai_engine": "heuristic"
}
```

### 7-2. Apache2 経由のサブパス疎通確認
サーバー内部から Apache2 のサブパス宛にリクエストを送信します。

```bash
# HTTPステータスコード 200 が返ることを確認
curl -I http://localhost/tool/github-description/
```

### 7-3. 公開ドメイン（Cloudflare経由）からのアクセス確認
外部ネットワークまたはブラウザから、本番URLへアクセスします。

- **ブラウザでアクセス**:
  👉 **`https://zyuuuukak1n.dev/tool/github-description/`**
- **curlで確認**:
  ```bash
  curl -I https://zyuuuukak1n.dev/tool/github-description/
  ```
  `HTTP/2 200` が返れば、Cloudflare Tunnel -> Apache2 -> FastAPI が完全に疎通しています。

### 7-4. ログ監視とトラブルシューティングコマンド

```bash
# アプリケーションのリアルタイムログ確認 (journald)
sudo journalctl -u github-description.service -f

# Apache2のアクセスログ・エラーログ確認
sudo tail -f /var/log/apache2/error.log
sudo tail -f /var/log/apache2/access.log

# Cloudflare Tunnelのログ確認
sudo journalctl -u cloudflared -f

# サービスプロセスの停止 / 再起動 / 状態確認
sudo systemctl restart github-description.service
sudo systemctl status github-description.service
```

### 7-5. アプリケーションのアップデート手順
機能追加や修正を反映する際は、以下のコマンドを実行します。

```bash
cd /var/www/tool/github-description
git pull origin main
./venv/bin/pip install -r requirements.txt
sudo systemctl restart github-description.service
```

以上で、`zyuuuukak1n.dev/tool/github-description/` への本番公開と運用準備はすべて完了です。
