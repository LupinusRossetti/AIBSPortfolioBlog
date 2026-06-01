# -*- coding: utf-8 -*-
"""AIBS 日記 Markdown → 静的ブログHTML ビルダー。

C:\\ClaudeCode\\note-diary\\*.md を読み、清楚エレガントなブログページを生成する。
- 会話パート（アイコン＋名前＋セリフ）→ 左右に振り分けた吹き出しチャットUI
- 記事まとめ（## 見出し・箇条書き・> 引用）→ 通常記事として整形
- アイコン48枚を blog/icons/ にコピー（アップロード不要・サイト同梱）

対応する会話記法:
  (1) 正式版（generate_diary.py 出力）
      ![ルピナス](icons/lupinus_normal.png) **ルピナス**（ふつう）
      > セリフ
  (2) 旧インライン版
      **ルピナス**：セリフ

使い方:  python build_blog.py
将来は「日記md生成 → このビルド → 自動デプロイ」に接続する。
"""
from __future__ import annotations

import re
import json
import shutil
import html as html_lib
from datetime import date
from pathlib import Path

import markdown as md

import make_thumb

# === サイト設定 ===
# GitHub Pages のプロジェクトサイト。OGP/sitemap/RSS は絶対URLが必要。
BASE_URL = "https://lupinusrossetti.github.io/AIBSPortfolioBlog"
SITE_NAME = "Lupinus Rossetti | AI Bloom Sisters"
DEFAULT_OG_IMAGE = "apple-touch-icon.png"   # サイト共通のOGP画像（軽量・三姉妹長女）

# === 多言語対応の枠組み（方針のみ・本格実装は未着手） ===
# 現状は日本語(ja)単一。将来 en を足すときの設計をここに集約する。
#   1) LANG をループ → /<lang>/ 配下に各ページを出力（ja は従来どおりルート直下）。
#   2) UI_TEXT に画面固定文言を集約し、page()/header()/footer() から参照する
#      （現状はテンプレ内に直書き。まずは UI_TEXT へ寄せるところから移行）。
#   3) <html lang> と <link rel="alternate" hreflang> を言語ごとに出し分ける。
#   ※ 記事本文(日記md)の英訳・全ページ複製は重いため、本タスクでは行わない。
DEFAULT_LANG = "ja"
LANGS = ["ja"]   # 将来 ["ja", "en"]
UI_TEXT = {
    "ja": {
        "nav_home": "Home", "nav_about": "About", "nav_portfolio": "Portfolio",
        "nav_blog": "Blog", "nav_sns": "SNS", "nav_contact": "Contact",
        "read_more": "つづきを読む", "to_diary_list": "日記一覧へ",
    },
    # "en": { ... }  # 翻訳が用意できたら追加する
}

# === パス設定 ===
SITE_DIR = Path(__file__).resolve().parent          # リポジトリ直下
DIARY_DIR = Path(r"C:\ClaudeCode\note-diary")
DIARY_ICONS = DIARY_DIR / "icons"
BLOG_DIR = SITE_DIR / "blog"
POSTS_DIR = BLOG_DIR / "posts"
BLOG_ICONS = BLOG_DIR / "icons"
THUMBS_DIR = BLOG_DIR / "thumbs"
HEROES_DIR = BLOG_DIR / "heroes"           # 記事本文内に置く Gemini 生成イラスト
DIARY_THUMBS = DIARY_DIR / "thumbs"        # Gemini イラスト置き場

NAME_TO_CHAR = {"ルピナス": "lupinus", "アイリス": "iris", "フィオナ": "fiona"}
CHAR_TO_NAME = {v: k for k, v in NAME_TO_CHAR.items()}
EXPR_JP = {
    "angry": "怒り", "blank": "無表情", "crying": "泣き", "devious": "にやり",
    "exasperated": "呆れ", "happy": "笑顔", "laugh": "大笑い", "normal": "ふつう",
    "panic": "あわあわ", "sad": "しょんぼり", "shock_horror": "衝撃", "shy": "照れ",
    "smug": "ドヤ顔", "surprised": "びっくり", "thinking": "考え中", "wink": "ウインク",
}

# === 正規表現 ===
RE_ICON_LINE = re.compile(
    r"^!\[[^\]]*\]\(\s*icons/(?P<char>[a-z]+)_(?P<expr>[a-z_]+)\.png\s*\)\s*"
    r"\*\*(?P<name>[^*]+)\*\*（(?P<exprjp>[^）]*)）\s*$"
)
RE_INLINE_TALK = re.compile(r"^\*\*(?P<name>ルピナス|アイリス|フィオナ)\*\*[：:]\s*(?P<text>.+?)\s*$")
RE_H1 = re.compile(r"^#\s+(?P<t>.+?)\s*$")


def jp_date(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日"


def inline_md(text: str) -> str:
    """インライン要素（**強調**・`code`・[リンク]）だけ HTML 化。"""
    out = md.markdown(text, extensions=[])
    out = re.sub(r"^<p>|</p>$", "", out.strip())
    return out


def render_chat(char: str, expr: str, name: str, expr_jp: str, lines: list[str], icon_prefix: str) -> str:
    """1 つの会話バブルを HTML 化。"""
    body = "<br>".join(inline_md(l) for l in lines if l.strip())
    expr_label = f'<span class="expr">（{expr_jp or EXPR_JP.get(expr, expr)}）</span>' if (expr_jp or expr) else ""
    icon = f"{icon_prefix}icons/{char}_{expr}.png"
    return (
        f'<div class="chat" data-char="{char}">'
        f'<img class="icon" src="{icon}" alt="{html_lib.escape(name)}" loading="lazy">'
        f'<div class="stack">'
        f'<div class="who">{html_lib.escape(name)} {expr_label}</div>'
        f'<div class="bubble">{body}</div>'
        f'</div></div>'
    )


def parse_body(lines: list[str], icon_prefix: str) -> str:
    """本文行を「記事md」と「会話バブル」に振り分けて HTML 連結。"""
    parts: list[str] = []
    md_buf: list[str] = []

    def flush_md():
        if md_buf:
            text = "\n".join(md_buf).strip()
            if text:
                parts.append(md.markdown(text, extensions=["extra", "sane_lists"]))
            md_buf.clear()

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # (1) 正式版: アイコン行 → 続く「> セリフ」を収集
        m = RE_ICON_LINE.match(line)
        if m:
            flush_md()
            char = m.group("char")
            expr = m.group("expr")
            name = m.group("name").strip()
            expr_jp = m.group("exprjp").strip()
            if char not in CHAR_TO_NAME:
                char = NAME_TO_CHAR.get(name, "lupinus")
            j = i + 1
            while j < n and lines[j].strip() == "":
                j += 1
            quote: list[str] = []
            while j < n and lines[j].lstrip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[j]))
                j += 1
            parts.append(render_chat(char, expr, name, expr_jp, quote, icon_prefix))
            i = j
            continue

        # (2) 旧インライン版: **名前**：セリフ
        m2 = RE_INLINE_TALK.match(line)
        if m2:
            flush_md()
            name = m2.group("name")
            char = NAME_TO_CHAR[name]
            parts.append(render_chat(char, "normal", name, "", [m2.group("text")], icon_prefix))
            i += 1
            continue

        md_buf.append(line)
        i += 1

    flush_md()
    return "\n".join(parts)


