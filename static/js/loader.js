
(function () {
    // Hide loader when page is fully loaded
    window.addEventListener('load', function () {
        var loader = document.getElementById('page-loader');
        if (loader) {
            loader.classList.add('hidden');
        }
    });

    // Safety: hide loader after 6s max
    setTimeout(function () {
        var loader = document.getElementById('page-loader');
        if (loader && !loader.classList.contains('hidden')) {
            loader.classList.add('hidden');
        }
    }, 6000);

    // Re-show loader on form submission 
    document.addEventListener('submit', function (e) {
        var form = e.target;
        // Skip AJAX forms or forms with data-no-loader attribute
        if (form.dataset.noLoader) return;
        var loader = document.getElementById('page-loader');
        if (loader) {
            loader.classList.remove('hidden');
        }
    });

    // Re-show loader on regular link navigation
    document.addEventListener('click', function (e) {
        var link = e.target.closest('a');
        if (!link) return;
        var href = link.getAttribute('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript:') ||
            link.target === '_blank' || link.dataset.noLoader) return;
        var loader = document.getElementById('page-loader');
        if (loader) {
            loader.classList.remove('hidden');
        }
    });
})();
