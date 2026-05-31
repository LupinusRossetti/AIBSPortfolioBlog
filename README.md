# Lupinus Rossetti / AI Bloom Sisters — Portfolio & Diary Site

清楚・エレガントを基調にした、ルピナス・ロゼッティのポートフォリオ＋日記サイト。
純粋な静的サイト（HTML + CSS + 少量のJS）で、ビルドツールは Python のみ。

## 構成

```
portfolio/
├── index.html          # Home（ヒーロー・三姉妹・実績抜粋・最新日記・SNS）
├── portfolio.html      # 制作実績（アニメ/イラスト/スタンプ/音楽/開発/配信）
├── archive.html        # ← build_blog.py が生成。動画/配信アーカイブ
├── assets/css/site.css # デザインシステム（清楚エレガント）
├── build_blog.py       # 日記md → ブログHTML ＋ サムネ ＋ アーカイブ ビルダー
├── make_thumb.py       # 記事サムネ生成（手動/Gemini画像 ＞ 自動合成）
├── data/archive.json   # アーカイブの元データ（プラットフォーム別・手で追記）
├── blog/               # ← build_blog.py が生成（手で編集しない）
│   ├── index.html      #   日記一覧
│   ├── posts/*.html    #   各記事（吹き出しチャット＋記事整形）
│   ├── icons/*.png     #   キャラ表情アイコン48枚（同梱・自動コピー）
│   └── thumbs/*.png    #   記事サムネ（三姉妹が主役・1200x630）
└── images/             # サイト素材（キャラ・背景・装飾・スタンプ・avatars）
```

## 日記ブログのビルド

日記Markdownは `C:\ClaudeCode\note-diary\*.md`（`generate_diary.py` が生成）。
これを取り込んでHTML化する：

```bash
cd portfolio
python build_blog.py
```

- 会話パート（`![名前](icons/char_expr.png) **名前**（表情）` ＋ `> セリフ`）を、
  左右に振り分けた吹き出しチャットUIに変換（旧 `**名前**：セリフ` 形式にも対応）
- 記事まとめ（`##` 見出し・箇条書き・`>` 引用）は通常記事として整形
- `note-diary/icons/` の48枚を `blog/icons/` へ自動コピー
- `index.html` の最新日記カード（`<!--LATEST_DIARY-->` 区間）も自動更新

## 記事サムネ（三姉妹が主役）

各記事に 1200x630 のサムネを用意します。優先順位は3層：

1. **手動 / Gemini画像**（最優先）… `C:\ClaudeCode\note-diary\thumbs\{slug}.png`（または `{YYYY-MM-DD}.png`）。
   **いつものブラウザGemini**（gemini.google.com にログインして画像生成→保存）で作った画像はここに置く。
   置けば次のビルドでそのままサムネに採用される。
2. **Gemini API**（任意）… `GEMINI_API_KEY` 環境変数か `note-diary\.gemini_key.txt` があれば自動生成（無ければスキップ）。
3. **自動合成**（フォールバック）… 既存の三姉妹アイコン＋その日のタイトルで上品なサムネをPILで合成。
   キーも手動画像も無いとき、必ずこの層で成立する。

サムネはブログカード／記事ヘッダ／SNSシェア用のOG画像に使われる。

## 動画・配信アーカイブ

`data/archive.json` を編集して `python build_blog.py` で `archive.html` に反映。
プラットフォーム別（YouTube動画 / YouTube配信 / TikTok / Instagram）にセクション分け。
- YouTube は `id` を足すだけでサムネ自動表示（キー不要）。
- TikTok / Instagram は `profile_url` と、各 item に `url` ＋任意の `thumb`。
  まだURL未設定の枠は「準備中」表示。**TikTok/Instagramのアカウントが決まったらURLを教えてください**。

## ローカル確認

```bash
cd portfolio
python -m http.server 8765
# http://localhost:8765/ を開く
```

## 公開（予定）

GitHub Pages で配信予定（現在は未設定）。将来の自動化イメージ：

1. `generate_diary.py` が毎日 md を生成
2. `build_blog.py` で md → HTML ビルド
3. GitHub Actions で push → Pages へ自動デプロイ

## デザイン方針

- 白背景ベース、広い余白、繊細なフォント（Cormorant Garamond / Shippori Mincho /
  Zen Kaku Gothic New）＋ブランドの筆記体（Great Vibes）
- 差し色は三姉妹カラーを淡く：ルピナス=藤、アイリス=やわらかゴールド、フィオナ=ペールピンク
- ポップは挿絵・吹き出しなど局所のみ。レスポンシブ対応
