import { patch } from "@web/core/utils/patch";
import { StripeOptions } from "@payment_stripe/interactions/stripe_options";

patch(StripeOptions.prototype, {
    /**
     * Payments through Meskis: load Stripe.js on the business's own Stripe
     * account (a direct charge), as payment_stripe's Stripe Connect hook allows.
     * The account id is in the form's dataset (data-stripe-account).
     */
    _prepareStripeOptions(dataset) {
        const options = super._prepareStripeOptions(...arguments);
        if (dataset && dataset.stripeAccount) {
            options.stripeAccount = dataset.stripeAccount;
        }
        return options;
    },
});
