# -*- coding: utf-8 -*-
"""Nanobanana2 ギャラリー取り込みスクリプト。

三姉妹LoRA学習素材（Gemini Nanobanana2生成 → るぴちゃんQC → LaMa透かし除去済みの
OK_clean 画像）を、750ギャラリーとは完全に別枠の「Nanobanana2」セクション用に
webp変換して取り込み、assets/data/nanobanana2.json を再生成する。

入力元:
  C:\\ClaudeCode\\flow-b-video-generator\\train_data_v4\\{char}\\img\\1_{char}\\OK_clean\\*.png
  （char = lupinus / iris / fiona。フォルダが無いキャラは黙ってスキップ）

出力先:
  images/gallery_nanobanana2/{char}/full/{char}_NNN.webp   … 長辺を抑えた表示用
  images/gallery_nanobanana2/{char}/thumbs/{char}_NNN.webp … サムネ（750ギャラリーのthumbsに解像度感を合わせる）
  assets/data/nanobanana2.json                              … 一覧データ（毎回全量再生成）

再実行について:
  このスクリプトは今後 iris/fiona のフォルダが出来た時・lupinusが増えた時に
  何度でも再実行される想定。毎回そのキャラの full/thumbs を全量作り直してから
  連番を振り直すので、素材が増減しても常に整合の取れた状態になる（差分更新はしない＝
  シンプルさ優先。仕様書の「毎回全量再生成でも構わない」を採用）。

使い方:
  cd C:\\LupinusPrivate
  python build_nanobanana2_gallery.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(r"C:\LupinusPrivate")
SRC_ROOT = Path(r"C:\ClaudeCode\flow-b-video-generator\train_data_v4")
OUT_ROOT = REPO_ROOT / "images" / "gallery_nanobanana2"
JSON_PATH = REPO_ROOT / "assets" / "data" / "nanobanana2.json"

CHARS = ["lupinus", "iris", "fiona"]
CHAR_LABEL = {"lupinus": "ルピナス", "iris": "アイリス", "fiona": "フィオナ"}

# 750ギャラリー既存 full/thumbs の解像度感（例: full 832x1216 / thumbs 400x584、
# いずれも横幅基準でアスペクト比を保ったままリサイズ）に合わせる。
FULL_MAX_WIDTH = 830
THUMB_WIDTH = 400
FULL_QUALITY = 85
THUMB_QUALITY = 80


def _resize_by_width(img: Image.Image, target_w: int) -> Image.Image:
    """横幅基準でアスペクト比を保ったままリサイズ（拡大はしない）。"""
    w, h = img.size
    if w <= target_w:
        return img
    scale = target_w / w
    return img.resize((target_w, max(1, round(h * scale))), Image.LANCZOS)


def _convert_one(src: Path, full_out: Path, thumb_out: Path):
    im = Image.open(src).convert("RGB")
    full_im = _resize_by_width(im, FULL_MAX_WIDTH)
    full_im.save(full_out, "WEBP", quality=FULL_QUALITY)
    thumb_im = _resize_by_width(im, THUMB_WIDTH)
    thumb_im.save(thumb_out, "WEBP", quality=THUMB_QUALITY)


def build_char(char: str):
    """1キャラ分の OK_clean を変換。フォルダが無ければ None を返してスキップ。"""
    src_dir = SRC_ROOT / char / "img" / f"1_{char}" / "OK_clean"
    if not src_dir.exists():
        print(f"[nanobanana2] {char}: OK_cleanフォルダ無し → スキップ")
        return None

    src_files = sorted(src_dir.glob("*.png")) + sorted(src_dir.glob("*.jpg")) + sorted(src_dir.glob("*.jpeg"))
    src_files = sorted(set(src_files))
    if not src_files:
        print(f"[nanobanana2] {char}: OK_clean は空 → スキップ")
        return None

    full_dir = OUT_ROOT / char / "full"
    thumb_dir = OUT_ROOT / char / "thumbs"
    # 毎回全量作り直し（増減しても連番がズレないように）
    if full_dir.exists():
        shutil.rmtree(full_dir)
    if thumb_dir.exists():
        shutil.rmtree(thumb_dir)
    full_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)

    items = []
    for i, src in enumerate(src_files, start=1):
        name = f"{char}_{i:03d}.webp"
        full_out = full_dir / name
        thumb_out = thumb_dir / name
        try:
            _convert_one(src, full_out, thumb_out)
        except Exception as e:
            print(f"[nanobanana2] 変換失敗: {src.name} ({e})")
            continue
        items.append({
            "char": char,
            "id": f"{char}_{i:03d}",
            "caption": f"{CHAR_LABEL[char]} Nanobanana2 #{i:03d}",
            "thumb": f"images/gallery_nanobanana2/{char}/thumbs/{name}",
            "full": f"images/gallery_nanobanana2/{char}/full/{name}",
        })

    print(f"[nanobanana2] {char}: {len(items)}枚 変換完了")
    return items


def main():
    all_items = []
    chars_meta = []
    for char in CHARS:
        items = build_char(char)
        if items:
            all_items.extend(items)
            chars_meta.append({"id": char, "total": len(items)})
        else:
            chars_meta.append({"id": char, "total": 0})

    data = {"chars": chars_meta, "items": all_items}
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[nanobanana2] {JSON_PATH} を書き出し（合計 {len(all_items)}枚）")


if __name__ == "__main__":
    main()
