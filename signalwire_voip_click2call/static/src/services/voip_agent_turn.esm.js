/** @odoo-module **/
import {VoipAgent} from "@voip_oca/services/voip_agent_service.esm";
import {patch} from "@web/core/utils/patch";

/* voip_oca's own agentConfig only ever configures SIP.js's default
 * STUN server - no TURN relay. Confirmed live 2026-09-20: a real
 * SignalWire outbound-PSTN call reliably failed with a SIP 480 /
 * cause=804 "MEDIA_TIMEOUT" without one on the network tested against
 * - STUN alone wasn't enough to establish the media path. Fetches a
 * short-lived, HMAC-derived TURN credential from our own backend
 * (res.users.get_signalwire_turn_credentials) at connect time rather
 * than ever storing the TURN server's shared secret in the browser.
 */
patch(VoipAgent.prototype, {
    async connectAgent() {
        try {
            this.turnCredentials = await this.orm.call(
                "res.users",
                "get_signalwire_turn_credentials",
                []
            );
        } catch {
            this.turnCredentials = false;
        }
        return super.connectAgent();
    },
    get agentConfig() {
        const config = super.agentConfig;
        const iceServers = [{urls: "stun:stun.l.google.com:19302"}];
        if (this.turnCredentials) {
            iceServers.push({
                urls: this.turnCredentials.urls,
                username: this.turnCredentials.username,
                credential: this.turnCredentials.credential,
            });
        }
        config.sessionDescriptionHandlerFactoryOptions = {
            peerConnectionConfiguration: {iceServers},
        };
        return config;
    },
});
