/** @odoo-module **/
import {PhoneField} from "@web/views/fields/phone/phone_field";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

/* voip_oca's own onPhoneClick dials the raw field value as-is
 * (voip_agent_service.esm.js's call() only strips non-digit
 * characters, it never adds a country code) - fine for a number
 * that's already fully-qualified, but a contact's phone field
 * commonly isn't. When the field being clicked belongs to a
 * res.partner record, route through format_partner() instead (fixed
 * in res_partner.py to return an E164-formatted number derived from
 * the contact's own country) so clicking a contact's phone number
 * dials the same correctly-qualified number the softphone's own
 * Partner tab already does. Any other model's phone field (e.g. a
 * lead) falls through to voip_oca's own unmodified behavior.
 */
patch(PhoneField.prototype, {
    setup() {
        super.setup();
        this.signalwireOrm = useService("orm");
    },
    async onPhoneClick(ev) {
        if (
            !this.agent.agent ||
            this.props.record.resModel !== "res.partner" ||
            !this.props.record.resId
        ) {
            return super.onPhoneClick(ev);
        }
        ev.preventDefault();
        ev.stopPropagation();
        const partner = await this.signalwireOrm.call("res.partner", "format_partner", [
            [this.props.record.resId],
        ]);
        this.agent.call({partner});
    },
});
