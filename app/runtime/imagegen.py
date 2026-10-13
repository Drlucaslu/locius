"""Image generation client: the OpenAI-compatible Images API (POST {base}/images/generations) — the Olares Router, OpenAI
(gpt-image-1 / DALL·E 3), or any local server that speaks the same schema. Replaceable by design, like llm.py.

Settings (runtime Settings): image_base_url ("" = the model endpoint), image_model ("" = auto-pick an image model the
endpoint serves). The key comes from the environment only (OMUSE_IMAGE_API_KEY, else the model key), never from Settings.
"""
from __future__ import annotations

import base64
import os
import re
import time

import httpx

from app.runtime.llm import auth_headers

# model ids that generate images (vision-LANGUAGE models like Qwen-VL understand images, they don't make them)
IMG_KEYS = ("gpt-image", "dall", "flux", "diffus", "sdxl", "sd3", "sd-", "stable", "imagen", "kolors", "janus",
            "qwen-image", "hidream", "playground", "image")
NOT_IMG = ("embed", "rerank", "whisper", "-vl", "vision", "tts", "kokoro", "speech", "ocr", "caption")
IMG_MODES = ("image", "image_generation", "images", "text-to-image", "t2i")

# aspect words / ratios -> candidate sizes, best first. gpt-image-1 wants 1024x1024 / 1536x1024 / 1024x1536, DALL·E 3
# wants 1024x1024 / 1792x1024 / 1024x1792, local SD servers take most multiples of 64 — so each shape lists fallbacks
# and generate() walks them when the server rejects a size.
SIZES = {
    "square": ["1024x1024", "1024x1024"],
    "landscape": ["1536x1024", "1792x1024", "1344x768", "1024x1024"],
    "portrait": ["1024x1536", "1024x1792", "768x1344", "1024x1024"],
}


class ImageError(Exception):
    pass


# Round 3 — style control. A short style word (English or Chinese) becomes a concrete prompt suffix the image models
# respond to, like Midjourney's style keywords / DALL·E's style presets. Unknown words are passed through as "<word> style".
STYLE_PRESETS = {
    "photorealistic": "photorealistic, ultra-detailed, natural lighting, shot on a DSLR, 85mm lens, shallow depth of field",
    "cinematic": "cinematic still, dramatic lighting, anamorphic lens, film grain, moody colour grading",
    "anime": "anime style, clean line art, cel shading, vibrant colours, Studio-quality key visual",
    "watercolor": "watercolor painting, soft washes, visible paper texture, loose brushwork, pastel palette",
    "oil painting": "oil painting, visible impasto brushstrokes, rich warm palette, classical composition",
    "3d render": "3D render, octane render, soft studio lighting, subsurface scattering, high detail",
    "flat vector": "flat vector illustration, minimal shapes, bold solid colours, clean geometry, no gradients",
    "pixel art": "pixel art, 16-bit, limited palette, crisp pixels",
    "sketch": "pencil sketch, hand-drawn lines, cross-hatching, white paper",
    "ink wash": "traditional Chinese ink wash painting (shuimo), expressive brush strokes, rice paper, negative space",
    "line art": "black-and-white line art, single-weight outlines, no shading",
    "isometric": "isometric illustration, clean 30° geometry, soft shadows",
    "low poly": "low-poly 3D style, faceted surfaces, pastel lighting",
    "pop art": "pop art, bold outlines, halftone dots, saturated primary colours",
    "minimalist": "minimalist composition, lots of negative space, one focal subject, muted palette",
    "logo": "clean logo design, flat vector, centred mark, simple shapes, solid background, no text unless asked",
    "product": "product photography, white seamless background, soft box lighting, sharp focus, commercial quality",
}
_STYLE_ZH = {
    "写实": "photorealistic", "真实": "photorealistic", "照片": "photorealistic", "摄影": "photorealistic",
    "电影": "cinematic", "电影感": "cinematic", "动漫": "anime", "二次元": "anime", "日漫": "anime",
    "水彩": "watercolor", "油画": "oil painting", "3d": "3d render", "三维": "3d render", "渲染": "3d render",
    "扁平": "flat vector", "矢量": "flat vector", "插画": "flat vector", "像素": "pixel art", "素描": "sketch",
    "铅笔": "sketch", "水墨": "ink wash", "国画": "ink wash", "线稿": "line art", "等距": "isometric",
    "低多边形": "low poly", "波普": "pop art", "极简": "minimalist", "简约": "minimalist", "logo": "logo",
    "标志": "logo", "产品图": "product", "商品图": "product", "电商": "product",
}


