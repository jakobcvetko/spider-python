# Bolha.com private API — reverse-engineered reference

A full HTTP-only walkthrough of the bolha.com / Njuškalo "Trikoder" platform
APIs that power the official iOS and Android apps. No browser, no Chromium,
no captcha solving — just `curl` (or any HTTP client).

> Discovered by: sniffing the Bolha web SPA's network traffic, then
> cross-referencing with the decompiled Android APK
> (`net.trikoder.android.bolha`). Verified end-to-end against a real account.

## Contents

1. [Architecture overview](#1-architecture-overview)
2. [Authentication](#2-authentication)
3. [User info — `whoami`](#3-user-info--whoami)
4. [Listing your ads](#4-listing-your-ads)
5. [Reading a single ad](#5-reading-a-single-ad)
6. [Creating a new ad](#6-creating-a-new-ad)
7. [Uploading images](#7-uploading-images)
8. [Public read API — no user login, JSON, scrape-friendly](#8-public-read-api--no-user-login-json-scrape-friendly)
9. [Refresh / republish / delete](#9-refresh--republish--delete)
10. [Error shapes](#10-error-shapes)

---

## 1. Architecture overview

`www.bolha.com` exposes **two parallel API surfaces** on the same origin:

| Surface    | Auth                             | Used for                                   |
| ---------- | -------------------------------- | ------------------------------------------ |
| `/papi/*`  | Static "obfuscated" bearer token | Anonymous reads — search, taxonomy         |
| `/ccapi/*` | OAuth2 JWT (or anonymous JWT)    | Logged-in actions — ads, profile, messages |

The static `/papi/*` token is `2!nekoThtuAipaPakuN$1` — that's literally the
string `1$NukaPapiAuthToken!2` reversed, embedded in the SPA's JS bundle.
Useful for unauthenticated reads but irrelevant for the rest of this guide.

**JSON:API** (`application/vnd.api+json`) is the wire format for almost every
`/ccapi/*` endpoint — payloads always nest under `{"data": {...}}` with
`type`, `id`, `attributes`, optional `relationships` and `included`.

**OAuth client credentials** (extracted from `static.bolha.com/dist/*.js`):

```
client_id     = njuskalo_js_app
client_secret = 1412aa6f3a6194adefceb8e547d5e6aa
token_url     = https://www.bolha.com/oauth2/token
```

The audience claim (`aud`) on every minted JWT is `njuskalo_js_app` — the same
infrastructure powers Njuškalo (Croatia), Bolha (Slovenia), and a few others.

A user-scoped JWT lives **6 hours** (`expires_in: 21600`). The accompanying
refresh token is a long PHP-encrypted blob and is good for many months.

---

## 2. Authentication

### 2a. Anonymous JWT (client_credentials)

Useful only when an endpoint refuses the static `/papi/*` token. Most reads
work without this.

```bash
curl -sS -X POST 'https://www.bolha.com/oauth2/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode 'client_id=njuskalo_js_app' \
  --data-urlencode 'client_secret=1412aa6f3a6194adefceb8e547d5e6aa'
```

Response:

```json
{ "token_type": "Bearer", "expires_in": 21600, "access_token": "eyJ0eXAi…" }
```

### 2b. User login — three steps, no `grant_type=password`

> **Why not password grant?** Bolha advertises it but enforces a fresh 2FA
> on every call against `grant_type=password`, even when you just cleared
> 2FA on the web form. The OAuth endpoint also doesn't accept the code as
> a parameter, so a single password-grant call burns a 2FA email and gets
> rate-limited (`error: 102`) after a few attempts. The web SPA avoids
> this by riding on the cookie session via **PKCE** instead — and so do we.

The flow is:

1. **`POST /prijava/`** — submit credentials. Bolha sets `PHPSESSID` and
   either lands on `/` (no 2FA) or redirects to `/2fa-enter-code` (2FA).
2. **`POST /2fa_check`** — only when challenged. Submits the 6-digit code
   and ratifies the cookie session.
3. **PKCE exchange via `/oauth2/authorize` → `/oauth2/token`** — turns the
   cookie session into an OAuth JWT + refresh token without re-prompting
   for 2FA.

#### Step 1 — POST credentials to the legacy login form

Get the CSRF token:

```bash
curl -sSc /tmp/cookies.txt 'https://www.bolha.com/prijava/' -o /tmp/login.html
TOKEN=$(grep -oE 'name="login\[_token\]"\s+value="[^"]+"' /tmp/login.html \
        | sed -E 's/.*value="([^"]+)".*/\1/')
```

POST credentials:

```bash
curl -sSb /tmp/cookies.txt -c /tmp/cookies.txt \
  'https://www.bolha.com/prijava/?returnUrl=/' \
  -d "login%5Busername%5D=$USER" \
  -d "login%5Bpassword%5D=$PASS" \
  -d 'login%5Bremember_me%5D=1' \
  -d "login%5B_token%5D=$TOKEN" \
  -L -o /tmp/login_resp.html -w '%{url_effective}\n'
```

Three possible outcomes:

- Lands on `/` — no 2FA needed, the cookie jar now holds the session.
- Lands on `/2fa-enter-code?…` — Bolha emailed a 6-digit code. Continue to step 2.
- Lands back on `/prijava/` with an error banner — bad credentials.

#### Step 2 — Submit the 2FA code

The code arrives at the registered email (in our case via AgentMail) from
`no-reply-varnost@bolha.com`, subject *"Dodatno preverjanje prijave"* (SI) or
*"Dodatna provjera prijave"* (HR). Extract the 6-digit code, then:

```bash
curl -sSb /tmp/cookies.txt -c /tmp/cookies.txt \
  'https://www.bolha.com/2fa_check' \
  -d "authCode=$CODE" \
  -d 'trustedDevice=true' \
  -L -o /dev/null -w '%{url_effective}\n'
```

Lands on `/` if accepted. The session cookie (`PHPSESSID`) and a fresh
`login_2fa` token are now in the jar.

> **Rate limit:** Bolha rate-limits 2FA emails to ~30 minutes. If you trigger
> too many, you'll get `error: 102 — Limit reached`. Don't retry a failed
> login in tight loops.

#### Step 3 — PKCE exchange the cookie session for a JWT

Generate a PKCE verifier + challenge, hit `/oauth2/authorize` with the
authenticated cookie jar, and the redirect URL contains the auth code:

```bash
# RFC 7636 PKCE pair
VERIFIER=$(openssl rand -base64 64 | tr -d '=+/' | cut -c1-86)
CHALLENGE=$(printf '%s' "$VERIFIER" | openssl dgst -sha256 -binary \
            | openssl base64 | tr -d '=' | tr '/+' '_-')

# 3a — let Bolha redirect us back with ?code=...
RESP_URL=$(curl -sS -b /tmp/cookies.txt -L -o /dev/null \
  -w '%{url_effective}' \
  "https://www.bolha.com/oauth2/authorize?client_id=njuskalo_js_app&client_secret=1412aa6f3a6194adefceb8e547d5e6aa&response_type=code&code_challenge=$CHALLENGE&code_challenge_method=S256&redirect_uri=https%3A%2F%2Fwww.bolha.com")
CODE=$(printf '%s' "$RESP_URL" | sed -n 's/.*[?&]code=\([^&]*\).*/\1/p')

# 3b — exchange code + verifier for the JWT
curl -sS -X POST 'https://www.bolha.com/oauth2/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'client_id=njuskalo_js_app' \
  --data-urlencode 'client_secret=1412aa6f3a6194adefceb8e547d5e6aa' \
  --data-urlencode 'grant_type=authorization_code' \
  --data-urlencode 'redirect_uri=https://www.bolha.com' \
  --data-urlencode "code_verifier=$VERIFIER" \
  --data-urlencode "code=$CODE"
```

Response:

```json
{
  "token_type":    "Bearer",
  "expires_in":    21600,
  "access_token":  "eyJ0eXAi…",
  "refresh_token": "def50200…"
}
```

Stash both. The access token is your `Authorization: Bearer …` for the rest
of this document. The refresh token is what you use 6 hours from now.

### 2c. Refresh the access token

```bash
curl -sS -X POST 'https://www.bolha.com/oauth2/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=refresh_token' \
  --data-urlencode 'client_id=njuskalo_js_app' \
  --data-urlencode 'client_secret=1412aa6f3a6194adefceb8e547d5e6aa' \
  --data-urlencode "refresh_token=$REFRESH_TOKEN"
```

Response is the same shape as a fresh login. The **refresh token is rotated**
on each call — always save the new one.

### 2d. Headers used on every authenticated request

```http
Authorization: Bearer <jwt>
Accept:        application/vnd.api+json
User-Agent:    Bolha/6.34.1 (iPhone; iOS 17.5; Scale/3.00)
```

The `User-Agent` does **not** strictly have to look like the iOS app, but
sending a desktop Chrome UA occasionally gets you intercepted by Avalon Insights
on edge cases. Use the iOS string for safety.

---

## 3. User info — whoami

```bash
curl -sS -H "Authorization: Bearer $TOK" \
  'https://www.bolha.com/ccapi/v3/users/me'
```

Returns full profile (JSON:API):

```json
{
  "data": {
    "type": "user",
    "id": "2257945",
    "attributes": {
      "username": "hermesa",
      "userType": "private-seller",
      "email": "…",
      "firstName": "…",
      "lastName": "…",
      "messagingUserId": "12345678",
      "scopes": ["…"],
      "isOnlinePaymentEnabled": true
    }
  }
}
```

Useful sibling endpoints (all `GET`):

| Path                                             | What                               |
| ------------------------------------------------ | ---------------------------------- |
| `/ccapi/v2/users/me`                             | Same shape, older fields           |
| `/ccapi/v3/feature-flag?page[limit]=1000`        | Feature flags applied to this user |
| `/ccapi/v3/user-personal-data-validation-status` | KYC / identity validation state    |
| `/ccapi/v4/billing/user-balance-overview`        | User balance (paid promotions)     |

---

## 4. Listing your ads

```bash
curl -sS -H "Authorization: Bearer $TOK" \
  -H 'Accept: application/vnd.api+json' \
  'https://www.bolha.com/ccapi/v3/my-ads?page[limit]=50&page[offset]=0'
```

Returns each ad with status, view count, expiry, and a thumbnail URL:

```json
{
  "data": [
    {
      "type": "myAd",
      "id": "15962620",
      "attributes": {
        "title": "Test medvedek (API)",
        "url": "https://www.bolha.com/darila-za-otroke/test-medvedek-api-oglas-15962620",
        "categoryId": 27836,
        "createdTime": "2026-05-23T23:23:39+02:00",
        "expiryTime":  "2026-06-22T23:39:03+02:00",
        "active": true,
        "inactive": false,
        "expired": false,
        "imageId": 60873951,
        "imageUrl": "https://www.bolha.com/image-140x140/…",
        "viewCount": 0,
        "messageCount": 0
      }
    }
  ],
  "meta": { "totalCount": 1 }
}
```

Filter by status with `filter[status]=active|inactive|expired`. The page
size cap is 100; iterate with `page[offset]`.

---

## 5. Reading a single ad

There are two complementary GETs depending on what you need:

| Path                         | Returns                                                                                                                  |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `/ccapi/v3/classifieds/{id}` | Public-facing detail (price, description, photos)                                                                        |
| `/ccapi/v3/ad-form/{id}`     | The **canonical edit form** — every field, with the choice metadata. Use this when you plan to edit or duplicate the ad. |

`ad-form/{id}` is what unlocks ad-posting (next section). Sample response is
in [`.tmp/ad_form_15962618.json`](../.tmp/ad_form_15962618.json) — keep one
on disk as a template.

---

## 6. Creating a new ad

This is the iOS app's actual code path. Pure HTTP, single round-trip.

```http
POST /ccapi/v3/ad-form HTTP/1.1
Host: www.bolha.com
Authorization: Bearer <jwt>
Accept: application/vnd.api+json
Content-Type: application/vnd.api+json
```

### 6a. Payload structure

The schema is the gotcha — `categoryId` lives at the **top of `attributes`**
(not inside `formElements`), and every "choice"-typed field is wrapped in a
`{id, type, attributes: {selected}}` object. Location data is grouped under
a single `LocalitySelector` object. `price` is its own object.

```json
{
  "data": {
    "type": "ad-form",
    "attributes": {
      "categoryId": "27836",
      "formElements": {
        "title":       "Medvedek",
        "description": "Mali medvedek za otroke do 2 lete starosti, bele barve",
        "price":       { "amount": 20, "priceOnRequest": false },
        "images":      ["60873951"],
        "conditionId":       { "id": "10",          "type": "choice", "attributes": { "selected": true } },
        "userIndividual":    { "id": "Posameznik",  "type": "choice", "attributes": { "selected": true } },
        "typeOfTransaction": { "id": "Prodam",      "type": "choice", "attributes": { "selected": true } },
        "priceOnRequest":    { "id": "priceOnRequest", "type": "choice", "attributes": { "selected": false } },
        "buyOption":         { "id": "buyOption",   "type": "choice", "attributes": { "selected": false } },
        "LocalitySelector": {
          "lat":  46.05807002571576,
          "long": 14.508557798025935,
          "isApproximateLocationOnMap": 1,
          "level0": { "id": "26320", "type": "choice", "attributes": { "selected": true } },
          "level1": { "id": "44267", "type": "choice", "attributes": { "selected": true } },
          "level2": { "id": "27090", "type": "choice", "attributes": { "selected": true } }
        },
        "phoneNumberControl": [],
        "youtubeUrl":         ""
      }
    }
  }
}
```

### 6b. Field reference

| Field                             | Type     | Notes                                                                                                                                   |
| --------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `categoryId`                      | string   | Leaf category ID. Get it from `/ccapi/v4/page-category-hierarchy` or by browsing one of your existing ads via `/ccapi/v3/ad-form/{id}`. |
| `formElements.title`              | string   | Listing title. Length cap depends on category (≈80 chars typical).                                                                      |
| `formElements.description`        | string   | Body text. Multi-line ok. Plain text (HTML stripped server-side).                                                                       |
| `formElements.price`              | object   | `{ "amount": <int>, "priceOnRequest": <bool> }`. EUR.                                                                                   |
| `formElements.images`             | string[] | Media IDs from `/ccapi/v3/media/main-gallery` (next section). Order = display order.                                                    |
| `formElements.conditionId`        | choice   | Common values: `10` (new), `20` (used). Per-category — fetch from `ad-form` of an existing ad.                                          |
| `formElements.typeOfTransaction`  | choice   | `Prodam` (selling), `Kupim` (buying), `Menjam` (trading)…                                                                               |
| `formElements.userIndividual`     | choice   | `Posameznik` (private), `Podjetje` (business).                                                                                          |
| `formElements.LocalitySelector`   | object   | See below.                                                                                                                              |
| `formElements.youtubeUrl`         | string   | Optional, empty string if none.                                                                                                         |
| `formElements.phoneNumberControl` | array    | Phone visibility config; empty list = hidden.                                                                                           |

`LocalitySelector` levels (`level0` / `level1` / `level2`) are the Slovenian
admin hierarchy: country → region → municipality. `lat`/`long` are decimal
degrees. `isApproximateLocationOnMap: 1` shows a 250 m blur radius;
`0` shows the exact pin.

### 6c. Successful response

```json
{
  "data": {
    "type": "ad",
    "id": "15962620",
    "attributes": {
      "title": "Medvedek",
      "url": "https://www.bolha.com/darila-za-otroke/medvedek-oglas-15962620",
      "active": false,
      "moderationStatus": "pending"
    }
  }
}
```

The new ad is **immediately visible to the owner**, but goes through human
moderation before appearing in public search (typically a few minutes).

### 6d. Editing an existing ad

```http
PATCH /ccapi/v3/ad-form/{adId}
```

…with the same payload shape, plus `"id": "<adId>"` on the `data` object.
The cleanest pattern is:

1. `GET /ccapi/v3/ad-form/{adId}` → mutate the JSON in memory.
2. `PATCH /ccapi/v3/ad-form/{adId}` with the mutated JSON.

This is also how you attach images to an existing ad (see next section).

---

## 7. Uploading images

The Android app (`com.undabot.android.adio.service.JSONResourceApi`) uses a
single `media/{mediaGroup}` endpoint, which on the wire resolves to:

```http
POST /ccapi/v3/media/main-gallery HTTP/1.1
Host: www.bolha.com
Authorization: Bearer <jwt>
Content-Type: multipart/form-data; boundary=…
```

Multipart body has exactly **one** part:

```
Content-Disposition: form-data; name="file"; filename="IMG_9884.jpg"
Content-Type: image/jpeg

<file bytes>
```

`curl` shorthand:

```bash
curl -sS -H "Authorization: Bearer $TOK" \
  -F "file=@IMG_9884.jpg;type=image/jpeg" \
  'https://www.bolha.com/ccapi/v3/media/main-gallery'
```

Response (truncated):

```json
{
  "data": {
    "type": "media",
    "id": "60873951",
    "attributes": {
      "size": 461894,
      "mimeType": "image/jpeg",
      "uploadTime": "2026-05-23T23:38:23+02:00"
    },
    "links": {
      "100x100": { "href": "https://www.bolha.com/scripts/get_image_variation.php?image_id=…", "meta": {"width":100,"height":100} },
      "w130":    { "href": "…", "meta": {…} },
      "640x480": { "href": "…", "meta": {…} }
    }
  }
}
```

The returned `id` is what you put in `formElements.images` when posting or
patching the ad.

Three media groups exist (from `Sa.r` enum in the APK):

| `mediaGroup`          | Use                                     |
| --------------------- | --------------------------------------- |
| `main-gallery`        | Standard ad photos (everyone uses this) |
| `ground-plan-gallery` | Real-estate floor plans                 |
| `360-view-gallery`    | 360° tour images                        |

### 7a. Attach to an existing ad

```bash
# 1. Upload
MEDIA_ID=$(curl -sS -H "Authorization: Bearer $TOK" \
  -F "file=@photo.jpg;type=image/jpeg" \
  'https://www.bolha.com/ccapi/v3/media/main-gallery' \
  | jq -r .data.id)

# 2. Pull the ad's current form, inject the new media id, PATCH it back
curl -sS -H "Authorization: Bearer $TOK" \
  -H 'Accept: application/vnd.api+json' \
  "https://www.bolha.com/ccapi/v3/ad-form/$AD_ID" -o /tmp/form.json

jq --arg id "$MEDIA_ID" \
   '.data.attributes.formElements.images |= (. + [$id])' \
   /tmp/form.json > /tmp/form_patched.json

curl -sS -H "Authorization: Bearer $TOK" \
  -H 'Accept: application/vnd.api+json' \
  -H 'Content-Type: application/vnd.api+json' \
  -X PATCH --data-binary @/tmp/form_patched.json \
  "https://www.bolha.com/ccapi/v3/ad-form/$AD_ID"
```

A successful PATCH returns:

```json
{ "data": { "type": "adFormAction", "id": "…", "attributes": { "style": "partialSuccess", … } } }
```

`style: "partialSuccess"` is normal — it means the change stuck but the ad is
re-entering moderation. `success` means accepted with no extra review.

---

## 8. Public read API — no user login, JSON, scrape-friendly

Bolha exposes a sizeable read surface that needs **no user account**. The only
auth is the anonymous `client_credentials` JWT from §2a, which lasts 6 hours.
Once you have it, the endpoints below return clean JSON:API and are **not
behind Avalon Insights / Radware** — only the JWT mint itself is, and that
clears with normal browser-style headers.

### 8a. Avalon caveat (only matters at `/oauth2/token`)

The `/ccapi/*` data endpoints accept the JWT directly with no fingerprint
checks. Avalon Insights is on `/oauth2/token` and `/papi/*` — if you mint a
token from a script with a non-Chrome **TLS fingerprint** (this includes
plain `requests` / `httpx` / `urllib`!), it gets bounced (HTTP 302 →
`validate.perfdrive.com`). What matters is not just headers — Avalon
fingerprints the TLS ClientHello (JA3). Headers + Chrome-like TLS = clean.

**Two clients that work out of the box:**

1. **`/usr/bin/curl`** with normal Chrome headers (curl's TLS fingerprint
   passes Avalon's gate as of 2026-05).
2. **`curl_cffi`** in Python — wraps libcurl with real Chrome TLS
   impersonation. Drop-in replacement for `requests`.

After the mint, any plain HTTP client works for the data calls (no Avalon
on `/ccapi/*`). Mint once every ≤ 6 hours; reuse the JWT for thousands of
reads.

```bash
# curl (shell): works
ANON=$(curl -sS -X POST 'https://www.bolha.com/oauth2/token' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'origin: https://www.bolha.com' \
  -H 'referer: https://www.bolha.com/' \
  -H 'sec-ch-ua: "Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -H 'sec-fetch-site: same-origin' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-dest: empty' \
  -H 'content-type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode 'client_id=njuskalo_js_app' \
  --data-urlencode 'client_secret=1412aa6f3a6194adefceb8e547d5e6aa' \
  | jq -r .access_token)
```

### 8b. Endpoint catalog

| Path                                                                    | What                                                                                                                                                     |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/ccapi/v3/latest-classifieds?include=image&page[limit]=N`              | **Realtime fire-hose** of newest ads, *all* categories. Returns id + title + price + adUrl + image. Slice by category with `filter[mainCategoryId]=N`.   |
| `/ccapi/v4/ad-search?filter[search]=…&sort=-createdTime&include=images` | Full-text search, sortable, with rich `attributes` (createdAt, location, price, condition, webUrl…). `filter[search]` is required and must be non-empty. |
| `/ccapi/v4/ad-search/category-aggregations`                             | Category facet counts for a query                                                                                                                        |
| `/ccapi/v4/ad-search/location-aggregations`                             | Location facet counts                                                                                                                                    |
| `/ccapi/v4/ad-search/price-ranges`                                      | Price histogram                                                                                                                                          |
| `/ccapi/v4/page-category-hierarchy`                                     | Full category tree (~6 MB JSON, cache it!)                                                                                                               |
| `/ccapi/v3/category/{categoryId}/auxiliary-category-items`              | Extra subcategories per category                                                                                                                         |
| `/ccapi/v4/title-pages/new-homepage`                                    | Curated homepage feed (categories + ads + banners)                                                                                                       |
| `/ccapi/v4/recommended-ads?page[limit]=N`                               | Anonymous "you may also like" recs                                                                                                                       |
| `/ccapi/v4/phone-numbers/ad/{adId}`                                     | Public phone number for an ad                                                                                                                            |
| `/ccapi/v4/similar-classifieds?adId={id}`                               | Similar-to-this-ad recs                                                                                                                                  |
| `/ccapi/v4/search-by-image`                                             | Reverse image search (multipart + JSON, see APK class `createSearchByImage`)                                                                             |

A full dump of 129 `/ccapi/*` paths discovered in the Android APK is at
[`.tmp/all_ccapi_paths.txt`](../.tmp/all_ccapi_paths.txt).

### 8c. There is **no unauthenticated `GET /ad/{id}`**

The natural-looking routes (`/ccapi/v3/classifieds/{id}`,
`/ccapi/v2/classifieds/{id}`, `/ccapi/v3/geo-classified-detail`) all 404 for
non-owners. To resolve a single ad's full detail without a user JWT you have
two options:

1. **Stay on the search/feed endpoints** — `/ccapi/v3/latest-classifieds`
   and `/ccapi/v4/ad-search` already return everything you need (title,
   price, location, condition, createdAt, webUrl, images via `include=`).
2. **Crawl the public ad URL HTML** — every ad has a stable
   `https://www.bolha.com/<category-slug>/<title-slug>-oglas-<id>` URL with
   embedded JSON-LD and a Vue/Nuxt hydration payload. This page **is** behind
   Avalon, so use a TLS-impersonating client (`curl_cffi`, `playwright`,
   `undici` with browser TLS) — but the page itself is unauthenticated.

### 8d. Realtime polling pattern

Pagination on `latest-classifieds` is largely cosmetic — `page[offset]`
beyond the first page returns the same fresh-now slice. The right pattern is
**poll the firehose, dedupe by `id`**:

```python
"""Verified working 2026-05 against live API. `pip install curl_cffi`."""
import time

from curl_cffi import requests as cc

OAUTH_TOKEN_URL = "https://www.bolha.com/oauth2/token"
LATEST_URL      = "https://www.bolha.com/ccapi/v3/latest-classifieds"
CLIENT_ID       = "njuskalo_js_app"
CLIENT_SECRET   = "1412aa6f3a6194adefceb8e547d5e6aa"


def mint_jwt() -> tuple[str, float]:
    r = cc.post(
        OAUTH_TOKEN_URL,
        data={
            "grant_type":    "client_credentials",
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={
            "origin":  "https://www.bolha.com",
            "referer": "https://www.bolha.com/",
        },
        impersonate="chrome124",
        timeout=20,
    )
    r.raise_for_status()
    body = r.json()
    return body["access_token"], time.time() + body["expires_in"] - 60


def stream_new_ads(poll_interval: float = 30.0):
    seen: set[str] = set()
    jwt, jwt_until = mint_jwt()
    while True:
        if time.time() >= jwt_until:
            jwt, jwt_until = mint_jwt()
        r = cc.get(
            LATEST_URL,
            params={"include": "image", "page[limit]": 60},
            headers={
                "authorization": f"Bearer {jwt}",
                "accept":        "application/vnd.api+json",
            },
            impersonate="chrome124",  # any TLS will do post-mint, but cheap insurance
            timeout=20,
        )
        r.raise_for_status()
        doc = r.json()
        images = {i["id"]: i["attributes"]["url"]
                  for i in doc.get("included", [])
                  if i["type"] == "latest-ad-image"}
        for ad in doc["data"]:
            aid = ad["id"]
            if aid in seen:
                continue
            seen.add(aid)
            attrs  = ad["attributes"]
            img_id = ad["relationships"]["image"]["data"]["id"]
            yield {
                "id":    aid,
                "title": attrs["title"],
                "price": attrs["price"],
                "url":   attrs["adUrl"],
                "image": images.get(img_id),
            }
        time.sleep(poll_interval)


# Usage:
#   for ad in stream_new_ads():
#       print(ad["id"], ad["title"], ad["price"], ad["url"])
```

`page[limit]=60` is the safe ceiling — the endpoint will silently cap higher
values. At 30 s polling intervals you catch every ad on a quiet day; on
peak weekend evenings (~5 ads/min sitewide) drop to 10 s.

For richer attributes (`createdAt`, `location`, `condition`, `description`),
swap `latest-classifieds` for
`/ccapi/v4/ad-search?filter[search]=<term>&sort=-createdTime&include=images,user,category`
and dedupe the same way.

### 8e. Rate limits & etiquette

- The data endpoints have no published per-IP limit, but stay below 5 req/s
  to avoid waking up Avalon. JWT mint hits ~1 req/6 hours per worker.
- The endpoints **omit** ads that are still in moderation (~2–10 min after
  posting). For a true firehose you should run two pollers — one against
  `latest-classifieds` (immediate) and one against `ad-search` 5 min later
  to backfill ads that took longer to clear moderation.
- Bolha includes a `Cache-Control: max-age=…` header — honouring it will
  cut your effective request count in half.

---

## 9. Refresh / republish / delete

Bolha lets free users "refresh" an ad once per cooldown window (~7 days) to
push it back to the top.

```bash
# Republish (also called "podaljšaj" in the UI)
curl -sS -X POST -H "Authorization: Bearer $TOK" \
  "https://www.bolha.com/ccapi/v2/classifieds/$AD_ID/renew"

# Delete
curl -sS -X DELETE -H "Authorization: Bearer $TOK" \
  "https://www.bolha.com/ccapi/v2/classifieds/$AD_ID"
```

The renew endpoint returns 200 with a `meta.cooldownUntil` field in the
JSON:API envelope. If you're inside the cooldown window it returns 409 with
`error.code = "cooldown"`.

---

## 10. Error shapes

Errors come back as a JSON:API `errors` array with stable codes:

```json
{
  "errors": [
    {
      "status": 422,
      "code":   "validation",
      "title":  "Invalid value",
      "detail": "Field 'price.amount' must be > 0",
      "source": { "pointer": "/data/attributes/formElements/price/amount" }
    }
  ]
}
```

The codes you'll hit most:

| HTTP | `code`             | Meaning                                                                                                               |
| ---- | ------------------ | --------------------------------------------------------------------------------------------------------------------- |
| 400  | `validation`       | Missing or malformed field. Inspect `source.pointer`.                                                                 |
| 401  | `unauthenticated`  | JWT missing or expired. Refresh and retry.                                                                            |
| 401  | (raw `error: 101`) | OAuth: 2FA challenge. Check email, run `/2fa_check`.                                                                  |
| 401  | (raw `error: 102`) | OAuth: rate-limited (30 min cooldown).                                                                                |
| 403  | `forbidden`        | Ad belongs to another user, or your account lacks scope.                                                              |
| 404  | `not_found`        | Ad / category / media id doesn't exist.                                                                               |
| 409  | `cooldown`         | Refresh cooldown still running.                                                                                       |
| 422  | `validation`       | Same as 400 but multi-error.                                                                                          |
| 500  | (no `code`)        | Almost always a malformed JSON:API payload — re-check structure against `/ccapi/v3/ad-form/{adId}` of an existing ad. |

**Quirky 500:** `"Argument #1 ($objectOrArray) must be of type object|array, int given"` — this is Symfony's `PropertyAccess` complaining that a field
which expects a `{ id, type, attributes }` object got a bare scalar.
Re-wrap the offending field as a choice object.

---

## Reference: complete request examples

A reproducible end-to-end transcript lives in
[`bolha-mcp/examples/`](../bolha-mcp/examples/) — each step as a standalone
shell script you can run against a real account.

## Provenance

- iOS app: `net.trikoder.iphone.bolha` v6.34.1, by *Styria digital marketplaces*.
- Android app: `net.trikoder.android.bolha` v6.32.0g (decompiled with `jadx`).
- Web SPA: `https://www.bolha.com/` (network capture via Playwright MCP).

The Android APK's Retrofit interface
(`com/undabot/android/adio/service/JSONResourceApi.java`) is the single best
source-of-truth for endpoint shapes — when in doubt, decompile a fresh APK
and grep for `@o(`, `@n(`, `@b(` (POST, PATCH, GET annotations after jadx
mangling).
