#!/usr/bin/env python3
"""
Extract documentation from Control4 .c4i and .c4z driver files.
Each output is a .zip containing the .html document and a manifest.txt.

- .c4i  → inline <documentation> text → HTML
- .c4z  → file referenced by <documentation file="..."/>:
            .rtf  → plain text → HTML
            .md   → rendered Markdown → HTML
            .html → body content reused, wrapped in template
          Falls back to inline <documentation> text if no file reference.

Outputs mirror the source directory structure under OUTPUT_DIR.
Generates index.csv mapping every output file to its driver metadata.
"""

import csv
import html as html_lib
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, unquote

import markdown as md_lib
from striprtf.striprtf import rtf_to_text

SOURCE_DIR = Path("/Users/torrence.welshans/Documents/DriverDocs")
OUTPUT_DIR = Path("/Users/torrence.welshans/Documents/DriverDocs_Export")

DOWNLOAD_BASE = "http://drivers.control4.com/"
LINK_TEXT     = "Click here to download the Control4 driver."

# ---------------------------------------------------------------------------
# Term corrections dictionary
# ---------------------------------------------------------------------------
# Controls how specific words are capitalised in output filenames.
# Keys must be lowercase. Values can include spaces to split compound words.
#
# To add a new entry, follow the existing pattern:
#   "myterm": "MyTerm",
# ---------------------------------------------------------------------------

