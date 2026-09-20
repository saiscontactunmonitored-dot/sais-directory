#!/usr/bin/env python3

"""
Generate crawlable SAIS business directory pages.

Pages are generated as:

business/<business-slug>/index.html

A sitemap.xml is also generated.

The existing index.html/search/filter system is not changed.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlparse


# ============================================================
# SETTINGS
# ============================================================

API_URL = "https://script.google.com/macros/s/AKfycbwl2XzI0HGvz5VcXSPuZmTQ-8fB9w328OZ5IsMEp-eRLr-Qr_2mbD81tCKZrt1Uxoa/exec"

SITE_URL = "https://directory.somersetanimalinformationservices.com"

ROOT = Path(__file__).resolve().parent

BUSINESS_DIR = ROOT / "business"

TEMP_DIR = ROOT / ".business-generated"


# ============================================================
# BASIC HELPERS
# ============================================================

def get_val(business, *keys):
    """
    Get the first non-empty value from a business record.
    """

    for key in keys:
        value = business.get(key)

        if value is not None and str(value).strip():
            return str(value).strip()

    return ""


def esc(value):
    """
    Safely escape text for HTML.
    """

    return html.escape(str(value or ""), quote=True)


# ============================================================
# BUSINESS FIELDS
# ============================================================

def business_id(business):
    return get_val(
        business,
        "Business ID",
        "BusinessID",
        "SAIS ID",
        "SAIS-ID",
        "ID"
    )


def business_name(business):
    return get_val(
        business,
        "Business Name",
        "Business name",
        "Name",
        "Company",
        "Company Name"
    )


def category(business):
    return get_val(
        business,
        "Category",
        "Business Category",
        "Business category",
        "Type"
    )


def location(business):
    return get_val(
        business,
        "Location",
        "Town",
        "Area",
        "County"
    )


def website(business):
    return get_val(
        business,
        "Website",
        "Web Site",
        "URL",
        "Website URL"
    )


def phone(business):
    return get_val(
        business,
        "Phone",
        "Telephone",
        "Telephone Number",
        "Phone Number",
        "Phone number",
        "Contact Number"
    )


def email(business):
    return get_val(
        business,
        "Email",
        "Email Address",
        "Contact Email"
    )


def address(business):
    return get_val(
        business,
        "Address",
        "Business Address",
        "Full Address"
    )


def description(business):
    return get_val(
        business,
        "Description",
        "Business Description",
        "About",
        "About Business"
    )


# ============================================================
# URL / SLUG FUNCTIONS
# ============================================================

def slugify(value):
    """
    Convert business name/ID into a clean URL slug.
    """

    value = str(value or "").lower().strip()

    value = value.replace("&", " and ")

    value = re.sub(r"[^a-z0-9]+", "-", value)

    value = re.sub(r"-+", "-", value)

    return value.strip("-")


def make_slug(business):
    """
    Create a stable business URL.

    Example:

    SAIS-0002 + Canine Insight

    becomes:

    sais-0002-canine-insight
    """

    bid = business_id(business)
    name = business_name(business)

    if bid and name:
        return slugify(f"{bid}-{name}")

    if bid:
        return slugify(bid)

    if name:
        return slugify(name)

    return ""


def business_url(slug):
    return (
        SITE_URL.rstrip("/")
        + "/business/"
        + quote(slug)
        + "/"
    )


# ============================================================
# WEBSITE VALIDATION
# ============================================================

def clean_website(value):
    """
    Make sure external websites use HTTP/HTTPS.
    """

    value = str(value or "").strip()

    if not value:
        return ""

    parsed = urlparse(value)

    if parsed.scheme in ("http", "https"):
        return value

    if not parsed.scheme:
        return "https://" + value

    return ""


# ============================================================
# OPTIONAL BUSINESS IMAGE
# ============================================================

def business_image(business):
    """
    Looks for an image supplied in the Google Sheet first.

    Otherwise checks:

    images/businesses/SAIS-0002.jpg
    images/businesses/SAIS-0002.jpeg
    images/businesses/SAIS-0002.png
    images/businesses/SAIS-0002.webp
    """

    supplied = get_val(
        business,
        "Image",
        "Image URL",
        "Business Image",
        "Business Image URL",
        "Photo",
        "Photo URL"
    )

    if supplied:
        return supplied

    bid = business_id(business)

    if not bid:
        return ""

    image_folder = ROOT / "images" / "businesses"

    for extension in (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    ):

        file_path = image_folder / f"{bid}{extension}"

        if file_path.exists():

            return (
                "../../images/businesses/"
                + quote(bid)
                + extension
            )

    return ""


# ============================================================
# JSON-LD STRUCTURED DATA
# ============================================================

def make_schema(business, slug):

    name = business_name(business)

    bid = business_id(business)

    cat = category(business)

    loc = location(business)

    addr = address(business)

    site = clean_website(website(business))

    tel = phone(business)

    mail = email(business)

    desc = description(business)

    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": name or bid or "SAIS Business",
        "url": business_url(slug)
    }

    if desc:
        data["description"] = desc

    if cat:
        data["category"] = cat

    if site:
        data["sameAs"] = [site]

    if tel:
        data["telephone"] = tel

    if mail:
        data["email"] = mail

    if addr:

        data["address"] = {
            "@type": "PostalAddress",
            "streetAddress": addr,
            "addressRegion": "Somerset",
            "addressCountry": "GB"
        }

    elif loc:

        data["address"] = {
            "@type": "PostalAddress",
            "addressRegion": loc,
            "addressCountry": "GB"
        }

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    )


# ============================================================
# DETAIL ROW
# ============================================================

def detail_row(label, value, href=None):

    if not value:
        return ""

    value_html = esc(value)

    if href:

        value_html = (
            f'<a href="{esc(href)}" '
            f'target="_blank" '
            f'rel="noopener noreferrer">'
            f'{esc(value)}'
            f'</a>'
        )

    return f"""
