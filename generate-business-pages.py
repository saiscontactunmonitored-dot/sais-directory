#!/usr/bin/env python3
"""
SAIS Business Page Generator

Fetches the live SAIS business directory from Google Apps Script and creates:

    business/<slug>/index.html

for every business with a Business ID.

Also generates:
    sitemap.xml

Designed for GitHub Pages and the SAIS directory.

SEO features:
- Unique page title
- Unique meta description
- Canonical URL
- Open Graph metadata
- Twitter/X metadata
- LocalBusiness structured data
- BreadcrumbList structured data
- Business contact information
- Internal links back to the main directory
- Sitemap generation
- Safe HTML escaping
- Stable Business ID based URLs
"""

from __future__ import annotations

import html
import json
import re
import shutil
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURATION
# ============================================================

API_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbzqHFo7Ea2Kp_YfkinmcVUgJ8mCRC3oOQqRoDVNB_0zpI3Rv6ZfdghGMdBVlYcTNTvV/"
    "exec"
)

SITE_URL = "https://directory.somersetanimalinformationservices.com"

SITE_NAME = "Somerset Animal Information Services"

DIRECTORY_NAME = "Somerset Animal Business Directory"

ROOT = Path(__file__).resolve().parent

BUSINESS_DIR = ROOT / "business"

SITEMAP_FILE = ROOT / "sitemap.xml"


# ============================================================
# GENERAL HELPERS
# ============================================================

def get_val(
    business: dict,
    keys: list[str],
    default: str = ""
) -> str:
    """
    Return the first non-empty matching field from a business record.

    Matching is case-insensitive so changes in spreadsheet header
    capitalisation do not break the generator.
    """

    if not isinstance(business, dict):
        return default

    normalised_business = {
        str(key).strip().lower(): value
        for key, value in business.items()
    }

    for key in keys:
        value = normalised_business.get(str(key).strip().lower())

        if value is not None and str(value).strip():
            return str(value).strip()

    return default


def esc(value: str) -> str:
    """
    Safely escape text for HTML attributes and page content.
    """

    return html.escape(str(value or ""), quote=True)


def normalise_whitespace(value: str) -> str:
    """
    Clean repeated spaces/newlines without changing the actual wording.
    """

    return re.sub(r"\s+", " ", str(value or "")).strip()


def truncate_text(value: str, max_length: int) -> str:
    """
    Create a clean meta description without cutting a word in half
    where possible.
    """

    value = normalise_whitespace(value)

    if len(value) <= max_length:
        return value

    shortened = value[:max_length].rsplit(" ", 1)[0].strip()

    if not shortened:
        shortened = value[:max_length].strip()

    return shortened.rstrip(".,;:-") + "..."


# ============================================================
# BUSINESS FIELD HELPERS
# ============================================================

def business_id(business: dict) -> str:
    """
    Get the existing SAIS Business ID.

    The generator never invents an ID for an individual page.
    """

    return get_val(
        business,
        [
            "Business ID",
            "BusinessID",
            "SAIS ID",
            "SAIS-ID",
            "ID",
        ],
    )


def business_name(business: dict) -> str:
    return get_val(
        business,
        [
            "Business Name",
            "Name",
            "Business",
            "Company",
        ],
        "Animal Business",
    )


def category(business: dict) -> str:
    return get_val(
        business,
        [
            "Category",
            "Category Name",
            "Service Category",
            "Services Offered",
            "Type",
        ],
        "Animal Service",
    )


def location(business: dict) -> str:
    return get_val(
        business,
        [
            "Area / Town",
            "Location",
            "Town",
            "Area",
            "City",
        ],
        "Somerset",
    )


def website(business: dict) -> str:
    value = get_val(
        business,
        [
            "Website",
            "Web",
            "URL",
            "Link",
            "Site",
        ],
    )

    if value and not re.match(
        r"^[a-zA-Z][a-zA-Z0-9+.-]*://",
        value
    ):
        value = "https://" + value

    return value


