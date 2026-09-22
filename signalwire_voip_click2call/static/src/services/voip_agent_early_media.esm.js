/** @odoo-module **/
/* global SIP */
import {_t} from "@web/core/l10n/translation";
import {VoipAgent} from "@voip_oca/services/voip_agent_service.esm";
import {patch} from "@web/core/utils/patch";

/* Root cause of the outbound-PSTN MEDIA_TIMEOUT saga, confirmed by
 * SignalWire support 2026-09-22 from a real packet capture: they
 * deliver the SDP answer in the 183 Session Progress, but SIP.js only
 * applies an answer carried in a provisional response when the
 * Inviter is constructed with `earlyMedia: true` - the default is
 * false. Without it, the answer is never applied, so the ICE agent
 * never gets SignalWire's candidates to pair against, never installs
 * a permission on our own TURN relay for SignalWire's media address,
 * and SignalWire's own connectivity checks (visible in the capture -
 * 60 well-formed STUN binding requests over the full 30s call) get
 * silently dropped by our own relay per RFC 8656 9.4, right up until
 * their 30-second DTLS timer fires the 480/cause=804 MEDIA_TIMEOUT.
 *
 * `earlyMedia` is only settable via the Inviter constructor's own
 * options (confirmed by reading voip_oca's vendored sip.js - Inviter
 * reads `options.earlyMedia` once, in its own constructor, with no
 * shared UserAgent-level default) - so, per this project's standing
 * "never hand-edit voip_oca itself" rule, there is no way to compose
 * this fix through `super.call()` the way voip_agent_turn.esm.js and
 * voip_agent_receptionist_status.esm.js do. This file instead fully
 * replaces `call()`, faithfully reproducing voip_oca's own method
 * (static/src/services/voip_agent_service.esm.js) with the single
 * changed line - and is loaded FIRST in the manifest's own explicit
 * assets list (deliberate, not alphabetical) specifically so those
 * two later patches' own `super.call()` chains land here, not on
 * voip_oca's untouched original. Accepted tradeoff: this duplicate
 * body can silently drift if voip_oca's own `call()` changes upstream
 * - if a future voip_oca upgrade touches its own `call()`, re-diff
 * this file against it by hand.
 */
patch(VoipAgent.prototype, {
    async call({number, partner}) {
        this.voip.isOpened = true;
        this.voip.isFolded = false;
        var phone_number = number;
        if (!number && partner) {
            phone_number = partner.phone;
        }
        this.playTone("dialtone");
        await this.createCall({
            partner_id: partner && partner.id,
            phone_number: phone_number,
            type_call: "outgoing",
            state: "calling",
        });
        this.voip.inCall = true;
        if (this.voip.mode === "prod") {
            const destination_number = SIP.UserAgent.makeURI(
                `sip:${phone_number.replace(/\D/g, "")}@${this.voip.pbx_domain}`
            );
            this.session = new SIP.Inviter(this.agent, destination_number, {
                earlyMedia: true,
            });
            this.session.delegate = {
                onBye: this._onHanghup.bind(this),
            };
            this.isMuted = false;
            this.isHolded = false;
            this.session.stateChange.addListener(this._onSessionStateChange.bind(this));
            this.session
                .invite({
                    requestDelegate: {
                        onAccept: this._onInviteAccepted.bind(this),
                        onReject: this._onInviteRejected.bind(this),
                    },
                })
                .catch((error) => {
                    // This might happen, for example, if we close the call too early.
                    this.notification.add(
                        _t("Failed to establish the call:\n\n%(error)s", {
                            error: error.message,
                        })
                    );
                });
        }
    },
});
