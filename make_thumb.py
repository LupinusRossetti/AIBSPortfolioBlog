# -*- coding: utf-8 -*-
"""ブログ記事サムネの生成。

優先順位（3層）:
  1. 手動上書き … C:\\ClaudeCode\\note-diary\\thumbs\\{slug}.png（または {date}.png）が
     あれば、それをそのまま採用（あなたが用意したAIイラスト等）。
  2. Gemini生成 … GEMINI_API_KEY が使えるなら、三姉妹が主役のサムネをAI生成。
     一度作ったら blog/thumbs/{slug}.png にキャッシュ（毎回は生成しない＝課金/時間節約）。
  3. 自動合成 … 既存の三姉妹キャラ画像＋その日のタイトルで、上品なサムネをPILで合成。
     キーが無くても必ずこの層で成立する。

サムネは 1200x630（OGP互換）。サイトのブログカード／記事ヘッダ／OG画像に使う。
"""
from __future__ import annotations

import os
import re
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

DIARY_DIR = Path(r"C:\ClaudeCode\note-diary")
ICONS_DIR = DIARY_DIR / "icons"
OVERRIDE_DIR = DIARY_DIR / "thumbs"        # 手動上書き置き場
GEMINI_KEY_FILE = DIARY_DIR / ".gemini_key.txt"  # 鍵ファイル（gitignore済み・任意）

W, H = 1200, 630

# Windows 同梱フォント
FONT_TITLE = r"C:\Windows\Fonts\yumindb.ttf"   # 游明朝 Demibold（清楚な見出し）
FONT_TITLE2 = r"C:\Windows\Fonts\yumin.ttf"    # 游明朝
FONT_SCRIPT = r"C:\Windows\Fonts\segoescb.ttf"  # Segoe Script Bold（筆記体）
FONT_LABEL = r"C:\Windows\Fonts\YuGothM.ttc"   # 游ゴシック Medium

# 三姉妹カラー（サイトと統一）
LUPINUS = (142, 124, 195)
IRIS = (201, 168, 92)
FIONA = (224, 128, 154)
INK = (58, 55, 66)
INK_SOFT = (111, 106, 120)

# その日ごとに表情を少し変えて“活動の雰囲気”を出す（決定論的）
EXPR_SETS = [
    ("wink", "laugh", "happy"),
    ("smug", "surprised", "shy"),
    ("happy", "wink", "thinking"),
    ("normal", "laugh", "happy"),
    ("thinking", "happy", "wink"),
    ("laugh", "happy", "smug"),
    ("happy", "shy", "surprised"),
]


_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002190-\U000021FF\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF\U0000FE00-\U0000FE0F\U00002300-\U000023FF\U0000200D]")


def _strip_emoji(text: str) -> str:
    """游明朝で描けない絵文字・記号を除去（豆腐□防止）。"""
    return re.sub(r"\s{2,}", " ", _EMOJI_RE.sub("", text)).strip()


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _gemini_key():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key.strip()
    if GEMINI_KEY_FILE.exists():
        return GEMINI_KEY_FILE.read_text(encoding="utf-8").strip()
    return None


# ---------- 1. 手動上書き ----------
def find_override(slug: str, date_iso: str):
    for cand in (OVERRIDE_DIR / f"{slug}.png", OVERRIDE_DIR / f"{date_iso}.png",
                 OVERRIDE_DIR / f"{slug}.jpg", OVERRIDE_DIR / f"{date_iso}.jpg"):
        if cand.exists():
            return cand
    return None