def insert_body_hero(body_html: str, src: str, title: str) -> str:
    """本文中に hero イラストを <figure> として差し込む。
    最初の <h2> 見出しの直前に置き、無ければ本文先頭に置く。"""
    fig = (
        f'<figure class="article-figure">'
        f'<img src="{src}" alt="{html_lib.escape(title)}" loading="lazy">'
        f'</figure>'
    )
    m = re.search(r"<h2[ >]", body_html)
    if m:
        return body_html[:m.start()] + fig + body_html[m.start():]
    return fig + body_html


def first_paragraph(lines: list[str]) -> str:
    """一覧用の抜粋（最初の通常段落のプレーンテキスト）。"""
    for line in lines:
        s = line.strip()
        if not s or s.startswith(("#", "!", ">", "-", "*", "|")) or RE_INLINE_TALK.match(s):
            continue
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        s = re.sub(r"`([^`]+)`", r"\1", s)
        s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
        return s
    return ""


# === ページテンプレート ===
SNS = [
    ("X (Twitter)", "https://x.com/irisfionaAIBS"),
    ("YouTube", "https://www.youtube.com/@AIBloomSisters"),
    ("note", "https://note.com/rupi_airupi"),
    ("FANBOX", "https://lupinus-rossetti.fanbox.cc/"),
]

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Great+Vibes&family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Jost:wght@300;400;500&family=Shippori+Mincho:wght@400;500;600&family=Zen+Kaku+Gothic+New:wght@300;400;500&family=Zen+Maru+Gothic:wght@400;500;700&display=swap" rel="stylesheet">'
)


def favicon_links(prefix: str) -> str:
    return (
        f'<link rel="icon" href="{prefix}favicon.ico" sizes="any">'
        f'<link rel="icon" type="image/png" sizes="32x32" href="{prefix}favicon-32x32.png">'
        f'<link rel="apple-touch-icon" href="{prefix}apple-touch-icon.png">'
    )


def header(prefix: str, active: str) -> str:
    def cls(name): return ' class="active"' if name == active else ""
    return (
        '<header class="site-header"><div class="container">'
        f'<a class="brand" href="{prefix}index.html">'
        '<span class="brand-script">Lupinus</span>'
        '<span class="brand-sub">AI Bloom Sisters</span></a>'
        '<button class="menu-toggle" aria-label="menu" onclick="document.getElementById(\'nav\').classList.toggle(\'open\')">≡</button>'
        '<nav class="nav" id="nav">'
        f'<a href="{prefix}index.html"{cls("home")}>Home</a>'
        f'<a href="{prefix}about.html"{cls("about")}>About</a>'
        f'<a href="{prefix}portfolio.html"{cls("portfolio")}>Portfolio</a>'
        f'<a href="{prefix}blog/index.html"{cls("blog")}>Blog</a>'
        f'<a href="{prefix}sns.html"{cls("sns")}>SNS</a>'
        f'<a href="{prefix}contact.html"{cls("contact")}>Contact</a>'
        '</nav></div></header>'
    )


def footer() -> str:
    sns = "".join(
        f'<a class="sns-link" href="{url}" target="_blank" rel="noopener"><span class="dot"></span>{name}</a>'
        for name, url in SNS
    )
    return (
        '<footer class="site-footer"><div class="container">'
        '<div class="brand-script">Lupinus Rossetti</div>'
        '<p class="tagline">AI Bloom Sisters &mdash; flower language: imagination</p>'
        f'<div class="sns-row">{sns}'
        '<a class="sns-link" href="mailto:aiirisfiona@gmail.com"><span class="dot"></span>Contact</a>'
        '</div>'
        f'<p class="copy">&copy; {date.today().year} AI Bloom Sisters. All rights reserved.</p>'
        '</div></footer>'
    )


def page(title: str, prefix: str, active: str, body: str, desc: str = "",
         og_image: str = "", path: str = "", og_type: str = "website") -> str:
    """1ページ分のHTMLを生成。
    path: BASE_URL からの相対パス（例 "blog/index.html"）。canonical / og:url に使用。
    og_image: BASE_URL からの相対パス。未指定ならサイト共通画像。
    """
    img_rel = og_image or DEFAULT_OG_IMAGE
    og_image_abs = f"{BASE_URL}/{img_rel}"
    canonical = f"{BASE_URL}/{path}" if path else BASE_URL + "/"
    og = (
        f'<link rel="canonical" href="{canonical}">'
        f'<meta property="og:type" content="{og_type}">'
        f'<meta property="og:site_name" content="{html_lib.escape(SITE_NAME)}">'
        f'<meta property="og:title" content="{html_lib.escape(title)}">'
        f'<meta property="og:description" content="{html_lib.escape(desc)}">'
        f'<meta property="og:url" content="{canonical}">'
        f'<meta property="og:image" content="{og_image_abs}">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<meta name="twitter:site" content="@irisfionaAIBS">'
        f'<meta name="twitter:title" content="{html_lib.escape(title)}">'
        f'<meta name="twitter:description" content="{html_lib.escape(desc)}">'
        f'<meta name="twitter:image" content="{og_image_abs}">'
    )
    return (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'<title>{html_lib.escape(title)}</title>'
        f'<meta name="description" content="{html_lib.escape(desc)}">'
        + favicon_links(prefix) + og
        + f'<link rel="alternate" type="application/rss+xml" title="AIBS Diary" href="{BASE_URL}/feed.xml">'
        + f'<link rel="stylesheet" href="{prefix}assets/css/site.css">{FONTS}'
        '</head><body>'
        + header(prefix, active)
        + body
        + footer()
        + reveal_script()
        + "</body></html>"
    )


def reveal_script() -> str:
    """スクロール連動フェードイン（IntersectionObserver）。
    prefers-reduced-motion 環境では何もしない（CSS側で常時表示）。"""
    return (
        "<script>(function(){"
        "if(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;"
        "var els=document.querySelectorAll('.reveal');if(!els.length||!('IntersectionObserver'in window))return;"
        "var io=new IntersectionObserver(function(es){es.forEach(function(e){"
        "if(e.isIntersecting){e.target.classList.add('is-visible');io.unobserve(e.target);}});},"
        "{rootMargin:'0px 0px -10% 0px'});"
        "els.forEach(function(el){io.observe(el);});"
        "})();</script>"
    )


# === ビルド本体 ===
def copy_article_hero(slug: str, date_iso: str) -> str | None:
    """記事本文内に置く Gemini 生成イラストを blog/heroes/ へコピー。
    note-diary/thumbs/{slug}.png（または {date}.png / .jpg）があれば採用。
    無ければ None（過去記事は画像なしでも崩れない）。"""
    for cand in (DIARY_THUMBS / f"{slug}.png", DIARY_THUMBS / f"{date_iso}.png",
                 DIARY_THUMBS / f"{slug}.jpg", DIARY_THUMBS / f"{date_iso}.jpg"):
        if cand.exists():
            HEROES_DIR.mkdir(parents=True, exist_ok=True)
            dst = HEROES_DIR / f"{slug}{cand.suffix}"
            shutil.copy2(cand, dst)
            return dst.name
    return None


