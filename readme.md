# add-qr-to-pdf

Add a QR code (and optional text label) to every page of a PDF file.

The QR code can be generated on the fly from a URL or text string, or you can supply an existing QR code image. Page dimensions are auto-detected from the input PDF so the script works correctly with both portrait and landscape orientations and any page size.

All positioning is in **millimetres** measured from the **bottom-left corner** of the page.

## Requirements

Python 3.10+ and the following packages:

```bash
pip install pypdf reportlab "qrcode[pil]" Pillow
```

## Quick start

```bash
# Generate a QR code from a URL and place it in the bottom-right corner
python add_qr_to_pdf.py scores.pdf output.pdf --url "https://example.com"
```

## Usage

```
python add_qr_to_pdf.py INPUT_PDF OUTPUT_PDF (--url URL | --image PATH) [options]
```

### Positional arguments

| Argument     | Description                  |
|-------------|------------------------------|
| `INPUT_PDF`  | Path to the source PDF file  |
| `OUTPUT_PDF` | Path for the output PDF file |

### QR code source (one required)

| Option          | Description                                        |
|----------------|----------------------------------------------------|
| `--url URL`     | URL or text string to encode as a QR code          |
| `--image PATH`  | Path to an existing QR code image file (PNG, JPG…) |

### Size and positioning

| Option                | Default         | Description |
|-----------------------|-----------------|-------------|
| `--size MM`           | `20`            | QR code width and height in mm |
| `--position PRESET`   | `bottom-right`  | Named position preset (see below) |
| `--x MM`              | —               | X offset from the left edge in mm (overrides `--position`) |
| `--y MM`              | —               | Y offset from the bottom edge in mm (overrides `--position`) |
| `--margin MM`         | `10`            | Margin from the page edge used by presets, in mm |

#### Position presets

| Preset          | Placement                        |
|----------------|----------------------------------|
| `bottom-left`   | Bottom-left corner               |
| `bottom-right`  | Bottom-right corner *(default)*  |
| `bottom-center` | Bottom edge, horizontally centred |
| `top-left`      | Top-left corner                  |
| `top-right`     | Top-right corner                 |
| `top-center`    | Top edge, horizontally centred   |
| `center`        | Centre of the page               |

Supplying both `--x` and `--y` overrides the preset entirely.

### Text label (optional)

| Option                 | Default  | Description |
|-----------------------|----------|-------------|
| `--text STRING`        | —        | Text to render alongside the QR code |
| `--text-position POS`  | `below`  | Position relative to the QR code: `above`, `below`, `left`, or `right` |
| `--font-size PT`       | `8`      | Font size in points (Helvetica) |

The text is centred along the relevant edge of the QR code — horizontally centred for `above`/`below`, vertically centred for `left`/`right`.

## Examples

### Basic — bottom-right with default settings

```bash
python add_qr_to_pdf.py scores.pdf output.pdf \
    --url "https://example.com/results"
```

### Position preset with custom size

```bash
python add_qr_to_pdf.py scores.pdf output.pdf \
    --url "https://example.com/results" \
    --size 25 --position top-right --margin 15
```

### Exact coordinates

```bash
python add_qr_to_pdf.py scores.pdf output.pdf \
    --url "https://example.com/results" \
    --size 20 --x 95 --y 5
```

### Existing QR image instead of generating one

```bash
python add_qr_to_pdf.py scores.pdf output.pdf \
    --image my_qr_code.png \
    --size 30 --position bottom-center
```

### With a text label

```bash
python add_qr_to_pdf.py scores.pdf output.pdf \
    --url "https://example.com/results" \
    --size 20 --position bottom-right \
    --text "Scan for results" --text-position below --font-size 9
```

### IANSEO landscape scoresheets

[IANSEO](https://www.ianseo.net/) exports landscape A4 scoresheets as PDF. The following places a 15 mm QR code in the top-right area of each sheet with a label to its left:

```bash
python add_qr_to_pdf.py ianseo_scoresheets.pdf output.pdf \
    --image "QR code image file" \
    --size 20 --x 270 --y 185 \
    --text "Archers Diary event login" --text-position left --font-size 12
```

This positions the QR code at 270 mm from the left edge and 185 mm from the bottom edge, which sits neatly in the top-right corner of a landscape A4 page (297 × 210 mm). The label is rendered to the left of the code at 12 pt.

## Python API

The script can also be imported and called directly:

```python
from add_qr_to_pdf import add_qr_to_pdf

add_qr_to_pdf(
    "ianseo_scoresheets.pdf",
    "output.pdf",
    url="https://results.example.com/tournament/2025",
    size_mm=15,
    x_mm=270,
    y_mm=190,
    text="Scan for live results",
    text_position="left",
    font_size=12,
)
```

## How it works

1. The input PDF is read with **pypdf** and the page dimensions (including rotation) are detected from the first page.
2. A transparent single-page overlay PDF is created with **ReportLab**, sized to match the input pages, containing only the QR code image and optional text.
3. The overlay is merged onto every page of the input using `page.merge_page()`.
4. The result is written to the output path.

Because the overlay is built to match the actual page size, the script handles portrait, landscape, and non-standard page sizes without any manual configuration.

## Coordinate reference

All coordinates are in millimetres from the **bottom-left corner** of the page:

```
(0, 297) ┌─────────────────────┐ (210, 297)   ← A4 portrait
         │                     │
         │         page        │
         │                     │
  (0, 0) └─────────────────────┘ (210, 0)

(0, 210) ┌─────────────────────────────────┐ (297, 210)   ← A4 landscape
         │                                 │
         │              page               │
         │                                 │
  (0, 0) └─────────────────────────────────┘ (297, 0)
```

## License

MIT