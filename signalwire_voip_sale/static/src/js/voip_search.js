/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

/**
 * The VoIP number search page (see views/voip_search_templates.xml) -
 * search by area code, one result row per available number with an
 * "Add to cart" button. Same shape as namecheap_domains_sale's own
 * DomainSearch interaction, simplified where SignalWire's own API
 * shape allows it (one flat price for every number, not a per-result
 * price like a domain's per-TLD cost).
 */
export class VoipSearch extends Interaction {
    static selector = ".o_voip_search";
    dynamicContent = {
        ".o_voip_search_form": { "t-on-submit.prevent": this.locked(this.onSearch) },
        ".o_voip_search_results": {
            "t-on-click": this.locked(this.onResultsClick),
        },
    };

    setup() {
        this.resultsEl = this.el.querySelector(".o_voip_search_results");
        this.inputEl = this.el.querySelector(".o_voip_search_input");
    }

    async onSearch() {
        const areaCode = (this.inputEl.value || "").trim();
        this.renderMessage(_t("Searching..."));
        let data;
        try {
            data = await this.waitFor(rpc("/voip/search", { area_code: areaCode }));
        } catch {
            this.renderMessage(_t("Something went wrong - please try again."));
            return;
        }
        if (data.error) {
            this.renderMessage(data.error);
            return;
        }
        this.renderResults(data);
    }

    renderMessage(text) {
        this.resultsEl.replaceChildren();
        const p = document.createElement("p");
        p.className = "text-muted";
        p.textContent = text;
        this.resultsEl.appendChild(p);
    }

    renderResults(data) {
        this.resultsEl.replaceChildren();
        if (!data.numbers.length) {
            this.renderMessage(_t("No numbers available for that area code - try another."));
            return;
        }
        for (const number of data.numbers) {
            const row = document.createElement("div");
            row.className =
                "d-flex align-items-center justify-content-between border rounded p-3 mb-2";

            const label = document.createElement("strong");
            label.textContent = number;
            row.appendChild(label);

            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn btn-primary o_voip_add_to_cart";
            button.dataset.number = number;
            button.textContent = _t("Add to cart - %(price)s %(currency)s/mo", {
                price: data.price.toFixed(2),
                currency: data.currency,
            });
            row.appendChild(button);

            this.resultsEl.appendChild(row);
        }
    }

    async onResultsClick(ev) {
        const button = ev.target.closest(".o_voip_add_to_cart");
        if (!button) {
            return;
        }
        const phoneNumber = button.dataset.number;
        button.disabled = true;
        button.textContent = _t("Adding...");
        let data;
        try {
            data = await this.waitFor(
                rpc("/voip/add_to_cart", { phone_number: phoneNumber })
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
        window.location.href = "/shop/cart";
    }
}

registry.category("public.interactions").add("signalwire_voip_sale.voip_search", VoipSearch);