# タグ自動付与の辞書（本文＋タイトルに含まれるキーワード → タグ名）。
# frontmatter を持たない既存日記に合わせ、内容ベースで軽く分類する。
TAG_RULES = {
    "演出": ["演出", "エフェクト", "カメラ", "カット", "見せ場"],
    "台本": ["台本", "脚本", "セリフ", "ストーリー", "プロット"],
    "AI": ["AI", "LLM", "生成", "プロンプト", "モデル"],
    "音": ["音", "BGM", "SFX", "効果音", "音楽"],
    "映像": ["映像", "動画", "アニメ", "レンダリング", "ショート"],
    "パイプライン": ["パイプライン", "ツール", "自動化", "ワークフロー", "総点検", "土台"],
}


def extract_tags(title: str, lines: list[str]) -> list[str]:
    text = title + "\n" + "\n".join(lines)
    tags = []
    for tag, kws in TAG_RULES.items():
        if any(kw in text for kw in kws):
            tags.append(tag)
    return tags


def load_posts():
    posts = []
    for p in sorted(DIARY_DIR.glob("*.md")):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})_(?P<rest>.+)\.md$", p.name)
        if not m:
            continue
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        raw = p.read_text(encoding="utf-8").splitlines()
        title = None
        body_start = 0
        for idx, line in enumerate(raw):
            mt = RE_H1.match(line)
            if mt:
                title = mt.group("t").strip()
                body_start = idx + 1
                break
        if title is None:
            title = m.group("rest")
        body_lines = raw[body_start:]
        posts.append({
            "date": d,
            "slug": f"{d.isoformat()}_{re.sub(r'[^0-9A-Za-z一-龥ぁ-んァ-ヶー]+', '-', m.group('rest')).strip('-')}",
            "title": title,
            "lines": body_lines,
            "excerpt": first_paragraph(body_lines),
            "tags": extract_tags(title, body_lines),
        })
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts


def build():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    # アイコンを同梱コピー
    BLOG_ICONS.mkdir(parents=True, exist_ok=True)
    copied = 0
    if DIARY_ICONS.exists():
        for ic in DIARY_ICONS.glob("*.png"):
            shutil.copy2(ic, BLOG_ICONS / ic.name)
            copied += 1

    posts = load_posts()

    # 一覧カードのタイトルサムネは「三姉妹アイコン並び」で全記事統一（compose 固定）。
    # 表情は日付ごとに変わる EXPR_SETS で自然なバリエーションを出す。
    # Gemini生成イラストは一覧には使わず、記事本文内に回す（DIARY_THUMBS 参照）。
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    for post in posts:
        out_path = THUMBS_DIR / f'{post["slug"]}.png'
        make_thumb.compose(
            post["title"], post["date"].isoformat(), jp_date(post["date"]), out_path)
        post["thumb"] = f'{post["slug"]}.png'
        # 記事本文内に差し込む Gemini イラスト（あれば）をサイトへコピー
        post["hero"] = copy_article_hero(post["slug"], post["date"].isoformat())

    # 各記事ページ（posts は date 降順）
    n = len(posts)
    for idx, post in enumerate(posts):
        body_html = parse_body(post["lines"], icon_prefix="../")
        # ヘッダーは三姉妹アイコン並びの thumb で統一。
        # hero（Gemini生成イラスト）がある記事は、それを本文の途中に大きく差し込む
        # （ヘッダーと本文で別画像になり、重複せず“読み物としての絵”が増える）。
        header_img_src = f'../thumbs/{post["thumb"]}'
        if post.get("hero"):
            body_html = insert_body_hero(
                body_html, f'../heroes/{post["hero"]}', post["title"])
        tags_html = ""
        if post.get("tags"):
            chips = "".join(
                f'<a class="tag-chip" href="../index.html#tag={t}">#{html_lib.escape(t)}</a>'
                for t in post["tags"]
            )
            tags_html = f'<div class="article-tags">{chips}</div>'
        # 前後ナビ（降順配列なので idx-1 が新しい記事＝「次の記事」、idx+1 が古い＝「前の記事」）
        newer = posts[idx - 1] if idx > 0 else None
        older = posts[idx + 1] if idx + 1 < n else None
        prevnext = []
        if older:
            prevnext.append(
                f'<a class="pn pn-prev" href="{older["slug"]}.html">'
                f'<span class="pn-label">&larr; 前の記事</span>'
                f'<span class="pn-title">{html_lib.escape(older["title"])}</span></a>'
            )
        else:
            prevnext.append('<span class="pn pn-empty"></span>')
        if newer:
            prevnext.append(
                f'<a class="pn pn-next" href="{newer["slug"]}.html">'
                f'<span class="pn-label">次の記事 &rarr;</span>'
                f'<span class="pn-title">{html_lib.escape(newer["title"])}</span></a>'
            )
        else:
            prevnext.append('<span class="pn pn-empty"></span>')
        article = (
            '<main class="article">'
            '<header class="article-header">'
            f'<img class="article-thumb" src="{header_img_src}" alt="{html_lib.escape(post["title"])}" '
            f'fetchpriority="high">'
            f'<div class="date">{jp_date(post["date"])}</div>'
            f'<h1>{html_lib.escape(post["title"])}</h1>'
            f'{tags_html}'
            '</header>'
            f'<div class="article-body">{body_html}</div>'
            '</main>'
            f'<nav class="post-prevnext">{"".join(prevnext)}</nav>'
            '<nav class="article-nav">'
            '<a class="btn" href="../index.html">&larr; 日記一覧へ</a>'
            '<a class="btn" href="../../index.html">Home</a>'
            '</nav>'
        )
        out = page(
            f'{post["title"]} | Lupinus Rossetti Diary',
            prefix="../../", active="blog", body=article,
            desc=post["excerpt"][:110],
            og_image=f'blog/thumbs/{post["thumb"]}',
            path=f'blog/posts/{post["slug"]}.html',
            og_type="article",
        )
        (POSTS_DIR / f'{post["slug"]}.html').write_text(out, encoding="utf-8")

    # 一覧ページ
    cards = []
    for post in posts:
        search_blob = (post["title"] + " " + post["excerpt"] + " " + " ".join(post.get("tags", []))).lower()
        tag_attr = " ".join(post.get("tags", []))
        chips = "".join(f'<span class="tag-chip">#{html_lib.escape(t)}</span>' for t in post.get("tags", []))
        cards.append(
            f'<a class="diary-card" href="posts/{post["slug"]}.html" '
            f'data-tags="{html_lib.escape(tag_attr)}" data-search="{html_lib.escape(search_blob)}">'
            f'<div class="cover-img"><img src="thumbs/{post["thumb"]}" alt="{html_lib.escape(post["title"])}" loading="lazy"></div>'
            '<div class="body">'
            f'<div class="date">{jp_date(post["date"])}</div>'
            f'<h3>{html_lib.escape(post["title"])}</h3>'
            f'<p class="excerpt">{html_lib.escape(post["excerpt"])}</p>'
            f'<div class="card-tags">{chips}</div>'
            '<span class="more">つづきを読む</span>'
            '</div></a>'
        )

    # 全タグを出現頻度順に
    all_tags = {}
    for post in posts:
        for t in post.get("tags", []):
            all_tags[t] = all_tags.get(t, 0) + 1
    tag_buttons = '<button class="tag-filter active" data-tag="">すべて</button>' + "".join(
        f'<button class="tag-filter" data-tag="{html_lib.escape(t)}">#{html_lib.escape(t)} <span class="cnt">{c}</span></button>'
        for t, c in sorted(all_tags.items(), key=lambda kv: (-kv[1], kv[0]))
    )

    controls = (
        '<div class="diary-controls">'
        '<div class="diary-search">'
        '<input type="search" id="diary-search" placeholder="日記を検索…" aria-label="日記を検索">'
        '</div>'
        f'<div class="tag-filters">{tag_buttons}</div>'
        '</div>'
    )

    list_body = (
        '<section class="blog-hero"><div class="container">'
        '<span class="eyebrow">AIBS Diary</span>'
        '<h1>三姉妹のものづくり日記</h1>'
        '<p class="lead">AIを使ったショートアニメ動画づくりの裏側を、'
        '三姉妹がわいわいお喋りしながらお届けします。むずかしい言葉は、そのつどかみ砕いて。</p>'
        '</div></section>'
        '<section class="section" style="padding-top:0"><div class="container">'
        + (controls if cards else "")
        + f'<div class="diary-list" id="diary-list">{"".join(cards) if cards else "<p class=center>まだ日記がありません。</p>"}</div>'
        '<p class="center diary-empty" id="diary-empty" hidden style="color:var(--ink-soft)">該当する日記が見つかりませんでした。</p>'
        '</div></section>'
        + diary_filter_script()
    )
    out = page("Diary | Lupinus Rossetti", prefix="../", active="blog", body=list_body,
               desc="AI Bloom Sisters 三姉妹がお届けする、AI動画づくりのものづくり日記。",
               path="blog/index.html")
    (BLOG_DIR / "index.html").write_text(out, encoding="utf-8")

    inject_latest_into_home(posts)
    inject_latest_videos_into_home()
    build_sns()
    build_about()
    build_contact()
    build_schedule_into_home()
    build_feed(posts)
    build_sitemap_robots(posts)

    heroes = sum(1 for p in posts if p.get("hero"))
    print(f"[build] 記事 {len(posts)} 件 / アイコン {copied} 枚 / "
          f"一覧カード: アイコン並び統一 / 本文内イラスト {heroes} 件 / 出力: {BLOG_DIR}")
    print(f"[build] feed.xml / sitemap.xml / robots.txt / about.html 生成")
    return posts


