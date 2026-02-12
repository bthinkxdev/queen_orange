(function() {
    "use strict";

    function getCookie(name) {
        var match = document.cookie.match(new RegExp("(?:^|; )" + name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1") + "=([^;]*)"));
        return match ? decodeURIComponent(match[1]) : "";
    }

    function getCsrfToken(form) {
        var input = form && form.querySelector("[name=csrfmiddlewaretoken]");
        return (input && input.value) ? input.value : getCookie("csrftoken");
    }

    document.addEventListener("DOMContentLoaded", function() {
        document.querySelectorAll(".js-cart-qty-form").forEach(function(form) {
            form.addEventListener("submit", function(e) { e.preventDefault(); });
            var input = form.querySelector(".quantity-input");
            if (!input) return;
            form.querySelectorAll(".js-cart-qty-btn").forEach(function(btn) {
                btn.addEventListener("click", function(e) {
                    e.preventDefault();
                    var quantity = parseInt(input.value, 10) || 0;
                    if (btn.dataset.direction === "increase") quantity += 1;
                    else if (btn.dataset.direction === "decrease") quantity -= 1;
                    if (quantity < 1) return;
                    var formData = new FormData(form);
                    formData.set("quantity", String(quantity));
                    var csrf = getCsrfToken(form);
                    if (!csrf) {
                        alert("Could not update cart. Please refresh and try again.");
                        return;
                    }
                    fetch(form.action, {
                        method: "POST",
                        headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf },
                        body: formData
                    })
                        .then(function(r) {
                            if (!r.ok) throw new Error("Network error");
                            return r.text();
                        })
                        .then(function() {
                            input.value = quantity;
                            location.reload();
                        })
                        .catch(function() {
                            alert("Could not update cart. Please try again.");
                        });
                });
            });
        });
    });
})();

(function() {
    "use strict";

    function getCookie(name) {
        var cookieValue = "";
        var cookies = document.cookie ? document.cookie.split(";") : [];
        for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i].trim();
            if (c.indexOf(name + "=") === 0) {
                cookieValue = decodeURIComponent(c.substring(name.length + 1));
                break;
            }
        }
        return cookieValue;
    }

    function initMobileMenu() {
    const menuToggle = document.querySelector(".mobile-menu-toggle");
    const navMenu = document.querySelector(".nav-menu");

    if (!menuToggle || !navMenu) return;

    menuToggle.addEventListener("click", () => {
        navMenu.classList.toggle("active");
        menuToggle.classList.toggle("active");
        document.body.style.overflow = navMenu.classList.contains("active") ? "hidden" : "";
    });

    navMenu.querySelectorAll(".nav-link").forEach((link) => {
        link.addEventListener("click", () => {
            navMenu.classList.remove("active");
            menuToggle.classList.remove("active");
            document.body.style.overflow = "";
        });
    });

    document.addEventListener("click", (event) => {
        if (!menuToggle.contains(event.target) && !navMenu.contains(event.target)) {
            navMenu.classList.remove("active");
            menuToggle.classList.remove("active");
            document.body.style.overflow = "";
        }
    });
}

function initMobileSearch() {
    const searchToggle = document.getElementById("mobileSearchToggle");
    const searchOverlay = document.getElementById("mobileSearchOverlay");
    const searchClose = document.getElementById("mobileSearchClose");
    const searchInput = document.querySelector(".mobile-search-input");

    if (!searchToggle || !searchOverlay) return;

    // Open mobile search
    searchToggle.addEventListener("click", () => {
        searchOverlay.classList.add("active");
        document.body.style.overflow = "hidden";
        
        // Auto-focus search input after animation
        setTimeout(() => {
            if (searchInput) searchInput.focus();
        }, 300);
    });

    // Close mobile search
    const closeSearch = () => {
        searchOverlay.classList.remove("active");
        document.body.style.overflow = "";
        if (searchInput) searchInput.value = "";
    };

    if (searchClose) {
        searchClose.addEventListener("click", closeSearch);
    }

    // Close on overlay click (outside form)
    searchOverlay.addEventListener("click", (e) => {
        if (e.target === searchOverlay) {
            closeSearch();
        }
    });

    // Close on ESC key
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && searchOverlay.classList.contains("active")) {
            closeSearch();
        }
    });
}

