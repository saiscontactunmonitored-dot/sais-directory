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
- Unique SEO page titles
- Unique meta descriptions
- Canonical URLs
- Open Graph metadata
- Twitter/X metadata
- LocalBusiness structured data
- BreadcrumbList structured data
- Real business listing information
- Business contact information
- Social links where available
- Optional business images
- Internal links
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

BUSINESS_IMAGE_DIR = ROOT / "images" / "businesses"


# ============================================================
# GENERAL HELPERS
# ============================================================

def normalise_key(value: str) -> str:
    """
    Normalise spreadsheet column names so that small differences
    in punctuation, spaces and capitalisation do not matter.
    """

    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value or "").strip().lower()
    )


def get_val(
    business: dict,
    keys: list[str],
    default: str = ""
) -> str:
    """
    Return the first non-empty matching field.

    Matching is tolerant of:
    - capitalisation
    - spaces
    - punctuation
    - slash characters
    """

    if not isinstance(business, dict):
        return default

    normalised_business = {
        normalise_key(key): value
        for key, value in business.items()
    }

    for key in keys:

        normalised_key = normalise_key(key)

        value = normalised_business.get(
            normalised_key
        )

        if value is not None and str(value).strip():
            return str(value).strip()

    return default


def esc(value: str) -> str:
    """
    Safely escape text for HTML.
    """

    return html.escape(
        str(value or ""),
        quote=True
    )


def normalise_whitespace(value: str) -> str:
    """
    Collapse repeated spaces and line breaks.
    """

    return re.sub(
        r"\s+",
        " ",
        str(value or "")
    ).strip()


def truncate_text(
    value: str,
    max_length: int
) -> str:
    """
    Create a clean search/social description without cutting
    through a word where possible.
    """

    value = normalise_whitespace(value)

    if len(value) <= max_length:
        return value

    shortened = value[
        :max_length
    ].rsplit(" ", 1)[0].strip()

    if not shortened:
        shortened = value[:max_length].strip()

    return shortened.rstrip(
        ".,;:-"
    ) + "..."


def clean_url(value: str) -> str:
    """
    Add HTTPS to URLs where the spreadsheet does not contain
    a protocol.
    """

    value = str(value or "").strip()

    if not value:
        return ""

    if re.match(
        r"^[a-zA-Z][a-zA-Z0-9+.-]*://",
        value
    ):
        return value

    return "https://" + value


def clean_phone_for_link(
    value: str
) -> str:
    """
    Make a telephone value suitable for a tel: link.
    """

    value = str(value or "").strip()

    if not value:
        return ""

    if value.startswith("+"):
        return "+" + re.sub(
            r"\D",
            "",
            value
        )

    return re.sub(
        r"\D",
        "",
        value
    )


# ============================================================
# BUSINESS FIELD HELPERS
# ============================================================

def business_id(
    business: dict
) -> str:

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


def business_name(
    business: dict
) -> str:

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


def category(
    business: dict
) -> str:

    return get_val(
        business,
        [
            "Category",
            "Category Name",
            "Service Category",
            "Type",
        ],
        "Animal Service",
    )


def subcategory(
    business: dict
) -> str:

    return get_val(
        business,
        [
            "Subcategory",
            "Sub Category",
            "Sub-Category",
            "Service Type",
        ],
    )


def location(
    business: dict
) -> str:

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


def website(
    business: dict
) -> str:

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

    return clean_url(value)


def phone(
    business: dict
) -> str:

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


def email_address(
    business: dict
) -> str:

    return get_val(
        business,
        [
            "Email",
            "Email Address",
            "Contact Email",
        ],
    )


def address(
    business: dict
) -> str:

    return get_val(
        business,
        [
            "Address",
            "Full Address",
            "Postal Address",
        ],
    )


def postcode(
    business: dict
) -> str:

    return get_val(
        business,
        [
            "Postcode",
            "Postal Code",
            "Post Code",
        ],
    )