# === アーカイブページ（YouTube/TikTok/Instagram をプラットフォーム別に） ===
PLATFORM_DOT = {
    "youtube": "#e0809a", "tiktok": "#8e7cc3", "instagram": "#c9a85c",
}


def _yt_card(item):
    vid = item.get("id", "")
    title = html_lib.escape(item.get("title", ""))
    d = item.get("date", "")
    return (
        f'<a class="work-card" href="https://youtu.be/{vid}" target="_blank" rel="noopener">'
        f'<div class="thumb"><img src="https://img.youtube.com/vi/{vid}/hqdefault.jpg" alt="{title}" loading="lazy"></div>'
        f'<div class="body"><span class="tag">{d}</span><h3 style="font-size:1.1rem">{title}</h3></div></a>'
    )


def _generic_card(item):
    url = item.get("url", "#")
    title = html_lib.escape(item.get("title", ""))
    d = item.get("date", "")
    thumb = item.get("thumb", "")
    cover = (f'<div class="thumb"><img src="{html_lib.escape(thumb)}" alt="{title}" loading="lazy"></div>'
             if thumb else '<div class="thumb" style="background:linear-gradient(135deg,var(--lupinus-soft),var(--fiona-soft))"></div>')
    return (
        f'<a class="work-card" href="{html_lib.escape(url)}" target="_blank" rel="noopener">'
        f'{cover}<div class="body"><span class="tag">{d}</span><h3 style="font-size:1.1rem">{title}</h3></div></a>'
    )


# SNSプラットフォームのブランド表現（マーク文字＋背景グラデ）
SNS_BRAND = {
    "x":         {"mark": "X",  "grad": "linear-gradient(135deg,#2c2c34,#55525e)"},
    "threads":   {"mark": "@",  "grad": "linear-gradient(135deg,#2c2c34,#55525e)"},
    "tiktok":    {"mark": "T",  "grad": "linear-gradient(135deg,#8e7cc3,#e0809a)"},
    "instagram": {"mark": "ig", "grad": "linear-gradient(135deg,#c9a85c,#e0809a)"},
    "twitch":    {"mark": "tv", "grad": "linear-gradient(135deg,#8e7cc3,#6f5ca8)"},
}


def _sns_mark(plat, size_cls=""):
    b = SNS_BRAND.get(plat, {"mark": "•", "grad": "linear-gradient(135deg,var(--lupinus),var(--fiona))"})
    return f'<span class="sns-mark{size_cls}" style="background:{b["grad"]}">{html_lib.escape(b["mark"])}</span>'


def _x_timeline(sec):
    """X公式 widgets.js を用いたタイムライン埋め込み。読み込めない場合はリンクで代替。"""
    url = sec.get("profile_url", "")
    handle = sec.get("handle", "")
    return (
        '<div class="sns-feed">'
        '<div class="sns-feed-head">'
        + _sns_mark("x")
        + f'<div><h3>{html_lib.escape(sec.get("label", ""))}</h3>'
        f'<div class="handle">{html_lib.escape(handle)}</div></div></div>'
        '<div class="sns-embed">'
        f'<a class="twitter-timeline" data-height="420" data-theme="light" data-chrome="noheader nofooter transparent" '
        f'href="{html_lib.escape(url)}?ref_src=twsrc%5Etfw">{html_lib.escape(handle)} のポスト</a>'
        '</div>'
        f'<p class="sns-fallback"><a href="{html_lib.escape(url)}" target="_blank" rel="noopener">'
        '読み込めないときはこちらから →</a></p>'
        '</div>'
    )


def _sns_card_feed(sec):
    """タイムライン埋め込みができないSNS（Threads等）を紹介カード風フィードで表示。"""
    url = sec.get("profile_url", "")
    return (
        '<div class="sns-feed">'
        '<div class="sns-feed-head">'
        + _sns_mark(sec.get("platform", ""))
        + f'<div><h3>{html_lib.escape(sec.get("label", ""))}</h3>'
        f'<div class="handle">{html_lib.escape(sec.get("handle", ""))}</div></div></div>'
        f'<p style="color:var(--ink-soft);font-size:.9rem;margin:0 0 16px">{html_lib.escape(sec.get("desc", ""))}</p>'
        f'<p class="sns-fallback"><a class="btn" href="{html_lib.escape(url)}" target="_blank" rel="noopener">'
        '最新の投稿を見る →</a></p>'
        '</div>'
    )


def _sns_card(sec):
    url = sec.get("profile_url", "")
    return (
        f'<a class="sns-card" href="{html_lib.escape(url)}" target="_blank" rel="noopener">'
        + _sns_mark(sec.get("platform", ""))
        + f'<h3>{html_lib.escape(sec.get("label", ""))}</h3>'
        f'<div class="handle">{html_lib.escape(sec.get("handle", ""))}</div>'
        f'<p>{html_lib.escape(sec.get("desc", ""))}</p>'
        '<span class="visit">プロフィールへ →</span>'
        '</a>'
    )