function initAnimations() {
    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("fade-in");
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.1, rootMargin: "0px 0px -50px 0px" }
    );

    document.querySelectorAll(".product-card, .category-card").forEach((el) => {
        observer.observe(el);
    });
}

function initScrollEffects() {
    var header = document.querySelector(".header");
    if (!header) return;
    window.addEventListener("scroll", function() {
        header.classList.toggle("scrolled", window.scrollY > 100);
    });
}

function scrollBestsellers(direction) {
    var container = document.querySelector(".bestsellers-scroll-container");
    if (!container) return;
    var scrollAmount = 320;
    var next = direction === "left" ? container.scrollLeft - scrollAmount : container.scrollLeft + scrollAmount;
    container.scrollTo({ left: next, behavior: "smooth" });
}

function initBestsellersScrollButtons() {
    document.querySelectorAll("[data-scroll-bestsellers]").forEach(function(btn) {
        btn.addEventListener("click", function() {
            var dir = this.getAttribute("data-scroll-bestsellers");
            if (dir) scrollBestsellers(dir);
        });
    });
}

function showNotification(message, type = "success") {
    const notification = document.createElement("div");
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => {
        notification.classList.add("show");
    }, 50);
    setTimeout(() => {
        notification.classList.remove("show");
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 2500);
}

function getCookie(name) {
    const cookieValue = document.cookie
        .split(";")
        .map((cookie) => cookie.trim())
        .find((cookie) => cookie.startsWith(`${name}=`));
    if (!cookieValue) return "";
    return decodeURIComponent(cookieValue.split("=")[1]);
}

function updateCartBadge(count) {
    const badges = document.querySelectorAll(".cart-badge");
    badges.forEach((badge) => {
        if (!count) {
            badge.remove();
            return;
        }
        badge.textContent = count;
        badge.style.display = "flex";
    });
    if (count && badges.length === 0) {
        const cartBtn = document.querySelector(".cart-btn");
        if (!cartBtn) return;
        const badge = document.createElement("span");
        badge.className = "cart-badge";
        badge.textContent = count;
        cartBtn.appendChild(badge);
    }
}

function initQuickAddToCart() {
    const buttons = document.querySelectorAll(".js-add-to-cart");
    if (!buttons.length) return;
    buttons.forEach((button) => {
        button.addEventListener("click", async (event) => {
            event.preventDefault();
            event.stopPropagation();
            const productId = button.dataset.productId;
            const size = button.dataset.size;
            const color = button.dataset.color || "";
            const isJewellery = button.dataset.isJewellery === "true";
            if (!productId) {
                showNotification("Invalid product.", "error");
                return;
            }
            if (!isJewellery && !size) {
                showNotification("Please select a size on the product page.", "error");
                return;
            }
            try {
                const formData = new FormData();
                formData.append("product_id", productId);
                if (!isJewellery) {
                    formData.append("size", size);
                    formData.append("color", color);
                }
                formData.append("quantity", "1");
                const response = await fetch("/cart/add/", {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: formData,
                });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    showNotification(data.error || "Unable to add to cart.", "error");
                    return;
                }
                updateCartBadge(data.cart_count);
                showNotification("Added to cart!");
            } catch (error) {
                showNotification("Unable to add to cart.", "error");
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", function() {
        initMobileMenu();
        initMobileSearch();
        initScrollEffects();
        initAnimations();
        initBestsellersScrollButtons();
        initQuickAddToCart();
    });
})();

(function() {
    var slider = document.getElementById("bannerSlider");
    if (!slider) return;
    var slides = slider.querySelectorAll(".banner-slide");
    if (slides.length <= 1) return;
    var current = 0;
    var bannerIntervalId = null;
    function showSlide(idx) {
        slides.forEach(function(slide, i) {
            slide.classList.toggle("active", i === idx);
        });
    }
    bannerIntervalId = setInterval(function() {
        current = (current + 1) % slides.length;
        showSlide(current);
    }, 3400);
    window.addEventListener("pagehide", function() {
        if (bannerIntervalId) clearInterval(bannerIntervalId);
    });
})();