"""Batch image conversion; originals are never overwritten."""
from pathlib import Path
import os
from io import BytesIO

from PIL import Image, ImageOps

FORMATS = {"JPG": (".jpg", "JPEG"), "PNG": (".png", "PNG"), "WebP": (".webp", "WEBP")}
RAW_EXTENSIONS = {".dng", ".nef", ".cr2", ".cr3", ".arw", ".raf", ".orf", ".rw2"}


def convert(source, output_dir, output_format="JPG", quality=85, max_side=0, target_kb=0):
    source, output_dir = Path(source), Path(output_dir)
    if not 1 <= quality <= 100 or max_side < 0 or target_kb < 0:
        raise ValueError("화질은 1~100, 최대 길이는 0 이상이어야 합니다.")
    extension, format_name = FORMATS[output_format]
    output_dir.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in RAW_EXTENSIONS:
        import rawpy
        with rawpy.imread(str(source)) as raw:
            pixels = raw.postprocess(use_camera_wb=True, output_bps=8)
        picture = Image.fromarray(pixels)
    else:
        with Image.open(source) as opened:
            picture = ImageOps.exif_transpose(opened).copy()
    try:
        if max_side:
            picture.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        if format_name == "JPEG":
            if picture.mode in ("RGBA", "LA") or "transparency" in picture.info:
                rgba = picture.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                picture.close()
                picture = background
            else:
                converted = picture.convert("RGB")
                picture.close()
                picture = converted
        options = {"optimize": True} if format_name == "PNG" else {"quality": quality}
        if format_name == "JPEG":
            options.update(optimize=True)
        # Measure the encoded bytes; lower quality first, then resolution.
        # PNG stays lossless and uses resolution changes only.
        encoded = BytesIO()
        current_quality = quality
        while True:
            encoded.seek(0)
            encoded.truncate()
            picture.save(encoded, format=format_name, **options)
            if not target_kb or encoded.tell() <= target_kb * 1024:
                break
            if format_name != "PNG" and current_quality > 35:
                current_quality = max(35, current_quality - 10)
                options["quality"] = current_quality
                continue
            width, height = picture.size
            if width == 1 and height == 1:
                raise ValueError("목표 용량이 너무 작습니다. 더 큰 용량을 선택하세요.")
            resized = picture.resize((max(1, int(width * .8)), max(1, int(height * .8))), Image.Resampling.LANCZOS)
            picture.close()
            picture = resized
        index = 0
        while True:
            suffix = f"_{index}" if index else ""
            target = output_dir / f"{source.stem}{suffix}{extension}"
            try:
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
                break
            except FileExistsError:
                index += 1
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded.getbuffer())
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return target
    finally:
        picture.close()
