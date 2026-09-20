#!/usr/bin/env python3
"""Generate crawlable SAIS directory pages from the Google Apps Script JSON feed.

Run from the repository root. Generated pages are written to business/<slug>/index.html
and a fresh sitemap.xml is generated at the repository root.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlparse

API_URL = "https://script.google.com/macros/s/AKfycbwl2XzI0HGvzV5cXSPuZmTQ-8fB9w328OZ5IsMEp-eRLr-Qr_2mbD81tCKZrt1Uxoa/exec"
SITE_URL = "https://directory.somersetanimalinformationservices.com"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "business"


def get_val(b, keys, default=""):
    if not isinstance(b, dict):
        return default
    lowered = {str(k).strip().lower(): v for k, v in b.items()}
    for key in keys:
        value = lowered.get(key.strip().lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def business_id(b):
    return get_val(b, ["Business ID", "BusinessID", "SAIS ID", "SAIS-ID", "ID"])


def name(b):
    return get_val(b, ["Business Name", "Name", "Business", "Company"], "Animal Business")


def category(b):
    return get_val(b, ["Category", "Category Name", "Service Category", "Services Offered", "Type"], "Animal Service")


def location(b):
    return get_val(b, ["Area / Town", "Location", "Town", "Area", "City"], "Somerset")


def website(b):
    return get_val(b, ["Website", "Web", "URL", "Link", "Site"])


def phone(b):
    return get_val(b, ["Phone", "Telephone", "Contact Number", "Mobile", "Tel"])


def email(b):
    return get_val(b, ["Email", "Email Address", "Contact Email"])


def address(b):
    return get_val(b, ["Address", "Full Address", "Postal Address"])


def description(b):
    return get_val(b, ["Description", "Services", "About", "Notes", "Details"])


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-") or "animal-business"


def page_slug(b):
    bid = slugify(business_id(b))
    business_name = slugify(name(b))
    return f"{bid}-{business_name}" if business_name else bid


def esc(value):
    return html.escape(str(value or ""), quote=True)


def absolute_website(value):
    if not value:
        return ""
    return value if re.match(r"^https?://", value, re.I) else "https://" + value


def fetch_businesses():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "SAIS-GitHub-Directory-Generator/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.load(response)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("businesses", "data"):
            if isinstance(data.get(key), list):
                return data[key]
    raise RuntimeError("The SAIS API did not return a recognised businesses/data array.")


def render_contact(b):
    bits = []
    p = phone(b)
    e = email(b)
    w = website(b)
    a = address(b)
    if p:
        bits.append(f'<div class="contact-item"><strong>Telephone</strong><a href="tel:{quote(p)}">{esc(p)}</a></div>')
    if e:
        bits.append(f'<div class="contact-item"><strong>Email</strong><a href="mailto:{esc(e)}">{esc(e)}</a></div>')
    if w:
        u = absolute_website(w)
        bits.append(f'<div class="contact-item"><strong>Website</strong><a href="{esc(u)}" target="_blank" rel="noopener noreferrer">Visit website ↗</a></div>')
    if a:
        bits.append(f'<div class="contact-item"><strong>Address</strong><span>{esc(a)}</span></div>')
    return "\n".join(bits)


def render_jsonld(b, url):
    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness" if address(b) else "Organization",
        "name": name(b),
        "url": url,
        "description": description(b) or f"{name(b)} — {category(b)} in {location(b)}, Somerset.",
    }
    if phone(b):
        data["telephone"] = phone(b)
    if email(b):
        data["email"] = email(b)
    if website(b):
        data["sameAs"] = [absolute_website(website(b))]
    if location(b):
        data["areaServed"] = {"@type": "Place", "name": location(b)}
    if address(b):
        data["address"] = {"@type": "PostalAddress", "streetAddress": address(b), "addressRegion": "Somerset", "addressCountry": "GB"}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def render_page(b):
    bid = business_id(b)
    title = f"{name(b)} | {category(b)} | Somerset Animal Business Directory"
    desc = description(b) or f"Find {name(b)}, a {category(b)} serving {location(b)}, Somerset. View contact and business information on the Somerset Animal Business Directory."
    url = f"{SITE_URL}/business/{page_slug(b)}/"
    image = f"{SITE_URL}/directorybanner.png"
    contact = render_contact(b)
    desc_html = esc(description(b)) if description(b) else f"{esc(name(b))} is listed in the Somerset Animal Business Directory under {esc(category(b))}, serving {esc(location(b))}, Somerset."

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc[:155])}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(url)}">
  <link rel="icon" type="image/png" href="/directorylogo.png">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(url)}">
  <meta property="og:title" content="{esc(name(b))} | {esc(category(b))}">
  <meta property="og:description" content="{esc(desc[:200])}">
  <meta property="og:image" content="{image}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(name(b))} | {esc(category(b))}">
  <meta name="twitter:description" content="{esc(desc[:200])}">
  <meta name="twitter:image" content="{image}">
  <script type="application/ld+json">{render_jsonld(b, url)}</script>
  <style>
    :root {{ --red:#c82333; --dark:#0f172a; --muted:#64748b; --bg:#f1f5f9; --border:#e2e8f0; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Plus Jakarta Sans,Arial,sans-serif; color:var(--dark); background:var(--bg); line-height:1.7; }}
    header {{ background:#fff; border-bottom:1px solid var(--border); padding:14px 20px; }}
    .header-inner {{ max-width:1050px; margin:auto; display:flex; align-items:center; justify-content:space-between; gap:16px; }}
    .brand {{ display:flex; align-items:center; gap:10px; font-weight:800; }}
    .brand img {{ width:42px; height:42px; object-fit:cover; border-radius:7px; }}
    .brand small {{ display:block; color:var(--red); font-size:11px; letter-spacing:.08em; text-transform:uppercase; }}
    nav a, .back {{ color:var(--red); text-decoration:none; font-weight:700; }}
    main {{ max-width:900px; margin:38px auto; padding:0 18px; }}
    .crumbs {{ font-size:.9rem; margin-bottom:18px; }}
    .crumbs a {{ color:var(--red); text-decoration:none; }}
    article {{ background:#fff; border:1px solid var(--border); border-radius:16px; overflow:hidden; box-shadow:0 8px 25px rgba(15,23,42,.06); }}
    .hero {{ padding:34px 34px 28px; background:linear-gradient(rgba(15,23,42,.82),rgba(15,23,42,.82)),url('/directorybanner.png') center/cover; color:#fff; }}
    .eyebrow {{ text-transform:uppercase; letter-spacing:.1em; font-size:.78rem; font-weight:800; opacity:.85; }}
    h1 {{ margin:8px 0 8px; font-size:clamp(1.8rem,4vw,2.8rem); line-height:1.15; }}
    .location {{ margin:0; opacity:.9; }}
    .content {{ padding:30px 34px 34px; }}
    .content h2 {{ margin-top:0; font-size:1.35rem; }}
    .contact-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-top:24px; }}
    .contact-item {{ border:1px solid var(--border); border-radius:10px; padding:14px; background:#f8fafc; }}
    .contact-item strong {{ display:block; font-size:.78rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-bottom:4px; }}
    .contact-item a {{ color:var(--red); font-weight:700; text-decoration:none; word-break:break-word; }}
    .actions {{ margin-top:26px; display:flex; flex-wrap:wrap; gap:10px; }}
    .button {{ display:inline-block; padding:11px 16px; border-radius:8px; background:var(--red); color:#fff; text-decoration:none; font-weight:800; }}
    .button.secondary {{ background:#fff; color:var(--red); border:1px solid var(--red); }}
    footer {{ text-align:center; padding:30px 18px; color:var(--muted); font-size:.9rem; }}
    @media(max-width:600px) {{ .hero,.content {{ padding:25px 20px; }} .header-inner {{ align-items:flex-start; }} nav {{ display:none; }} }}
  </style>
</head>
<body>
<header><div class="header-inner">
  <a class="brand" href="/"><img src="/directorylogo.png" alt="Somerset Animal Information Services"><span>Somerset Animal Business Directory<small>Somerset Animal Information Services</small></span></a>
  <nav><a href="/">Directory</a></nav>
</div></header>
<main>
  <div class="crumbs"><a href="/">Somerset Animal Business Directory</a> &nbsp;›&nbsp; {esc(category(b))} &nbsp;›&nbsp; {esc(name(b))}</div>
  <article>
    <section class="hero">
      <div class="eyebrow">{esc(category(b))}</div>
      <h1>{esc(name(b))}</h1>
      <p class="location">📍 {esc(location(b))}, Somerset</p>
    </section>
    <section class="content">
      <h2>About {esc(name(b))}</h2>
      <p>{desc_html}</p>
      {f'<p><strong>SAIS Business ID:</strong> {esc(bid)}</p>' if bid else ''}
      <div class="contact-grid">{contact}</div>
      <div class="actions">
        <a class="button" href="/">← Back to directory</a>
        {f'<a class="button secondary" href="{esc(absolute_website(website(b)))}" target="_blank" rel="noopener noreferrer">Visit business website ↗</a>' if website(b) else ''}
      </div>
    </section>
  </article>
</main>
<footer>Listed by Somerset Animal Information Services. Business information is provided by or on behalf of listed businesses and may change.</footer>
</body>
</html>
'''


def main():
    businesses = fetch_businesses()
    valid = []
    seen = set()
    for b in businesses:
        bid = business_id(b).strip()
        if not bid or bid.lower() in seen:
            continue
        seen.add(bid.lower())
        valid.append(b)

    if not valid:
        raise RuntimeError("No businesses with Business IDs were returned; refusing to delete existing generated pages.")

    OUT.mkdir(parents=True, exist_ok=True)
    # Only generated business directories are removed; other repository content is untouched.
    for child in OUT.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        elif child.is_file():
            child.unlink()

    urls = [f"{SITE_URL}/"]
    for b in valid:
        d = OUT / page_slug(b)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(render_page(b), encoding="utf-8")
        urls.append(f"{SITE_URL}/business/{page_slug(b)}/")

    # Keep the homepage legal pages in the sitemap if they exist.
    for page in ("privacy.html", "terms.html"):
        if (ROOT / page).exists():
            urls.append(f"{SITE_URL}/{page}")

    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sitemap.append(f"  <url><loc>{html.escape(u)}</loc></url>")
    sitemap.append('</urlset>')
    (ROOT / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")

    print(f"Generated {len(valid)} business pages and sitemap with {len(urls)} URLs.")


if __name__ == "__main__":
    main()
