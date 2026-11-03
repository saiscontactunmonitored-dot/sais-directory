# SAIS Android pre-launch checklist

## Website and functionality
- [ ] Directory data loads reliably in a clean browser session and on Android.
- [ ] Search, filters, pagination, listing details and external links work.
- [ ] Contact SAIS link works.
- [ ] Website uses HTTPS throughout.
- [ ] Offline saved-information feature works after force-closing and reopening with airplane mode enabled.
- [ ] Service worker handles offline navigation and errors gracefully.

## TWA and signing
- [ ] Confirm application ID: `uk.co.sais.animaldirectory`.
- [ ] Generate release signing key and store securely; never commit it to GitHub.
- [ ] Add `/.well-known/assetlinks.json` on the directory domain.
- [ ] Verify its SHA-256 fingerprint matches the appropriate Play signing certificate.
- [ ] Build signed AAB and test on a physical Android device.

## Play Console
- [ ] Final store icon, feature graphic, screenshots and listing copy.
- [ ] Public, accurate privacy policy URL.
- [ ] Data safety form based on actual app/site behaviour.
- [ ] Content rating questionnaire completed.
- [ ] Target audience, ads declaration and app access details completed accurately.
- [ ] Check account-specific testing requirements.
- [ ] Submit for review and wait for approval before announcing public availability.

## Known blocker
A live inspection of the website showed “Directory could not be loaded.” Fix this before testing or publishing.
