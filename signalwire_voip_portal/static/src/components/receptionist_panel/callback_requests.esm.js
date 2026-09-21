/** @odoo-module **/
import {SignalWireReceptionistPanel} from "@signalwire_voip_click2call/components/receptionist_panel/receptionist_panel.esm";
import {patch} from "@web/core/utils/patch";

/* Adds a "Callback Requests" section to the existing receptionist
 * panel (signalwire_voip_click2call, Phase D) rather than building a
 * separate page - the panel already has the live bus subscription,
 * the notification service, and this is exactly the kind of thing a
 * receptionist would want alongside active calls and team status.
 * "Call Now" reuses the softphone's own already-working outbound-call
 * path verbatim (agent.call()) - no new SIP/VoIP code at all here.
 */
patch(SignalWireReceptionistPanel.prototype, {
    setup() {
        super.setup();
        this.state.callbackRequests = [];
    },
    async loadData() {
        await super.loadData();
        this.state.callbackRequests = await this.orm.searchRead(
            "signalwire.callback_request",
            [["state", "!=", "completed"]],
            ["partner_id", "phone_number", "note", "state", "claimed_by_user_id"],
            {order: "create_date desc"}
        );
    },
    async claimRequest(req) {
        await this.orm.call("signalwire.callback_request", "action_claim", [[req.id]]);
    },
    callNow(req) {
        this.agent.call({number: req.phone_number});
    },
    async completeRequest(req) {
        await this.orm.call("signalwire.callback_request", "action_complete", [[req.id]]);
    },
});