def style_suffix(style: str | None) -> str:
    """The prompt suffix for a style word ('水彩', 'anime', 'oil painting' …); '' when no style was given."""
    s = str(style or "").strip().lower()
    if not s:
        return ""
    if s in STYLE_PRESETS:
        return STYLE_PRESETS[s]
    for zh, en in _STYLE_ZH.items():
        if zh in s:
            return STYLE_PRESETS[en]
    for key, suffix in STYLE_PRESETS.items():   # 'photo' / 'realistic' / 'water color' …
        if key.replace(" ", "") in s.replace(" ", "") or s.replace(" ", "") in key.replace(" ", ""):
            return suffix
    return f"{s} style"


def with_style(prompt: str, style: str | None) -> str:
    suf = style_suffix(style)
    if not suf or suf.split(",")[0].lower() in prompt.lower():
        return prompt
    return f"{prompt.rstrip('. ')}, {suf}"


def image_auth_headers(settings: dict | None = None) -> dict:
    """The key for the image endpoint: with the user's own model settings in force, their key (the system's
    OMUSE_IMAGE_API_KEY must never go to a user's endpoint); otherwise OMUSE_IMAGE_API_KEY, else the model endpoint's key."""
    if settings and settings.get("model_override"):
        return auth_headers(settings)
    key = (os.environ.get("OMUSE_IMAGE_API_KEY") or "").strip()
    return {"Authorization": f"Bearer {key}"} if key else auth_headers(settings)


def pick_image_model(models: list[dict]) -> str:
    """The first model that generates images: an explicit image mode wins, else judge by the name. Loading models are
    skipped; vision-language / embedding / speech models are never picked."""
    by_name = []
    for m in models:
        mid = str(m.get("id") or "")
        if not mid:
            continue
        low = mid.lower()
        mode = str(m.get("mode") or m.get("type") or "").lower()
        if str(m.get("readiness") or "ready").lower() not in ("ready", "running", "loaded"):
            continue
        if mode in IMG_MODES:
            return mid
        if mode and mode not in IMG_MODES:
            continue   # the server says it is something else (chat / embedding / tts …)
        if any(k in low for k in NOT_IMG):
            continue
        if any(k in low for k in IMG_KEYS):
            by_name.append(mid)
    return by_name[0] if by_name else ""


