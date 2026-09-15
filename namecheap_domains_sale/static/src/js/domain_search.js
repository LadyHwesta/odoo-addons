/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

/**
 * The domain search page (see views/domain_search_templates.xml) - a
 * plain search box, one result row per checked domain, and an "Add to
 * cart" button per available result. Deliberately not built as a
 * full-blown product configurator: there's no variant/attribute
 * selection here, just "is this domain free, and what does it cost."
 */
export class DomainSearch extends Interaction {
    static selector = ".o_domain_search";
    dynamicContent = {
        ".o_domain_search_form": { "t-on-submit.prevent": this.locked(this.onSearch) },
        ".o_domain_search_results": {
            "t-on-click": this.locked(this.onResultsClick),
        },
    };

    setup() {
        this.resultsEl = this.el.querySelector(".o_domain_search_results");
        this.inputEl = this.el.querySelector(".o_domain_search_input");
    }

    async onSearch() {
        const domain = (this.inputEl.value || "").trim().toLowerCase();
        this.resultsEl.replaceChildren();
        if (!domain) {
            return;
        }
        this.renderMessage(_t("Checking availability..."));
        let data;
        try {
            data = await this.waitFor(rpc("/domains/search", { domain }));
        } catch {
            this.renderMessage(_t("Something went wrong - please try again."));
            return;
        }
        if (data.error) {
            this.renderMessage(data.error);
            return;
        }
        this.renderResult(data);
    }

    renderMessage(text) {
        this.resultsEl.replaceChildren();
        const p = document.createElement("p");
        p.className = "text-muted";
        p.textContent = text;
        this.resultsEl.appendChild(p);
    }

    renderResult(data) {
        this.resultsEl.replaceChildren();
        const row = document.createElement("div");
        row.className =
            "d-flex align-items-center justify-content-between border rounded p-3";

        const label = document.createElement("div");
        const name = document.createElement("strong");
        name.textContent = data.domain;
        label.appendChild(name);
        if (!data.available) {
            const span = document.createElement("span");
            span.className = "text-danger ms-2";
            span.textContent = _t("Already taken");
            label.appendChild(span);
        } else if (data.premium) {
            const span = document.createElement("span");
            span.className = "badge text-bg-warning ms-2";
            span.textContent = _t("Premium");
            label.appendChild(span);
        }
        row.appendChild(label);

        if (data.available && data.price) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn btn-primary o_domain_add_to_cart";
            button.dataset.domain = data.domain;
            button.textContent = _t("Add to cart - %(price)s %(currency)s/yr", {
                price: data.price.toFixed(2),
                currency: data.currency,
            });
            row.appendChild(button);
        }

        this.resultsEl.appendChild(row);
    }

    async onResultsClick(ev) {
        const button = ev.target.closest(".o_domain_add_to_cart");
        if (!button) {
            return;
        }
        const domain = button.dataset.domain;
        button.disabled = true;
        button.textContent = _t("Adding...");
        let data;
        try {
            data = await this.waitFor(
                rpc("/domains/add_to_cart", { domain, years: 1 })
            );
        } catch {
            button.disabled = false;
            button.textContent = _t("Add to cart");
            this.renderMessage(_t("Something went wrong - please try again."));
            return;
        }
        if (data.error) {
            button.disabled = false;
            this.renderMessage(data.error);
            return;
        }
        button.textContent = _t("Added ✓");
        this.el.dispatchEvent(
            new CustomEvent("cart_updated", { bubbles: true, detail: data })
        );
        window.location.href = "/shop/cart";
    }
}

registry.category("public.interactions").add("namecheap_domains_sale.domain_search", DomainSearch);