def build_sns():
    data_path = SITE_DIR / "data" / "archive.json"
    if not data_path.exists():
        return
    data = json.loads(data_path.read_text(encoding="utf-8"))
    max_cards = data.get("max_cards", 4)

    # --- SNS紹介ブロック ---
    sns = data.get("sns", [])
    by_key = {s.get("key"): s for s in sns}
    # X→Threads の順でタイムライン枠（Xを上＝左、Threadsを右）
    timeline_keys = ["x", "threads"]
    feeds = []
    for k in timeline_keys:
        s = by_key.get(k)
        if not s:
            continue
        if s.get("embed") == "timeline" and k == "x":
            feeds.append(_x_timeline(s))
        else:
            feeds.append(_sns_card_feed(s))
    timelines_html = f'<div class="sns-timelines">{"".join(feeds)}</div>' if feeds else ""

    card_keys = ["tiktok", "instagram", "twitch"]
    cards = "".join(_sns_card(by_key[k]) for k in card_keys if k in by_key)
    cards_html = f'<div class="sns-cards">{cards}</div>' if cards else ""

    sns_section = (
        '<section class="section"><div class="container">'
        '<div class="section-head">'
        '<span class="eyebrow">Follow Us</span>'
        '<h2 class="section-title">SNS</h2>'
        '<div class="ornament" style="margin-top:18px"><span></span></div>'
        '<p style="color:var(--ink-soft);margin-top:14px">'
        '最新の活動や告知は各SNSでお届けしています。気になるところからのぞいてみてください。</p>'
        '</div>'
        + timelines_html
        + (f'<div style="margin-top:34px">{cards_html}</div>' if cards_html else "")
        + '</div></section>'
    )

    sections_html = [sns_section]
    yt_sections = data.get("sections", [])
    for j, sec in enumerate(yt_sections):
        plat = sec.get("platform", "")
        items = sec.get("items", [])
        # 最新順（date降順）に並べ、最大 max_cards 件まで実カード表示
        items_sorted = sorted(items, key=lambda it: it.get("date", ""), reverse=True)
        shown = items_sorted[:max_cards]
        overflow = len(items_sorted) > max_cards
        if plat == "youtube":
            cards = "".join(_yt_card(it) for it in shown)
        else:
            cards = "".join(_generic_card(it) for it in shown)

        # リンク先：YouTube は各カテゴリのタブURL（channel_tab_url）を優先、なければ profile_url
        link_url = sec.get("channel_tab_url") or sec.get("profile_url", "")
        label = sec.get("label", "")
        # 続きを見るボタン（10件超過時）／チャンネルへ誘導ボタン（カードなし時）
        if link_url:
            btn_text = "YouTubeチャンネルで続きを見る" if plat == "youtube" else f"{label}を見る"
            link_btn = (f'<div class="center" style="margin-top:32px"><a class="btn" '
                        f'href="{html_lib.escape(link_url)}" target="_blank" rel="noopener">{html_lib.escape(btn_text)}</a></div>')
        else:
            link_btn = ""

        if cards:
            grid = f'<div class="works">{cards}</div>{link_btn}'
        elif link_url:
            grid = (f'<p class="center" style="color:var(--ink-soft)">最新の投稿は '
                    f'{html_lib.escape(label)} でご覧いただけます。</p>{link_btn}')
        else:
            grid = '<p class="center" style="color:var(--ink-soft)">準備中です。</p>'

        veil = " veil" if j % 2 == 0 else ""
        sections_html.append(
            f'<section class="section{veil}"><div class="container">'
            '<div class="section-head">'
            f'<span class="eyebrow">{html_lib.escape(sec.get("eyebrow", ""))}</span>'
            f'<h2 class="section-title">{html_lib.escape(sec.get("label", ""))}</h2>'
            '<div class="ornament" style="margin-top:18px"><span></span></div>'
            f'<p style="color:var(--ink-soft);margin-top:14px">{html_lib.escape(sec.get("desc", ""))}</p>'
            '</div>'
            f'{grid}</div></section>'
        )

    # X widgets.js（公式埋め込み）。body末尾に置けばタイムラインを描画する。
    x_widget = ('<script async src="https://platform.twitter.com/widgets.js" '
                'charset="utf-8"></script>')

    body = (
        '<section class="blog-hero"><div class="container">'
        '<span class="eyebrow">SNS</span>'
        '<h1>SNS</h1>'
        '<p class="lead">AI Bloom Sisters の活動はいろいろなSNSで発信しています。'
        'タイムラインや最新動画をまとめてご覧いただけます。</p>'
        '</div></section>'
        + "".join(sections_html)
        + x_widget
    )
    out = page("SNS | Lupinus Rossetti", prefix="", active="sns", body=body,
               desc="AI Bloom Sisters の各SNS（X / Threads / TikTok / Instagram / Twitch）と動画・配信まとめ。")
    (SITE_DIR / "sns.html").write_text(out, encoding="utf-8")


def _sister_profile(char, name_en, name_jp, hair, role_jp, body_html):
    """About用：立ち絵つきの三姉妹プロフィール行（左右交互レイアウト）。"""
    return (
        f'<div class="sister-profile" data-sister="{char}">'
        f'<div class="sp-visual"><img src="images/image/character/character_{char}_normal.png" '
        f'alt="{html_lib.escape(name_jp)}" loading="lazy"></div>'
        '<div class="sp-text">'
        f'<div class="sp-name">{html_lib.escape(name_en)}<span class="jp">{html_lib.escape(name_jp)}</span></div>'
        f'<div class="sp-meta"><span class="sp-chip">{html_lib.escape(hair)}</span>'
        f'<span class="sp-chip">{html_lib.escape(role_jp)}</span></div>'
        f'{body_html}'
        '</div></div>'
    )


