#!/usr/bin/env python3
"""
Add a QR code to every page of a PDF file.

The QR code can be:
  - Generated from a URL/text string, OR
  - Loaded from an existing image file

Position and size are fully configurable. All measurements are in millimetres
relative to the bottom-left corner of the page. The script automatically
detects the page dimensions from the input PDF, so it works with both
portrait and landscape orientations (and any page size).

Usage examples:
  # Generate QR from a URL, place 20mm code in the bottom-right corner
  python add_qr_to_pdf.py input.pdf output.pdf --url "https://example.com" \
      --size 20 --position bottom-right

  # Use an existing QR image, place 25mm code centred at the top
  python add_qr_to_pdf.py input.pdf output.pdf --image qr.png \
      --size 25 --position top-center

  # Exact coordinates (mm from bottom-left corner)
  python add_qr_to_pdf.py input.pdf output.pdf --url "https://example.com" \
      --size 20 --x 270 --y 10

Requirements:
  pip install pypdf reportlab qrcode[pil] Pillow
"""

import argparse
import io
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


# Points per mm (1 point = 1/72 inch, 1 inch = 25.4 mm)
PT_PER_MM = 72.0 / 25.4


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


def get_page_dimensions_mm(page) -> tuple[float, float]:
    """
    Read the MediaBox from a pypdf page and return (width_mm, height_mm).

    Handles rotated pages: if the page has a /Rotate of 90 or 270 the
    effective width and height are swapped.
    """
    box = page.mediabox
    w_pt = float(box.width)
    h_pt = float(box.height)

    rotation = page.get("/Rotate", 0) or 0
    if rotation in (90, 270):
        w_pt, h_pt = h_pt, w_pt

    return w_pt / PT_PER_MM, h_pt / PT_PER_MM


def create_qr_overlay(
    qr_image_path_or_buf,
    x_mm: float,
    y_mm: float,
    size_mm: float,
    page_w_pt: float,
    page_h_pt: float,
) -> io.BytesIO:
    """
    Create a single-page PDF matching the given page dimensions,
    containing only the QR code image at the specified position.

    Parameters
    ----------
    qr_image_path_or_buf : str, Path, or BytesIO
        Path to a QR code image file, or an in-memory BytesIO PNG.
    x_mm, y_mm : float
        Offset from the bottom-left corner of the page (mm).
    size_mm : float
        Width and height of the QR code on the page (mm).
    page_w_pt, page_h_pt : float
        Page dimensions in PDF points (matching the input page).
    """
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w_pt, page_h_pt))

    img = ImageReader(qr_image_path_or_buf)
    c.drawImage(
        img,
        x_mm * mm,
        y_mm * mm,
        width=size_mm * mm,
        height=size_mm * mm,
        preserveAspectRatio=True,
        anchor="sw",
        mask="auto",
    )

    c.save()
    buf.seek(0)
    return buf


# --------------- Convenience position helpers ---------------

POSITION_PRESETS = {
    #                         (page_w, page_h, qr_size, margin) -> (x, y)
    "bottom-left":   lambda w, h, s, m: (m, m),
    "bottom-right":  lambda w, h, s, m: (w - s - m, m),
    "bottom-center": lambda w, h, s, m: ((w - s) / 2, m),
    "top-left":      lambda w, h, s, m: (m, h - s - m),
    "top-right":     lambda w, h, s, m: (w - s - m, h - s - m),
    "top-center":    lambda w, h, s, m: ((w - s) / 2, h - s - m),
    "center":        lambda w, h, s, m: ((w - s) / 2, (h - s) / 2),
}


def resolve_position(
    preset: str | None,
    x_mm: float | None,
    y_mm: float | None,
    size_mm: float,
    margin_mm: float,
    page_w_mm: float,
    page_h_mm: float,
) -> tuple[float, float]:
    """Return (x, y) in mm — either from explicit coordinates or a preset."""
    if x_mm is not None and y_mm is not None:
        return x_mm, y_mm

    if preset and preset in POSITION_PRESETS:
        return POSITION_PRESETS[preset](page_w_mm, page_h_mm, size_mm, margin_mm)

    # Default to bottom-right
    return POSITION_PRESETS["bottom-right"](page_w_mm, page_h_mm, size_mm, margin_mm)


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

    # Read the input PDF
    reader = PdfReader(str(input_pdf))

    # Detect page size from the first page
    first_page = reader.pages[0]
    page_w_mm, page_h_mm = get_page_dimensions_mm(first_page)
    orientation = "landscape" if page_w_mm > page_h_mm else "portrait"

    # Raw MediaBox in points (for the overlay canvas)
    box = first_page.mediabox
    page_w_pt = float(box.width)
    page_h_pt = float(box.height)

    # Handle rotated pages — swap the canvas dimensions so the overlay
    # is built in the same effective orientation as the visible page.
    rotation = first_page.get("/Rotate", 0) or 0
    if rotation in (90, 270):
        page_w_pt, page_h_pt = page_h_pt, page_w_pt

    # Resolve position using actual page dimensions
    x, y = resolve_position(
        position, x_mm, y_mm, size_mm, margin_mm, page_w_mm, page_h_mm
    )

    # Build the overlay PDF sized to match the input pages
    overlay_buf = create_qr_overlay(
        qr_source, x, y, size_mm, page_w_pt, page_h_pt
    )
    overlay_page = PdfReader(overlay_buf).pages[0]

    # Stamp onto every page
    writer = PdfWriter()
    for page in reader.pages:
        page.merge_page(overlay_page)
        writer.add_page(page)

    with open(str(output_pdf), "wb") as f:
        writer.write(f)

    print(
        f"Done — wrote {len(reader.pages)} page(s) to {output_pdf}\n"
        f"  Detected: {page_w_mm:.1f} x {page_h_mm:.1f} mm ({orientation})\n"
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
origin is the bottom-left corner of the page. Page dimensions are
auto-detected from the input PDF (works with any size/orientation).

Examples:
  %(prog)s scores.pdf out.pdf --url "https://example.com"
  %(prog)s scores.pdf out.pdf --url "https://example.com" --size 25 --position top-right
  %(prog)s scores.pdf out.pdf --url "https://example.com" --size 20 --x 270 --y 10
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