<div class="detail-row">
    <div class="detail-label">{esc(label)}</div>
    <div>{value_html}</div>
</div>
"""


# ============================================================
# CREATE BUSINESS PAGE
# ============================================================

def create_business_page(business, slug):

    name = business_name(business) or "SAIS Business"

    bid = business_id(business)

    cat = category(business)

    loc = location(business)

    addr = address(business)

    site = clean_website(website(business))

    tel = phone(business)

    mail = email(business)

    desc = description(business)

    image = business_image(business)

    canonical = business_url(slug)

    description_text = (
        desc
        or f"{name} is listed in the Somerset Animal Information Services directory."
    )

    description_text = description_text[:155]

    image_html = ""

    if image:

        image_html = f"""
<div class="business-image-wrap">
    <img
        src="{esc(image)}"
        alt="{esc(name)}"
        class="business-image"
    >
</div>
"""

    about_html = ""

    if desc:

        about_html = f"""
<section class="about">

    <h2>About {esc(name)}</h2>

    <p>{esc(desc)}</p>

</section>
"""

    details = ""

    details += detail_row(
        "Category",
        cat
    )

    details += detail_row(
        "Location",
        loc
    )

    details += detail_row(
        "Address",
        addr
    )

    if tel:

        details += detail_row(
            "Phone",
            tel,
            f"tel:{tel}"
        )

    if mail:

        details += detail_row(
            "Email",
            mail,
            f"mailto:{mail}"
        )

    if site:

        details += detail_row(
            "Website",
            site,
            site
        )

    details += detail_row(
        "SAIS Business ID",
        bid
    )

    actions = ""

    if site:

        actions += f"""
<a
    class="button"
    href="{esc(site)}"
    target="_blank"
    rel="noopener noreferrer"
>
    Visit Website
</a>
"""

    if tel:

        actions += f"""
<a
    class="button secondary"
    href="tel:{esc(tel)}"
>
    Call Business
</a>
"""

    if mail:

        actions += f"""
<a
    class="button secondary"
    href="mailto:{esc(mail)}"
>
    Email Business
</a>
"""

    return f"""<!DOCTYPE html>

<html lang="en-GB">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
{esc(name)}
|
Somerset Animal Information Services
</title>

<meta
    name="description"
    content="{esc(description_text)}"
>

<meta
    name="robots"
    content="index, follow"
>

<link
    rel="canonical"
    href="{esc(canonical)}"
>

<link
    rel="icon"
    href="../../directorylogo.png"
>

<link
    rel="apple-touch-icon"
    href="../../directorylogo.png"
>


<!-- Open Graph -->

<meta
    property="og:type"
    content="business.business"
>

<meta
    property="og:title"
    content="{esc(name)} | SAIS Directory"
>

<meta
    property="og:description"
    content="{esc(description_text)}"
>

<meta
    property="og:url"
    content="{esc(canonical)}"
>

<meta
    property="og:site_name"
    content="Somerset Animal Information Services"
>


<!-- Twitter -->

<meta
    name="twitter:card"
    content="summary_large_image"
>

<meta
    name="twitter:title"
    content="{esc(name)} | SAIS Directory"
>

<meta
    name="twitter:description"
    content="{esc(description_text)}"
>


<!-- Structured data -->

<script type="application/ld+json">

{make_schema(business, slug)}

</script>


<style>

:root {{

    --red: #c82333;

    --navy: #17324d;

    --text: #20252b;

    --muted: #68717a;

    --border: #e4e7eb;

    --background: #f7f8fa;

    --white: #ffffff;

}}

