/**
 * Login modal – shown when guest tries add-to-cart, cart, or account.
 * Uses OTP login via AJAX; on success redirects to intended page.
 */
(function() {
    function getCookie(name) {
        var match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return match ? match[2] : null;
    }

    var overlay = null;
    var nextInput = null;
    var emailStep = null;
    var otpStep = null;
    var emailInput = null;
    var otpDigits = [];
    var otpHidden = null;
    var loginAjaxUrl = '';

    function getEl(id) { return document.getElementById(id); }

    function getSafeRedirectUrl(url) {
        if (!url) return (window.location.pathname + window.location.search) || '/';
        var u = (url.split('?')[0] || '').replace(/\/$/, '');
        if (u === '/cart/add' || u.indexOf('/cart/remove/') === 0 || u === '/cart/update' || u.indexOf('/checkout/place-order') === 0) {
            return (window.location.pathname + window.location.search) || '/cart/';
        }
        return url;
    }

    function openLoginModal(nextUrl) {
        if (!overlay) return;
        nextUrl = getSafeRedirectUrl(nextUrl || (window.location.pathname + window.location.search) || '/');
        if (nextInput) nextInput.value = nextUrl;
        if (emailStep) {
            emailStep.classList.remove('is-hidden');
            if (emailInput) { emailInput.value = ''; emailInput.focus(); }
        }
        if (otpStep) {
            otpStep.classList.remove('is-visible');
            otpDigits.forEach(function(d) { d.value = ''; });
            if (otpHidden) otpHidden.value = '';
        }
        overlay.classList.add('is-open');
        document.body.style.overflow = 'hidden';
    }

    function closeLoginModal() {
        if (!overlay) return;
        overlay.classList.remove('is-open');
        document.body.style.overflow = '';
    }

    function setLoading(btn, loading) {
        if (!btn) return;
        btn.disabled = loading;
        var text = btn.querySelector('.btn-text');
        var loader = btn.querySelector('.btn-loader');
        if (text) text.style.display = loading ? 'none' : '';
        if (loader) loader.style.display = loading ? '' : 'none';
    }

    function showError(el, msg) {
        if (!el) return;
        el.textContent = msg || '';
    }

    function validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email || '');
    }

    function initModal() {
        overlay = getEl('loginModalOverlay');
        nextInput = getEl('loginModalNext');
        emailStep = getEl('loginModalEmailStep');
        otpStep = getEl('loginModalOtpStep');
        emailInput = document.querySelector('#loginModalOverlay input[name="login_modal_email"]');
        otpHidden = getEl('loginModalOtpHidden');
        if (!overlay || !loginAjaxUrl) return;

        var closeBtn = overlay.querySelector('.login-modal-close');
        if (closeBtn) closeBtn.addEventListener('click', closeLoginModal);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) closeLoginModal();
        });

        var sendOtpBtn = getEl('loginModalSendOtp');
        if (sendOtpBtn && emailInput) {
            sendOtpBtn.addEventListener('click', function() {
                var email = (emailInput.value || '').trim().toLowerCase();
                showError(getEl('loginModalEmailError'), '');
                if (!validateEmail(email)) {
                    showError(getEl('loginModalEmailError'), 'Please enter a valid email address.');
                    return;
                }
                setLoading(sendOtpBtn, true);
                var formData = new FormData();
                formData.append('action', 'request_otp');
                formData.append('email', email);
                formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
                fetch(loginAjaxUrl, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
                .then(function(_ref) {
                    var ok = _ref.ok, data = _ref.data;
                    setLoading(sendOtpBtn, false);
                    if (ok && data.success) {
                        if (emailStep) emailStep.classList.add('is-hidden');
                        if (otpStep) {
                            otpStep.classList.add('is-visible');
                            var disp = getEl('loginModalEmailDisplay');
                            if (disp) disp.textContent = data.email || email;
                            otpDigits[0] && otpDigits[0].focus();
                        }
                    } else {
                        showError(getEl('loginModalEmailError'), data.error || 'Failed to send OTP.');
                    }
                })
                .catch(function() {
                    setLoading(sendOtpBtn, false);
                    showError(getEl('loginModalEmailError'), 'Network error. Please try again.');
                });
            });
        }

        var verifyBtn = getEl('loginModalVerify');
        if (verifyBtn) {
            verifyBtn.addEventListener('click', function() {
                var otp = (otpHidden && otpHidden.value) || otpDigits.map(function(d) { return d.value; }).join('');
                showError(getEl('loginModalOtpError'), '');
                if (otp.length !== 4) {
                    showError(getEl('loginModalOtpError'), 'Please enter the 4-digit OTP.');
                    return;
                }
                var email = (emailInput && emailInput.value || '').trim().toLowerCase();
                var nextVal = (nextInput && nextInput.value) || '/';
                setLoading(verifyBtn, true);
                var formData = new FormData();
                formData.append('action', 'verify_otp');
                formData.append('email', email);
                formData.append('otp', otp);
                formData.append('next', nextVal);
                formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
                fetch(loginAjaxUrl, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
                .then(function(_ref) {
                    var ok = _ref.ok, data = _ref.data;
                    setLoading(verifyBtn, false);
                    if (ok && data.success && data.redirect) {
                        closeLoginModal();
                        window.location.href = data.redirect;
                    } else {
                        showError(getEl('loginModalOtpError'), data.error || 'Invalid OTP. Please try again.');
                    }
                })
                .catch(function() {
                    setLoading(verifyBtn, false);
                    showError(getEl('loginModalOtpError'), 'Network error. Please try again.');
                });
            });
        }

        var changeEmailBtn = getEl('loginModalChangeEmail');
        if (changeEmailBtn) {
            changeEmailBtn.addEventListener('click', function() {
                if (otpStep) otpStep.classList.remove('is-visible');
                if (emailStep) {
                    emailStep.classList.remove('is-hidden');
                    if (emailInput) emailInput.focus();
                }
            });
        }

        var digitsContainer = overlay.querySelector('.login-modal-otp-digits');
        if (digitsContainer) {
            otpDigits = Array.from(digitsContainer.querySelectorAll('input'));
            otpDigits.forEach(function(input, idx) {
                input.addEventListener('input', function() {
                    this.value = (this.value || '').replace(/[^0-9]/g, '').slice(0, 1);
                    if (otpHidden) {
                        otpHidden.value = otpDigits.map(function(x) { return x.value; }).join('');
                    }
                    if (this.value.length === 1 && idx < otpDigits.length - 1) otpDigits[idx + 1].focus();
                });
                input.addEventListener('keydown', function(e) {
                    if (e.key === 'Backspace' && !this.value && idx > 0) otpDigits[idx - 1].focus();
                });
            });
        }

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && overlay && overlay.classList.contains('is-open')) closeLoginModal();
        });
    }

    function interceptCartAndAccount() {
        var loggedIn = window.__USER_LOGGED_IN__ === true;
        if (loggedIn) return;
        var cartBtn = document.querySelector('a.cart-btn[href*="/cart/"]');
        if (cartBtn) {
            cartBtn.addEventListener('click', function(e) {
                e.preventDefault();
                openLoginModal('/cart/');
            });
        }
        var accountLinks = document.querySelectorAll('a[href*="/accounts/account/"]');
        accountLinks.forEach(function(a) {
            a.addEventListener('click', function(e) {
                e.preventDefault();
                openLoginModal('/accounts/account/');
            });
        });
    }

    function run() {
        loginAjaxUrl = window.__LOGIN_AJAX_URL__ || '';
        if (!loginAjaxUrl) return;
        initModal();
        interceptCartAndAccount();
        window.openLoginModal = openLoginModal;
        window.closeLoginModal = closeLoginModal;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }
})();
