/** @odoo-module **/
import {VoipAgent} from "@voip_oca/services/voip_agent_service.esm";
import {patch} from "@web/core/utils/patch";

/* Caller ID by company: just before dialing, tell Odoo who's being called
 * and from which record (set by the phone field when a number is clicked),
 * with the current company in the request's context. Odoo picks the number
 * the call goes out as (the provider asks it a moment later) and answers
 * with a "Calling as ..." note. Best-effort: dialing never waits on a
 * failure here. */
patch(VoipAgent.prototype, {
    async call(args) {
        const record = this.signalwireCallRecord || null;
        this.signalwireCallRecord = null;
        const number = args?.number || args?.partner?.phone;
        if (number) {
            try {
                const result = await this.orm.call("res.users", "signalwire_note_outbound_call", [
                    number,
                    record?.model || false,
                    record?.id || false,
                ]);
                if (result?.label) {
                    this.notification.add(result.label, {type: "info"});
                }
            } catch {
                // The call still goes out as the Calls Out As number.
            }
        }
        return super.call(...arguments);
    },
});
