# -*- coding: utf-8 -*-
"""AIBS三姉妹の**出荷・投稿済みの絵**を集めて、このサイトのギャラリーを作る。

るぴちゃん依頼（2026-09-02）＝
  「AIBS三姉妹の今までの出荷分や投稿分もルピナスのサイトに、
    ひみつの眠り姫サイトのようなギャラリーを新規に作って並べたい」

🚨中身は共通エンジン（`aibs-ops/scripts/sns/gallery_core.py`）。
　 ひみつの眠り姫のギャラリーと**同じロジック**を使う（2本持つとズレるため）。
　 ここはこのサイトの設定だけを持つ。

  python build_sns_gallery.py [--force] [--keep] [--dry]

出すもの＝
  images/gallery-sns/sfw/{キャラ}/{id}.webp      （表示用）
  images/gallery-sns/sfw/{キャラ}/{id}_t.webp    （一覧用）
  data/sns-gallery.json                           （ページが読む目録）
"""
import argparse
import os
import sys

sys.path.insert(0, r"C:\ClaudeCode\aibs-ops\scripts\sns")
import gallery_core as G                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# 三姉妹（誰がいるかは `characters_sns.json` の `aibs.members` が正本）
# 🚨色は**このサイトの `assets/css/site.css` の変数と同じ値**にしてある
#   （--lupinus / --iris / --fiona）。サイトの見た目と食い違わせない。
CHARS = {
    "lupinus": dict(name="ルピナス", short="ルピナス", color="#8e7cc3"),
    "iris": dict(name="アイリス", short="アイリス", color="#c9a85c"),
    "fiona": dict(name="フィオナ", short="フィオナ", color="#e0809a"),
    "three": dict(name="三人いっしょ", short="三人", color="#6f5ca8"),
}
# フォルダ名の末尾やタイトルに出てくる呼び名
ALIAS = [
    ("lupinus", ("lupinus", "ルピナス")),
    ("iris", ("iris", "アイリス")),
    ("fiona", ("fiona", "フィオナ")),
]

SITE = G.Site(
    site_dir=HERE,
    # 🚨三姉妹は全年齢だけ（R18のアカウントを持たない）
    sources=[("AIBS三姉妹", False)],
    chars=CHARS,
    alias=ALIAS,
    img_rel="images/gallery-sns",
    data_name="sns-gallery.json",
    max_nsfw_level=0,
    # 🚨三姉妹の計画だけを見る。指定しないと**眠り姫の同時刻の枠**を拾ってしまう。
    #   （三姉妹の定時フォルダには名前が入っていないので、cast を計画から引く）
    plans_dirs={"aibs"},
    # ギャラリーのJSは正本から配ってもらう（ひみつの眠り姫と同じものが入る）
    js_dest="assets/js/sns-gallery.js",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="webpを作り直す")
    ap.add_argument("--keep", action="store_true", help="使わなくなったwebpを消さない")
    ap.add_argument("--dry", action="store_true", help="書かずに数える")
    a = ap.parse_args()
    rc = G.build(SITE, force=a.force, keep=a.keep, dry=a.dry)
    # 📺2026-09-05 るぴちゃん指示＝YouTubeショートに上げた漫画動画のギャラリー（gallery-videos.html）も
    #   同じ push に乗せる。目録は aibs-ops の youtube_folder.py --gallery が作る（台帳の URL 付きだけ）
    if not a.dry:
        import subprocess
        r = subprocess.run([sys.executable, r"C:\ClaudeCode\aibs-ops\scripts\sns\youtube_folder.py", "--gallery"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        sys.stdout.write(r.stdout or "")
        if r.returncode:
            sys.stderr.write(r.stderr or "")
            print("[NG] 動画ギャラリーの目録を作れなかった")
            rc = rc or 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
