#!/usr/bin/env python3
"""
Add a QR code to every page of a PDF file.

The QR code can be:
  - Generated from a URL/text string, OR
  - Loaded from an existing image file

Position and size are fully configurable. All measurements are in millimetres
relative to the bottom-left corner of an A4 page (210 x 297 mm).

Usage examples:
  # Generate QR from a URL, place 20mm code in the bottom-right corner
  python add_qr_to_pdf.py input.pdf output.pdf --url "https://example.com" \
      --size 20 --x 180 --y 10

  # Use an existing QR image, place 25mm code centred at the top
  python add_qr_to_pdf.py input.pdf output.pdf --image qr.png \
      --size 25 --x 92.5 --y 267

Requirements:
  pip install pypdf reportlab qrcode[pil] Pillow
"""

import argparse
import io
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_qr_image(data: str) -> io.BytesIO:
    """Generate a QR code PNG in memory from the given data string."""
    import qrcode

    qr = qrcode.QRCode(
        version=None,  # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def create_qr_overlay(
    qr_image_path_or_buf,
    x_mm: float,
    y_mm: float,
    size_mm: float,
) -> io.BytesIO:
    """
    Create a single-page PDF (A4) containing only the QR code image,
    positioned at (x_mm, y_mm) from the bottom-left corner.

    Parameters
    ----------
    qr_image_path_or_buf : str, Path, or BytesIO
        Path to a QR code image file, or an in-memory BytesIO PNG.
    x_mm : float
        Horizontal offset from the left edge of the page (mm).
    y_mm : float
        Vertical offset from the bottom edge of the page (mm).
    size_mm : float
        Width and height of the QR code on the page (mm).

    Returns
    -------
    BytesIO
        A single-page PDF with the QR code placed at the specified position.
    """
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    img = ImageReader(qr_image_path_or_buf)
    c.drawImage(
        img,
        x_mm * mm,
        y_mm * mm,
        width=size_mm * mm,
        height=size_mm * mm,
        preserveAspectRatio=True,
        anchor="sw",      # anchor at south-west (bottom-left of image)
        mask="auto",       # respect transparency if present
    )

    c.save()
    buf.seek(0)
    return buf


# --------------- Convenience position helpers ---------------

A4_W_MM = 210.0
A4_H_MM = 297.0

POSITION_PRESETS = {
    "bottom-left":   lambda s, m: (m, m),
    "bottom-right":  lambda s, m: (A4_W_MM - s - m, m),
    "bottom-center": lambda s, m: ((A4_W_MM - s) / 2, m),
    "top-left":      lambda s, m: (m, A4_H_MM - s - m),
    "top-right":     lambda s, m: (A4_W_MM - s - m, A4_H_MM - s - m),
    "top-center":    lambda s, m: ((A4_W_MM - s) / 2, A4_H_MM - s - m),
    "center":        lambda s, m: ((A4_W_MM - s) / 2, (A4_H_MM - s) / 2),
}


def resolve_position(
    preset: str | None,
    x_mm: float | None,
    y_mm: float | None,
    size_mm: float,
    margin_mm: float,
) -> tuple[float, float]:
    """Return (x, y) in mm — either from an explicit coordinate or a preset."""
    if x_mm is not None and y_mm is not None:
        return x_mm, y_mm

    if preset and preset in POSITION_PRESETS:
        return POSITION_PRESETS[preset](size_mm, margin_mm)

    # Default to bottom-right
    return POSITION_PRESETS["bottom-right"](size_mm, margin_mm)


def add_qr_to_pdf(
    input_pdf: str | Path,
    output_pdf: str | Path,
    *,
    url: str | None = None,
    image: str | Path | None = None,
    size_mm: float = 20.0,
    x_mm: float | None = None,
    y_mm: float | None = None,
    position: str | None = None,
    margin_mm: float = 10.0,
) -> None:
    """
    Read *input_pdf*, stamp a QR code on every page, write *output_pdf*.

    Supply exactly one of ``url`` (to generate a QR code) or ``image``
    (to use an existing QR image file).
    """
    if not url and not image:
        raise ValueError("Provide either --url or --image.")
    if url and image:
        raise ValueError("Provide only one of --url or --image, not both.")

    # Resolve QR source
    if url:
        qr_source = generate_qr_image(url)
    else:
        qr_source = str(image)

    # Resolve position
    x, y = resolve_position(position, x_mm, y_mm, size_mm, margin_mm)

    # Build the overlay PDF (one transparent page with just the QR)
    overlay_buf = create_qr_overlay(qr_source, x, y, size_mm)
    overlay_page = PdfReader(overlay_buf).pages[0]

    # Stamp onto every page of the input
    reader = PdfReader(str(input_pdf))
    writer = PdfWriter()

    for page in reader.pages:
        page.merge_page(overlay_page)
        writer.add_page(page)

    with open(str(output_pdf), "wb") as f:
        writer.write(f)

    print(
        f"Done — wrote {len(reader.pages)} page(s) to {output_pdf}\n"
        f"  QR size : {size_mm} mm\n"
        f"  Position: ({x:.1f}, {y:.1f}) mm from bottom-left"
    )


# ------------------------------------------------------------------ CLI ---

def main():
    parser = argparse.ArgumentParser(
        description="Add a QR code to every page of a PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Position presets (--position):
  bottom-left   bottom-right (default)   bottom-center
  top-left      top-right                top-center
  center

Explicit --x and --y override any preset. All measurements in mm,
origin is the bottom-left corner of the A4 page (210 x 297 mm).

Examples:
  %(prog)s scores.pdf out.pdf --url "https://example.com"
  %(prog)s scores.pdf out.pdf --url "https://example.com" --size 25 --position top-right
  %(prog)s scores.pdf out.pdf --url "https://example.com" --size 20 --x 95 --y 10
  %(prog)s scores.pdf out.pdf --image my_qr.png --size 30 --position bottom-center
""",
    )

    parser.add_argument("input_pdf", help="Path to the input PDF file")
    parser.add_argument("output_pdf", help="Path for the output PDF file")

    qr_group = parser.add_mutually_exclusive_group(required=True)
    qr_group.add_argument("--url", help="URL or text to encode as a QR code")
    qr_group.add_argument("--image", help="Path to an existing QR code image")

    parser.add_argument(
        "--size", type=float, default=20.0,
        help="QR code width/height in mm (default: 20)",
    )
    parser.add_argument(
        "--x", type=float, default=None,
        help="X offset from left edge in mm (overrides --position)",
    )
    parser.add_argument(
        "--y", type=float, default=None,
        help="Y offset from bottom edge in mm (overrides --position)",
    )
    parser.add_argument(
        "--position", choices=list(POSITION_PRESETS.keys()),
        default="bottom-right",
        help="Named position preset (default: bottom-right)",
    )
    parser.add_argument(
        "--margin", type=float, default=10.0,
        help="Margin from page edge for presets, in mm (default: 10)",
    )

    args = parser.parse_args()

    if not Path(args.input_pdf).exists():
        sys.exit(f"Error: input file not found: {args.input_pdf}")
    if args.image and not Path(args.image).exists():
        sys.exit(f"Error: QR image not found: {args.image}")

    add_qr_to_pdf(
        args.input_pdf,
        args.output_pdf,
        url=args.url,
        image=args.image,
        size_mm=args.size,
        x_mm=args.x,
        y_mm=args.y,
        position=args.position,
        margin_mm=args.margin,
    )


if __name__ == "__main__":
    main()