/**
 * Product card image slider: auto-slide on hover (desktop) and touch (mobile).
 * - Slide interval: 1.25s
 * - First image change occurs immediately on hover for visible feedback
 * - On leave/touch end/scroll: stop and reset to first image
 * - Single image: no behaviour
 * - No duplicate intervals; preload next image to avoid flash
 */
(function () {
    var SLIDE_INTERVAL_MS = 1250;
    var FADE_DURATION_MS = 350;
    var TOUCH_LONG_PRESS_MS = 400;

    function parseImages(el) {
        var raw = el.getAttribute("data-card-images");
        if (!raw || typeof raw !== "string") return [];
        var trimmed = raw.trim();
        if (!trimmed || trimmed === "[]") return [];
        try {
            var arr = JSON.parse(trimmed);
            return Array.isArray(arr) ? arr.filter(function (u) { return u && typeof u === "string"; }) : [];
        } catch (e) {
            return [];
        }
    }

    function getImg(el) {
        if (!el || !el.querySelector) return null;
        return el.querySelector(".card-slider-img") || null;
    }

    function preload(url) {
        if (!url) return;
        try {
            var im = new Image();
            im.src = url;
        } catch (err) {}
    }

    function stopSliding(el) {
        if (!el) return;
        var tid = el._cardSliderTimerId;
        if (tid) {
            clearInterval(tid);
            el._cardSliderTimerId = null;
        }
        el._cardSliderActive = false;
    }

    function showIndex(el, index) {
        var images = el._cardSliderImages;
        var img = getImg(el);
        if (!images || !images.length || !img) return;
        index = index % images.length;
        if (index < 0) index += images.length;
        el._cardSliderIndex = index;
        var url = images[index];
        if (!url) return;
        img.classList.add("card-slider-fade-out");
        var afterFade = function () {
            img.classList.remove("card-slider-fade-out");
            img.src = url;
            var nextIndex = (index + 1) % images.length;
            var nextUrl = images[nextIndex];
            if (nextUrl) preload(nextUrl);
        };
        setTimeout(afterFade, FADE_DURATION_MS);
    }

    function startSliding(el) {
        var images = el._cardSliderImages;
        var img = getImg(el);
        if (!images || images.length <= 1 || !img) return;
        stopSliding(el);
        el._cardSliderActive = true;
        showIndex(el, 1);
        var next = function () {
            var idx = (el._cardSliderIndex || 0) + 1;
            showIndex(el, idx);
        };
        el._cardSliderTimerId = setInterval(next, SLIDE_INTERVAL_MS);
    }

    function resetToFirst(el) {
        stopSliding(el);
        var images = el._cardSliderImages;
        var img = getImg(el);
        if (!images || !images.length || !img) return;
        var first = images[0];
        if (first) {
            img.src = first;
            img.classList.remove("card-slider-fade-out");
        }
        el._cardSliderIndex = 0;
    }

    function onPointerStart(el) {
        if (el._cardSliderImages && el._cardSliderImages.length > 1) {
            el._cardSliderTouchTimer = setTimeout(function () {
                startSliding(el);
            }, TOUCH_LONG_PRESS_MS);
        }
    }

    function onPointerEnd(el) {
        if (el._cardSliderTouchTimer) {
            clearTimeout(el._cardSliderTouchTimer);
            el._cardSliderTouchTimer = null;
        }
        resetToFirst(el);
    }

    function onScroll() {
        document.querySelectorAll(".js-product-card-slider").forEach(function (container) {
            if (container._cardSliderActive) {
                resetToFirst(container);
            }
        });
    }

    function bindSlider(container) {
        if (!container || !container.classList.contains("js-product-card-slider") || container._cardSliderBound) return;
        var images = parseImages(container);
        if (images.length <= 1) return;
        container._cardSliderImages = images;
        container._cardSliderIndex = 0;
        container._cardSliderBound = true;

        container.addEventListener("mouseenter", function () {
            startSliding(container);
        }, { passive: true });
        container.addEventListener("mouseleave", function () {
            resetToFirst(container);
        }, { passive: true });

        container.addEventListener("touchstart", function () {
            onPointerStart(container);
        }, { passive: true });
        container.addEventListener("touchend", function () {
            onPointerEnd(container);
        }, { passive: true });
        container.addEventListener("touchcancel", function () {
            onPointerEnd(container);
        }, { passive: true });
    }

    function init() {
        document.querySelectorAll(".js-product-card-slider").forEach(bindSlider);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            init();
            window.addEventListener("scroll", onScroll, { passive: true });
        });
    } else {
        init();
        window.addEventListener("scroll", onScroll, { passive: true });
    }

    window.ProductCardSliderInit = init;
})();
