# GitHub Description Generator ✨

[![CI / Test and Code Quality](https://github.com/zyuuuukak1n/github-description-generator/actions/workflows/main.yml/badge.svg)](https://github.com/zyuuuukak1n/github-description-generator/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](compose.yaml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)

GitHubのパブリックリポジトリの内容・README・技術スタックを自動解析し、GitHubの仕様である**350文字以内**に最適化された高品質な説明文（Description）とトピックタグ（Topics）を生成・直接設定するWebアプリケーションです。

---

## 🌟 主な機能

- **リポジトリ自動解析**:
  - リポジトリURLまたは `owner/repo` を入力するだけで、README、ファイル構造、主言語、スター数等を高速取得。
- **3つのトーンで説明文を即時生成**:
  - **簡潔 (Concise)**: 1〜2文でリポジトリの目的とスタックを的確に伝える標準スタイル。
  - **訴求 (Catchy)**: 開発者の目を惹きつける価値訴求型スタイル。
  - **技術 (Technical)**: アーキテクチャと採用技術にフォーカスした開発者向けスタイル。
- **GitHub制限（350文字）の厳格な遵守**:
  - 生成された説明文はGitHub Descriptionの上限値（350文字）を絶対に超えないよう自動整形・トリミング。
  - リアルタイム文字数カウンター付きのエディタで自由に推敲可能。
- **推奨トピックタグの自動提案**:
  - 構成ファイル（Dockerfile, pyproject.toml, package.json等）やREADMEからトピックを自動抽出。ワンクリックで選択・解除可能。
- **ワンクリック直接反映 & クリップボードコピー**:
  - GitHub Personal Access Token (PAT) を指定することで、ブラウザから該当リポジトリのDescriptionとTopicsを直接更新。
  - PATを使わず手動設定したい場合でも「クリップボードにコピー」で即座に貼り付け可能。
- **ハイブリッドAI & 0コスト稼働**:
  - Google Gemini API (`gemini-2.5-flash`) または OpenAI API に対応。
  - APIキーが未設定、または外部API障害時でも**スマートヒューリスティック抽出エンジン**へ自動フォールバックするため、完全無料かつ安定して動作します。
- **万全のセキュリティと防御的設計**:
  - 機密情報（PATやAPIキー）のハードコード禁止、サーバーログでの自動マスキング処理。
  - パストラバーサルやSSRF（Server-Side Request Forgery）を防止する厳格な正規表現バリデーション。
  - 内部スタックトレースのクライアント非漏洩設計。
- **Docker一元管理 & 非rootコンテナ設計**:
  - `python:3.12-slim` ベースのマルチステージビルドによる軽量・堅牢なコンテナ。
  - コンテナ内非rootユーザー（`appuser`）実行、127.0.0.1ローカルループバックバインド。

---

## 🛠 技術スタック

| レイヤー | 技術 |
|---|---|
| **バックエンド** | Python 3.12, FastAPI, Uvicorn, Pydantic v2 |
| **HTTPクライアント** | HTTPX (非同期通信) |
| **AI / NLP** | Google Gemini REST API / OpenAI API / スマートヒューリスティック自然言語抽出 |
| **フロントエンド** | HTML5, Modern CSS (Glassmorphism / Dark Theme), Lucide Icons, Vanilla JS |
| **コンテナ・インフラ** | Docker, Docker Compose (`compose.yaml`), Apache2 (Reverse Proxy), Cloudflare Tunnel |
| **セキュリティ・レート制限** | SlowAPI, カスタムログマスキングフィルター, セキュリティヘッダー |
| **テスト & CI** | Pytest, Pytest-Asyncio, Ruff, GitHub Actions |

---

## 🚀 クイックスタート

### 方法A: Docker Compose での起動 (推奨・本番環境同等)

```bash
# 1. リポジトリのクローン
git clone https://github.com/zyuuuukak1n/github-description-generator.git
cd github-description-generator

# 2. 環境設定ファイルの作成
cp .env.example .env

# 3. コンテナのビルドと起動
docker compose up -d --build

# 4. ヘルスチェック確認
curl http://127.0.0.1:8085/health
```

ブラウザで `http://localhost:8085` にアクセスしてください。

---

### 方法B: ローカルPython環境での起動

```bash
# 1. 仮想環境の作成と有効化
python -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# 2. 依存パッケージのインストール
pip install -r requirements.txt

# 3. 環境設定
cp .env.example .env

# 4. サーバー起動
uvicorn app.main:app --host 127.0.0.1 --port 8085 --reload
```

---

## 🧪 テストの実行

正常系、境界値（350文字制限）、異常系（不正URL、存在しないリポジトリ）、セキュリティ（パストラバーサル、トークン未指定による権限外アクセスの拒否）を網羅したテストスイートを実行します。

```bash
# テストの実行
pytest -v

# コード品質・フォーマットチェック (Ruff)
ruff check .
```

---

## 📄 ライセンス

本プロジェクトは [MIT License](LICENSE) の下で公開されています。
Copyright (c) 2026 じゅーかきん