# ---------- 2. Gemini生成 ----------
def gemini_generate(title: str, excerpt: str, out_path: Path) -> bool:
    key = _gemini_key()
    if not key:
        return False
    try:
        from google import genai
        from google.genai import types
    except Exception:
        return False
    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation")
    prompt = (
        "Soft, elegant anime-style YouTube thumbnail illustration, 16:9. "
        "Three sisters of the unit 'AI Bloom Sisters' as the main subject: "
        "Lupinus (eldest, long silver hair, calm gentle elegant big-sister), "
        "Iris (middle, blonde hair, cheerful energetic), "
        "Fiona (youngest, soft pink hair, gentle and kind). "
        "Pure, clean, pastel palette, white background, refined and cute, lots of soft light. "
        f"The scene gently expresses today's topic: {title}. {excerpt[:160]}. "
        "No text, no watermark, leave calm empty space on the left for a title overlay."
    )
    try:
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model=model, contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        img_bytes = None
        for part in resp.candidates[0].content.parts:
            data = getattr(part, "inline_data", None)
            if data and getattr(data, "data", None):
                img_bytes = data.data
                break
        if not img_bytes:
            return False
        import io
        base = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        base = _cover_resize(base, W, H)
        # タイトル等のオーバーレイを乗せて仕上げる
        _overlay_text(base, title, out_path, dark_scrim=True)
        print(f"[thumb] Gemini生成: {out_path.name}")
        return True
    except Exception as e:
        print(f"[thumb] Gemini生成スキップ（{e.__class__.__name__}）→ 合成にフォールバック")
        return False