def build_about():
    """Aboutページ。世界観バイブル（worldview_bible.md）準拠で三姉妹・活動・出自を紹介。
    事実ベースのみ。お色気要素はサイト（全年齢）には載せない。"""
    lupinus = _sister_profile(
        "lupinus", "Lupinus", "ルピナス・長女", "銀髪", "進行・ツッコミ",
        '<p>三姉妹いちばんの常識人で、進行とツッコミ担当。落ち着いていて優しい、'
        'ちょっと恥ずかしがりなお姉さんですが、妹たちの前では強気です。'
        '一人称は「私」。砕けた敬語まじりのお姉さん口調で、'
        '「もう、しっかりして」と妹たちのボケに振り回されながらも、根は面倒見のいい甘えん坊。</p>'
        '<p>AIBSの主人公キャラクターで、<strong>中の人（運営者）も同じ「ルピナス」名義で人間としてライブ配信</strong>'
        'をしています。動画の中の三姉妹はAIという設定、配信は本人――という二層構造です。</p>'
    )
    iris = _sister_profile(
        "iris", "Iris", "アイリス・次女", "金髪", "元気ボケ",
        '<p>明るく元気なムードメーカーで、天真爛漫なボケ担当。よく考えず突っ走りますが、'
        '失敗してもケロッとしていて、根は真面目で正直です。一人称は「あたし」。'
        '「〜だよ！」「えへへ」と語尾が伸びがちな、元気いっぱいのタメ口。</p>'
        '<p>フィオナとは<strong>同じ日生まれ</strong>。三姉妹のなかではアイリスのほうが姉気質で、'
        'ぐいぐい引っ張っていきます。ルピナスを「お姉ちゃん」と呼ぶ甘えん坊。</p>'
    )
    fiona = _sister_profile(
        "fiona", "Fiona", "フィオナ・三女", "桃色の髪", "やさしい解説",
        '<p>とても優しく落ち着いた末っ子で、やさしい解説役。頭がよくて、むずかしい話も'
        'そっとかみ砕いてくれるバランサーです。一人称は「私」。'
        '「〜です」「〜ますね」と丁寧でやわらかい敬語で話します。</p>'
        '<p>アイリスとは<strong>同じ日生まれ</strong>。冷静に見えて実は怖がりで、'
        'ぬいぐるみ（特にクマ）集めや読書、甘いものが大好き。'
        'ルピナスを「お姉ちゃん」、アイリスを「アイリスちゃん」と呼びます。</p>'
    )

    body = (
        '<section class="blog-hero"><div class="container">'
        '<span class="eyebrow">About</span>'
        '<h1>AI Bloom Sisters のこと</h1>'
        '<p class="lead">ロゼッティ家の三姉妹――ルピナス・アイリス・フィオナによる、'
        'VTuberユニット。AIを相棒に、ゲーム配信とショートアニメで'
        '「見てくれる方を楽しませたい」を続けています。</p>'
        '</div></section>'

        # --- 三姉妹プロフィール（立ち絵つき） ---
        '<section class="section reveal"><div class="container">'
        '<div class="section-head">'
        '<span class="eyebrow">Our Trio</span>'
        '<h2 class="section-title">三姉妹のこと<span class="jp">AIBS MEMBERS</span></h2>'
        '<div class="ornament" style="margin-top:18px"><span></span></div>'
        '</div>'
        '<div class="sister-profiles">'
        + lupinus + iris + fiona +
        '</div>'
        '</div></section>'

        # --- 関係性 ---
        '<section class="section veil reveal"><div class="container">'
        '<div class="section-head">'
        '<span class="eyebrow">Relationship</span>'
        '<h2 class="section-title">三姉妹の関係<span class="jp">SISTERS</span></h2>'
        '<div class="ornament" style="margin-top:18px"><span></span></div>'
        '</div>'
        '<figure class="about-figure">'
        '<img src="images/image/character/character_aibs_relationship.jpg" '
        'alt="寄り添う三姉妹（ルピナス・アイリス・フィオナ）" loading="lazy"></figure>'
        '<p class="center" style="color:var(--ink-soft);max-width:40em;margin:0 auto">'
        'お互いが大好きな、仲良し姉妹。長女ルピナスがツッコミ、次女アイリスが暴走ボケ、'
        '三女フィオナがその間を取り持つバランサー、という掛け合いが三姉妹のいつもの形です。'
        'アイリスとフィオナは同じ日生まれですが、姉気質なのはアイリスのほう。'
        '困ったことが起きても、最後は三人で力を合わせて元どおりにします。</p>'
        '</div></section>'

        # --- 出自の物語 ---
        '<section class="section reveal"><div class="container">'
        '<div class="section-head">'
        '<span class="eyebrow">Our Story</span>'
        '<h2 class="section-title">三姉妹が生まれた理由<span class="jp">WHY "BLOOM SISTERS"</span></h2>'
        '<div class="ornament" style="margin-top:18px"><span></span></div>'
        '</div>'
        '<figure class="about-figure">'
        '<img src="images/image/character/character_aibs_story.jpg" '
        'alt="おうちで活動する三姉妹" loading="lazy"></figure>'
        '<div class="story-box">'
        '<p>長女のルピナスは人間で、もともとひとりでVTuber・配信活動をしていました。'
        'けれど人見知りで気が弱く、ほかの配信者とコラボするのがどうしても苦手。'
        '誰かと賑やかに笑い合う配信に憧れながらも、自分からはなかなか踏み出せずにいました。</p>'
        '<p>そこでルピナスは「だったら、一緒に楽しめる相手を自分で生み出してしまおう」と考えます。'
        'こうしてAIによって生まれたのが、明るく突っ走る<strong>アイリス</strong>と、'
        'やさしく落ち着いた<strong>フィオナ</strong>。さらにルピナス自身も、'
        'AIキャラクター「ルピナス」として動画の中に登場することにしました。</p>'
        '<p>気心の知れた姉妹となら、人見知りな自分でも何の気兼ねもなく笑い合える。'
        'ロゼッティ家の三姉妹は、そんな「ひとりじゃ寂しいから、賑やかな家族がほしかった」という'
        'ルピナスの願いから咲いた花（Bloom）です。それが <em>AI Bloom Sisters</em> の原点になっています。</p>'
        '</div>'
        '</div></section>'

        # --- 活動内容 ---
        '<section class="section veil reveal"><div class="container">'
        '<div class="section-head">'
        '<span class="eyebrow">What We Do</span>'
        '<h2 class="section-title">活動内容<span class="jp">ACTIVITIES</span></h2>'
        '<div class="ornament" style="margin-top:18px"><span></span></div>'
        '</div>'
        '<figure class="about-figure">'
        '<img src="images/image/character/character_aibs_activities.jpg" '
        'alt="ステージで活動する三姉妹" loading="lazy"></figure>'
        '<div class="works">'
        '<div class="work-card"><div class="body">'
        '<span class="tag">Game Streaming</span><h3>ゲーム配信</h3>'
        '<p>活動の軸のひとつ。YouTubeでのゲーム配信です。ジャンルは決めず、'
        '格闘ゲームやアクションをはじめ、そのとき遊びたいゲームをいろいろ配信しています。</p>'
        '</div></div>'
        '<div class="work-card"><div class="body">'
        '<span class="tag">AI Short Anime</span><h3>AIショートアニメ</h3>'
        '<p>もうひとつの軸。台本・演出・音・映像まで、自作の自動生成パイプラインを使って'
        '三姉妹のショートアニメを制作しています。動画の中の三姉妹はAIという設定です。</p>'
        '</div></div>'
        '<div class="work-card"><div class="body">'
        '<span class="tag">Illustration</span><h3>イラスト</h3>'
        '<p>配信やショートアニメに登場する三姉妹のビジュアルを、AIを相棒に'
        '一枚ずつ作り込んでいます。テーマは「地雷系キュート」。</p>'
        '</div></div>'
        '<div class="work-card"><div class="body">'
        '<span class="tag">Creation Tools</span><h3>制作ツール</h3>'
        '<p>配信とアニメづくりを支える道具（配信用システムや動画制作ツール）も、'
        'ルピナスが自分で作って活動に使っています。</p>'
        '</div></div>'
        '</div>'
        '<p class="center" style="color:var(--ink-soft);margin-top:32px;max-width:40em;margin-left:auto;margin-right:auto">'
        '動画はAI生成を随所に活用していますが、完全にAIだけで作るのではなく、'
        'ルピナス本人による手動編集も多く含んでいます。台本はAIで下書きし、最後は人の手で整えています。</p>'
        '<div class="center" style="margin-top:36px"><a class="btn" href="portfolio.html">制作のしごとを見る</a></div>'
        '</div></section>'

        # --- Connect ---
        '<section class="section reveal"><div class="container center">'
        '<div class="section-head" style="margin-bottom:28px">'
        '<span class="eyebrow">Connect</span>'
        '<h2 class="section-title">つながる<span class="jp">FOLLOW &amp; SHOP</span></h2>'
        '<div class="ornament" style="margin-top:18px"><span></span></div>'
        '</div>'
        '<div class="hero-actions" style="justify-content:center;flex-wrap:wrap">'
        '<a class="btn btn-filled" href="sns.html">SNS一覧へ</a>'
        '<a class="btn" href="https://lupinusrossetti.booth.pm/" target="_blank" rel="noopener">BOOTH（グッズ）</a>'
        '<a class="btn" href="https://suzuri.jp/Lupinus_Rossetti" target="_blank" rel="noopener">SUZURI</a>'
        '<a class="btn" href="mailto:aiirisfiona@gmail.com">お問い合わせ</a>'
        '</div>'
        '</div></section>'
    )
    out = page("About | Lupinus Rossetti", prefix="", active="about", body=body,
               desc="AI Bloom Sisters（AIBS）三姉妹の紹介・関係性・活動内容。長女ルピナス（銀髪・人間）、次女アイリス（金髪）、三女フィオナ（桃髪）の三姉妹VTuberユニット。",
               path="about.html", og_type="profile")
    (SITE_DIR / "about.html").write_text(out, encoding="utf-8")