def description(
    business: dict
) -> str:

    return get_val(
        business,
        [
            "Description",
            "About",
            "Business Description",
            "Listing Description",
            "Details",
        ],
    )


def services(
    business: dict
) -> str:

    return get_val(
        business,
        [
            "Services",
            "Services Offered",
            "Services Provided",
            "What We Do",
        ],
    )


def facebook(
    business: dict
) -> str:

    return clean_url(
        get_val(
            business,
            [
                "Facebook",
                "Facebook URL",
                "Facebook Page",
            ],
        )
    )


def instagram(
    business: dict
) -> str:

    return clean_url(
        get_val(
            business,
            [
                "Instagram",
                "Instagram URL",
            ],
        )
    )


def twitter(
    business: dict
) -> str:

    return clean_url(
        get_val(
            business,
            [
                "Twitter",
                "Twitter URL",
                "X",
                "X URL",
            ],
        )
    )


def linkedin(
    business: dict
) -> str:

    return clean_url(
        get_val(
            business,
            [
                "LinkedIn",
                "LinkedIn URL",
            ],
        )
    )


def tiktok(
    business: dict
) -> str:

    return clean_url(
        get_val(
            business,
            [
                "TikTok",
                "TikTok URL",
            ],
        )
    )


def youtube(
    business: dict
) -> str:

    return clean_url(
        get_val(
            business,
            [
                "YouTube",
                "YouTube URL",
            ],
        )
    )


def updated_date(
    business: dict
) -> str:

    return get_val(
        business,
        [
            "Last Updated",
            "Updated",
            "Updated Date",
            "Modified",
            "Modified Date",
        ],
    )


# ============================================================
# BUSINESS IMAGE
# ============================================================

def business_image(
    business: dict
) -> str:
    """
    If a business image exists in:

        images/businesses/SAIS-XXXX.jpg

    it will automatically be used.

    Otherwise the page simply uses the SAIS directory banner
    for social sharing.
    """

    bid = business_id(
        business
    )

    if not bid:
        return ""

    possible_files = [
        BUSINESS_IMAGE_DIR / f"{bid}.jpg",
        BUSINESS_IMAGE_DIR / f"{bid}.jpeg",
        BUSINESS_IMAGE_DIR / f"{bid}.png",
        BUSINESS_IMAGE_DIR / f"{bid}.webp",
    ]

    for file_path in possible_files:

        if file_path.exists():

            return (
                f"{SITE_URL}/images/businesses/"
                f"{file_path.name}"
            )

    return ""


# ============================================================
# SLUG / URL HELPERS
# ============================================================

def slugify(
    value: str
) -> str:

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


def business_slug(
    business: dict
) -> str:

    bid = slugify(
        business_id(business)
    )

    name = slugify(
        business_name(business)
    )

    if bid and name:
        return f"{bid}-{name}"

    if bid:
        return bid

    return name


# ============================================================
# SEO
# ============================================================

def create_page_title(
    business: dict
) -> str:

    name = business_name(
        business
    )

    cat = category(
        business
    )

    loc = location(
        business
    )

    parts = [name]

    if (
        cat
        and cat.lower() not in name.lower()
    ):
        parts.append(cat)

    if (
        loc
        and loc.lower() not in name.lower()
    ):
        parts.append(loc)

    parts.append("SAIS")

    return " | ".join(parts)


def create_meta_description(
    business: dict
) -> str:

    name = business_name(
        business
    )

    cat = category(
        business
    )

    loc = location(
        business
    )

    desc = description(
        business
    )

    service_text = services(
        business
    )

    pieces = []

    if desc:
        pieces.append(desc)

    if service_text and service_text.lower() != desc.lower():
        pieces.append(
            service_text
        )

    if pieces:

        text = (
            f"{name} in {loc}, Somerset. "
            f"{' '.join(pieces)}"
        )

    else:

        text = (
            f"{name} is listed in the "
            f"Somerset Animal Business Directory "
            f"as a {cat.lower()} in {loc}, Somerset."
        )

    return truncate_text(
        text,
        155
    )


