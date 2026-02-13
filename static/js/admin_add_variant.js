/**
 * Admin product list: Add Variant modal (AJAX).
 * - Load modal content via GET when "Add Variant" is clicked (clothing only).
 * - Duplicate color name check (case-insensitive), disable submit if duplicate.
 * - Max 3 images, at least 1 required; at least 1 size; stock >= 0; no duplicate sizes.
 * - Submit via AJAX (FormData), on success inject new variant or reload.
 */
(function() {
    "use strict";

    var modal = document.getElementById("add-variant-modal");
    var modalBody = document.getElementById("add-variant-modal-body");
    var modalUrlMeta = document.querySelector('meta[name="add-variant-modal-url"]');
    var saveUrlMeta = document.querySelector('meta[name="add-variant-save-url"]');

    function getModalUrl(productId) {
        if (!modalUrlMeta) return null;
        return modalUrlMeta.getAttribute("content").replace(/\/products\/\d+\//, "/products/" + productId + "/");
    }
    function getSaveUrl(productId) {
        if (!saveUrlMeta) return null;
        return saveUrlMeta.getAttribute("content").replace(/\/products\/\d+\//, "/products/" + productId + "/");
    }

    function openModal() {
        if (modal) modal.style.display = "block";
    }
    function closeModal() {
        if (modal) modal.style.display = "none";
        if (modalBody) modalBody.innerHTML = "";
    }

    function getExistingColors(formEl) {
        var raw = formEl ? formEl.getAttribute("data-existing-colors") : "";
        if (!raw) return [];
        return raw.split("||").map(function(s) { return s.trim(); }).filter(Boolean);
    }

    function checkDuplicateColor(enteredName, existingColors) {
        if (!enteredName) return false;
        var lower = enteredName.trim().toLowerCase();
        return existingColors.some(function(c) { return c.toLowerCase() === lower; });
    }

    function bindDuplicateCheck(formEl) {
        var colorInput = formEl.querySelector("#add-variant-color-name");
        var submitBtn = formEl.querySelector("#add-variant-submit");
        var errorEl = formEl.querySelector("#add-variant-color-name-error");
        var existing = getExistingColors(formEl);

        function updateState() {
            var val = (colorInput && colorInput.value) ? colorInput.value.trim() : "";
            var isDup = checkDuplicateColor(val, existing);
            if (errorEl) {
                errorEl.style.display = isDup ? "block" : "none";
                errorEl.textContent = isDup ? "This color already exists for this product." : "";
            }
            if (submitBtn) submitBtn.disabled = isDup;
            if (colorInput) colorInput.classList.toggle("is-invalid", isDup);
        }
        if (colorInput) {
            colorInput.addEventListener("input", updateState);
            colorInput.addEventListener("blur", updateState);
            updateState();
        }
    }

    function bindImageLimit(formEl) {
        var files = formEl.querySelectorAll(".add-variant-file");
        var allowed = 3;
        files.forEach(function(input) {
            input.addEventListener("change", function() {
                var count = 0;
                var inputs = formEl.querySelectorAll(".add-variant-file");
                for (var i = 0; i < inputs.length; i++) {
                    if (inputs[i].files && inputs[i].files.length) count++;
                }
                if (count > allowed) {
                    input.value = "";
                    var err = formEl.querySelector("#add-variant-images-error");
                    if (err) {
                        err.style.display = "block";
                        err.textContent = "Maximum " + allowed + " images allowed.";
                    }
                } else {
                    var err = formEl.querySelector("#add-variant-images-error");
                    if (err) err.style.display = "none";
                }
            });
        });
    }

    var sizeIndex = 1;
    var standardSizes = ["Free Size", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "6XL", "7XL", "8XL", "9XL", "10XL"];

    function addSizeRow(container) {
        var idx = sizeIndex++;
        var row = document.createElement("div");
        row.className = "add-variant-size-row";
        row.setAttribute("data-index", idx);
        var selectHtml = '<option value="">Select size</option>' +
            standardSizes.map(function(s) { return '<option value="' + s + '">' + s + '</option>'; }).join("");
        row.innerHTML =
            '<select name="size_' + idx + '" class="form-control add-variant-size-select">' + selectHtml + '</select>' +
            '<input type="number" name="stock_' + idx + '" class="form-control add-variant-stock" min="0" placeholder="Stock" value="0">' +
            '<button type="button" class="btn btn-sm btn-outline-danger add-variant-remove-size" title="Remove size" aria-label="Remove size"><i class="fas fa-times"></i></button>';
        container.appendChild(row);
        row.querySelector(".add-variant-remove-size").addEventListener("click", function() {
            row.remove();
        });
    }

    function bindSizes(formEl) {
        var container = formEl.querySelector("#add-variant-sizes-container");
        var addBtn = formEl.querySelector("#add-variant-add-size");
        if (addBtn && container) {
            addBtn.addEventListener("click", function() {
                addSizeRow(container);
            });
        }
        formEl.querySelectorAll(".add-variant-remove-size").forEach(function(btn) {
            btn.addEventListener("click", function() {
                var row = btn.closest(".add-variant-size-row");
                if (row && container && container.querySelectorAll(".add-variant-size-row").length > 1) {
                    row.remove();
                }
            });
        });
    }

    function collectSizes(formEl) {
        var rows = formEl.querySelectorAll(".add-variant-size-row");
        var out = [];
        var seen = {};
        for (var i = 0; i < rows.length; i++) {
            var sel = rows[i].querySelector(".add-variant-size-select");
            var stockInput = rows[i].querySelector(".add-variant-stock");
            var size = sel && sel.value ? sel.value.trim() : "";
            if (!size) continue;
            if (seen[size]) return { error: "Duplicate size: " + size };
            seen[size] = true;
            var stock = 0;
            if (stockInput && stockInput.value !== "" && stockInput.value !== null) {
                stock = parseInt(stockInput.value, 10);
                if (isNaN(stock) || stock < 0) return { error: "Stock cannot be negative." };
            }
            out.push({ size: size, stock: stock });
        }
        if (out.length === 0) return { error: "At least one size is required." };
        return { sizes: out };
    }

    function validateForm(formEl) {
        var errors = [];
        var colorName = (formEl.querySelector("#add-variant-color-name") || {}).value;
        if (!(colorName && colorName.trim())) errors.push({ field: "color_name", msg: "Color name is required." });
        if (checkDuplicateColor(colorName, getExistingColors(formEl))) errors.push({ field: "color_name", msg: "This color already exists." });

        var fileCount = 0;
        formEl.querySelectorAll(".add-variant-file").forEach(function(inp) {
            if (inp.files && inp.files.length) fileCount++;
        });
        if (fileCount === 0) errors.push({ field: "images", msg: "At least one image is required." });
        if (fileCount > 3) errors.push({ field: "images", msg: "Maximum 3 images allowed." });

        var sizeResult = collectSizes(formEl);
        if (sizeResult.error) errors.push({ field: "sizes", msg: sizeResult.error });

        return errors;
    }

    function showFormErrors(formEl, serverErrors) {
        var wrap = formEl.querySelector("#add-variant-form-errors");
        if (!wrap) return;
        var list = [];
        if (serverErrors && typeof serverErrors === "object") {
            Object.keys(serverErrors).forEach(function(k) {
                var arr = serverErrors[k];
                if (Array.isArray(arr)) arr.forEach(function(m) { list.push(m); });
            });
        }
        wrap.innerHTML = list.length ? "<ul class=\"list-unstyled mb-0\">" + list.map(function(m) { return "<li>" + escapeHtml(m) + "</li>"; }).join("") + "</ul>" : "";
        wrap.style.display = list.length ? "block" : "none";
    }
    function escapeHtml(s) {
        var div = document.createElement("div");
        div.textContent = s;
        return div.innerHTML;
    }

    function bindSubmit(formEl, productId) {
        formEl.addEventListener("submit", function(e) {
            e.preventDefault();
            var errs = validateForm(formEl);
            if (errs.length) {
                showFormErrors(formEl, { __all__: errs.map(function(x) { return x.msg; }) });
                return;
            }
            showFormErrors(formEl, null);

            var formData = new FormData(formEl);
            var sizeResult = collectSizes(formEl);
            if (sizeResult.sizes) formData.set("sizes_json", JSON.stringify(sizeResult.sizes));

            var saveUrl = getSaveUrl(productId);
            if (!saveUrl) return;
            var submitBtn = formEl.querySelector("#add-variant-submit");
            if (submitBtn) submitBtn.disabled = true;

            var xhr = new XMLHttpRequest();
            xhr.open("POST", saveUrl);
            xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
            xhr.onload = function() {
                if (submitBtn) submitBtn.disabled = false;
                var json = null;
                try { json = JSON.parse(xhr.responseText); } catch (err) {}
                if (xhr.status >= 200 && xhr.status < 300 && json && json.success) {
                    closeModal();
                    window.location.reload();
                } else if (json && json.errors) {
                    showFormErrors(formEl, json.errors);
                } else {
                    showFormErrors(formEl, { __all__: ["Something went wrong. Please try again."] });
                }
            };
            xhr.onerror = function() {
                if (submitBtn) submitBtn.disabled = false;
                showFormErrors(formEl, { __all__: ["Network error. Please try again."] });
            };
            xhr.send(formData);
        });
    }

    function bindCancel(formEl) {
        var cancelBtn = formEl.querySelector(".add-variant-cancel");
        if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
    }

    document.querySelectorAll(".add-variant-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
            var productId = btn.getAttribute("data-product-id");
            if (!productId || !modalBody) return;
            var url = getModalUrl(productId);
            if (!url) return;
            modalBody.innerHTML = "<div class=\"add-variant-loading\"><i class=\"fas fa-spinner fa-spin\"></i> Loading...</div>";
            openModal();

            var xhr = new XMLHttpRequest();
            xhr.open("GET", url);
            xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 300) {
                    modalBody.innerHTML = xhr.responseText;
                    var formEl = modalBody.querySelector("#add-variant-form");
                    if (formEl) {
                        sizeIndex = 1;
                        bindDuplicateCheck(formEl);
                        bindImageLimit(formEl);
                        bindSizes(formEl);
                        bindSubmit(formEl, productId);
                        bindCancel(formEl);
                    }
                } else {
                    modalBody.innerHTML = "<p class=\"text-danger\">Failed to load form.</p>";
                }
            };
            xhr.onerror = function() {
                modalBody.innerHTML = "<p class=\"text-danger\">Network error.</p>";
            };
            xhr.send();
        });
    });

    var backdrop = document.getElementById("add-variant-backdrop");
    if (backdrop) backdrop.addEventListener("click", closeModal);
})();
