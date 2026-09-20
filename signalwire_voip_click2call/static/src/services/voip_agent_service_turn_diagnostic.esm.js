/** @odoo-module **/
/* eslint-disable no-console */
import {VoipAgent} from "@voip_oca/services/voip_agent_service.esm";
import {patch} from "@web/core/utils/patch";

/* TEMPORARY DIAGNOSTIC - NOT a permanent fix.
 *
 * voip_oca's own agentConfig only ever configures SIP.js's default
 * STUN server (stun.l.google.com), no TURN server at all. A call
 * that gets a real SIP response (e.g. SignalWire's own 480 /
 * cause=804 "MEDIA_TIMEOUT") but never connects audio is the classic
 * symptom of STUN alone being insufficient to establish the actual
 * media path for this network. This patch points SIP.js at a
 * well-known public TURN test relay (openrelay.metered.ca) purely to
 * confirm that diagnosis - it is not something to leave running in
 * production (rate-limited, shared, no uptime guarantee). Remove this
 * file and its manifest entry once the real TURN solution is decided.
 */
patch(VoipAgent.prototype, {
    get agentConfig() {
        const config = super.agentConfig;
        config.sessionDescriptionHandlerFactoryOptions = {
            peerConnectionConfiguration: {
                iceServers: [
                    {urls: "stun:stun.l.google.com:19302"},
                    {
                        urls: "turn:openrelay.metered.ca:80",
                        username: "openrelayproject",
                        credential: "openrelayproject",
                    },
                    {
                        urls: "turn:openrelay.metered.ca:443",
                        username: "openrelayproject",
                        credential: "openrelayproject",
                    },
                    {
                        urls: "turn:openrelay.metered.ca:443?transport=tcp",
                        username: "openrelayproject",
                        credential: "openrelayproject",
                    },
                ],
            },
        };
        return config;
    },
});