def phone(business: dict) -> str:
    return get_val(
        business,
        [
            "Phone",
            "Telephone",
            "Contact Number",
            "Mobile",
            "Tel",
        ],
    )


def email_address(business: dict) -> str:
    return get_val(
        business,
        [
            "Email",
            "Email Address",
            "Contact Email",
        ],
    )


def address(business: dict) -> str:
    return get_val(
        business,
        [
            "Address",
            "Full Address",
            "Postal Address",
        ],
    )


def description(business: dict) -> str:
    return get_val(
        business,
        [
            "Description",
            "Services",
            "About",
            "Notes",
            "Details",
        ],
    )


# ============================================================
# SLUG / URL HELPERS
# ============================================================

def slugify(value: str) -> str:
    """
    Convert business information into a clean URL slug.
    """

    value = unicodedata.normalize(
        "NFKD",
        str(value or "")
    ).encode(
        "ascii",
        "ignore"
    ).decode(
        "ascii"
    )

    value = value.lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value
    )

    value = value.strip("-")

    return value or "business"


def business_slug(business: dict) -> str:
    """
    Business URLs use:

    sais-0006-pawsome-training-and-behaviour

    The Business ID comes first so URLs remain tied to the
    permanent SAIS Business ID.
    """

    bid = slugify(business_id(business))
    name = slugify(business_name(business))

    if bid and name:
        return f"{bid}-{name}"

    if bid:
        return bid

    return name


# ============================================================
# SEO HELPERS
# ============================================================

def create_page_title(
    business: dict
) -> str:
    """
    Create a unique title for each business page.
    """

    name = business_name(business)
    cat = category(business)
    loc = location(business)

    parts = []

    if name:
        parts.append(name)

    if cat and cat.lower() not in name.lower():
        parts.append(cat)

    if loc and loc.lower() not in name.lower():
        parts.append(loc)

    parts.append("SAIS")

    return " | ".join(parts)


def create_meta_description(
    business: dict
) -> str:
    """
    Create a useful search-result description from the actual
    listing information.

    We do not invent services or claims that aren't present
    in the business record.
    """

    name = business_name(business)
    cat = category(business)
    loc = location(business)
    desc = description(business)

    if desc:
        text = (
            f"{name} is listed in the Somerset Animal Business Directory. "
            f"{desc}"
        )
    else:
        text = (
            f"{name} is listed in the Somerset Animal Business Directory "
            f"as a {cat.lower()} in {loc}, Somerset."
        )

    return truncate_text(text, 155)


def create_social_description(
    business: dict
) -> str:
    """
    Slightly longer description for social sharing.
    """

    name = business_name(business)
    cat = category(business)
    loc = location(business)
    desc = description(business)

    if desc:
        text = (
            f"{name} — {cat} in {loc}, Somerset. {desc}"
        )
    else:
        text = (
            f"{name} — {cat} in {loc}, Somerset. "
            f"Listed in the Somerset Animal Business Directory."
        )

    return truncate_text(text, 250)


# ============================================================
# STRUCTURED DATA
# ============================================================

def create_local_business_jsonld(
    business: dict,
    page_url: str
) -> str:
    """
    Generate LocalBusiness structured data using only information
    actually available in the business listing.
    """

    name = business_name(business)
    cat = category(business)
    loc = location(business)
    desc = description(business)
    site = website(business)
    tel = phone(business)
    email = email_address(business)
    addr = address(business)

    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": name,
        "url": page_url,
        "areaServed": {
            "@type": "AdministrativeArea",
            "name": "Somerset",
        },
    }

    if desc:
        data["description"] = desc

    if cat:
        data["category"] = cat

    if loc:
        data["addressLocality"] = loc

    if tel:
        data["telephone"] = tel

    if email:
        data["email"] = email

    if site:
        data["sameAs"] = [site]

    if addr:
        data["address"] = {
            "@type": "PostalAddress",
            "streetAddress": addr,
            "addressRegion": "Somerset",
            "addressCountry": "GB",
        }
    else:
        data["address"] = {
            "@type": "PostalAddress",
            "addressLocality": loc or "Somerset",
            "addressRegion": "Somerset",
            "addressCountry": "GB",
        }

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    )