def create_social_description(
    business: dict
) -> str:

    name = business_name(
        business
    )

    cat = category(
        business
    )

    loc = location(
        business
    )

    desc = description(
        business
    )

    if desc:

        text = (
            f"{name} — {cat} in {loc}, Somerset. "
            f"{desc}"
        )

    else:

        text = (
            f"{name} — {cat} in {loc}, Somerset. "
            f"Listed in the Somerset Animal "
            f"Business Directory."
        )

    return truncate_text(
        text,
        250
    )


# ============================================================
# STRUCTURED DATA
# ============================================================

def create_local_business_jsonld(
    business: dict,
    page_url: str
) -> str:

    name = business_name(
        business
    )

    cat = category(
        business
    )

    loc = location(
        business
    )

    desc = description(
        business
    )

    site = website(
        business
    )

    tel = phone(
        business
    )

    email = email_address(
        business
    )

    addr = address(
        business
    )

    postcode_value = postcode(
        business
    )

    image = business_image(
        business
    )

    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": name,
        "url": page_url,
    }

    if desc:
        data["description"] = desc

    if cat:
        data["category"] = cat

    if tel:
        data["telephone"] = tel

    if email:
        data["email"] = email

    if image:
        data["image"] = image

    # --------------------------------------------------------
    # ADDRESS
    # --------------------------------------------------------

    postal_address = {
        "@type": "PostalAddress",
        "addressRegion": "Somerset",
        "addressCountry": "GB",
    }

    if addr:
        postal_address[
            "streetAddress"
        ] = addr

    if loc:
        postal_address[
            "addressLocality"
        ] = loc

    if postcode_value:
        postal_address[
            "postalCode"
        ] = postcode_value

    data["address"] = postal_address

    # --------------------------------------------------------
    # AREA SERVED
    # --------------------------------------------------------

    if loc:

        data["areaServed"] = {
            "@type": "Place",
            "name": loc,
        }

    else:

        data["areaServed"] = {
            "@type": "AdministrativeArea",
            "name": "Somerset",
        }

    # --------------------------------------------------------
    # SOCIAL / IDENTITY LINKS
    # --------------------------------------------------------

    social_links = []

    for social_url in [
        facebook(business),
        instagram(business),
        twitter(business),
        linkedin(business),
        tiktok(business),
        youtube(business),
    ]:

        if social_url:
            social_links.append(
                social_url
            )

    if social_links:
        data["sameAs"] = social_links

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    ).replace(
        "</",
        "<\\/"
    )


def create_breadcrumb_jsonld(
    business: dict,
    page_url: str
) -> str:

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
                "name": business_name(
                    business
                ),
                "item": page_url,
            },
        ],
    }

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    ).replace(
        "</",
        "<\\/"
    )


# ============================================================
# FETCH LIVE DIRECTORY
# ============================================================

