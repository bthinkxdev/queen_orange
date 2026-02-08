# JavaScript Audit Summary – Queen Orange

## Step 1 – Inventory & Map

### External JS (static/js/)

| File | Purpose | Loaded on |
|------|---------|-----------|
| **main.js** | Cart qty form (AJAX), mobile menu, mobile search, scroll effects, animations, bestseller scroll buttons, quick add-to-cart, banner slider | All frontend (base.html) |
| **wishlist.js** | Wishlist toggle (AJAX), redirect guests to login | All frontend (base.html) |
| **product-card-slider.js** | Product card image slider (hover/touch) | All frontend (base.html) |
| **product-detail.js** | Size/color options, gallery, add-to-cart validation, image zoom modal | product.html only |
| **home-ajax-sections.js** | Load New Arrivals / Top Selling / Recently Viewed via AJAX | index.html only |
| **checkout.js** | Address selection, payment selection, address toggle | checkout.html |
| **address.js** | Phone/pincode input validation | checkout.html, address_form.html, profile.html |
| **otp-login.js** | OTP login: email validation, OTP digits, resend, change email | auth/otp_login.html |
| **product_list.js** | Admin product delete check + confirm, CSRF | admin product_list.html |
| **admin-mobile.js** | Admin filter sheet, report filter sheet | All admin (admin/base.html) |
| **admin-reports.js** | Report AJAX filter, sort, pagination, export links | admin report_orders, report_sales, report_products, report_customers |

### Removed (unused / dead)

- **data.js** – Static PRODUCTS/CATEGORIES; not loaded by any template. Removed.
- **search.js** – Navbar search using PRODUCTS; not loaded; depended on data.js. Removed.
- **cart.js** – localStorage cart helpers; not loaded; depended on data.js. Removed.

### Inline scripts

- **base.html** – Notification auto-hide (guard for missing elements).
- **admin/base.html** – Sidebar toggle, alert close, auto-dismiss (with null checks).
- **admin/dashboard.html** – Chart.js revenue chart (canvas and data guarded).
- **admin/reports/report_inventory.html** – ReportConfig + export URLs (form guard).
- **admin/reports/report_orders.html** (and products, sales, customers) – ReportConfig only.
- **product.html** – `window.sizeColorStock`, `useColorVariants`, etc. for product-detail.js.
- **auth/otp_login.html** – `window.AUTH_LOGIN_URL` for otp-login.js resend.

### Event handlers in HTML

- **index.html** – Bestseller scroll: switched from `onclick="scrollBestsellers(...)"` to `data-scroll-bestsellers="left|right"` (handled in main.js).
- **admin** – `onchange="this.form.submit()"` and `onsubmit="return confirm(...)"` left as-is (simple, no duplication).

---

## Step 2 – Duplication & Dead Code

- Removed **data.js**, **search.js**, **cart.js** (unused).
- Cart CSRF: single path via form input or cookie in main.js (getCsrfToken).
- Wishlist CSRF: fallback to cookie if no `[name=csrfmiddlewaretoken]`.
- Single DOMContentLoaded in main.js for UI inits + initBestsellersScrollButtons + initQuickAddToCart.
- Removed **console.log** in address.js; removed **console.error** in product_list.js (silent catch).

---

## Step 3 – Broken & Silent Failures

- **product-detail.js** – `updateColorOptions`: guard for missing `selectedSize`; use `selectedSizeEl.value`; guard `sizeColorStock`. Cart form: guard `selectedSize`/`selectedColor` and `sizeColorStock`.
- **admin/base.html** – Sidebar outside click: guard `sidebar` and `menuToggle`; alert close: guard `parentElement`.
- **admin/dashboard.html** – Revenue chart: guard canvas, parse, array; IIFE so no globals.
- **report_inventory.html** – Guard form before FormData; build params once.
- **otp-login.js** – Resend OTP URL from `window.AUTH_LOGIN_URL` (set in otp_login.html); no Django template tag inside static JS.

---

## Step 4 – Null & Edge Case Safety

- **main.js** – Cart form: getCsrfToken(form); guard input; no submit without CSRF.
- **wishlist.js** – getCSRFToken: form input or cookie.
- **product-detail.js** – All getElementById and optional objects guarded; `sizeColorStock` checked before use.
- **admin-reports.js** – Guard `tableWrap`, `tbody`, `data.html` before replaceChild.
- **base.html** – Notification script: only set timeout if `.notification` exists; guard in forEach.

---

## Step 5 – Event & Interval Management

- **main.js** – Banner slider: `bannerIntervalId` declared inside banner IIFE; cleared on `pagehide`.
- No duplicate listeners: cart qty and quick add use single DOMContentLoaded; wishlist uses one delegated body listener; product-card-slider binds once per container with `_cardSliderBound`.

---

## Step 6 – AJAX & API Consistency

- CSRF: main.js (cart, quick add) and wishlist.js use form token or cookie.
- otp-login.js uses `window.AUTH_LOGIN_URL` from template.
- admin-reports.js uses ReportConfig from each report template; fetch + JSON; loading state and error handling in place.

---

## Step 7 – Performance

- No `defer` added so as not to risk DOMContentLoaded already fired; scripts remain at end of body.
- Banner interval cleared on pagehide to avoid leaks.

---

## Step 8 – Admin vs Frontend Isolation

- **Frontend (base.html)** – main.js, wishlist.js, product-card-slider.js; block `extra_js` for page-specific (product-detail, home-ajax-sections, checkout, address, otp-login).
- **Admin (admin/base.html)** – Inline + admin-mobile.js; block `extra_js` for dashboard chart, reports (ReportConfig + admin-reports.js), product_list.js.
- No admin JS on storefront; no storefront JS in admin.

---

## Step 9 – Structure & Naming

- **main.js** – Cart IIFE, then UI IIFE (getCookie, initMobileMenu, initMobileSearch, initScrollEffects, initAnimations, initBestsellersScrollButtons, showNotification, updateCartBadge, initQuickAddToCart), then banner IIFE.
- **product-detail.js** – Config from window; updateColorOptions; renderSizeOptionsForColor; updateGallery; fetchColorImages; image viewer IIFE; DOMContentLoaded for thumbnails, color/size, cart form.
- **admin-reports.js** – Single IIFE; ReportConfig; form, tableWrap, tbody, pagination, summary; getFormParams, paramsToQuery, setLoading, updateSummary, updatePagination, fetchReport; event bindings.

---

## Step 10 – Verification Checklist

- [ ] **Desktop** – Home, product list, product detail, cart, checkout, wishlist, login/OTP: no console errors.
- [ ] **Mobile** – Same; mobile menu, mobile search, product card slider, admin filter sheets work.
- [ ] **Admin** – Dashboard chart, reports (orders/sales/products/customers) filter and export, product list delete check: no errors.
- [ ] **Edge cases** – Product page without color variants; report page without table; inventory report: no throws.

---

## Files Touched

- **static/js:** main.js, wishlist.js, product-detail.js, address.js, admin-reports.js, otp-login.js, product_list.js; removed data.js, search.js, cart.js.
- **templates:** base.html, index.html, admin/base.html, admin/dashboard.html, admin/reports/report_inventory.html, auth/otp_login.html.

---

## Expected Result

- No JS console errors on normal flows.
- No duplicated logic; single source for CSRF and inits.
- Safe DOM and AJAX handling; no throws on missing elements or empty data.
- Banner interval cleared; bestseller scroll via data attribute.
- Admin and frontend JS loaded only where needed.