* {{

    box-sizing: border-box;

}}

body {{

    margin: 0;

    background: var(--background);

    color: var(--text);

    font-family:
        Arial,
        Helvetica,
        sans-serif;

    line-height: 1.6;

}}

header {{

    background: var(--white);

    border-bottom:
        1px solid
        var(--border);

}}

.header-inner {{

    max-width: 1100px;

    margin: auto;

    padding: 18px 20px;

    display: flex;

    align-items: center;

    justify-content: space-between;

    gap: 20px;

}}

.brand {{

    display: flex;

    align-items: center;

    gap: 12px;

    text-decoration: none;

    color: var(--navy);

    font-weight: 700;

}}

.brand img {{

    width: 55px;

    height: 55px;

    object-fit: contain;

}}

.back-button {{

    background: var(--red);

    color: white;

    padding:
        10px 16px;

    border-radius: 8px;

    text-decoration: none;

    font-weight: 700;

}}

main {{

    max-width: 1000px;

    margin: auto;

    padding:
        40px 20px
        70px;

}}

.breadcrumbs {{

    margin-bottom: 20px;

    font-size: 14px;

    color: var(--muted);

}}

.breadcrumbs a {{

    color: var(--red);

    text-decoration: none;

}}

.card {{

    background: var(--white);

    border:
        1px solid
        var(--border);

    border-radius: 18px;

    overflow: hidden;

    box-shadow:
        0 8px 30px
        rgba(0,0,0,.05);

}}

.business-image-wrap {{

    background: #eef1f3;

}}

.business-image {{

    display: block;

    width: 100%;

    max-height: 430px;

    object-fit: cover;

}}

.content {{

    padding: 34px;

}}

.eyebrow {{

    color: var(--red);

    font-size: 13px;

    font-weight: 800;

    text-transform: uppercase;

    letter-spacing: .06em;

}}

h1 {{

    margin:
        6px 0 10px;

    color: var(--navy);

    font-size:
        clamp(
            30px,
            5vw,
            48px
        );

    line-height: 1.1;

}}

.location {{

    color: var(--muted);

    font-size: 17px;

    margin-bottom: 28px;

}}

.details {{

    border-top:
        1px solid
        var(--border);

}}

.detail-row {{

    display: grid;

    grid-template-columns:
        160px
        1fr;

    gap: 20px;

    padding:
        14px 0;

    border-bottom:
        1px solid
        var(--border);

}}

.detail-label {{

    font-weight: 700;

    color: var(--navy);

}}

.detail-row a {{

    color: var(--red);

    word-break: break-word;

}}

.about {{

    margin-top: 32px;

}}

.about h2 {{

    color: var(--navy);

}}

.actions {{

    display: flex;

    flex-wrap: wrap;

    gap: 12px;

    margin-top: 30px;

}}

.button {{

    display: inline-block;

    padding:
        12px 18px;

    border-radius: 9px;

    background: var(--red);

    color: white;

    text-decoration: none;

    font-weight: 700;

}}

.button.secondary {{

    background: var(--navy);

}}

footer {{

    background: var(--navy);

    color: white;

    text-align: center;

    padding: 28px 20px;

    font-size: 14px;

}}

@media (max-width: 650px) {{

    .header-inner {{

        align-items: flex-start;

    }}

    .brand span {{

        display: none;

    }}

    .content {{

        padding: 24px;

    }}

    .detail-row {{

        grid-template-columns: 1fr;

        gap: 3px;

    }}

}}

</style>

</head>


<body>


<header>

<div class="header-inner">

<a
    class="brand"
    href="{esc(SITE_URL)}/"
>

<img
    src="../../directorylogo.png"
    alt="Somerset Animal Information Services"
>

<span>
Somerset Animal Information Services
</span>

</a>


<a
    class="back-button"
    href="{esc(SITE_URL)}/"
>
Back to Directory
</a>

</div>

</header>


<main>


<div class="breadcrumbs">

<a href="{esc(SITE_URL)}/">
SAIS Directory
</a>

&nbsp;›&nbsp;

{esc(name)}

</div>


<article class="card">


{image_html}


<div class="content">


<div class="eyebrow">
SAIS Business Directory
</div>


<h1>
{esc(name)}
</h1>


{f'<div class="location">{esc(loc)}</div>' if loc else ''}


<div class="details">

{details}

</div>


{about_html}


<div class="actions">

{actions}

</div>


</div>

</article>


</main>


<footer>

<div>
Somerset Animal Information Services
</div>

<div>
Free animal business directory and information service.
</div>

</footer>


</body>