def fetch_businesses() -> list[dict]:

    print(
        "Fetching SAIS business data..."
    )

    print(
        API_URL
    )

    request = Request(
        API_URL,
        headers={
            "User-Agent":
                "SAIS-Business-Page-Generator/3.0",
            "Accept":
                "application/json,text/plain,*/*",
        },
    )

    try:

        with urlopen(
            request,
            timeout=60
        ) as response:

            raw = response.read().decode(
                "utf-8-sig"
            )

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

        data = json.loads(
            raw
        )

    except json.JSONDecodeError as exc:

        preview = raw[:500].replace(
            "\n",
            " "
        )

        raise RuntimeError(
            "The Apps Script endpoint did not return valid JSON. "
            f"Response started with: {preview!r}"
        ) from exc

    if isinstance(
        data,
        list
    ):

        businesses = data

    elif isinstance(
        data,
        dict
    ):

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
        if isinstance(
            business,
            dict
        )
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

    name = business_name(
        business
    )

    cat = category(
        business
    )

    subcat = subcategory(
        business
    )

    loc = location(
        business
    )

    desc = description(
        business
    )

    service_text = services(
        business
    )

    site = website(
        business
    )

    tel = phone(
        business
    )

    tel_link = clean_phone_for_link(
        tel
    )

    email = email_address(
        business
    )

    addr = address(
        business
    )

    postcode_value = postcode(
        business
    )

    bid = business_id(
        business
    )

    image = business_image(
        business
    )

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

    local_business_schema = (
        create_local_business_jsonld(
            business,
            page_url
        )
    )

    breadcrumb_schema = (
        create_breadcrumb_jsonld(
            business,
            page_url
        )
    )

    # --------------------------------------------------------
    # SOCIAL IMAGE
    # --------------------------------------------------------

    social_image = (
        image
        if image
        else f"{SITE_URL}/directorybanner.png"
    )

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    if desc:

        description_html = esc(
            desc
        )

    else:

        description_html = (
            f"{esc(name)} is listed in the "
            f"Somerset Animal Business Directory."
        )

    # --------------------------------------------------------
    # SERVICES
    # --------------------------------------------------------

    services_html = ""

    if service_text:

        services_html = f"""
        <section class="extra-section">
          <h2>Services</h2>
          <p>{esc(service_text)}</p>
        </section>
        """

    # --------------------------------------------------------
    # CONTACT BUTTONS
    # --------------------------------------------------------

    contact_buttons = []

    if site:

        contact_buttons.append(
            f"""
            <a
              class="button"
              href="{esc(site)}"
              target="_blank"
              rel="noopener noreferrer"
            >
              Visit Website
            </a>
            """
        )

    if tel and tel_link:

        contact_buttons.append(
            f"""
            <a
              class="button secondary"
              href="tel:{esc(tel_link)}"
            >
              Call {esc(tel)}
            </a>
            """
        )

    if email:

        contact_buttons.append(
            f"""
            <a
              class="button secondary"
              href="mailto:{esc(email)}"
            >
              Email
            </a>
            """
        )

    # --------------------------------------------------------
    # DETAILS
    # --------------------------------------------------------

    details = []

    if addr:

        address_display = esc(
            addr
        )

        if postcode_value:

            address_display += (
                f"<br>{esc(postcode_value)}"
            )

        details.append(
            f"""
            <div class="detail">
              <strong>Address</strong>
              <span>{address_display}</span>
            </div>
            """
        )

    if tel:

        phone_target = (
            esc(tel_link)
            if tel_link
            else esc(tel)
        )

        details.append(
            f"""
            <div class="detail">
              <strong>Telephone</strong>
              <a href="tel:{phone_target}">
                {esc(tel)}
              </a>
            </div>
            """
        )

    if email:

        details.append(
            f"""
            <div class="detail">
              <strong>Email</strong>
              <a href="mailto:{esc(email)}">
                {esc(email)}
              </a>
            </div>
            """
        )

    if site:

        details.append(
            f"""
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
            """
        )

    if bid:

        details.append(
            f"""
            <div class="detail">
              <strong>SAIS Business ID</strong>
              <span>{esc(bid)}</span>
            </div>
            """
        )

    if subcat:

        details.append(
            f"""
            <div class="detail">
              <strong>Service Type</strong>
              <span>{esc(subcat)}</span>
            </div>
            """
        )

    # --------------------------------------------------------
    # SOCIAL LINKS
    # --------------------------------------------------------

    social_links = []

    social_items = [
        ("Facebook", facebook(business)),
        ("Instagram", instagram(business)),
        ("TikTok", tiktok(business)),
        ("YouTube", youtube(business)),
        ("LinkedIn", linkedin(business)),
        ("X", twitter(business)),
    ]

    for label, url in social_items:

        if not url:
            continue

        social_links.append(
            f"""
            <a
              class="social-link"
              href="{esc(url)}"
              target="_blank"
              rel="noopener noreferrer"
            >
              {esc(label)}
            </a>
            """
        )

    social_html = ""

    if social_links:

        social_html = f"""
        <section class="social-section">
          <h2>Find {esc(name)} online</h2>
          <div class="social-links">
            {''.join(social_links)}
          </div>
        </section>
        """

    # --------------------------------------------------------
    # BUSINESS IMAGE
    # --------------------------------------------------------

    image_html = ""

    if image:

        image_html = f"""
        <div class="business-image-wrap">
          <img
            class="business-image"
            src="{esc(image)}"
            alt="{esc(name)}"
            loading="eager"
          >
        </div>
        """

    # --------------------------------------------------------
    # GENERATED PAGE
    # --------------------------------------------------------

    return f"""<!doctype html>
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

  <meta
    name="theme-color"
    content="#c82333"
  >

  <!-- SAIS favicon -->

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
    content="website"
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
    content="{esc(social_image)}"
  >

  <meta
    property="og:image:alt"
    content="{esc(name)}"
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
    content="{esc(social_image)}"
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

    .business-image-wrap {{
      margin: -5px -5px 28px;
    }}

    .business-image {{
      display: block;
      width: 100%;
      max-height: 360px;
      object-fit: cover;
      border-radius: 14px;
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

    h2 {{
      color: var(--navy);
      font-size: 1.05rem;
      margin: 0 0 9px;
    }}

    .description {{
      font-size: 1.04rem;
      white-space: pre-line;
      color: var(--text);
    }}

    .extra-section,
    .social-section {{
      margin-top: 30px;
      padding-top: 25px;
      border-top: 1px solid var(--border);
    }}

    .extra-section p {{
      margin: 0;
      white-space: pre-line;
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

    .social-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 9px;
    }}

    .social-link {{
      display: inline-block;
      color: var(--blue);
      border: 1px solid var(--border);
      background: #ffffff;
      padding: 8px 13px;
      border-radius: 8px;
      text-decoration: none;
      font-weight: 700;
    }}

    .social-link:hover {{
      border-color: var(--blue);
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

    {image_html}

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

      <h2 id="about-business">
        About {esc(name)}
      </h2>

      <div class="description">
        {description_html}
      </div>

    </section>

    {services_html}

    <div class="details">

      {''.join(details)}

    </div>

    {social_html}

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
"""