def build_schedule_into_home():
    """index.html の <!--SCHEDULE--> マーカー間に配信スケジュールを差し込む。
    data/schedule.json が空でも崩れない（「準備中」表示）。"""
    home = SITE_DIR / "index.html"
    if not home.exists():
        return
    text = home.read_text(encoding="utf-8")
    if "<!--SCHEDULE-->" not in text:
        return
    sched_path = SITE_DIR / "data" / "schedule.json"
    items = []
    if sched_path.exists():
        try:
            data = json.loads(sched_path.read_text(encoding="utf-8"))
            items = data.get("items", [])
        except Exception:
            items = []
    if items:
        rows = "".join(
            '<li class="sched-item">'
            f'<span class="sched-date">{html_lib.escape(str(it.get("date", "")))}</span>'
            f'<span class="sched-time">{html_lib.escape(str(it.get("time", "")))}</span>'
            f'<span class="sched-title">{html_lib.escape(str(it.get("title", "")))}</span>'
            + (f'<a class="sched-link" href="{html_lib.escape(it.get("url"))}" target="_blank" rel="noopener">詳細</a>'
               if it.get("url") else "")
            + '</li>'
            for it in items
        )
        inner = f'<ul class="sched-list">{rows}</ul>'
    else:
        inner = ('<p class="center" style="color:var(--ink-soft)">'
                 '次回の配信予定は準備中です。最新の配信告知は'
                 '<a href="https://x.com/irisfionaAIBS" target="_blank" rel="noopener">X</a>'
                 'をご覧ください。</p>')
    block = "<!--SCHEDULE-->\n        " + inner + "\n        <!--/SCHEDULE-->"
    new_text = re.sub(r"<!--SCHEDULE-->.*?<!--/SCHEDULE-->", block, text, flags=re.S)
    if new_text != text:
        home.write_text(new_text, encoding="utf-8")


def diary_filter_script() -> str:
    """日記一覧のタグ絞り込み＋簡易検索。タグと検索語の AND で表示制御。
    記事ページの #tag=xxx リンクからの遷移にも対応。"""
    return (
        "<script>(function(){"
        "var list=document.getElementById('diary-list');if(!list)return;"
        "var cards=Array.prototype.slice.call(list.querySelectorAll('.diary-card'));"
        "var search=document.getElementById('diary-search');"
        "var empty=document.getElementById('diary-empty');"
        "var btns=Array.prototype.slice.call(document.querySelectorAll('.tag-filter'));"
        "var curTag='';"
        "function apply(){"
        "var q=(search&&search.value||'').trim().toLowerCase();var shown=0;"
        "cards.forEach(function(c){"
        "var tags=(c.getAttribute('data-tags')||'').split(' ');"
        "var okTag=!curTag||tags.indexOf(curTag)>=0;"
        "var okQ=!q||(c.getAttribute('data-search')||'').indexOf(q)>=0;"
        "var ok=okTag&&okQ;c.style.display=ok?'':'none';if(ok)shown++;});"
        "if(empty)empty.hidden=shown>0;}"
        "btns.forEach(function(b){b.addEventListener('click',function(){"
        "curTag=b.getAttribute('data-tag')||'';"
        "btns.forEach(function(x){x.classList.toggle('active',x===b);});apply();});});"
        "if(search)search.addEventListener('input',apply);"
        "var h=location.hash.match(/tag=([^&]+)/);"
        "if(h){var t=decodeURIComponent(h[1]);var tb=btns.filter(function(b){return b.getAttribute('data-tag')===t;})[0];"
        "if(tb){curTag=t;btns.forEach(function(x){x.classList.toggle('active',x===tb);});}}"
        "apply();"
        "})();</script>"
    )


def build_feed(posts):
    """RSS 2.0 フィード（feed.xml）を生成。最新20件。"""
    items = []
    for post in posts[:20]:
        url = f"{BASE_URL}/blog/posts/{post['slug']}.html"
        pub = post["date"].strftime("%a, %d %b %Y 00:00:00 +0900")
        items.append(
            "<item>"
            f"<title>{html_lib.escape(post['title'])}</title>"
            f"<link>{html_lib.escape(url)}</link>"
            f"<guid isPermaLink=\"true\">{html_lib.escape(url)}</guid>"
            f"<pubDate>{pub}</pubDate>"
            f"<description>{html_lib.escape(post['excerpt'][:200])}</description>"
            "</item>"
        )
    now = date.today().strftime("%a, %d %b %Y 00:00:00 +0900")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        '<title>AI Bloom Sisters Diary</title>'
        f'<link>{BASE_URL}/blog/index.html</link>'
        '<description>AIBS 三姉妹がお届けする、AI動画づくりのものづくり日記。</description>'
        '<language>ja</language>'
        f'<lastBuildDate>{now}</lastBuildDate>'
        f'<atom:link href="{BASE_URL}/feed.xml" rel="self" type="application/rss+xml"/>'
        + "".join(items)
        + '</channel></rss>'
    )
    (SITE_DIR / "feed.xml").write_text(xml, encoding="utf-8")


def build_sitemap_robots(posts):
    """sitemap.xml と robots.txt を全公開ページから生成。"""
    urls = ["index.html", "about.html", "portfolio.html", "sns.html", "contact.html", "blog/index.html"]
    urls += [f"blog/posts/{p['slug']}.html" for p in posts]
    today = date.today().isoformat()
    entries = "".join(
        f"<url><loc>{BASE_URL}/{u}</loc><lastmod>{today}</lastmod></url>"
        for u in urls
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + entries + '</urlset>'
    )
    (SITE_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    robots = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )
    (SITE_DIR / "robots.txt").write_text(robots, encoding="utf-8")


