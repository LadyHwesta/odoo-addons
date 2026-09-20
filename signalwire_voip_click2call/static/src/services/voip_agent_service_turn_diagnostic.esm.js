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
        console.warn(
            "SIGNALWIRE TURN DIAGNOSTIC - agentConfig built with:",
            JSON.stringify(config.sessionDescriptionHandlerFactoryOptions)
        );
        return config;
    },
});

/* Also log every ICE candidate SIP.js/the browser actually gathers,
 * and any ICE candidate errors (e.g. a TURN allocation failing,
 * which produces no candidate at all and no thrown exception - only
 * this event reveals it). Patched onto RTCPeerConnection itself since
 * that's the one place guaranteed to see every attempt regardless of
 * which layer of voip_oca/SIP.js constructs the connection.
 */
const nativeAddEventListener = window.RTCPeerConnection.prototype.addEventListener;
window.RTCPeerConnection.prototype.addEventListener = function (type, ...rest) {
    if (type === "icecandidate" || type === "icecandidateerror") {
        console.warn(`SIGNALWIRE TURN DIAGNOSTIC - listener attached for ${type}`);
    }
    return nativeAddEventListener.call(this, type, ...rest);
};
const OriginalRTCPeerConnection = window.RTCPeerConnection;
window.RTCPeerConnection = function (...args) {
    const pc = new OriginalRTCPeerConnection(...args);
    console.warn(
        "SIGNALWIRE TURN DIAGNOSTIC - RTCPeerConnection created with iceServers:",
        JSON.stringify(args[0] && args[0].iceServers)
    );
    pc.addEventListener("icecandidate", (ev) => {
        if (ev.candidate) {
            console.warn(
                "SIGNALWIRE TURN DIAGNOSTIC - candidate:",
                ev.candidate.type,
                ev.candidate.candidate
            );
        } else {
            console.warn("SIGNALWIRE TURN DIAGNOSTIC - candidate gathering complete");
        }
    });
    pc.addEventListener("icecandidateerror", (ev) => {
        console.warn(
            "SIGNALWIRE TURN DIAGNOSTIC - candidate error:",
            ev.errorCode,
            ev.errorText,
            ev.url
        );
    });
    return pc;
};
window.RTCPeerConnection.prototype = OriginalRTCPeerConnection.prototype;