# ============================================================
# SITEMAP
# ============================================================

def create_sitemap(
    urls: list[tuple[str, str | None]]
) -> str:

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for url, lastmod in urls:

        lines.append(
            "  <url>"
        )

        lines.append(
            f"    <loc>{esc(url)}</loc>"
        )

        if lastmod:

            lines.append(
                f"    <lastmod>{esc(lastmod)}</lastmod>"
            )

        lines.append(
            "  </url>"
        )

    lines.append(
        "</urlset>"
    )

    return "\n".join(
        lines
    ) + "\n"


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

        sitemap_urls: list[
            tuple[str, str | None]
        ] = [
            (
                f"{SITE_URL}/",
                None
            )
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
                temp_business_dir /
                slug
            )

            out_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            output_file = (
                out_dir /
                "index.html"
            )

            output_file.write_text(
                page_html(
                    business,
                    slug
                ),
                encoding="utf-8"
            )

            page_url = (
                f"{SITE_URL}/business/{slug}/"
            )

            # Only use a Last Updated date in the sitemap
            # if the spreadsheet actually provides one.
            lastmod = updated_date(
                business
            )

            if lastmod:

                # Keep only a normal ISO-style date where possible.
                match = re.search(
                    r"\d{4}-\d{2}-\d{2}",
                    lastmod
                )

                if match:
                    lastmod = match.group(0)
                else:
                    lastmod = None

            else:

                lastmod = None

            sitemap_urls.append(
                (
                    page_url,
                    lastmod
                )
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
        # Replace generated business pages
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
            f"Business pages generated: "
            f"{generated_count}"
        )

        print(
            f"Businesses skipped: "
            f"{skipped_count}"
        )

        print(
            f"Sitemap URLs: "
            f"{len(sitemap_urls)}"
        )

        print(
            f"Sitemap: "
            f"{SITEMAP_FILE}"
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