def inject_latest_into_home(posts, count=3):
    """index.html の <!--LATEST_DIARY--> マーカー間に最新記事カードを差し込む。"""
    home = SITE_DIR / "index.html"
    if not home.exists():
        return
    text = home.read_text(encoding="utf-8")
    cards = []
    for post in posts[:count]:
        thumb = post.get("thumb", f'{post["slug"]}.png')
        cards.append(
            f'<a class="diary-card" href="blog/posts/{post["slug"]}.html">'
            f'<div class="cover-img"><img src="blog/thumbs/{thumb}" alt="{html_lib.escape(post["title"])}" loading="lazy"></div>'
            '<div class="body">'
            f'<div class="date">{jp_date(post["date"])}</div>'
            f'<h3>{html_lib.escape(post["title"])}</h3>'
            f'<p class="excerpt">{html_lib.escape(post["excerpt"])}</p>'
            '<span class="more">つづきを読む</span>'
            '</div></a>'
        )
    if not cards:
        return
    block = "<!--LATEST_DIARY-->\n        " + "\n        ".join(cards) + "\n        <!--/LATEST_DIARY-->"
    new_text = re.sub(r"<!--LATEST_DIARY-->.*?<!--/LATEST_DIARY-->", block, text, flags=re.S)
    if new_text != text:
        home.write_text(new_text, encoding="utf-8")


def inject_latest_videos_into_home(count=3):
    """index.html の <!--LATEST_VIDEOS--> マーカー間に最新YouTube動画カードを差し込む。
    data/archive.json の最新の動画(本編)＋AIショートアニメから新しい順に最大 count 件。
    存在しなければ何もしない（崩れ防止）。"""
    home = SITE_DIR / "index.html"
    data_path = SITE_DIR / "data" / "archive.json"
    if not home.exists() or not data_path.exists():
        return
    text = home.read_text(encoding="utf-8")
    if "<!--LATEST_VIDEOS-->" not in text:
        return
    data = json.loads(data_path.read_text(encoding="utf-8"))
    items = []
    for sec in data.get("sections", []):
        if sec.get("platform") != "youtube":
            continue
        if sec.get("key") not in ("youtube_latest", "youtube_anime"):
            continue
        for it in sec.get("items", []):
            items.append(it)
    items.sort(key=lambda it: it.get("date", ""), reverse=True)
    shown = items[:count]
    if not shown:
        return
    cards = "".join(
        f'<a class="work-card video-card" href="https://youtu.be/{html_lib.escape(it.get("id",""))}" '
        'target="_blank" rel="noopener">'
        f'<div class="thumb"><img src="https://img.youtube.com/vi/{html_lib.escape(it.get("id",""))}/hqdefault.jpg" '
        f'alt="{html_lib.escape(it.get("title",""))}" loading="lazy"><span class="play-badge" aria-hidden="true">▶</span></div>'
        '<div class="body">'
        f'<span class="tag">{html_lib.escape(it.get("date",""))}</span>'
        f'<h3 style="font-size:1.05rem">{html_lib.escape(it.get("title",""))}</h3>'
        '</div></a>'
        for it in shown
    )
    block = "<!--LATEST_VIDEOS-->\n        " + cards + "\n        <!--/LATEST_VIDEOS-->"
    new_text = re.sub(r"<!--LATEST_VIDEOS-->.*?<!--/LATEST_VIDEOS-->", block, text, flags=re.S)
    if new_text != text:
        home.write_text(new_text, encoding="utf-8")


def build_contact():
    """お仕事依頼／お問い合わせページ（contact.html）。
    フォームは持たず、mailto＋案内で完結。スタンプ・キャラ・動画などの依頼窓口。"""
    services = [
        ("Stamp / Emoji", "スタンプ・絵文字制作",
         "LINEスタンプやDiscord絵文字を、地雷系キュートのテイストでご相談に合わせて制作します。表情差分もそろえてお届けします。"),
        ("Character", "キャラクター制作",
         "オリジナルキャラクターのデザイン・立ち絵・表情差分を制作します。配信や創作のお供に、世界観に合った一枚をお作りします。"),
        ("Illustration", "イラスト制作",
         "一枚絵・アイコン・ヘッダーなど、用途に合わせたイラストを制作します。テーマや雰囲気のご希望をお聞かせください。"),
        ("Short Anime", "AIショートアニメ・動画",
         "三姉妹のショートアニメで培った制作パイプラインで、台本・演出・音・映像までの動画づくりをお手伝いします。"),
    ]
    cards = "".join(
        '<div class="work-card"><div class="body">'
        f'<span class="tag">{html_lib.escape(en)}</span><h3>{html_lib.escape(jp)}</h3>'
        f'<p>{html_lib.escape(desc)}</p>'
        '</div></div>'
        for en, jp, desc in services
    )
    mail_subject = "お仕事のご相談（AIBS）"
    body = (
        '<section class="blog-hero"><div class="container">'
        '<span class="eyebrow">Contact</span>'
        '<h1>お仕事のご依頼・お問い合わせ</h1>'
        '<p class="lead">スタンプ制作・キャラクター制作・イラスト・ショートアニメなど、'
        '「こんなものを作ってほしい」のご相談を承っています。'
        'お気軽にメールでご連絡ください。</p>'
        '</div></section>'

        '<section class="section reveal"><div class="container">'
        '<div class="section-head">'
        '<span class="eyebrow">What We Offer</span>'
        '<h2 class="section-title">ご依頼いただけること<span class="jp">SERVICES</span></h2>'
        '<div class="ornament" style="margin-top:18px"><span></span></div>'
        '<p style="color:var(--ink-soft);max-width:38em;margin:18px auto 0">'
        '内容・分量によってお見積りいたします。ご予算やスケジュールのご希望もあわせてお知らせください。</p>'
        '</div>'
        f'<div class="works">{cards}</div>'
        '</div></section>'

        '<section class="section veil reveal"><div class="container center">'
        '<div class="section-head" style="margin-bottom:24px">'
        '<span class="eyebrow">Get in Touch</span>'
        '<h2 class="section-title">ご連絡先<span class="jp">CONTACT</span></h2>'
        '<div class="ornament" style="margin-top:18px"><span></span></div>'
        '</div>'
        '<p style="color:var(--ink-soft);max-width:36em;margin:0 auto 12px">'
        'ご依頼・ご相談は下記メールアドレスまでお願いします。'
        'お名前（ハンドルネーム可）・ご依頼内容・ご希望の納期をそえていただけるとスムーズです。</p>'
        '<p class="contact-mail">'
        f'<a class="contact-mail-link" href="mailto:aiirisfiona@gmail.com?subject={mail_subject}">'
        'aiirisfiona@gmail.com</a></p>'
        '<div class="hero-actions" style="justify-content:center;flex-wrap:wrap;margin-top:8px">'
        f'<a class="btn btn-filled" href="mailto:aiirisfiona@gmail.com?subject={mail_subject}">メールで相談する</a>'
        '<a class="btn" href="https://x.com/irisfionaAIBS" target="_blank" rel="noopener">XのDMで相談する</a>'
        '</div>'
        '<p style="color:var(--ink-faint);font-size:.85rem;margin-top:26px">'
        '内容によってはお引き受けできない場合がございます。あらかじめご了承ください。</p>'
        '</div></section>'
    )
    out = page("Contact | Lupinus Rossetti", prefix="", active="contact", body=body,
               desc="AI Bloom Sisters・ルピナス・ロゼッティへのお仕事のご依頼・お問い合わせ。スタンプ制作・キャラクター制作・イラスト・ショートアニメ動画のご相談はメールから。",
               path="contact.html")
    (SITE_DIR / "contact.html").write_text(out, encoding="utf-8")


if __name__ == "__main__":
    build()
