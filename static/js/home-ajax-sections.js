/**
 * Home page AJAX sections: New Arrivals, Top Selling, Recently Viewed.
 * Section-specific card layouts: tall (new-arrivals), compact (top-selling), mini (recently-viewed).
 * Auto-hides Recently Viewed when empty. Scroll shadow logic. Deal countdown timer.
 */
(function () {
    "use strict";

    var WISHLIST_SVG = '<svg class="wishlist-heart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';

    function buildCardTall(p) {
        if (!p || typeof p !== "object") return null;
        var card = document.createElement("div");
        card.className = "product-card-tall featured-product-card";
        var imgSrc = (Array.isArray(p.card_images) ? p.card_images[0] : null) || p.image_url || "";
        var link = document.createElement("a");
        link.href = p.url || "#";
        link.className = "featured-product-link";
        var imgWrap = document.createElement("div");
        imgWrap.className = "card-image featured-product-image product-card-image-slider" + ((p.card_images && p.card_images.length > 1) ? " js-product-card-slider" : "");
        if (p.card_images && p.card_images.length > 1) imgWrap.setAttribute("data-card-images", JSON.stringify(p.card_images));
        var img = document.createElement("img");
        img.src = imgSrc.trim() || "/static/images/banner.png";
        img.alt = p.name || "";
        img.loading = "lazy";
        img.className = "card-slider-img";
        img.setAttribute("decoding", "async");
        imgWrap.appendChild(img);
        link.appendChild(imgWrap);
        var info = document.createElement("div");
        info.className = "card-info featured-product-info";
        if (p.category_name) {
            var cat = document.createElement("div");
            cat.className = "featured-product-category";
            cat.textContent = p.category_name;
            info.appendChild(cat);
        }
        var title = document.createElement("h3");
        title.className = "card-title";
        title.textContent = p.name || "";
        info.appendChild(title);
        var priceWrap = document.createElement("div");
        priceWrap.className = "card-price featured-product-price";
        var curr = document.createElement("span");
        curr.className = "current-price";
        curr.textContent = "₹" + (p.price || "0");
        priceWrap.appendChild(curr);
        if (p.original_price && parseFloat(p.original_price) > parseFloat(p.price || 0)) {
            var orig = document.createElement("span");
            orig.className = "original-price";
            orig.textContent = "₹" + p.original_price;
            priceWrap.appendChild(orig);
        }
        info.appendChild(priceWrap);
        link.appendChild(info);
        card.appendChild(link);
        var wishlist = document.createElement("button");
        wishlist.type = "button";
        wishlist.className = "product-card-wishlist js-wishlist-toggle";
        wishlist.setAttribute("data-product-id", p.id);
        wishlist.setAttribute("aria-label", "Add to wishlist");
        wishlist.innerHTML = WISHLIST_SVG;
        card.insertBefore(wishlist, card.firstChild);
        if (p.discount_percent && p.discount_percent > 0) {
            var badge = document.createElement("span");
            badge.className = "featured-product-badge";
            badge.textContent = p.discount_percent + "% OFF";
            card.insertBefore(badge, card.firstChild);
        }
        var cta = document.createElement("a");
        cta.href = p.url || "#";
        cta.className = "featured-add-to-cart";
        cta.textContent = "View Details";
        card.appendChild(cta);
        return card;
    }

    function buildCardCompact(p) {
        if (!p || typeof p !== "object") return null;
        var card = document.createElement("div");
        card.className = "product-card-compact featured-product-card";
        var imgSrc = (Array.isArray(p.card_images) ? p.card_images[0] : null) || p.image_url || "";
        var badge = document.createElement("span");
        badge.className = "badge-popular";
        badge.textContent = "🔥 Popular";
        card.appendChild(badge);
        var wishlist = document.createElement("button");
        wishlist.type = "button";
        wishlist.className = "product-card-wishlist js-wishlist-toggle";
        wishlist.setAttribute("data-product-id", p.id);
        wishlist.setAttribute("aria-label", "Add to wishlist");
        wishlist.innerHTML = WISHLIST_SVG;
        card.appendChild(wishlist);
        var link = document.createElement("a");
        link.href = p.url || "#";
        link.className = "featured-product-link";
        var imgWrap = document.createElement("div");
        imgWrap.className = "card-image featured-product-image";
        var img = document.createElement("img");
        img.src = imgSrc.trim() || "/static/images/banner.png";
        img.alt = p.name || "";
        img.loading = "lazy";
        img.setAttribute("decoding", "async");
        imgWrap.appendChild(img);
        link.appendChild(imgWrap);
        var info = document.createElement("div");
        info.className = "card-info";
        var title = document.createElement("h3");
        title.className = "card-title";
        title.textContent = p.name || "";
        info.appendChild(title);
        var priceWrap = document.createElement("div");
        priceWrap.className = "card-price";
        var curr = document.createElement("span");
        curr.className = "current-price";
        curr.textContent = "₹" + (p.price || "0");
        priceWrap.appendChild(curr);
        if (p.original_price && parseFloat(p.original_price) > parseFloat(p.price || 0)) {
            var orig = document.createElement("span");
            orig.className = "original-price";
            orig.textContent = "₹" + p.original_price;
            priceWrap.appendChild(orig);
        }
        info.appendChild(priceWrap);
        link.appendChild(info);
        card.appendChild(link);
        var cta = document.createElement("a");
        cta.href = p.url || "#";
        cta.className = "featured-add-to-cart";
        cta.textContent = "View Details";
        card.appendChild(cta);
        return card;
    }

    function buildCardMini(p) {
        if (!p || typeof p !== "object") return null;
        var card = document.createElement("a");
        card.href = p.url || "#";
        card.className = "product-card-mini featured-product-card";
        var imgSrc = (Array.isArray(p.card_images) ? p.card_images[0] : null) || p.image_url || "";
        var imgWrap = document.createElement("div");
        imgWrap.className = "card-image";
        var img = document.createElement("img");
        img.src = imgSrc.trim() || "/static/images/banner.png";
        img.alt = p.name || "";
        img.loading = "lazy";
        img.setAttribute("decoding", "async");
        imgWrap.appendChild(img);
        card.appendChild(imgWrap);
        var info = document.createElement("div");
        info.className = "card-info";
        var title = document.createElement("h3");
        title.className = "card-title";
        title.textContent = p.name || "";
        info.appendChild(title);
        var priceWrap = document.createElement("div");
        priceWrap.className = "card-price";
        var curr = document.createElement("span");
        curr.className = "current-price";
        curr.textContent = "₹" + (p.price || "0");
        priceWrap.appendChild(curr);
        info.appendChild(priceWrap);
        card.appendChild(info);
        return card;
    }

    function getCardBuilder(sectionType) {
        if (sectionType === "new-arrivals") return buildCardTall;
        if (sectionType === "top-selling") return buildCardCompact;
        if (sectionType === "recently-viewed") return buildCardMini;
        return buildCardTall;
    }

    function loadSection(section) {
        var apiUrl = section.getAttribute("data-api-url");
        var sectionType = section.getAttribute("data-section-type") || "new-arrivals";
        var container = section.querySelector(".js-home-ajax-products");
        if (!apiUrl || !container) return;

        fetch(apiUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(function (response) {
                if (!response.ok) return null;
                return response.json();
            })
            .then(function (data) {
                if (!data || !Array.isArray(data.products)) {
                    if (sectionType === "recently-viewed") section.classList.add("is-empty");
                    return;
                }
                if (sectionType === "recently-viewed") section.classList.remove("is-empty");
                var builder = getCardBuilder(sectionType);
                data.products.forEach(function (p) {
                    var node = builder(p);
                    if (node) container.appendChild(node);
                });
                if (typeof window.ProductCardSliderInit === "function") {
                    window.ProductCardSliderInit();
                }
            })
            .catch(function () {
                if (sectionType === "recently-viewed") section.classList.add("is-empty");
            });
    }

    function updateScrollShadows(el) {
        if (!el || !el.classList) return;
        var wrapper = el.closest(".js-scroll-shadow");
        if (!wrapper) return;
        var left = el.scrollLeft > 8;
        var right = el.scrollLeft < el.scrollWidth - el.clientWidth - 8;
        wrapper.classList.toggle("has-scroll-left", left);
        wrapper.classList.toggle("has-scroll-right", right);
    }

    function initScrollShadows() {
        var sections = document.querySelectorAll(".js-scroll-shadow");
        sections.forEach(function (wrapper) {
            var scrollEl = wrapper.querySelector(".scroll-section");
            if (!scrollEl) return;
            updateScrollShadows(scrollEl);
            scrollEl.addEventListener("scroll", function () {
                updateScrollShadows(scrollEl);
            });
            window.addEventListener("resize", function () {
                updateScrollShadows(scrollEl);
            });
        });
    }

    function initDealCountdown() {
        var countdown = document.querySelector(".js-deal-countdown");
        if (!countdown) return;
        var hrsEl = countdown.querySelector(".js-countdown-hours");
        var minsEl = countdown.querySelector(".js-countdown-mins");
        var secsEl = countdown.querySelector(".js-countdown-secs");
        if (!hrsEl || !minsEl || !secsEl) return;
        var endOfDay = function () {
            var d = new Date();
            d.setHours(23, 59, 59, 999);
            return d.getTime();
        };
        var pad = function (n) { return (n < 10 ? "0" : "") + n; };
        var tick = function () {
            var now = Date.now();
            var end = endOfDay();
            var diff = Math.max(0, end - now);
            if (diff <= 0) {
                hrsEl.textContent = "00";
                minsEl.textContent = "00";
                secsEl.textContent = "00";
                return;
            }
            var h = Math.floor(diff / 3600000);
            var m = Math.floor((diff % 3600000) / 60000);
            var s = Math.floor((diff % 60000) / 1000);
            hrsEl.textContent = pad(h);
            minsEl.textContent = pad(m);
            secsEl.textContent = pad(s);
        };
        tick();
        setInterval(tick, 1000);
    }

    function init() {
        document.querySelectorAll(".js-home-ajax-section").forEach(loadSection);
        initScrollShadows();
        initDealCountdown();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
