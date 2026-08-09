/**
 * app/static/js/admin_modal.js
 *
 * Shared modal + toast utility for the admin panel, replacing
 * browser prompt()/alert(). Loaded once via base admin layout;
 * exposes window.AdminModal and window.AdminToast globally so every
 * admin page's inline script can call them without imports.
 */

(function () {
    function ensureContainer() {
        let container = document.getElementById("cl-modal-root");
        if (!container) {
            container = document.createElement("div");
            container.id = "cl-modal-root";
            document.body.appendChild(container);
        }
        return container;
    }

    function ensureToastContainer() {
        let container = document.getElementById("cl-toast-root");
        if (!container) {
            container = document.createElement("div");
            container.id = "cl-toast-root";
            container.className = "cl-toast-root";
            document.body.appendChild(container);
        }
        return container;
    }

    window.AdminToast = {
        show: function (message, type) {
            type = type || "info";
            const container = ensureToastContainer();
            const toast = document.createElement("div");
            toast.className = "cl-toast cl-toast-" + type;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(function () {
                toast.classList.add("cl-toast-fade");
                setTimeout(function () { toast.remove(); }, 300);
            }, 3200);
        },
        success: function (message) { this.show(message, "success"); },
        error: function (message) { this.show(message, "error"); },
    };

    window.AdminModal = {
        /**
         * fields: [{ name, label, value, type ("text"|"textarea"|"select"), options }]
         * Returns a Promise resolving to an object of {name: value} or null if cancelled.
         */
        form: function (title, fields) {
            return new Promise(function (resolve) {
                const root = ensureContainer();

                const fieldsHtml = fields.map(function (f) {
                    if (f.type === "textarea") {
                        return `<div class="cl-field">
                            <label>${f.label}</label>
                            <textarea id="modal-field-${f.name}" rows="5">${f.value || ""}</textarea>
                        </div>`;
                    }
                    if (f.type === "select") {
                        const optionsHtml = (f.options || []).map(function (o) {
                            const selected = o.value === f.value ? "selected" : "";
                            return `<option value="${o.value}" ${selected}>${o.label}</option>`;
                        }).join("");
                        return `<div class="cl-field">
                            <label>${f.label}</label>
                            <select id="modal-field-${f.name}">${optionsHtml}</select>
                        </div>`;
                    }
                    return `<div class="cl-field">
                        <label>${f.label}</label>
                        <input type="text" id="modal-field-${f.name}" value="${f.value || ""}">
                    </div>`;
                }).join("");

                root.innerHTML = `
                    <div class="cl-modal-overlay">
                        <div class="cl-modal-box">
                            <h3 class="cl-modal-title">${title}</h3>
                            <div class="cl-modal-body">${fieldsHtml}</div>
                            <div class="cl-modal-actions">
                                <button class="cl-btn cl-btn-sm cl-btn-outline" id="modal-cancel-btn">انصراف</button>
                                <button class="cl-btn cl-btn-sm" id="modal-confirm-btn">تأیید</button>
                            </div>
                        </div>
                    </div>`;

                function close(result) {
                    root.innerHTML = "";
                    resolve(result);
                }

                root.querySelector("#modal-cancel-btn").addEventListener("click", function () { close(null); });
                root.querySelector(".cl-modal-overlay").addEventListener("click", function (e) {
                    if (e.target.classList.contains("cl-modal-overlay")) close(null);
                });

                root.querySelector("#modal-confirm-btn").addEventListener("click", function () {
                    const result = {};
                    fields.forEach(function (f) {
                        result[f.name] = document.getElementById(`modal-field-${f.name}`).value.trim();
                    });
                    close(result);
                });
            });
        },

        confirm: function (message) {
            return new Promise(function (resolve) {
                const root = ensureContainer();

                root.innerHTML = `
                    <div class="cl-modal-overlay">
                        <div class="cl-modal-box cl-modal-box-sm">
                            <p class="cl-modal-confirm-text">${message}</p>
                            <div class="cl-modal-actions">
                                <button class="cl-btn cl-btn-sm cl-btn-outline" id="modal-cancel-btn">انصراف</button>
                                <button class="cl-btn cl-btn-sm" id="modal-confirm-btn" style="background:linear-gradient(135deg, var(--warn) 0%, #ff8a8a 100%);">حذف</button>
                            </div>
                        </div>
                    </div>`;

                function close(result) {
                    root.innerHTML = "";
                    resolve(result);
                }

                root.querySelector("#modal-cancel-btn").addEventListener("click", function () { close(false); });
                root.querySelector("#modal-confirm-btn").addEventListener("click", function () { close(true); });
                root.querySelector(".cl-modal-overlay").addEventListener("click", function (e) {
                    if (e.target.classList.contains("cl-modal-overlay")) close(false);
                });
            });
        },
    };
})();