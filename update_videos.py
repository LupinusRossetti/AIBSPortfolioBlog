# -*- coding: utf-8 -*-
"""AIBS YouTube動画 自動更新スクリプト。

YouTubeチャンネルのRSSフィードから新着動画を取得し、
data/archive.json の各セクション(最新の動画/AIショートアニメ/ライブ配信)へ反映する。

- RSSは最新15件まで。新規動画のみ追加(既存IDは保持)。
- oEmbedで動画のwidth/heightを取得し、縦長(width<height)=ショート、横長=本編/配信と分類。
- タイトルに「配信」「ライブ」を含む横長=ライブ配信、それ以外の横長=本編、縦長=AIショートアニメ。
- 自動追記したアイテムには "auto": true を付け、手動追加と区別する。
- 実行後に build_blog.py を呼び、サイトHTMLを再生成する。

自走方針:
- channel_idは @AIBloomSisters のHTMLからexternalId/browseIdを抽出する(取得済み: UC7dZB73rrcg7btiAXO78bdw)。
- 取得失敗時はCHANNEL_ID_FALLBACKを使う。
"""
from __future__ import annotations

import io
import json
import re
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent
ARCHIVE_JSON = SITE_DIR / "data" / "archive.json"

CHANNEL_HANDLE = "@AIBloomSisters"
CHANNEL_ID_FALLBACK = "UC7dZB73rrcg7btiAXO78bdw"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

# 縦長(ショート)の最大保持数とポートフォリオ表示数の上限
MAX_KEEP_PER_SECTION = 30
SNS_LATEST_COUNT = 4
SNS_LIVE_COUNT = 4
SNS_ANIME_COUNT = 4
PORTFOLIO_LIVE_COUNT = 6


