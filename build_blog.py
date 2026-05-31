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

# === パス設定 ===
SITE_DIR = Path(__file__).resolve().parent          # リポジトリ直下
DIARY_DIR = Path(r"C:\ClaudeCode\note-diary")
DIARY_ICONS = DIARY_DIR / "icons"
BLOG_DIR = SITE_DIR / "blog"
POSTS_DIR = BLOG_DIR / "posts"
BLOG_ICONS = BLOG_DIR / "icons"
THUMBS_DIR = BLOG_DIR / "thumbs"

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
    ("Ci-en", "https://ci-en.net/creator/28203"),
    ("FANBOX", "https://lupinus-rossetti.fanbox.cc/"),
]

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Great+Vibes&family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Jost:wght@300;400;500&family=Shippori+Mincho:wght@400;500;600&family=Zen+Kaku+Gothic+New:wght@300;400;500&family=Zen+Maru+Gothic:wght@400;500;700&display=swap" rel="stylesheet">'
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
        f'<a href="{prefix}portfolio.html"{cls("portfolio")}>Portfolio</a>'
        f'<a href="{prefix}blog/index.html"{cls("blog")}>Blog</a>'
        f'<a href="{prefix}archive.html"{cls("archive")}>Archive</a>'
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
        f'<div class="sns-row">{sns}</div>'
        f'<p class="copy">&copy; {date.today().year} AI Bloom Sisters. All rights reserved.</p>'
        '</div></footer>'
    )


def page(title: str, prefix: str, active: str, body: str, desc: str = "", og_image: str = "") -> str:
    og = ""
    if og_image:
        og_url = f"{prefix}{og_image}"
        og = (
            '<meta property="og:type" content="article">'
            f'<meta property="og:title" content="{html_lib.escape(title)}">'
            f'<meta property="og:description" content="{html_lib.escape(desc)}">'
            f'<meta property="og:image" content="{og_url}">'
            '<meta name="twitter:card" content="summary_large_image">'
        )
    return (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'<title>{html_lib.escape(title)}</title>'
        f'<meta name="description" content="{html_lib.escape(desc)}">{og}'
        f'<link rel="stylesheet" href="{prefix}assets/css/site.css">{FONTS}'
        '</head><body>'
        + header(prefix, active)
        + body
        + footer()
        + "</body></html>"
    )


def menu_script():
    return ""


# === ビルド本体 ===
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

    # サムネ生成（手動/Gemini画像 ＞ 自動合成）
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    thumb_stats = {}
    for post in posts:
        out_path = THUMBS_DIR / f'{post["slug"]}.png'
        kind = make_thumb.ensure_thumb(
            post["slug"], post["date"].isoformat(), jp_date(post["date"]),
            post["title"], post["excerpt"], out_path)
        post["thumb"] = f'{post["slug"]}.png'
        thumb_stats[kind] = thumb_stats.get(kind, 0) + 1

    # 各記事ページ
    for post in posts:
        body_html = parse_body(post["lines"], icon_prefix="../")
        article = (
            '<main class="article">'
            '<header class="article-header">'
            f'<img class="article-thumb" src="../thumbs/{post["thumb"]}" alt="{html_lib.escape(post["title"])}">'
            f'<div class="date">{jp_date(post["date"])}</div>'
            f'<h1>{html_lib.escape(post["title"])}</h1>'
            '</header>'
            f'<div class="article-body">{body_html}</div>'
            '</main>'
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
        )
        (POSTS_DIR / f'{post["slug"]}.html').write_text(out, encoding="utf-8")

    # 一覧ページ
    cards = []
    for post in posts:
        cards.append(
            f'<a class="diary-card" href="posts/{post["slug"]}.html">'
            f'<div class="cover-img"><img src="thumbs/{post["thumb"]}" alt="{html_lib.escape(post["title"])}" loading="lazy"></div>'
            '<div class="body">'
            f'<div class="date">{jp_date(post["date"])}</div>'
            f'<h3>{html_lib.escape(post["title"])}</h3>'
            f'<p class="excerpt">{html_lib.escape(post["excerpt"])}</p>'
            '<span class="more">つづきを読む</span>'
            '</div></a>'
        )
    list_body = (
        '<section class="blog-hero"><div class="container">'
        '<span class="eyebrow">AIBS Diary</span>'
        '<h1>三姉妹のものづくり日記</h1>'
        '<p class="lead">AIを使ったショートアニメ動画づくりの裏側を、'
        '三姉妹がわいわいお喋りしながらお届けします。むずかしい言葉は、そのつどかみ砕いて。</p>'
        '</div></section>'
        '<section class="section" style="padding-top:0"><div class="container">'
        f'<div class="diary-list">{"".join(cards) if cards else "<p class=center>まだ日記がありません。</p>"}</div>'
        '</div></section>'
    )
    out = page("Diary | Lupinus Rossetti", prefix="../", active="blog", body=list_body,
               desc="AI Bloom Sisters 三姉妹がお届けする、AI動画づくりのものづくり日記。")
    (BLOG_DIR / "index.html").write_text(out, encoding="utf-8")

    inject_latest_into_home(posts)
    build_archive()

    tsum = " / ".join(f"{k}:{v}" for k, v in thumb_stats.items())
    print(f"[build] 記事 {len(posts)} 件 / アイコン {copied} 枚 / サムネ（{tsum}）/ 出力: {BLOG_DIR}")
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


def build_archive():
    data_path = SITE_DIR / "data" / "archive.json"
    if not data_path.exists():
        return
    data = json.loads(data_path.read_text(encoding="utf-8"))
    max_cards = data.get("max_cards", 10)
    sections_html = []
    for i, sec in enumerate(data.get("sections", [])):
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

        veil = " veil" if i % 2 == 1 else ""
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

    body = (
        '<section class="blog-hero"><div class="container">'
        '<span class="eyebrow">Archive</span>'
        '<h1>動画・配信アーカイブ</h1>'
        '<p class="lead">ショートアニメ作品とゲーム配信のアーカイブ、各SNSのショート動画をまとめてご覧いただけます。</p>'
        '</div></section>'
        + "".join(sections_html)
    )
    out = page("Archive | Lupinus Rossetti", prefix="", active="archive", body=body,
               desc="AI Bloom Sisters の動画・配信アーカイブ（YouTube / TikTok / Instagram）。")
    (SITE_DIR / "archive.html").write_text(out, encoding="utf-8")


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


if __name__ == "__main__":
    build()