def create_breadcrumb_jsonld(
    business: dict,
    page_url: str
) -> str:
    """
    Breadcrumb structured data for:

    Home
      >
    Somerset Animal Business Directory
      >
    Business
    """

    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": f"{SITE_URL}/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": DIRECTORY_NAME,
                "item": f"{SITE_URL}/",
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": business_name(business),
                "item": page_url,
            },
        ],
    }

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    )


# ============================================================
# FETCH LIVE DIRECTORY
# ============================================================

def fetch_businesses() -> list[dict]:
    print("Fetching SAIS business data...")
    print(API_URL)

    request = Request(
        API_URL,
        headers={
            "User-Agent": "SAIS-Business-Page-Generator/2.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )

    try:
        with urlopen(
            request,
            timeout=60
        ) as response:
            raw = response.read().decode("utf-8-sig")

    except HTTPError as exc:
        raise RuntimeError(
            "Could not retrieve the SAIS Apps Script data. "
            f"HTTP {exc.code}: {exc.reason}\n"
            f"URL: {API_URL}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            "Could not retrieve the SAIS Apps Script data. "
            f"Network error: {exc.reason}\n"
            f"URL: {API_URL}"
        ) from exc

    except TimeoutError as exc:
        raise RuntimeError(
            "The SAIS Apps Script request timed out.\n"
            f"URL: {API_URL}"
        ) from exc

    try:
        data = json.loads(raw)

    except json.JSONDecodeError as exc:
        preview = raw[:500].replace(
            "\n",
            " "
        )

        raise RuntimeError(
            "The Apps Script endpoint did not return valid JSON. "
            f"Response started with: {preview!r}"
        ) from exc

    if isinstance(data, list):
        businesses = data

    elif isinstance(data, dict):
        businesses = (
            data.get("businesses")
            or data.get("data")
            or []
        )

    else:
        businesses = []

    if not isinstance(
        businesses,
        list
    ):
        raise RuntimeError(
            "The Apps Script response contains an unexpected "
            "business data format."
        )

    clean = [
        business
        for business in businesses
        if isinstance(business, dict)
    ]

    print(
        f"Found {len(clean)} businesses."
    )

    return clean


# ============================================================
# PAGE HTML
# ============================================================

def page_html(
    business: dict,
    slug: str
) -> str:

    name = business_name(business)
    cat = category(business)
    loc = location(business)
    desc = description(business)
    site = website(business)
    tel = phone(business)
    email = email_address(business)
    addr = address(business)
    bid = business_id(business)

    page_url = (
        f"{SITE_URL}/business/{slug}/"
    )

    title = create_page_title(
        business
    )

    meta_description = create_meta_description(
        business
    )

    social_description = create_social_description(
        business
    )

    local_business_schema = create_local_business_jsonld(
        business,
        page_url
    )

    breadcrumb_schema = create_breadcrumb_jsonld(
        business,
        page_url
    )

    # --------------------------------------------------------
    # CONTACT BUTTONS
    # --------------------------------------------------------

    contact_buttons = []

    if site:
        contact_buttons.append(
            f'''
            <a
              class="button"
              href="{esc(site)}"
              target="_blank"
              rel="noopener noreferrer"
            >
              Visit Website
            </a>
            '''
        )

    if tel:
        contact_buttons.append(
            f'''
            <a
              class="button secondary"
              href="tel:{esc(tel)}"
            >
              Call {esc(tel)}
            </a>
            '''
        )

    if email:
        contact_buttons.append(
            f'''
            <a
              class="button secondary"
              href="mailto:{esc(email)}"
            >
              Email
            </a>
            '''
        )

    # --------------------------------------------------------
    # DETAILS
    # --------------------------------------------------------

    details = []

    if addr:
        details.append(
            f'''
            <div class="detail">
              <strong>Address</strong>
              <span>{esc(addr)}</span>
            </div>
            '''
        )

    if tel:
        details.append(
            f'''
            <div class="detail">
              <strong>Telephone</strong>
              <a href="tel:{esc(tel)}">
                {esc(tel)}
              </a>
            </div>
            '''
        )

    if email:
        details.append(
            f'''
            <div class="detail">
              <strong>Email</strong>
              <a href="mailto:{esc(email)}">
                {esc(email)}
              </a>
            </div>
            '''
        )

    if site:
        details.append(
            f'''
            <div class="detail">
              <strong>Website</strong>
              <a
                href="{esc(site)}"
                target="_blank"
                rel="noopener noreferrer"
              >
                {esc(site)}
              </a>
            </div>
            '''
        )

    if bid:
        details.append(
            f'''
            <div class="detail">
              <strong>SAIS Business ID</strong>
              <span>{esc(bid)}</span>
            </div>
            '''
        )

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    if desc:
        description_html = esc(desc)
    else:
        description_html = (
            f"{esc(name)} is listed in the "
            f"Somerset Animal Business Directory."
        )

    # --------------------------------------------------------
    # GENERATED PAGE
    # --------------------------------------------------------

    return f'''<!doctype html>
<html lang="en-GB">
<head>

  <meta charset="utf-8">

  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >

  <title>{esc(title)}</title>

  <meta
    name="description"
    content="{esc(meta_description)}"
  >

  <meta
    name="robots"
    content="index, follow"
  >

  <link
    rel="canonical"
    href="{esc(page_url)}"
  >

  <!-- SAIS Branding -->

  <link
    rel="icon"
    type="image/png"
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
    property="og:site_name"
    content="{esc(SITE_NAME)}"
  >

  <meta
    property="og:title"
    content="{esc(title)}"
  >

  <meta
    property="og:description"
    content="{esc(social_description)}"
  >

  <meta
    property="og:url"
    content="{esc(page_url)}"
  >

  <meta
    property="og:image"
    content="{SITE_URL}/directorybanner.png"
  >

  <meta
    property="og:image:width"
    content="1200"
  >

  <meta
    property="og:image:height"
    content="630"
  >

  <!-- Twitter / X -->

  <meta
    name="twitter:card"
    content="summary_large_image"
  >

  <meta
    name="twitter:title"
    content="{esc(title)}"
  >

  <meta
    name="twitter:description"
    content="{esc(social_description)}"
  >

  <meta
    name="twitter:url"
    content="{esc(page_url)}"
  >

  <meta
    name="twitter:image"
    content="{SITE_URL}/directorybanner.png"
  >

  <!-- LocalBusiness structured data -->

  <script type="application/ld+json">
{local_business_schema}
  </script>

  <!-- Breadcrumb structured data -->

  <script type="application/ld+json">
{breadcrumb_schema}
  </script>

  <style>

    :root {{
      --brand-red: #c82333;
      --brand-red-dark: #9e1b28;
      --navy: #172033;
      --blue: #174f78;
      --blue-dark: #0d3857;
      --text: #334155;
      --muted: #64748b;
      --border: #e2e8f0;
      --background: #f1f5f9;
      --white: #ffffff;
    }}

    * {{
      box-sizing: border-box;
    }}

    html {{
      scroll-behavior: smooth;
    }}

    body {{
      margin: 0;
      font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Roboto,
        Arial,
        sans-serif;
      background: var(--background);
      color: var(--text);
      line-height: 1.65;
    }}

    header {{
      background: var(--white);
      border-bottom: 1px solid var(--border);
      padding: 14px 20px;
    }}

    .header-inner {{
      max-width: 1120px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      gap: 14px;
    }}

    .logo-link {{
      display: flex;
      align-items: center;
      flex-shrink: 0;
    }}

    .logo {{
      width: 54px;
      height: 54px;
      object-fit: contain;
      border-radius: 10px;
    }}

    .brand {{
      color: var(--navy);
      text-decoration: none;
      font-weight: 800;
      font-size: 1rem;
      line-height: 1.25;
    }}

    .brand-small {{
      display: block;
      color: var(--brand-red);
      font-size: .68rem;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-top: 3px;
    }}

    main {{
      max-width: 920px;
      margin: 42px auto;
      padding: 0 18px;
    }}

    .breadcrumbs {{
      margin-bottom: 16px;
      font-size: .84rem;
      color: var(--muted);
    }}

    .breadcrumbs a {{
      color: var(--blue);
      text-decoration: none;
      font-weight: 600;
    }}

    .breadcrumbs a:hover {{
      text-decoration: underline;
    }}

    .card {{
      background: var(--white);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 34px;
      box-shadow:
        0 8px 30px rgba(15,23,42,.08);
    }}

    .eyebrow {{
      display: inline-block;
      color: var(--brand-red);
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .07em;
      font-size: .78rem;
      margin-bottom: 5px;
    }}

    h1 {{
      color: var(--navy);
      margin: 5px 0 7px;
      font-size: clamp(2rem, 5vw, 3.1rem);
      line-height: 1.1;
      letter-spacing: -.025em;
    }}

    .location {{
      color: var(--muted);
      font-size: 1rem;
      margin-bottom: 25px;
    }}

    .description-heading {{
      color: var(--navy);
      font-size: 1.05rem;
      margin: 0 0 8px;
    }}

    .description {{
      font-size: 1.04rem;
      white-space: pre-line;
      color: var(--text);
    }}

    .details {{
      margin-top: 30px;
      border-top: 1px solid var(--border);
    }}

    .detail {{
      padding: 15px 0;
      border-bottom: 1px solid var(--border);
      display: grid;
      grid-template-columns: 150px 1fr;
      gap: 15px;
      overflow-wrap: anywhere;
    }}

    .detail strong {{
      color: var(--navy);
    }}

    .detail a {{
      color: var(--blue);
      font-weight: 600;
    }}

    .buttons {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 28px;
    }}

    .button {{
      display: inline-block;
      background: var(--brand-red);
      color: #ffffff;
      text-decoration: none;
      padding: 11px 18px;
      border-radius: 10px;
      font-weight: 700;
      transition:
        background-color .15s ease,
        transform .15s ease;
    }}

    .button:hover {{
      background: var(--brand-red-dark);
      transform: translateY(-1px);
    }}

    .button.secondary {{
      background: var(--blue);
    }}

    .button.secondary:hover {{
      background: var(--blue-dark);
    }}

    .back {{
      display: inline-block;
      margin-top: 24px;
      color: var(--blue);
      text-decoration: none;
      font-weight: 700;
    }}

    .back:hover {{
      text-decoration: underline;
    }}

    footer {{
      text-align: center;
      color: var(--muted);
      padding: 30px 18px 45px;
      font-size: .88rem;
    }}

    footer a {{
      color: var(--blue);
      font-weight: 600;
    }}

    @media (max-width: 650px) {{

      main {{
        margin: 25px auto;
      }}

      .card {{
        padding: 23px 20px;
        border-radius: 14px;
      }}

      .detail {{
        grid-template-columns: 1fr;
        gap: 4px;
      }}

      .buttons {{
        flex-direction: column;
      }}

      .button {{
        text-align: center;
        width: 100%;
      }}

      .brand {{
        font-size: .9rem;
      }}

      .brand-small {{
        font-size: .58rem;
      }}

    }}

  </style>

</head>

<body>

<header>

  <div class="header-inner">

    <a
      class="logo-link"
      href="../../"
      aria-label="Back to Somerset Animal Business Directory"
    >
      <img
        class="logo"
        src="../../directorylogo.png"
        alt="Somerset Animal Information Services logo"
      >
    </a>

    <a
      class="brand"
      href="../../"
    >
      {esc(DIRECTORY_NAME)}

      <span class="brand-small">
        {esc(SITE_NAME)}
      </span>
    </a>

  </div>

</header>

<main>

  <nav
    class="breadcrumbs"
    aria-label="Breadcrumb"
  >
    <a href="../../">
      Somerset Animal Business Directory
    </a>

    <span aria-hidden="true">
      &nbsp;›&nbsp;
    </span>

    <span>
      {esc(name)}
    </span>
  </nav>

  <article class="card">

    <div class="eyebrow">
      {esc(cat)}
    </div>

    <h1>
      {esc(name)}
    </h1>

    <div class="location">
      📍 {esc(loc)}
    </div>

    <section aria-labelledby="about-business">

      <h2
        id="about-business"
        class="description-heading"
      >
        About {esc(name)}
      </h2>

      <div class="description">
        {description_html}
      </div>

    </section>

    <div class="details">

      {''.join(details)}

    </div>

    <div class="buttons">

      {''.join(contact_buttons)}

    </div>

    <a
      class="back"
      href="../../"
    >
      ← Back to Somerset Animal Business Directory
    </a>

  </article>

</main>

<footer>

  <div>
    <strong>
      Somerset Animal Information Services
    </strong>
  </div>

  <div>
    Free Somerset animal business directory and information service
  </div>

  <div>
    <a href="../../">
      Browse the Somerset Animal Business Directory
    </a>
  </div>

</footer>

</body>
</html>
'''


# ============================================================
# SITEMAP
# ============================================================

def create_sitemap(
    urls: list[str]
) -> str:

    generated_time = datetime.now(
        timezone.utc
    ).date().isoformat()

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for url in urls:

        lines.append(
            "  <url>"
            f"<loc>{esc(url)}</loc>"
            f"<lastmod>{generated_time}</lastmod>"
            "</url>"
        )

    lines.append(
        "</urlset>"
    )

    return "\n".join(lines) + "\n"


# ============================================================
# GENERATION
# ============================================================

def generate() -> None:

    businesses = fetch_businesses()

    if not businesses:
        raise RuntimeError(
            "No businesses were returned. Nothing was generated."
        )

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="sais-business-pages-",
            dir=str(ROOT)
        )
    )

    temp_business_dir = (
        temp_dir / "business"
    )

    temp_business_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        used_slugs: set[str] = set()

        sitemap_urls = [
            f"{SITE_URL}/"
        ]

        generated_count = 0

        skipped_count = 0

        for business in businesses:

            bid = business_id(
                business
            )

            if not bid:

                print(
                    "Skipping business without Business ID: "
                    f"{business_name(business)}"
                )

                skipped_count += 1

                continue

            base_slug = business_slug(
                business
            )

            slug = base_slug

            counter = 2

            while slug in used_slugs:

                slug = (
                    f"{base_slug}-{counter}"
                )

                counter += 1

            used_slugs.add(
                slug
            )

            out_dir = (
                temp_business_dir / slug
            )

            out_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            output_file = (
                out_dir / "index.html"
            )

            output_file.write_text(
                page_html(
                    business,
                    slug
                ),
                encoding="utf-8"
            )

            sitemap_urls.append(
                f"{SITE_URL}/business/{slug}/"
            )

            generated_count += 1

            print(
                f"Generated: {bid} | "
                f"{business_name(business)} | "
                f"{slug}"
            )

        if generated_count == 0:

            raise RuntimeError(
                "No business pages were generated."
            )

        # ----------------------------------------------------
        # Replace existing generated business directory
        # ----------------------------------------------------

        if BUSINESS_DIR.exists():
            shutil.rmtree(
                BUSINESS_DIR
            )

        shutil.move(
            str(temp_business_dir),
            str(BUSINESS_DIR)
        )

        # ----------------------------------------------------
        # Generate sitemap
        # ----------------------------------------------------

        sitemap_content = create_sitemap(
            sitemap_urls
        )

        SITEMAP_FILE.write_text(
            sitemap_content,
            encoding="utf-8"
        )

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
            f"Business pages generated: {generated_count}"
        )
        print(
            f"Businesses skipped: {skipped_count}"
        )
        print(
            f"Sitemap URLs: {len(sitemap_urls)}"
        )
        print(
            f"Sitemap: {SITEMAP_FILE}"
        )
        print(
            "=========================================="
        )

    finally:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    generate()
