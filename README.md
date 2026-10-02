# GitHub Description Generator ✨

[![CI / Test and Code Quality](https://github.com/owner/github-description-generator/actions/workflows/main.yml/badge.svg)](https://github.com/owner/github-description-generator/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
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
  - Google Gemini API (`gemini-2.5-flash` / `gemini-1.5-flash`) または OpenAI API に対応。
  - APIキーが未設定、または外部API障害時でも**スマートヒューリスティック抽出エンジン**へ自動フォールバックするため、完全無料かつ安定して動作します。
- **万全のセキュリティと防御的設計**:
  - 機密情報（PATやAPIキー）のハードコード禁止、サーバーログでの自動マスキング処理。
  - パストラバーサルやSSRF（Server-Side Request Forgery）を防止する厳格な正規表現バリデーション。
  - 内部スタックトレースのクライアント非漏洩設計。

---

## 🛠 技術スタック

| レイヤー | 技術 |
|---|---|
| **バックエンド** | Python 3.10+, FastAPI, Uvicorn, Pydantic v2 |
| **HTTPクライアント** | HTTPX (非同期通信) |
| **AI / NLP** | Google Gemini REST API / OpenAI API / スマートヒューリスティック自然言語抽出 |
| **フロントエンド** | HTML5, Vanilla CSS (Dark Aesthetic / Glassmorphism), Modern JavaScript |
| **セキュリティ・レート制限** | SlowAPI, カスタムログマスキングフィルター, セキュリティヘッダー |
| **テスト & CI** | Pytest, Pytest-Asyncio, Ruff, GitHub Actions |
| **本番インフラ** | Ubuntu Server, Apache2 (Reverse Proxy), systemd デーモン |

---

## 🚀 クイックスタート (ローカル環境)

### 1. 必要要件
- Python 3.10 以上
- Git

### 2. リポジトリのクローンと環境構築
```bash
git clone https://github.com/your-username/github-description.git
cd github-description

# 仮想環境の作成と有効化
python -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# 依存パッケージのインストール
pip install -r requirements.txt
```

### 3. 環境設定
`.env.example` をコピーして `.env` を作成します。
```bash
cp .env.example .env
```
※ APIキー（`GEMINI_API_KEY` 等）は任意です。空欄のままでもスマート分析エンジンにより動作します。

### 4. サーバー起動
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8085 --reload
```
ブラウザで `http://localhost:8085` にアクセスしてください。

---

## 🧪 テストの実行

正常系、境界値（350文字制限）、異常系（不正URL、存在しないリポジトリ）、セキュリティ（パストラバーサル、トークン未指定による権限外アクセスの拒否）を網羅したテストスイートを実行します。

```bash
# テストの実行
pytest -v

# コード品質チェック (Ruff)
ruff check .
```

---

## 🌐 本番サーバー（Ubuntu + Apache2）へのデプロイ

詳細なセットアップ手順、Apache2のリバースプロキシ設定、systemdによるデーモン化、および運用コマンドについては、付属の [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) をご参照ください。

---

## 📄 ライセンス

本ソフトウェアは [MIT License](LICENSE) の下で公開されています。  
Copyright (c) 2026 慧すたん