</html>
"""


# ============================================================
# GET BUSINESSES FROM GOOGLE APPS SCRIPT
# ============================================================

def fetch_businesses():

    print("Fetching SAIS business data...")

    print(API_URL)

    request = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent":
                "SAIS-Business-Page-Generator/1.0",

            "Accept":
                "application/json,text/plain,*/*"
        }
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=60
        ) as response:

            raw = response.read().decode(
                "utf-8"
            )

    except Exception as error:

        raise RuntimeError(
            "\n"
            "Could not retrieve the SAIS Apps Script data.\n"
            "\n"
            f"URL:\n{API_URL}\n"
            "\n"
            f"Error:\n{error}\n"
        ) from error


    try:

        data = json.loads(raw)

    except json.JSONDecodeError as error:

        print(
            "The server returned:"
        )

        print(raw[:2000])

        raise RuntimeError(
            "The Apps Script endpoint did not return valid JSON."
        ) from error


    if isinstance(data, list):

        businesses = data

    elif isinstance(data, dict):

        businesses = (
            data.get("businesses")
            or data.get("data")
            or data.get("results")
            or []
        )

    else:

        businesses = []


    if not isinstance(
        businesses,
        list
    ):

        raise RuntimeError(
            "The Apps Script response does not contain a business list."
        )


    businesses = [
        item
        for item in businesses
        if isinstance(item, dict)
    ]


    print(
        f"Businesses received: {len(businesses)}"
    )


    if not businesses:

        raise RuntimeError(
            "The Apps Script feed returned zero businesses. "
            "No pages were generated."
        )


    return businesses


# ============================================================
# SITEMAP
# ============================================================

def create_sitemap(slugs):

    urls = [
        SITE_URL.rstrip("/") + "/"
    ]

    for slug in slugs:

        urls.append(
            business_url(slug)
        )


    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',

        '<urlset '
        'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]


    for url in urls:

        lines.append(
            "  <url>"
        )

        lines.append(
            f"    <loc>{html.escape(url)}</loc>"
        )

        lines.append(
            "  </url>"
        )


    lines.append(
        "</urlset>"
    )


    sitemap_path = (
        ROOT /
        "sitemap.xml"
    )


    sitemap_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )


    print(
        f"Sitemap generated: {sitemap_path}"
    )

    print(
        f"URLs in sitemap: {len(urls)}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    businesses = fetch_businesses()


    # --------------------------------------------------------
    # Generate everything into a temporary directory first.
    # --------------------------------------------------------

    if TEMP_DIR.exists():

        shutil.rmtree(
            TEMP_DIR
        )


    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    generated = 0

    slugs = set()


    # --------------------------------------------------------
    # Create every business page.
    # --------------------------------------------------------

    for business in businesses:

        bid = business_id(
            business
        )

        name = business_name(
            business
        )

        slug = make_slug(
            business
        )


        if not slug:

            print(
                "Skipping business without "
                "Business ID or name."
            )

            continue


        if slug in slugs:

            print(
                f"Skipping duplicate slug: {slug}"
            )

            continue


        slugs.add(
            slug
        )


        folder = (
            TEMP_DIR /
            slug
        )


        folder.mkdir(
            parents=True,
            exist_ok=True
        )


        page = create_business_page(
            business,
            slug
        )


        (
            folder /
            "index.html"
        ).write_text(
            page,
            encoding="utf-8"
        )


        generated += 1


        print(
            f"[{generated}] "
            f"{bid or 'NO-ID'} | "
            f"{name or 'Unnamed'} | "
            f"/business/{slug}/"
        )


    # --------------------------------------------------------
    # Safety check.
    # --------------------------------------------------------

    if generated == 0:

        shutil.rmtree(
            TEMP_DIR,
            ignore_errors=True
        )

        raise RuntimeError(
            "No business pages were generated."
        )


    # --------------------------------------------------------
    # Replace the old generated business directory.
    # --------------------------------------------------------

    if BUSINESS_DIR.exists():

        shutil.rmtree(
            BUSINESS_DIR
        )


    TEMP_DIR.rename(
        BUSINESS_DIR
    )


    # --------------------------------------------------------
    # Generate sitemap.
    # --------------------------------------------------------

    create_sitemap(
        sorted(slugs)
    )


    # --------------------------------------------------------
    # Finished.
    # --------------------------------------------------------

    print()
    print(
        "=========================================="
    )

    print(
        "SAIS BUSINESS PAGE GENERATION COMPLETE"
    )

    print(
        "=========================================="
    )

    print(
        f"Business pages generated: {generated}"
    )

    print(
        f"Output: {BUSINESS_DIR}"
    )

    print(
        f"Sitemap: {ROOT / 'sitemap.xml'}"
    )


if __name__ == "__main__":

    main()
