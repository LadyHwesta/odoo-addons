/** @odoo-module **/
import {VoipAgent} from "@voip_oca/services/voip_agent_service.esm";
import {patch} from "@web/core/utils/patch";

/* Reports this user's own softphone call state to the backend
 * (res.users.set_signalwire_call_state) whenever it changes, so the
 * live receptionist panel can show it - SignalWire itself has no
 * presence API at all (confirmed earlier in this project), so this
 * is the only source for "is this user actually on a call" data.
 * Best-effort: a failed report (e.g. the receptionist panel/group
 * isn't set up yet) is swallowed rather than surfacing an error
 * toast for something that isn't the user's own active task.
 */
patch(VoipAgent.prototype, {
    _reportCallState(state) {
        this.orm.call("res.users", "set_signalwire_call_state", [state]).catch(() => {});
    },
    onInvite(session) {
        this._reportCallState("ringing");
        return super.onInvite(session);
    },
    async call(params) {
        this._reportCallState("ringing");
        return super.call(params);
    },
    _onInviteAccepted() {
        this._reportCallState("on_call");
        return super._onInviteAccepted();
    },
    async accept() {
        this._reportCallState("on_call");
        return super.accept();
    },
    _onInviteRejected(response) {
        this._reportCallState("idle");
        return super._onInviteRejected(response);
    },
    async _onCancelInvitation() {
        this._reportCallState("idle");
        return super._onCancelInvitation();
    },
    async _onHanghup() {
        this._reportCallState("idle");
        return super._onHanghup();
    },
});