def shape_of(size: str | None, aspect: str | None = None) -> tuple[str, list[str]]:
    """Normalise what the model asked for into a shape name and the sizes to try, best first.
    Accepts '1024x1024', ratios like '16:9' / '9:16' / '1:1' / '4:3', or words (square / landscape / portrait / wide / tall)."""
    s = str(size or aspect or "").strip().lower()
    m = re.fullmatch(r"(\d{3,4})\s*[x×*]\s*(\d{3,4})", s)
    if m:   # an explicit size: try it first, then the matching shape's fallbacks
        w, h = int(m.group(1)), int(m.group(2))
        shape = "square" if w == h else ("landscape" if w > h else "portrait")
        return shape, [f"{w}x{h}"] + [x for x in SIZES[shape] if x != f"{w}x{h}"]
    m = re.fullmatch(r"(\d{1,2})\s*[:/]\s*(\d{1,2})", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        shape = "square" if a == b else ("landscape" if a > b else "portrait")
        return shape, list(dict.fromkeys(SIZES[shape]))
    if s in ("", "square", "1", "方", "方形", "正方形"):
        return "square", ["1024x1024"]
    if any(k in s for k in ("land", "wide", "horizontal", "横", "宽", "banner", "16:9", "cover", "desktop", "桌面", "电脑")):
        return "landscape", list(dict.fromkeys(SIZES["landscape"]))
    if any(k in s for k in ("port", "tall", "vertical", "竖", "phone", "手机", "story", "poster", "海报")):
        return "portrait", list(dict.fromkeys(SIZES["portrait"]))
    return "square", ["1024x1024"]


def _bad_size(text: str) -> bool:
    t = (text or "").lower()
    return "size" in t or "dimension" in t or "resolution" in t or "width" in t or "height" in t


async def list_models(base: str, timeout: float = 15, settings: dict | None = None) -> list[dict]:
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.get(f"{base}/models", headers=image_auth_headers(settings))
    if r.status_code >= 400:
        raise ImageError(f"HTTP {r.status_code} from {base}/models")
    data = r.json()
    return [m for m in (data.get("data") or data.get("models") or []) if isinstance(m, dict)]


async def resolve(settings: dict) -> tuple[str, str]:
    """(base_url, model) for image generation, or raise ImageError with a message the agent can relay."""
    base = str(settings.get("image_base_url") or settings.get("model_base_url") or "").rstrip("/")
    if not base:
        raise ImageError("没有配置模型地址 (no model endpoint configured: Settings → Model endpoint)")
    model = str(settings.get("image_model") or "").strip()
    if model:
        return base, model
    try:
        model = pick_image_model(await list_models(base, settings=settings))
    except Exception as e:
        raise ImageError(f"无法读取模型列表 (could not list models at the endpoint): {str(e)[:120]}")
    if not model:
        raise ImageError("模型端点上没有图像生成模型 (the endpoint serves no image-generation model). "
                         "在 Settings → Image model 填一个图像模型（如 gpt-image-1 / dall-e-3 / FLUX），或设置 image_base_url 指向一个"
                         "支持 OpenAI Images API 的服务 (set Settings → Image model, or point image_base_url at an OpenAI-Images-compatible server).")
    return base, model


# optional request fields: dropped one by one when a server says it doesn't know them (OpenAI rejects negative_prompt,
# local SD servers reject background / output_format / quality …), so one code path serves every vendor
OPTIONAL_FIELDS = ("response_format", "quality", "negative_prompt", "background", "output_format", "style")


def _moderated(status: int, text: str) -> bool:
    t = (text or "").lower()
    return status in (400, 403) and any(k in t for k in ("content_policy", "safety system", "moderation", "not allowed by our",
                                                           "violat", "rejected as a result of", "blocked"))


async def generate(settings: dict, prompt: str, *, size: str | None = None, aspect: str | None = None, n: int = 1,
                   quality: str | None = None, model: str | None = None, timeout: float | None = None,
                   negative_prompt: str | None = None, background: str | None = None, output_format: str | None = None,
                   vendor_style: str | None = None) -> dict:
    """Make `n` images. Returns {"images": [png bytes …], "model", "size", "latency_s", "revised_prompt"}.
    Walks the size fallbacks when the server rejects one, and drops optional fields the server doesn't know — so
    gpt-image-1, DALL·E 3 and local SD servers all work without per-vendor code. background='transparent' and
    output_format (png/jpeg/webp) follow gpt-image-1; negative_prompt follows SD-style servers; vendor_style is
    DALL·E 3's vivid/natural."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise ImageError("需要图片描述 (prompt required)")
    base, mdl = await resolve(settings)
    if model:
        mdl = model
    n = max(1, min(int(n or 1), 4))
    shape, sizes = shape_of(size, aspect)
    t0 = time.time()
    tmo = httpx.Timeout(float(timeout or settings.get("llm_timeout") or 600), connect=15)
    last = ""
    body = {"model": mdl, "prompt": prompt, "n": n, "response_format": "b64_json"}
    for k, v in (("quality", quality), ("negative_prompt", negative_prompt), ("background", background),
                 ("output_format", output_format), ("style", vendor_style)):
        if v:
            body[k] = v
    async with httpx.AsyncClient(timeout=tmo) as c:
        for sz in sizes:
            body["size"] = sz
            for _ in range(len(OPTIONAL_FIELDS) + 1):   # strip fields the server rejects, then retry the same size
                try:
                    r = await c.post(f"{base}/images/generations", json=body, headers=image_auth_headers(settings))
                except httpx.TimeoutException:
                    raise ImageError("图像生成超时 (image generation timed out) — 稍后再试一次 try once more later")
                if r.status_code < 400:
                    break
                txt = r.text[:300]
                low = txt.lower()
                if _moderated(r.status_code, txt):
                    raise ImageError("内容被模型的安全策略拒绝 (the image model's safety policy declined this prompt) — "
                                     "换一个描述；不要重试同样的内容 rephrase; do not retry the same prompt")
                hit = [f for f in OPTIONAL_FIELDS if f in body and f in low]      # the field the server named
                if not hit and any(k in low for k in ("unknown parameter", "unrecognized", "unexpected", "extra_forbidden")):
                    hit = [f for f in OPTIONAL_FIELDS if f in body][:1]        # unnamed: drop optionals one at a time
                if r.status_code == 400 and hit:
                    body.pop(hit[0]); continue
                if r.status_code == 400 and _bad_size(low):
                    last = txt; r = None; break   # try the next size
                raise ImageError(f"图像生成失败 image generation failed HTTP {r.status_code}: {txt}")
            if r is None:
                continue
            data = r.json()
            items = data.get("data") or []
            out = []
            for it in items:
                if it.get("b64_json"):
                    out.append(base64.b64decode(it["b64_json"]))
                elif it.get("url"):
                    rr = await c.get(it["url"])
                    if rr.status_code < 400:
                        out.append(rr.content)
            if not out:
                raise ImageError("图像生成没有返回图片 (the server returned no image data)")
            return {"images": out, "model": mdl, "size": sz, "shape": shape, "latency_s": round(time.time() - t0, 1),
                    "revised_prompt": str((items[0] or {}).get("revised_prompt") or "")}
    raise ImageError(f"服务不接受任何尺寸 (the server rejected every size tried: {', '.join(sizes)}): {last}")


# ------------------------------------------------------------------ Rounds 4-6: edit (inpainting / img2img) + variations
VARIATION_PROMPT = ("Create a close variation of this image: keep the same subject, composition, style and palette, "
                    "with small natural differences in details and pose")


def _guess_mime(name: str) -> str:
    n = (name or "").lower()
    return "image/jpeg" if n.endswith((".jpg", ".jpeg")) else "image/webp" if n.endswith(".webp") else "image/png"


async def edit(settings: dict, images: list[tuple[str, bytes]], prompt: str, *, mask: bytes | None = None,
               size: str | None = None, aspect: str | None = None, n: int = 1, model: str | None = None,
               timeout: float | None = None) -> dict:
    """POST {base}/images/edits (multipart). `images` = [(filename, bytes)…]: the first is the picture being edited; more
    are reference images (gpt-image-1 takes several). `mask`: PNG whose transparent pixels mark the area to repaint
    (inpainting). Without a mask, gpt-image-1 edits by prompt. Size fallbacks and unknown-field dropping as in generate()."""
    prompt = (prompt or "").strip()
    if not images:
        raise ImageError("需要一张图片 (an image is required)")
    if not prompt:
        raise ImageError("需要说明怎么改 (prompt required: what to change)")
    base, mdl = await resolve(settings)
    if model:
        mdl = model
    n = max(1, min(int(n or 1), 4))
    shape, sizes = shape_of(size, aspect)
    t0 = time.time()
    tmo = httpx.Timeout(float(timeout or settings.get("llm_timeout") or 600), connect=15)
    data = {"model": mdl, "prompt": prompt, "n": str(n), "response_format": "b64_json"}
    last = ""
    async with httpx.AsyncClient(timeout=tmo) as c:
        for sz in sizes:
            data["size"] = sz
            multi = len(images) > 1
            for attempt in range(6):
                files = []
                for i, (name, blob) in enumerate(images):
                    files.append(("image[]" if multi else "image", (name or f"image{i}.png", blob, _guess_mime(name))))
                if mask:
                    files.append(("mask", ("mask.png", mask, "image/png")))
                try:
                    r = await c.post(f"{base}/images/edits", data=data, files=files, headers=image_auth_headers(settings))
                except httpx.TimeoutException:
                    raise ImageError("图像编辑超时 (image edit timed out) — 稍后再试一次 try once more later")
                if r.status_code < 400:
                    break
                txt = r.text[:300]
                low = txt.lower()
                if _moderated(r.status_code, txt):
                    raise ImageError("内容被模型的安全策略拒绝 (the image model's safety policy declined this edit) — "
                                     "换一个描述；不要重试同样的内容 rephrase; do not retry the same prompt")
                if r.status_code == 400 and "response_format" in low and "response_format" in data:
                    data.pop("response_format"); continue
                if r.status_code == 400 and multi and ("image[]" in low or "image" in low and "array" in low):
                    images, multi = images[:1], False; continue    # server takes one image: keep the main one
                if r.status_code == 400 and _bad_size(low):
                    last = txt; r = None; break
                if r.status_code == 404 or (r.status_code == 400 and "mask" in low and mask):
                    raise ImageError(f"这个模型/服务不支持图片编辑 (this model or server does not support image edits): {txt}")
                raise ImageError(f"图像编辑失败 image edit failed HTTP {r.status_code}: {txt}")
            if r is None:
                continue
            items = (r.json().get("data") or [])
            out = []
            for it in items:
                if it.get("b64_json"):
                    out.append(base64.b64decode(it["b64_json"]))
                elif it.get("url"):
                    rr = await c.get(it["url"])
                    if rr.status_code < 400:
                        out.append(rr.content)
            if not out:
                raise ImageError("图像编辑没有返回图片 (the server returned no image data)")
            return {"images": out, "model": mdl, "size": sz, "shape": shape, "latency_s": round(time.time() - t0, 1),
                    "revised_prompt": str((items[0] or {}).get("revised_prompt") or "")}
    raise ImageError(f"服务不接受任何尺寸 (the server rejected every size tried: {', '.join(sizes)}): {last}")


async def variation(settings: dict, image: tuple[str, bytes], *, prompt: str = "", n: int = 1, size: str | None = None,
                    aspect: str | None = None, model: str | None = None, timeout: float | None = None) -> dict:
    """Variations of one image: {base}/images/variations when the server has it (DALL·E 2 style), otherwise an edit with a
    'close variation' prompt (gpt-image-1 and most local servers)."""
    base, mdl = await resolve(settings)
    if model:
        mdl = model
    n = max(1, min(int(n or 1), 4))
    shape, sizes = shape_of(size, aspect)
    tmo = httpx.Timeout(float(timeout or settings.get("llm_timeout") or 600), connect=15)
    t0 = time.time()
    async with httpx.AsyncClient(timeout=tmo) as c:
        try:
            r = await c.post(f"{base}/images/variations", data={"model": mdl, "n": str(n), "size": sizes[0], "response_format": "b64_json"},
                             files=[("image", (image[0] or "image.png", image[1], _guess_mime(image[0])))], headers=image_auth_headers(settings))
        except httpx.TimeoutException:
            r = None
        if r is not None and r.status_code < 400:
            items = r.json().get("data") or []
            out = [base64.b64decode(it["b64_json"]) for it in items if it.get("b64_json")]
            if out:
                return {"images": out, "model": mdl, "size": sizes[0], "shape": shape, "latency_s": round(time.time() - t0, 1),
                        "revised_prompt": "", "via": "variations"}
    p = VARIATION_PROMPT + (f". Also: {prompt.strip()}" if prompt and prompt.strip() else "")
    res = await edit(settings, [image], p, size=size, aspect=aspect, n=n, model=model, timeout=timeout)
    res["via"] = "edit"
    return res
