# LupinusPrivate 公開構造リファクタ計画書

作成日: 2026-05-31  
担当: リリィ（サイト管理人）  
目的: GitHub Pages 公開に向け、`portfolio/` 配下を**リポジトリ直下**へ昇格させる。

---

## 0. 現状サマリ

- リポジトリ: `C:\LupinusPrivate`（GitHub: `LupinusRossetti/LupinusPrivate`, branch `main`, remote 設定済）
- `.git` 既存 / `.gitignore` 既存（サムネキャッシュ`*.gemini`等を除外済） / `README.md` は `portfolio/README.md` にのみ存在（リポ直下にはまだ無し）
- 公開対象は `portfolio/` 配下：
  - HTML: `index.html` / `portfolio.html` / `archive.html`
  - CSS: `assets/css/site.css`
  - 画像: `images/image/...`（character / avatars / 等）
  - ブログ生成物: `blog/index.html` / `blog/posts/*.html` / `blog/icons/*.png` / `blog/thumbs/*.png`
  - データ: `data/archive.json`
  - スクリプト: `build_blog.py` / `make_thumb.py`（直下にあるが原則 Pages では参照されない）
  - `__pycache__/`

- 未コミット差分:
  - `M portfolio/blog/thumbs/2026-05-31_演出の引き算.png`（Gemini再生成中で中断）
  - `?? .claude/`（既存 `.gitignore` に追記推奨）

---

## 1. ゴール

`https://lupinusrossetti.github.io/LupinusPrivate/` のルート直下から `index.html` が引けるようにする。  
=> **`portfolio/` 配下のサイト資産をリポジトリ直下に移動**する。

---

## 2. 移動するもの（portfolio/ → リポジトリ直下）

| 種別 | from | to |
|---|---|---|
| ページ | `portfolio/index.html` | `index.html` |
| ページ | `portfolio/portfolio.html` | `portfolio.html` |
| ページ | `portfolio/archive.html` | `archive.html` |
| CSS | `portfolio/assets/` | `assets/` |
| 画像 | `portfolio/images/` | `images/` |
| データ | `portfolio/data/` | `data/` |
| ブログ生成物 | `portfolio/blog/` | `blog/` |
| ビルダ | `portfolio/build_blog.py` | `build_blog.py` |
| ビルダ | `portfolio/make_thumb.py` | `make_thumb.py` |
| README | `portfolio/README.md` | `README.md`（リポ直下を正本に） |

**残すもの** : `Doc/` / `persona_rules.md` / `.git` / `.gitignore` / `.claude/`（ignore対象）

**削除するもの** : 空になった `portfolio/` / `portfolio/__pycache__/`（再生成可）

---

## 3. 相対パス影響範囲（調査結果）

サイト内のリンクは**ほぼ全て階層維持の相対パス**なので、`portfolio/` ごと中身を平行移動すれば壊れない。

### 3-1. HTML（壊れない）
- `index.html` / `portfolio.html` / `archive.html` の参照:  
  `assets/css/site.css` / `images/image/...` / `portfolio.html` / `blog/index.html` / `blog/posts/...html` / `blog/thumbs/...png` ── すべて**同一階層内**の相対パスなのでそのまま動く。
- `blog/posts/*.html` の参照:  
  `../icons/...png`（サムネ・吹き出しアイコン） / `../thumbs/...png` / `../index.html`（日記一覧） / `../../index.html`（Home）── これも**ディレクトリ構造を保ったまま** `portfolio/` ごと上へ持ち上げるので**そのまま動く**。

### 3-2. CSS
- `assets/css/site.css` 内の `url(...)` 参照は `../../images/...` 形式（assets/css → 上に2階層→images）。階層を保ったまま移動するので問題なし。  
  （※実調査では `portfolio/` 文字列の出現 0 件）

### 3-3. Python（**1か所だけ要対応**）
- `build_blog.py:33` ： `SITE_DIR = Path(__file__).resolve().parent  # portfolio/`  
  → スクリプト自体をリポ直下に置けば `SITE_DIR = リポ直下` となり**コード変更不要**。コメントの `# portfolio/` は誤誘導なので**書き換える**。
- `build_blog.py:179` ： ナビ生成 `f'<a href="{prefix}portfolio.html"`  
  → ファイル名 `portfolio.html` であってフォルダ名ではない（ポートフォリオページ）。**変更不要**。
- `make_thumb.py` ： `portfolio` 文字列出現 0 件。**変更不要**。

### 3-4. README
- `portfolio/README.md` 内のコード例は `cd portfolio` 前提。**リポ直下を正本に書き換える**（`cd LupinusPrivate` または不要）。

