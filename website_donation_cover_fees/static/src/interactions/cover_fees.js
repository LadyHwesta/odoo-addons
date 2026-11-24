import { patch } from "@web/core/utils/patch";
import { patchDynamicContent } from "@web/public/utils";

import { PaymentForm } from "@payment/interactions/payment_form";

/**
 * "I'll cover the processing fees" on the donation form: shows the extra
 * amount for the gift chosen and tells the server the donor's choice. The
 * server works out the real amount itself; this figure is only a preview.
 */
patch(PaymentForm.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            'input[name="o_donation_amount"], input[name="amount"], #o_donation_cover_fees': {
                "t-on-change": this._updateCoverFeesPreview.bind(this),
                "t-on-input": this._updateCoverFeesPreview.bind(this),
            },
        });
    },

    async start() {
        await super.start?.(...arguments);
        this._updateCoverFeesPreview();
    },

    _coverFeesGift() {
        const checked = this.el.querySelector('input[name="o_donation_amount"][type="radio"]:checked');
        const other = this.el.querySelector("#other_amount_value");
        const value = checked ? checked.value : other?.value ?? this.paymentContext.amount;
        return parseFloat(value) || 0;
    },

    _updateCoverFeesPreview() {
        const box = this.el.querySelector(".o_donation_cover_fees");
        if (!box) {
            return;
        }
        const label = box.querySelector(".o_donation_cover_fees_amount");
        const gift = this._coverFeesGift();
        const percent = parseFloat(box.dataset.feePercent) || 0;
        const fixed = parseFloat(box.dataset.feeFixed) || 0;
        const digits = parseInt(box.dataset.currencyDigits ?? "2");
        if (gift <= 0 || percent >= 100) {
            label.textContent = "";
            return;
        }
        const step = Math.pow(10, -digits);
        const total = Math.ceil(((gift + fixed) / (1 - percent / 100)) / step - 1e-6) * step;
        const amount = (total - gift).toFixed(digits);
        const symbol = box.dataset.currencySymbol || "";
        label.textContent = box.dataset.currencyPosition === "after"
            ? `(+${amount} ${symbol})` : `(+${symbol}${amount})`;
    },

    _prepareTransactionRouteParams() {
        const params = super._prepareTransactionRouteParams(...arguments);
        const box = this.el.querySelector("#o_donation_cover_fees");
        if (document.querySelector(".o_donation_payment_form") && box) {
            params.donation_cover_fees = box.checked;
        }
        return params;
    },
});