def fetch(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def resolve_channel_id() -> str:
    """@AIBloomSisters の公開HTMLから channelId を抽出。
    取得できなければフォールバックを返す。"""
    try:
        html = fetch(f"https://www.youtube.com/{CHANNEL_HANDLE}").decode("utf-8", "ignore")
        m = re.search(r'"externalId":"(UC[A-Za-z0-9_-]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'"browseId":"(UC[A-Za-z0-9_-]+)"', html)
        if m:
            return m.group(1)
    except Exception as e:
        print(f"[update_videos] channelId抽出失敗 -> フォールバック使用: {e}")
    return CHANNEL_ID_FALLBACK


def fetch_rss(channel_id: str) -> list[dict]:
    """RSSから videoId / title / published を抜き出す。"""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    xml = fetch(url)
    root = ET.fromstring(xml)
    items = []
    for entry in root.findall("atom:entry", NS):
        vid_el = entry.find("yt:videoId", NS)
        title_el = entry.find("atom:title", NS)
        pub_el = entry.find("atom:published", NS)
        if vid_el is None or title_el is None or pub_el is None:
            continue
        pub = pub_el.text or ""
        d = pub[:10] if len(pub) >= 10 else ""
        items.append({
            "id": vid_el.text,
            "title": title_el.text or "",
            "date": d,
        })
    return items


def oembed_orientation(video_id: str) -> str | None:
    """oEmbedの width/height から動画の向きを推定。
    'short' = 縦長, 'wide' = 横長, None = 取得不可。"""
    try:
        url = f"https://www.youtube.com/oembed?url=https://youtu.be/{video_id}&format=json"
        data = json.loads(fetch(url, timeout=10).decode("utf-8"))
        w = int(data.get("width") or 0)
        h = int(data.get("height") or 0)
        if w and h:
            return "short" if h > w else "wide"
    except Exception:
        return None
    return None


def classify(item: dict) -> str:
    """動画を youtube_anime / youtube_live / youtube_latest のいずれかに分類。

    1) oEmbedで縦長判定 -> youtube_anime
    2) タイトルに配信/ライブ/Live のキーワード -> youtube_live
    3) それ以外（横長の本編アニメ） -> youtube_latest
    """
    orient = oembed_orientation(item["id"])
    if orient == "short":
        return "youtube_anime"
    title = item.get("title", "")
    live_kws = ["配信", "ライブ", "Live", "LIVE", "live", "実況"]
    if any(k in title for k in live_kws):
        return "youtube_live"
    return "youtube_latest"


def merge_section(section: dict, new_items: list[dict]) -> int:
    """section.items に new_items のうち未収載のものを auto:true 付きで追記。
    返り値は追加件数。"""
    existing_ids = {it.get("id") for it in section.get("items", [])}
    added = 0
    for it in new_items:
        if it["id"] in existing_ids:
            continue
        section.setdefault("items", []).append({**it, "auto": True})
        added += 1
    # 日付降順で並べ、上限まで残す（手動追加も含めて整理）
    section["items"].sort(key=lambda x: x.get("date", ""), reverse=True)
    if len(section["items"]) > MAX_KEEP_PER_SECTION:
        # 手動分は優先保持、auto分のみ末尾から削る
        kept = []
        autos_tail = []
        for it in section["items"]:
            if it.get("auto"):
                autos_tail.append(it)
            else:
                kept.append(it)
        room = MAX_KEEP_PER_SECTION - len(kept)
        kept_autos = autos_tail[:max(0, room)]
        section["items"] = sorted(kept + kept_autos, key=lambda x: x.get("date", ""), reverse=True)
    return added


def update_archive() -> dict:
    data = json.loads(ARCHIVE_JSON.read_text(encoding="utf-8"))
    sections = {s["key"]: s for s in data.get("sections", []) if "key" in s}

    channel_id = resolve_channel_id()
    print(f"[update_videos] channel_id={channel_id}")
    rss = fetch_rss(channel_id)
    print(f"[update_videos] RSS取得: {len(rss)}件")

    # 既存IDをまとめておき、新規だけ分類処理（oEmbed節約）
    all_existing = set()
    for s in sections.values():
        for it in s.get("items", []):
            all_existing.add(it.get("id"))

    classified: dict[str, list[dict]] = {"youtube_latest": [], "youtube_anime": [], "youtube_live": []}
    for item in rss:
        if item["id"] in all_existing:
            continue
        key = classify(item)
        classified[key].append(item)
        print(f"[update_videos] 新規: [{key}] {item['date']} {item['title'][:40]}")

    total_added = 0
    for key, new_items in classified.items():
        if key not in sections:
            continue
        total_added += merge_section(sections[key], new_items)

    ARCHIVE_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[update_videos] 追加合計 {total_added} 件 -> {ARCHIVE_JSON.name} 更新")
    return data


# === ポートフォリオページのマーカー差し込み ===
def _iframe_card(it: dict, shorts: bool = False) -> str:
    vid = it.get("id", "")
    title = (it.get("title", "") or "").replace('"', "&quot;")
    cls = "video-embed shorts" if shorts else "video-embed"
    caption = it.get("title", "") or ""
    return (
        f'        <div class="{cls}">\n'
        f'          <div class="frame16x9">\n'
        f'            <iframe src="https://www.youtube-nocookie.com/embed/{vid}" title="{title}"\n'
        f'              loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"\n'
        f'              allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>\n'
        f'          </div>\n'
        f'          <div class="video-caption">{caption}</div>\n'
        f'        </div>\n'
    )


def _section_items(data: dict, key: str) -> list[dict]:
    for s in data.get("sections", []):
        if s.get("key") == key:
            items = list(s.get("items", []))
            items.sort(key=lambda x: x.get("date", ""), reverse=True)
            return items
    return []


def inject_portfolio_videos(data: dict) -> None:
    """portfolio.html の3マーカーへ最新動画iframeを差し込む。"""
    p = SITE_DIR / "portfolio.html"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")

    latest_items = _section_items(data, "youtube_latest")[:1]  # 本編は最新1本
    anime_items = _section_items(data, "youtube_anime")[:4]
    live_items = _section_items(data, "youtube_live")[:PORTFOLIO_LIVE_COUNT]

    blocks = {
        "PORTFOLIO_VIDEOS_LATEST": "".join(_iframe_card(it) for it in latest_items),
        "PORTFOLIO_VIDEOS_ANIME": "".join(_iframe_card(it, shorts=True) for it in anime_items),
        "PORTFOLIO_VIDEOS_LIVE": "".join(_iframe_card(it) for it in live_items),
    }
    new_text = text
    for marker, content in blocks.items():
        pattern = re.compile(
            rf"<!--{marker}-->.*?<!--/{marker}-->", re.S
        )
        replacement = f"<!--{marker}-->\n{content}        <!--/{marker}-->"
        new_text = pattern.sub(replacement, new_text)
    if new_text != text:
        p.write_text(new_text, encoding="utf-8")
        print(f"[update_videos] portfolio.html マーカー差し込み完了")


def main() -> int:
    if not ARCHIVE_JSON.exists():
        print(f"[update_videos] エラー: {ARCHIVE_JSON} が見つかりません", file=sys.stderr)
        return 1
    data = update_archive()
    inject_portfolio_videos(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
