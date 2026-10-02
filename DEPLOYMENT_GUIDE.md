# 手動オペレーション手順書（DEPLOYMENT_GUIDE.md）

本ドキュメントは、**GitHub Description Generator** のコード生成完了状態から、GitHubへのPublic公開、自宅Ubuntu Server（Apache2環境）への配置、systemdによるデーモン化、および本番稼働・ヘルスチェックに至る全手順を解説したステップバイステップガイドです。

---

## 目次
- [STEP 1: GitHubリポジトリの初期化とPush](#step-1-githubリポジトリの初期化とpush)
- [STEP 2: アーキテクチャ判定結果と設計理由](#step-2-アーキテクチャ判定結果と設計理由)
- [STEP 3: 実行・ホスティング環境のセットアップ（Ubuntu Server + Apache2）](#step-3-実行ホスティング環境のセットアップubuntu-server--apache2)
- [STEP 4: 本番環境変数（.env）の配置とセキュリティ設定](#step-4-本番環境変数の配置とセキュリティ設定)
- [STEP 5: CI/CD（GitHub Actions）の設定](#step-5-cicdgithub-actionsの設定)
- [STEP 6: 動作確認・ヘルスチェック・運用保守](#step-6-動作確認ヘルスチェック運用保守)

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

### 1-2. .gitignore の確認と初回コミット
`.env` などの機密情報が含まれていないことを確実に確認してからコミットします。

```powershell
# 作業ディレクトリに移動
cd d:\02_work_04_開発リポジトリ\03_tool_04_github_description

# Gitリポジトリの初期化
git init -b main

# 除外対象の確認 (.env がステージングされないことを確認)
git status --ignored

# 全ファイルをステージングして初回コミット
git add .
git commit -m "feat: initial commit for GitHub Description Generator (FastAPI + Modern Web UI)"
```

### 1-3. GitHub Publicリポジトリの作成とPush
GitHubのWeb画面または `gh` CLIで空のPublicリポジトリを作成後、リモートを追加してPushします。

```powershell
# リモートリポジトリの登録 (your-username をご自身のアカウント名に置換)
git remote add origin https://github.com/<your-username>/github-description-generator.git

# mainブランチへPush
git push -u origin main
```

---

## STEP 2: アーキテクチャ判定結果と設計理由

### 2-1. 判定結果: 【区分4: Webアプリ（軽量〜中規模、API、セッション管理型）】
自宅Ubuntu Server（既存Apache2稼働機）配下の独立したWebアプリケーションとして構成します。

### 2-2. 設計理由と選定技術
1. **既存稼働保護とポート分離**:
   - 既存のWebサイトやサービスに一切干渉しないよう、独立した未使用ポート `8085`（環境変数で任意に変更可能）を割り当てます。
   - バックエンドプロセスは `127.0.0.1:8085`（ローカルループバック）にのみバインドし、外部ネットワークに直接ポートを晒さない安全な構成とします。
2. **Apache2 リバースプロキシ連携**:
   - 外部からのアクセスは既存のApache2（ポート80/443）が受け取り、仮想ホスト設定（`/etc/apache2/sites-available/github-description.conf`）経由で `http://127.0.0.1:8085/` へリバースプロキシ転送（`ProxyPass`）します。
3. **systemd による自動再起動・クラッシュ対策**:
   - サーバー再起動時や不意のクラッシュ発生時にも自律復帰できるよう、systemdサービスユニット（`Restart=always`, `RestartSec=5s`）を作成してデーモン管理します。
4. **防御的設計と0コスト運用（ハイブリッドAI）**:
   - Google Gemini API / OpenAI API キーを設定すれば最新LLMで高精度な説明文が生成可能。
   - APIキー未設定やAPI障害時でも内蔵の「スマートヒューリスティック抽出エンジン」が自律動作し、完全無料・無停止での運用を実現します。

---

## STEP 3: 実行・ホスティング環境のセットアップ（Ubuntu Server + Apache2）

自宅のUbuntu ServerにSSH接続し、以下のコマンドを順次実行して環境を構築します。

### 3-1. 必要なパッケージのインストール
Python 3、仮想環境ツール、およびApache2のプロキシモジュールを準備します。

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

### 3-2. デプロイ先ディレクトリの作成とソースコードの取得
本番の標準的な配置場所として `/var/www/github-description` を使用します。

```bash
# 配置先ディレクトリの作成（所有者を現在のログインユーザーに変更）
sudo mkdir -p /var/www/github-description
sudo chown -R $USER:$USER /var/www/github-description

# リポジトリのクローン
git clone https://github.com/<your-username>/github-description-generator.git /var/www/github-description
cd /var/www/github-description

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

# サービスファイル内のユーザー名・パスが環境に合致しているか確認（必要に応じて編集）
# デフォルト: User=ubuntu, WorkingDirectory=/var/www/github-description
sudo nano /etc/systemd/system/github-description.service

# systemd デーモンのリロード
sudo systemctl daemon-reload

# サービスの有効化（OS起動時の自動起動）と即時起動
sudo systemctl enable github-description.service
sudo systemctl start github-description.service

# 起動ステータスの確認
sudo systemctl status github-description.service
```

### 3-4. Apache2 仮想ホスト（リバースプロキシ）の設定
リポジトリ内の `deploy/apache2.conf` をApache2のサイト設定へコピーし、有効化します。

```bash
# 設定ファイルの配置
sudo cp deploy/apache2.conf /etc/apache2/sites-available/github-description.conf

# ドメイン名やホスト名を編集（例: ServerName github-desc.local や ご自身のドメイン名）
sudo nano /etc/apache2/sites-available/github-description.conf

# サイトの有効化
sudo a2ensite github-description.conf

# 構文チェック（Syntax OK と出ることを確認）
sudo apache2ctl configtest

# Apache2の設定をリロード
sudo systemctl reload apache2
```

> **【既存環境保護のポイント】**
> - `a2ensite github-description.conf` は独立した設定ファイルを読み込むため、既存のサイト（`000-default.conf` や他アプリの設定）には一切影響を与えません。
> - 万が一設定を戻したい場合は `sudo a2dissite github-description.conf && sudo systemctl reload apache2` で即座に切り離しが可能です。

---

## STEP 4: 本番環境変数（.env）の配置とセキュリティ設定

### 4-1. .env ファイルの生成と権限保護
`.env.example` を元に、本番専用の `.env` ファイルを作成します。

```bash
cd /var/www/github-description
cp .env.example .env

# パーミッションを厳格化 (所有者のみ読み書き可能に設定)
chmod 600 .env
```

### 4-2. パラメータの編集
```bash
nano .env
```

設定内容の例：
```ini
# 本番運用モード
APP_ENV=production

# サーバーバインド設定 (Apache2からの転送を受けるため127.0.0.1で固定)
HOST=127.0.0.1
PORT=8085

# CORS設定 (ブラウザからのアクセス元ドメインを指定。カンマ区切り可)
CORS_ORIGINS=*

# ログレベル (本番は INFO を推奨)
LOG_LEVEL=INFO

# レート制限 (過剰アクセス対策: 1IPあたり毎分60リクエスト)
RATE_LIMIT_PER_MINUTE=60

# GitHubトークン (任意: 未認証60回/時のレートリミットを回避したい場合に設定)
GITHUB_DEFAULT_TOKEN=

# AIプロバイダー設定 (任意: 空欄の場合はビルトインのスマート分析エンジンが稼働)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

編集完了後、設定を反映するためにサービスを再起動します。
```bash
sudo systemctl restart github-description.service
```

---

## STEP 5: CI/CD（GitHub Actions）の設定

リポジトリの `.github/workflows/main.yml` により、コミットがPushされるたびに自動で構文チェック（Ruff）とテスト（Pytest）が実行されます。

### 5-1. GitHub Secrets の登録（必要な場合）
本アプリは防御的設計により、シークレットなしでもヒューリスティックエンジンでテストが100%通過するように設計されています。
もしCI上で本物のGemini APIテスト等を実施したい場合のみ、GitHubリポジトリ画面で以下を登録します。

1. GitHubリポジトリ画面の **Settings** > **Secrets and variables** > **Actions** を開く。
2. **New repository secret** をクリック。
   - `GEMINI_API_KEY`: Google AI Studioで取得したAPIキー（任意）
   - `GITHUB_DEFAULT_TOKEN`: GitHub Personal Access Token（任意）

### 5-2. CIパイプラインの動作確認
1. コードをPushした後、GitHubの **Actions** タブを開きます。
2. `CI / Test and Code Quality` ワークフローが自動トリガーされ、Lint（Ruff）およびPython 3.10/3.11/3.12でのテストがすべてグリーン（Pass）になることを確認します。

---

## STEP 6: 動作確認・ヘルスチェック・運用保守

サーバー上で正常に動作しているか、以下のコマンドで包括的に検証します。

### 6-1. ローカルバックエンドの直接ヘルスチェック
まず、FastAPI (ポート8085) が正常に応答しているか確認します。

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

### 6-2. Apache2 リバースプロキシ経由の疎通確認
Apache2経由でWebページおよびAPIが正常にルーティングされているか確認します。

```bash
# HTTPステータスコード 200 が返ることを確認
curl -I http://localhost/
```

### 6-3. リポジトリ分析APIのコマンドライン実行テスト
パブリックリポジトリ（例: `octocat/Hello-World`）の分析リクエストを送信してレスポンスを確認します。

```bash
curl -X POST http://127.0.0.1:8085/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo_input": "octocat/Hello-World",
    "language": "ja",
    "tone": "concise",
    "target_char_limit": 350
  }' | jq .
```

### 6-4. ログ監視とトラブルシューティングコマンド

```bash
# アプリケーションのリアルタイムログ確認 (journald)
sudo journalctl -u github-description.service -f

# Apache2のアクセスログ・エラーログ確認
sudo tail -f /var/log/apache2/github_description_access.log
sudo tail -f /var/log/apache2/github_description_error.log

# サービスプロセスの停止 / 再起動 / 状態確認
sudo systemctl stop github-description.service
sudo systemctl restart github-description.service
sudo systemctl status github-description.service
```

### 6-5. アプリケーションのアップデート手順
機能追加や修正を反映する際は、以下の3ステップで完了します。

```bash
cd /var/www/github-description
git pull origin main
./venv/bin/pip install -r requirements.txt
sudo systemctl restart github-description.service
```

以上で、GitHub Description Generator の本番デプロイと運用準備はすべて完了です。
ブラウザから設定したドメインまたはサーバーIPにアクセスし、快適なリポジトリ説明文生成をお楽しみください。
