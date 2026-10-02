"""Make lossless two-page contact sheets for internal visual inspection."""

from pathlib import Path
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent / "template_populated_stress"


def main() -> None:
    for product in ("SalINTEL", "SalTHIRA", "SalOPS", "SalCAPA"):
        folder = ROOT / f"render_final_{product}"
        pages = sorted(folder.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
        for offset in range(0, len(pages), 2):
            pair = pages[offset:offset + 2]
            images = [Image.open(path).convert("RGB") for path in pair]
            width = sum(image.width for image in images) + 40 * (len(images) + 1)
            height = max(image.height for image in images) + 70
            canvas = Image.new("RGB", (width, height), "#b8b8b8")
            draw = ImageDraw.Draw(canvas)
            x = 40
            for path, image in zip(pair, images):
                draw.text((x, 14), f"{product} {path.stem}", fill="black")
                canvas.paste(image, (x, 50))
                x += image.width + 40
            target = folder / f"contact-{offset // 2 + 1:02d}.png"
            canvas.save(target)
            print(target)


if __name__ == "__main__":
    main()