### 3-5. その他外部
- `Doc/` / `persona_rules.md` はサイトから参照されない（探索済）。影響なし。

---

## 4. build_blog.py / make_thumb.py の出力先

`SITE_DIR = Path(__file__).resolve().parent` 設計のおかげで、**スクリプトを直下に移すだけで出力先も自動的に直下** `blog/` 配下になる。出力先パスは固定文字列でハードコードされておらず、書き換え不要。

唯一書き換えるのは `# portfolio/` のコメントのみ。

---

## 5. 実行手順案（承認後に実施）

1. ローカル http サーバ停止確認
2. `.gitignore` に `.claude/` と `__pycache__/`（既に有り）を追記
3. ファイル移動（`git mv` で履歴を保つ）  
   ```
   git mv portfolio/index.html .
   git mv portfolio/portfolio.html .
   git mv portfolio/archive.html .
   git mv portfolio/assets assets
   git mv portfolio/images images
   git mv portfolio/data data
   git mv portfolio/blog blog
   git mv portfolio/build_blog.py .
   git mv portfolio/make_thumb.py .
   git mv portfolio/README.md README.md
   ```
4. `portfolio/__pycache__/` を削除（追跡外）
5. 空になった `portfolio/` を `rmdir`
6. `build_blog.py:33` のコメントを `# リポジトリ直下` に修正
7. README を新構成（リポ直下基準）に書き換え
8. ローカル検証: `python -m http.server 8765` → 全ページ＋ブログ記事＋サムネ＋アーカイブ動作確認
9. `python build_blog.py` 再実行で再生成しても差分が出ないこと確認
10. （ルピナス承認後）`git add` → commit → push → GitHub Pages 設定（Settings → Pages → Source: `main` / root）

---

## 6. リスク評価

| リスク | 深刻度 | 対策 |
|---|---|---|
| 内部相対パスの想定外参照漏れ | 低 | 移動後ローカルサーバで全ページ目視＋devtools のネットワークタブで 404 検査 |
| `git mv` でWindowsの大文字小文字違いリネーム不可 | 低 | 名前変更は無し（移動のみ）なので発生せず |
| GitHub Pages の jekyll 干渉（`_` 始まりファイル無視） | 低 | アンダースコア始まりのファイル無し。念のため `.nojekyll` をリポ直下に置く（**追加推奨**） |
| 公開後にprivate情報が見えてしまう | 中 | `Doc/` `persona_rules.md` `.claude/` は `.gitignore` 済みか確認（`Doc/` `persona_rules.md` は現在トラッキング状態。**公開可否要確認**） |
| Geminiサムネ中断状態のまま push | 中 | サムネ再生成完了まで push を保留 |
| ローカルとGitHubでの大小文字差 | 低 | 既存ファイル名は全て区別なしで安全 |

---

## 7. ルピナスへの確認事項

1. **移動実行の最終承認**（手順5）  
2. `Doc/` ディレクトリと `persona_rules.md` は**公開リポジトリに残してよいか**（中身は内部メモ寄り）  
   → 残したくない場合は `.gitignore` 追加＋`git rm --cached` 案内します  
3. README は portfolio/ 内のものをリポ直下に上げて書き換える方針でよいか  
4. `.nojekyll` 追加してよいか（GitHub Pages の Jekyll 処理を無効化、純静的サイトでは標準的）  
5. **Gemini サムネ再開のタイミング**：先に構造リファクタを片付けるか、サムネ完成を待ってからリファクタするか  
   → 推奨：リファクタは別系統の作業なので**サムネ完成を待たずに先に進めて問題なし**。サムネは独立Chromeで並行作業OK  
6. GitHub Pages の **公開URLパス**は `https://lupinusrossetti.github.io/LupinusPrivate/` でよいか（カスタムドメインの予定有無）

---

## 8. GitHub Pages 公開手順概要

1. リファクタ完了＆ローカル検証OK
2. ルピナスの「push して」指示
3. `git push origin main`
4. GitHub の `Settings → Pages` で:  
   - Source: `Deploy from a branch`  
   - Branch: `main` / `/ (root)`  
   - Save
5. 1〜2分後に `https://lupinusrossetti.github.io/LupinusPrivate/` が公開
6. `index.html` / `blog/index.html` / `archive.html` / 任意の記事を実URLで巡回検証
7. 以降の更新フロー: 日記mdを書く → `python build_blog.py` → `git add/commit/push` → 数分で反映

---

以上。ルピナスの承認が出次第、手順5から実行します。