def _cover_resize(img: Image.Image, w: int, h: int) -> Image.Image:
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
    x = (img.width - w) // 2
    y = (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


# ---------- 3. 自動合成 ----------
# アイコンは全キャラ共通構図（バストアップで顔が上寄り）。
# 顔を円の中心に収めるため、顔まわりにズームしつつ上方を残して切り出す。
FACE_ZOOM = 1.28      # 顔へのズーム率（>1で寄る＝顔が大きくなる）
FACE_CENTER_Y = 0.46  # 元画像の縦のどこを円の中心に置くか（0=上端,1=下端）


def _face_crop(src: Path, size: int) -> Image.Image:
    """顔が円の中心に来るよう、顔位置基準で正方形クロップ＋リサイズ。"""
    im = Image.open(src).convert("RGB")
    iw, ih = im.size
    # 切り出す正方形の一辺（元画像基準）。ズームが大きいほど小さく切る。
    crop = int(min(iw, ih) / FACE_ZOOM)
    cx = iw / 2
    cy = ih * FACE_CENTER_Y
    left = int(round(cx - crop / 2))
    top = int(round(cy - crop / 2))
    # 画像外にはみ出さないようクランプ
    left = max(0, min(left, iw - crop))
    top = max(0, min(top, ih - crop))
    im = im.crop((left, top, left + crop, top + crop))
    return im.resize((size, size), Image.LANCZOS)


def _circle_avatar(src: Path, size: int, ring: tuple, ring_w: int = 8) -> Image.Image:
    im = _face_crop(src, size).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    # リング
    ringed = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(ringed)
    d.ellipse((ring_w // 2, ring_w // 2, size - ring_w // 2, size - ring_w // 2),
              outline=ring + (255,), width=ring_w)
    out = Image.alpha_composite(out, ringed)
    return out


def _vertical_gradient(w, h, top, bottom):
    base = Image.new("RGB", (w, h), top)
    top_im = Image.new("RGB", (w, h), bottom)
    mask = Image.new("L", (w, h))
    md = mask.load()
    for y in range(h):
        v = int(255 * (y / h))
        for x in range(w):
            md[x, y] = v
    return Image.composite(top_im, base, mask)


def _soft_blob(canvas: Image.Image, cx, cy, r, color, alpha=70):
    blob = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(blob).ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (alpha,))
    blob = blob.filter(ImageFilter.GaussianBlur(r // 2))
    canvas.alpha_composite(blob)


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        test = cur + ch
        if draw.textlength(test, font=font) > max_w and cur:
            lines.append(cur); cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines[:4]


def _expr_for(date_iso: str):
    try:
        _, m, d = (int(x) for x in date_iso.split("-"))
        idx = (m * 31 + d) % len(EXPR_SETS)
    except Exception:
        idx = 0
    return EXPR_SETS[idx]


def compose(title: str, date_iso: str, date_label: str, out_path: Path):
    canvas = _vertical_gradient(W, H, (255, 255, 255), (250, 247, 252)).convert("RGBA")
    # やわらかな三姉妹カラーの光
    _soft_blob(canvas, 980, 150, 260, LUPINUS, 55)
    _soft_blob(canvas, 1120, 430, 240, FIONA, 55)
    _soft_blob(canvas, 880, 520, 220, IRIS, 45)

    draw = ImageDraw.Draw(canvas)
    # 内側の細フレーム
    draw.rectangle((26, 26, W - 27, H - 27), outline=(221, 213, 230, 255), width=2)

    # 三姉妹アバター（右側に少し重ねて扇状に）
    expr = _expr_for(date_iso)
    chars = [("lupinus", LUPINUS), ("iris", IRIS), ("fiona", FIONA)]
    av_size = 250
    positions = [(720, 70), (905, 200), (705, 360)]
    for (cname, color), e, (px, py) in zip(chars, expr, positions):
        src = ICONS_DIR / f"{cname}_{e}.png"
        if not src.exists():
            src = ICONS_DIR / f"{cname}_normal.png"
        if src.exists():
            av = _circle_avatar(src, av_size, color)
            sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(sh).ellipse((px + 8, py + 14, px + av_size + 8, py + av_size + 14),
                                       fill=(78, 64, 110, 60))
            sh = sh.filter(ImageFilter.GaussianBlur(12))
            canvas.alpha_composite(sh)
            canvas.alpha_composite(av, (px, py))

    # 左側テキスト
    f_script = _font(FONT_SCRIPT, 56)
    f_brand = _font(FONT_LABEL, 22)
    f_title = _font(FONT_TITLE, 52)
    f_date = _font(FONT_TITLE2, 26)

    x0 = 72
    draw.text((x0, 70), "Diary", font=f_script, fill=LUPINUS + (255,))
    draw.text((x0 + 4, 142), "AI BLOOM SISTERS", font=f_brand, fill=INK_SOFT + (255,))
    # 区切りの小さなダイヤ
    draw.line((x0 + 6, 188, x0 + 150, 188), fill=(221, 213, 230, 255), width=2)

    lines = _wrap(draw, _strip_emoji(title), f_title, max_w=560)
    ty = 224
    for ln in lines:
        draw.text((x0, ty), ln, font=f_title, fill=INK + (255,))
        ty += 70

    draw.text((x0 + 2, max(ty + 6, 470)), date_label, font=f_date, fill=IRIS + (255,))

    canvas.convert("RGB").save(out_path, "PNG")
    print(f"[thumb] 合成: {out_path.name}")


def _overlay_text(base_rgb: Image.Image, title: str, out_path: Path, dark_scrim=False):
    """Gemini画像の上にタイトル等を上品に重ねる。"""
    canvas = base_rgb.convert("RGBA")
    if dark_scrim:
        scrim = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(scrim).rectangle((0, 0, 600, H), fill=(255, 255, 255, 150))
        scrim = scrim.filter(ImageFilter.GaussianBlur(40))
        canvas.alpha_composite(scrim)
    draw = ImageDraw.Draw(canvas)
    f_script = _font(FONT_SCRIPT, 52)
    f_title = _font(FONT_TITLE, 50)
    x0 = 64
    draw.text((x0, 70), "Diary", font=f_script, fill=LUPINUS + (255,))
    lines = _wrap(draw, _strip_emoji(title), f_title, max_w=520)
    ty = 170
    for ln in lines:
        draw.text((x0, ty), ln, font=f_title, fill=INK + (255,))
        ty += 66
    canvas.convert("RGB").save(out_path, "PNG")


# ---------- エントリ ----------
def ensure_thumb(slug: str, date_iso: str, date_label: str, title: str,
                 excerpt: str, out_path: Path) -> str:
    """サムネを用意して、生成方法を返す（'override'|'gemini'|'compose'）。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ov = find_override(slug, date_iso)
    if ov:
        # ブラウザでGemini生成して thumbs/ に保存した画像（または任意の手動画像）を採用
        img = _cover_resize(Image.open(ov).convert("RGB"), W, H)
        img.save(out_path, "PNG")
        print(f"[thumb] 手動/Gemini画像を採用: {ov.name}")
        return "override"

    # Gemini はキャッシュ優先（既にある＝生成済みなら作り直さない）
    marker = out_path.with_suffix(".gemini")
    if marker.exists() and out_path.exists():
        return "gemini"
    if gemini_generate(title, excerpt, out_path):
        marker.write_text("1", encoding="utf-8")
        return "gemini"

    compose(title, date_iso, date_label, out_path)
    return "compose"
