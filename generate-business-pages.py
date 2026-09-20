#!/usr/bin/env python3
"""
SAIS Business Page Generator

Fetches the live SAIS business directory from Google Apps Script and creates:
  business/<slug>/index.html
for every business, plus sitemap.xml.

Designed for GitHub Pages and the SAIS directory.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://script.google.com/macros/s/AKfycbzqHFo7Ea2Kp_YfkinmcVUgJ8mCRC3oOQqRoDVNB_0zpI3Rv6ZfdghGMdBVlYcTNTvV/exec"
SITE_URL = "https://directory.somersetanimalinformationservices.com"

ROOT = Path(__file__).resolve().parent
BUSINESS_DIR = ROOT / "business"
SITEMAP_FILE = ROOT / "sitemap.xml"


def get_val(business: dict, keys: list[str], default: str = "") -> str:
    for key in keys:
        value = business.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def business_id(business: dict) -> str:
    return get_val(business, [
        "Business ID", "BusinessID", "SAIS ID", "SAIS-ID", "ID"
    ])


def business_name(business: dict) -> str:
    return get_val(business, [
        "Business Name", "Name", "Business", "Company"
    ], "Animal Business")


def category(business: dict) -> str:
    return get_val(business, [
        "Category", "Category Name", "Service Category", "Services Offered", "Type"
    ], "Animal Service")


def location(business: dict) -> str:
    return get_val(business, [
        "Area / Town", "Location", "Town", "Area", "City"
    ], "Somerset")


def website(business: dict) -> str:
    value = get_val(business, ["Website", "Web", "URL", "Link", "Site"])
    if value and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        value = "https://" + value
    return value


def phone(business: dict) -> str:
    return get_val(business, ["Phone", "Telephone", "Contact Number", "Mobile", "Tel"])


def email_address(business: dict) -> str:
    return get_val(business, ["Email", "Email Address", "Contact Email"])


def address(business: dict) -> str:
    return get_val(business, ["Address", "Full Address", "Postal Address"])


def description(business: dict) -> str:
    return get_val(business, ["Description", "Services", "About", "Notes", "Details"])


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "business"


def business_slug(business: dict) -> str:
    bid = slugify(business_id(business))
    name = slugify(business_name(business))
    return f"{bid}-{name}" if bid else name


def esc(value: str) -> str:
    return html.escape(str(value or ""), quote=True)


def jsonld(business: dict, page_url: str) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": business_name(business),
        "url": page_url,
        "description": description(business),
        "areaServed": "Somerset, UK",
    }

    addr = address(business)
    if addr:
        data["address"] = {
            "@type": "PostalAddress",
            "streetAddress": addr,
            "addressRegion": "Somerset",
            "addressCountry": "GB",
        }

    tel = phone(business)
    if tel:
        data["telephone"] = tel

    site = website(business)
    if site:
        data["sameAs"] = [site]

    return json.dumps(data, ensure_ascii=False, indent=2)


def fetch_businesses() -> list[dict]:
    print("Fetching SAIS business data...")
    print(API_URL)

    request = Request(
        API_URL,
        headers={
            "User-Agent": "SAIS-Business-Page-Generator/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )

    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8-sig")
    except HTTPError as exc:
        raise RuntimeError(
            f"Could not retrieve the SAIS Apps Script data. HTTP {exc.code}: {exc.reason}\nURL: {API_URL}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            f"Could not retrieve the SAIS Apps Script data. Network error: {exc.reason}\nURL: {API_URL}"
        ) from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        preview = raw[:500].replace("\n", " ")
        raise RuntimeError(
            "The Apps Script endpoint did not return valid JSON. "
            f"Response started with: {preview!r}"
        ) from exc

    if isinstance(data, list):
        businesses = data
    elif isinstance(data, dict):
        businesses = data.get("businesses") or data.get("data") or []
    else:
        businesses = []

    if not isinstance(businesses, list):
        raise RuntimeError("The Apps Script response contains an unexpected business data format.")

    clean = [b for b in businesses if isinstance(b, dict)]
    print(f"Found {len(clean)} businesses.")
    return clean


def page_html(business: dict, slug: str) -> str:
    name = business_name(business)
    cat = category(business)
    loc = location(business)
    desc = description(business) or f"{name} is listed in the Somerset Animal Information Services directory."
    site = website(business)
    tel = phone(business)
    email = email_address(business)
    addr = address(business)
    bid = business_id(business)
    page_url = f"{SITE_URL}/business/{slug}/"

    contact_bits = []
    if site:
        contact_bits.append(f'<a class="button" href="{esc(site)}" target="_blank" rel="noopener noreferrer">Visit Website</a>')
    if tel:
        contact_bits.append(f'<a class="button secondary" href="tel:{esc(tel)}">Call {esc(tel)}</a>')
    if email:
        contact_bits.append(f'<a class="button secondary" href="mailto:{esc(email)}">Email</a>')

    details = []
    if addr:
        details.append(f'<div class="detail"><strong>Address</strong><span>{esc(addr)}</span></div>')
    if tel:
        details.append(f'<div class="detail"><strong>Telephone</strong><span>{esc(tel)}</span></div>')
    if email:
        details.append(f'<div class="detail"><strong>Email</strong><span>{esc(email)}</span></div>')
    if site:
        details.append(f'<div class="detail"><strong>Website</strong><a href="{esc(site)}" target="_blank" rel="noopener noreferrer">{esc(site)}</a></div>')
    if bid:
        details.append(f'<div class="detail"><strong>SAIS Business ID</strong><span>{esc(bid)}</span></div>')

    return f'''<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(name)} | {esc(cat)} | Somerset Animal Information Services</title>
  <meta name="description" content="{esc(desc[:155])}">
  <link rel="canonical" href="{esc(page_url)}">
  <link rel="icon" href="../../directorylogo.png">
  <link rel="apple-touch-icon" href="../../directorylogo.png">
  <meta property="og:type" content="business.business">
  <meta property="og:title" content="{esc(name)} | Somerset Animal Information Services">
  <meta property="og:description" content="{esc(desc[:200])}">
  <meta property="og:url" content="{esc(page_url)}">
  <meta property="og:image" content="{SITE_URL}/directorylogo.png">
  <script type="application/ld+json">
{jsonld(business, page_url)}
  </script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f5f7fa; color: #172033; line-height: 1.65; }}
    header {{ background: #fff; border-bottom: 1px solid #e5e7eb; padding: 14px 20px; }}
    .header-inner {{ max-width: 1100px; margin: auto; display: flex; align-items: center; gap: 14px; }}
    .logo {{ width: 58px; height: 58px; object-fit: contain; border-radius: 12px; }}
    .brand {{ font-weight: 800; color: #172033; text-decoration: none; }}
    main {{ max-width: 900px; margin: 45px auto; padding: 0 18px; }}
    .card {{ background: #fff; border-radius: 18px; padding: 32px; box-shadow: 0 8px 30px rgba(15,23,42,.08); }}
    .eyebrow {{ color: #c82333; font-weight: 800; text-transform: uppercase; letter-spacing: .06em; font-size: .85rem; }}
    h1 {{ margin: 8px 0; font-size: clamp(2rem, 5vw, 3.1rem); line-height: 1.1; }}
    .location {{ color: #5d6878; margin-bottom: 24px; }}
    .description {{ font-size: 1.05rem; white-space: pre-line; }}
    .details {{ margin-top: 28px; border-top: 1px solid #e5e7eb; }}
    .detail {{ padding: 15px 0; border-bottom: 1px solid #e5e7eb; display: grid; grid-template-columns: 150px 1fr; gap: 15px; }}
    .detail strong {{ color: #3b4657; }}
    a {{ color: #0b5ea8; }}
    .buttons {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 28px; }}
    .button {{ display: inline-block; background: #c82333; color: white; text-decoration: none; padding: 11px 18px; border-radius: 10px; font-weight: 700; }}
    .button.secondary {{ background: #174f78; }}
    .back {{ display: inline-block; margin-top: 20px; text-decoration: none; font-weight: 700; }}
    footer {{ text-align: center; color: #667085; padding: 30px 18px 45px; font-size: .9rem; }}
    @media (max-width: 650px) {{ .card {{ padding: 23px; }} .detail {{ grid-template-columns: 1fr; gap: 4px; }} }}
  </style>
</head>
<body>
<header>
  <div class="header-inner">
    <a href="../../"><img class="logo" src="../../directorylogo.png" alt="Somerset Animal Information Services"></a>
    <a class="brand" href="../../">Somerset Animal Information Services</a>
  </div>
</header>
<main>
  <article class="card">
    <div class="eyebrow">{esc(cat)}</div>
    <h1>{esc(name)}</h1>
    <div class="location">📍 {esc(loc)}</div>
    <div class="description">{esc(desc)}</div>
    <div class="details">{''.join(details)}</div>
    <div class="buttons">{''.join(contact_bits)}</div>
    <a class="back" href="../../">← Back to Somerset Animal Business Directory</a>
  </article>
</main>
<footer>
  Somerset Animal Information Services · Free Somerset animal business directory and information service
</footer>
</body>
</html>
'''


def generate() -> None:
    businesses = fetch_businesses()
    if not businesses:
        raise RuntimeError("No businesses were returned. Nothing was generated.")

    temp_dir = Path(tempfile.mkdtemp(prefix="sais-business-pages-", dir=str(ROOT)))
    temp_business_dir = temp_dir / "business"
    temp_business_dir.mkdir(parents=True, exist_ok=True)

    try:
        used_slugs: set[str] = set()
        sitemap_urls = [f"{SITE_URL}/"]

        for business in businesses:
            bid = business_id(business)
            if not bid:
                print(f"Skipping business without Business ID: {business_name(business)}")
                continue

            base_slug = business_slug(business)
            slug = base_slug
            counter = 2
            while slug in used_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1
            used_slugs.add(slug)

            out_dir = temp_business_dir / slug
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(page_html(business, slug), encoding="utf-8")
            sitemap_urls.append(f"{SITE_URL}/business/{slug}/")

        # Replace the generated business directory atomically enough for GitHub Actions.
        if BUSINESS_DIR.exists():
            shutil.rmtree(BUSINESS_DIR)
        shutil.move(str(temp_business_dir), str(BUSINESS_DIR))

        sitemap_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        for url in sitemap_urls:
            sitemap_lines.append(f"  <url><loc>{esc(url)}</loc></url>")
        sitemap_lines.append('</urlset>')
        SITEMAP_FILE.write_text("\n".join(sitemap_lines) + "\n", encoding="utf-8")

        print(f"Generated {len(sitemap_urls) - 1} business pages.")
        print(f"Sitemap: {SITEMAP_FILE}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    generate()
