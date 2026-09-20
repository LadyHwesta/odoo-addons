/** @odoo-module **/
import {VoipAgent} from "@voip_oca/services/voip_agent_service.esm";
import {patch} from "@web/core/utils/patch";

/* voip_oca's own agentConfig only ever configures SIP.js's default
 * STUN server - no TURN relay. Confirmed live 2026-09-20: a real
 * SignalWire outbound-PSTN call reliably failed with a SIP 480 /
 * cause=804 "MEDIA_TIMEOUT" without one - STUN alone wasn't enough to
 * establish the media path on the network tested against.
 *
 * Fetches a short-lived, HMAC-derived TURN credential from our own
 * backend (res.users.get_signalwire_turn_credentials) fresh on every
 * outbound call attempt, rather than once when the softphone first
 * connects - a softphone can stay connected in an open browser tab
 * for far longer than a short-lived credential's TTL, so caching one
 * at connect time meant every call placed after that TTL elapsed
 * silently used an expired credential (confirmed live: eturnal logged
 * "credentials expired" and TURN allocation failed, even though the
 * SDP correctly offered relay candidates). SIP.js reads
 * userAgent.configuration.sessionDescriptionHandlerFactoryOptions
 * fresh for each new session's own SDH setup (confirmed by reading
 * SIP.js's own source), so mutating it directly on the live agent
 * right before each call is enough - no need to reconstruct the
 * UserAgent itself.
 */
patch(VoipAgent.prototype, {
    async call(params) {
        await this._refreshTurnCredentials();
        return super.call(params);
    },
    async _refreshTurnCredentials() {
        if (!this.agent) {
            return;
        }
        let turnCredentials = false;
        try {
            turnCredentials = await this.orm.call(
                "res.users",
                "get_signalwire_turn_credentials",
                []
            );
        } catch {
            turnCredentials = false;
        }
        const iceServers = [{urls: "stun:stun.l.google.com:19302"}];
        if (turnCredentials) {
            iceServers.push({
                urls: turnCredentials.urls,
                username: turnCredentials.username,
                credential: turnCredentials.credential,
            });
        }
        this.agent.configuration.sessionDescriptionHandlerFactoryOptions = {
            peerConnectionConfiguration: {iceServers},
        };
    },
});