TERM_CORRECTIONS = {
    # Control4 / AV industry acronyms
    "ip":           "IP",
    "ir":           "IR",
    "av":           "AV",
    "hd":           "HD",
    "hdmi":         "HDMI",
    "hdbaset":      "HDBaseT",
    "4k":           "4K",
    "rs232":        "RS232",
    "rs485":        "RS485",
    "tcp":          "TCP",
    "udp":          "UDP",
    "c4":           "C4",
    "rx":           "RX",
    "tx":           "TX",
    "mx":           "MX",
    "sr":           "SR",
    "ac":           "AC",

    # Compound words that should be split or re-cased
    "avswitch":     "AV Switch",
    "avpro":        "AVPro",
    "avproedge":    "AVProEdge",
    "mediaservice": "Media Service",
    "driverworks":  "DriverWorks",
    "mxnet":        "MXNet",
}

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body      {{ font-family: sans-serif; max-width: 860px; margin: 2em auto; padding: 0 1.5em; line-height: 1.6; color: #222; }}
    .meta     {{ font-size: 0.875em; color: #555; border-bottom: 1px solid #ddd; padding-bottom: 0.75em; margin-bottom: 1.5em; }}
    .meta span{{ margin-right: 1.5em; }}
    .download {{ margin: 0.5em 0 1.5em; }}
    h1        {{ font-size: 1.75em; font-weight: 700; margin: 0.75em 0 0.25em; color: #111; }}
    h2        {{ font-size: 1.3em;  font-weight: 600; margin: 1.5em 0 0.3em;  color: #222; border-bottom: 1px solid #eee; padding-bottom: 0.2em; }}
    h3        {{ font-size: 1.05em; font-weight: 600; margin: 1.2em 0 0.2em;  color: #333; }}
    p         {{ margin: 0.6em 0; }}
  </style>
</head>
<body>
  <div class="meta">{meta_html}</div>
  {body_html}
</body>
</html>"""


def render_html(title, meta, body_html, url):
    meta_spans = "".join(
        f'<span><strong>{k.capitalize()}:</strong> {html_lib.escape(v)}</span>'
        for k, v in meta.items() if v
    )
    download_div = (
        f'<div class="download"><a href="{url}">{LINK_TEXT}</a></div>'
    )
    # Insert after the first heading tag; fall back to top of body if none found.
    heading_match = re.search(r"</h[1-3]>", body_html, re.IGNORECASE)
    if heading_match:
        pos = heading_match.end()
        body_html = body_html[:pos] + "\n  " + download_div + body_html[pos:]
    else:
        body_html = download_div + "\n  " + body_html
    return HTML_TEMPLATE.format(
        title     = html_lib.escape(title or "Control4 Driver Documentation"),
        meta_html = meta_spans,
        body_html = body_html,
    )


# ---------------------------------------------------------------------------
# Content converters
# ---------------------------------------------------------------------------

def plain_to_html(text):
    """Convert plain text to HTML, preserving paragraph breaks."""
    parts = []
    for para in re.split(r"\n{2,}", text.strip()):
        para = para.strip()
        if para:
            escaped = html_lib.escape(para).replace("\n", "<br>\n")
            parts.append(f"<p>{escaped}</p>")
    return "\n".join(parts)


def extract_body_html(html_source):
    """Pull content between <body> tags; fall back to the full source."""
    if isinstance(html_source, bytes):
        html_source = html_source.decode("utf-8", errors="replace")
    m = re.search(r"<body[^>]*>(.*?)</body>", html_source, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else html_source.strip()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _text(root, tag):
    el = root.find(tag)
    return el.text.strip() if el is not None and el.text else ""


def get_metadata(root):
    return {
        "manufacturer":  _text(root, "manufacturer"),
        "model":         _text(root, "model"),
        "name":          _text(root, "name"),
        "version":       _text(root, "version"),
        "controlmethod": _text(root, "controlmethod"),
        "creator":       _text(root, "creator"),
    }


def build_download_url(source_path):
    return DOWNLOAD_BASE + quote(source_path.name, safe="%")


def to_title_name(stem):
    """Convert a raw driver filename stem to a title-cased, space-separated name.

    Steps:
      1. URL-decode  (%20 -> space, etc.)
      2. Split camelCase on lowercase->uppercase boundaries
      3. Replace underscores with spaces
      4. Collapse multiple spaces
      5. Apply title case
      6. Apply TERM_CORRECTIONS word by word
    """
    name = unquote(stem)
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    name = name.replace('_', ' ')
    name = re.sub(r' {2,}', ' ', name).strip()
    name = name.title()
    def correct_token(token):
        lower = token.lower()
        # 1. Exact match
        if lower in TERM_CORRECTIONS:
            return TERM_CORRECTIONS[lower]
        # 2. Hyphen-separated parts (e.g. Ac-Mxnet-Cbox -> AC-MXNet-Cbox)
        if '-' in token:
            parts = [correct_token(p) for p in token.split('-')]
            return '-'.join(parts)
        # 3. Prefix match — handles cases like Mmsmcp5E where the key is
        #    "mmsmcp" but the token has a trailing version/model suffix.
        best_key = max(
            (k for k in TERM_CORRECTIONS if lower.startswith(k)),
            key=len, default=None,
        )
        if best_key:
            suffix = token[len(best_key):]
            correction = TERM_CORRECTIONS[best_key]
            if suffix and (suffix[0].isdigit() or suffix[0].isupper()):
                return correction + ' ' + suffix
            return correction + suffix
        return token

    words = name.split(' ')
    corrected = [correct_token(w) for w in words]
    name = re.sub(r' {2,}', ' ', ' '.join(corrected)).strip()
    return name


def build_manifest(html_filename, manufacturer):
    """Generate manifest.txt content matching the Control4 CMS format."""
    return (
        f"format:HTML\n"
        f"indexFile:{html_filename}\n"
        f"author:{manufacturer}\n"
        f"resourceType:Course\n"
        f"language:English\n"
    )


def write_zip_output(zip_path, html_filename, html_content, manifest_content):
    """Write a zip containing the HTML doc and manifest.txt."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(html_filename, html_content.encode("utf-8"))
        zf.writestr("manifest.txt", manifest_content.encode("utf-8"))


# ---------------------------------------------------------------------------
# .c4i processing
# ---------------------------------------------------------------------------

def process_c4i(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return None, f"XML parse error: {exc}"

    # ET tag matching is exact: 'documentation' will NOT match 'driverdocumentation'
    doc_el = root.find(".//documentation")
    if doc_el is None or not (doc_el.text or "").strip():
        return None, "no <documentation> element"

    meta         = get_metadata(root)
    url          = build_download_url(path)
    html_content = render_html(
        title     = meta.get("name") or meta.get("model"),
        meta      = meta,
        body_html = plain_to_html(doc_el.text.strip()),
        url       = url,
    )

    rel           = path.relative_to(SOURCE_DIR)
    title_stem    = to_title_name(rel.stem) + " Driver Documentation"
    html_filename = title_stem + ".html"
    zip_path      = OUTPUT_DIR / rel.parent / (title_stem + ".zip")
    write_zip_output(zip_path, html_filename, html_content,
                     build_manifest(html_filename, meta.get("manufacturer", "")))

    return {**meta,
            "source_file": str(rel),
            "output_file": str(zip_path.relative_to(OUTPUT_DIR)),
            "doc_format":  "html (from txt)"}, None


# ---------------------------------------------------------------------------
# .c4z processing
# ---------------------------------------------------------------------------

def process_c4z(path):
    try:
        zf = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile as exc:
        return None, f"bad zip: {exc}"

    with zf:
        names     = zf.namelist()
        lower_map = {n.lower(): n for n in names}

        if "driver.xml" not in lower_map:
            return None, "no driver.xml in archive"

        try:
            root = ET.fromstring(zf.read(lower_map["driver.xml"]))
        except ET.ParseError as exc:
            return None, f"driver.xml parse error: {exc}"

        meta       = get_metadata(root)
        doc_el     = root.find(".//documentation")
        if doc_el is None:
            return None, "no <documentation> element in driver.xml"

        doc_file_attr = doc_el.get("file")
        rel           = path.relative_to(SOURCE_DIR)
        url           = build_download_url(path)

        # --- file reference ---
        if doc_file_attr:
            normalised = doc_file_attr.replace("\\", "/").lower()

            # index.html is a React app shell — the real content is www/documentation.md
            if normalised.endswith("index.html") and "www/documentation.md" in lower_map:
                normalised = "www/documentation.md"

            actual_name = lower_map.get(normalised)
            if actual_name is None:
                return None, f"referenced doc file not found in archive: {doc_file_attr}"

            doc_bytes  = zf.read(actual_name)
            source_ext = Path(actual_name).suffix.lower()

            if source_ext == ".rtf":
                plain     = rtf_to_text(doc_bytes.decode("latin-1", errors="replace"), errors="replace")
                body_html = plain_to_html(plain.strip())
                doc_format = "html (from rtf)"

            elif source_ext == ".md":
                md_text   = doc_bytes.decode("utf-8", errors="replace")
                body_html = md_lib.markdown(md_text, extensions=["tables", "fenced_code"])
                doc_format = "html (from md)"

            elif source_ext in (".html", ".htm"):
                body_html  = extract_body_html(doc_bytes)
                doc_format = "html (from html)"

            else:
                body_html  = plain_to_html(doc_bytes.decode("utf-8", errors="replace"))
                doc_format = f"html (from {source_ext})"

        # --- inline text fallback ---
        else:
            inline = (doc_el.text or "").strip()
            if not inline:
                return None, "empty inline <documentation>"
            body_html  = plain_to_html(inline)
            doc_format = "html (inline)"

        html_content = render_html(
            title     = meta.get("name") or meta.get("model"),
            meta      = meta,
            body_html = body_html,
            url       = url,
        )
        title_stem    = to_title_name(rel.stem) + " Driver Documentation"
        html_filename = title_stem + ".html"
        zip_path      = OUTPUT_DIR / rel.parent / (title_stem + ".zip")
        write_zip_output(zip_path, html_filename, html_content,
                         build_manifest(html_filename, meta.get("manufacturer", "")))

        return {**meta,
                "source_file": str(rel),
                "output_file": str(zip_path.relative_to(OUTPUT_DIR)),
                "doc_format":  doc_format}, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "manufacturer", "model", "name", "version",
    "controlmethod", "creator",
    "source_file", "output_file", "doc_format",
]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    records = []
    skipped = []

    driver_files = sorted(
        p for p in SOURCE_DIR.rglob("*")
        if p.suffix.lower() in (".c4i", ".c4z")
    )

    print(f"Found {len(driver_files)} driver files. Processing...")

    for i, path in enumerate(driver_files, 1):
        if path.suffix.lower() == ".c4i":
            record, err = process_c4i(path)
        else:
            record, err = process_c4z(path)

        if record:
            records.append(record)
        else:
            skipped.append((str(path.relative_to(SOURCE_DIR)), err))

        if i % 100 == 0:
            print(f"  {i}/{len(driver_files)} processed...")

    # Write index.csv
    index_path = OUTPUT_DIR / "index.csv"
    with open(index_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)

    # Write skipped log
    if skipped:
        skip_path = OUTPUT_DIR / "skipped.log"
        with open(skip_path, "w", encoding="utf-8") as f:
            for src, reason in skipped:
                f.write(f"{src}\t{reason}\n")

    print(f"\nDone.")
    print(f"  Extracted : {len(records)}")
    print(f"  Skipped   : {len(skipped)}  (see {OUTPUT_DIR}/skipped.log)")
    print(f"  Index     : {index_path}")


if __name__ == "__main__":
    main()
