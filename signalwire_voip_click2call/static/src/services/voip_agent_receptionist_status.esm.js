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
 *
 * Idle is also reported whenever a call's SIP session ends, however it
 * ended (some endings, such as the call being answered on another of
 * the user's devices, bypass the hang-up handlers below), and once the
 * softphone registers, so a state left over from a closed tab clears.
 */
patch(VoipAgent.prototype, {
    _reportCallState(state) {
        this.orm.call("res.users", "set_signalwire_call_state", [state]).catch(() => {});
    },
    onInvite(session) {
        if (this.session) {
            // Already on a call. voip_oca answers busy here but then
            // carries on and replaces the call in progress with this one;
            // stop after the busy instead.
            session.reject({statusCode: 486});
            return;
        }
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
    _onSessionStateChange(newState) {
        if (newState === "Terminated") {
            this._reportCallState("idle");
        }
        return super._onSessionStateChange(newState);
    },
    _onRegistererStateChange(state) {
        if (state === "Registered" && !this.session) {
            this._reportCallState("idle");
        }
        return super._onRegistererStateChange(state);
    },
});
