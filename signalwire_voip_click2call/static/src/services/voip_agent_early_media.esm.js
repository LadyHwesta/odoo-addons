/** @odoo-module **/
/* global SIP */
import {VoipAgent} from "@voip_oca/services/voip_agent_service.esm";
import {patch} from "@web/core/utils/patch";

/* Root cause of the outbound MEDIA_TIMEOUT/488 saga, confirmed jointly
 * by SignalWire support (a server-side SIP trace) and our own SIP.js
 * debug log (browser console, developer mode) on 2026-09-22:
 * SignalWire delivers their SDP answer in the 183 Session Progress,
 * unreliable (no 100rel/RSeq - our INVITE doesn't request it).
 * SignalWire's own trace proved the dialog never changes between the
 * 183 and the 200 OK (identical Call-ID/To-tag/From-tag, byte-
 * identical SDP) - and our own client-side sip.invite-dialog logger
 * confirms it independently, tracking one persistent dialog object
 * from "constructed" at the 183 straight through to the ACK/BYE we
 * send ourselves.
 *
 * Despite that, setting `earlyMedia: true` on the Inviter (the fix
 * SignalWire originally suggested, and the one this project shipped
 * first) makes SIP.js immediately tear the call down right at answer:
 *
 *   sip.js:6476 (Inviter.onAccept)
 *   "Early media dialog does not equal confirmed dialog, terminating
 *   session"
 *
 * Reading onProgress/onAccept directly
 * (voip_oca/static/lib/sip.js) shows why: onProgress (handling the
 * 183) sets `this.earlyMediaDialog = session`, where `session` is a
 * *per-response* wrapper object (`inviteResponse.session`). onAccept
 * (handling the 200 OK) later compares `this.earlyMediaDialog !==
 * session` by plain JS reference equality against a *different* per-
 * response wrapper for the exact same real dialog. Both wrappers
 * represent the identical SIP dialog - they're just different JS
 * object instances - so the check is structurally wrong and always
 * fires a false positive for this call shape. This is a genuine
 * SIP.js library defect: its last release was 0.21.2 in October 2022
 * (our exact vendored version), no newer release exists, and no
 * matching public issue was found either - not fixable upstream.
 *
 * The actual fix: Session.setAnswer() (sip.js:2330) operates on
 * `this` (the Inviter instance itself, which persists for the whole
 * call) and its own lazily-created SessionDescriptionHandler - never
 * on the buggy per-response `session` wrapper at all. So the real
 * work that establishes ICE/DTLS doesn't need SIP.js's own
 * `earlyMedia` machinery in the first place:
 *
 * 1. Every Inviter in this project is constructed with earlyMedia at
 *    its SIP.js default (false) - `this.earlyMediaDialog` is then
 *    never assigned anywhere in stock SIP.js code, so onAccept's
 *    buggy `if (this.earlyMediaDialog)` branch is structurally
 *    unreachable. onAccept itself needs zero changes.
 * 2. This patch fully replaces Inviter.prototype.onProgress so that,
 *    the moment a provisional response arrives with a matching SDP
 *    answer, it calls `this.setAnswer(answer, options)` immediately -
 *    the same call SIP.js's own earlyMedia path would have made, just
 *    without ever touching earlyMediaDialog.
 * 3. When the real 200 OK arrives, stock onAccept reapplies its own
 *    answer via the same unmodified setAnswer() call it already makes
 *    today - a harmless, idempotent no-op here since SignalWire's SDP
 *    is byte-identical between the 183 and the 200 OK.
 *
 * Sequencing constraint, found while confirming this is safe: sip.js
 * itself isn't part of voip_oca's regular web.assets_backend bundle -
 * it's its own lazy bundle (voip_oca.agent_assets), loaded via
 * loadBundle(...) inside VoipAgent.connectAgent()
 * (voip_agent_service.esm.js). The global `SIP` object genuinely
 * doesn't exist until that resolves, so the SIP.Inviter.prototype
 * patch below can't run at module load time (would throw
 * ReferenceError) - it's applied from a connectAgent() patch instead,
 * once, guarded so reconnecting doesn't stack duplicate patches onto
 * the same shared prototype.
 */
let sipInviterEarlyAnswerPatched = false;

function patchSipInviterEarlyAnswer() {
    if (sipInviterEarlyAnswerPatched) {
        return;
    }
    // connectAgent() returns early without loading the sip.js bundle at
    // all (non-prod mode, no RTC support, missing PBX config) - `SIP`
    // may genuinely not exist yet even after it resolves. `typeof` is
    // the only way to check an identifier's existence without throwing
    // a ReferenceError if it was never declared.
    if (typeof SIP === "undefined") {
        return;
    }
    sipInviterEarlyAnswerPatched = true;
    patch(SIP.Inviter.prototype, {
        onProgress(inviteResponse) {
            if (this.state !== SIP.SessionState.Establishing) {
                this.logger.error(
                    `Progress received while in state ${this.state}, dropping response`
                );
                return Promise.reject(new Error(`Invalid session state ${this.state}`));
            }
            const response = inviteResponse.message;
            const session = inviteResponse.session;
            if (response.hasHeader("P-Asserted-Identity")) {
                this._assertedIdentity = SIP.Grammar.nameAddrHeaderParse(
                    response.getHeader("P-Asserted-Identity")
                );
            }
            const requireHeader = response.getHeader("require");
            const rseqHeader = response.getHeader("rseq");
            const rseq =
                requireHeader && requireHeader.includes("100rel") && rseqHeader
                    ? Number(rseqHeader)
                    : undefined;
            const responseReliable = !!rseq;
            const extraHeaders = [];
            if (responseReliable) {
                extraHeaders.push(
                    "RAck: " + response.getHeader("rseq") + " " + response.getHeader("cseq")
                );
            }
            switch (session.signalingState) {
                case SIP.SignalingState.Initial:
                    if (responseReliable) {
                        inviteResponse.prack({extraHeaders});
                    }
                    return Promise.resolve();
                case SIP.SignalingState.HaveLocalOffer:
                    if (responseReliable) {
                        inviteResponse.prack({extraHeaders});
                    }
                    return Promise.resolve();
                case SIP.SignalingState.HaveRemoteOffer: {
                    if (!responseReliable) {
                        this.logger.warn(
                            "Non-reliable provisional response MUST NOT contain an " +
                                "initial offer, discarding response."
                        );
                        return Promise.resolve();
                    }
                    const sdh = this.sessionDescriptionHandlerFactory(
                        this,
                        this.userAgent.configuration.sessionDescriptionHandlerFactoryOptions ||
                            {}
                    );
                    if (this.delegate?.onSessionDescriptionHandler) {
                        this.delegate.onSessionDescriptionHandler(sdh, true);
                    }
                    this.earlyMediaSessionDescriptionHandlers.set(session.id, sdh);
                    return sdh
                        .setDescription(
                            response.body,
                            this.sessionDescriptionHandlerOptions,
                            this.sessionDescriptionHandlerModifiers
                        )
                        .then(() =>
                            sdh.getDescription(
                                this.sessionDescriptionHandlerOptions,
                                this.sessionDescriptionHandlerModifiers
                            )
                        )
                        .then((description) => {
                            const body = {
                                contentDisposition: "session",
                                contentType: description.contentType,
                                content: description.body,
                            };
                            inviteResponse.prack({extraHeaders, body});
                        })
                        .catch((error) => {
                            this.stateTransition(SIP.SessionState.Terminated);
                            throw error;
                        });
                }
                case SIP.SignalingState.Stable: {
                    if (responseReliable) {
                        inviteResponse.prack({extraHeaders});
                    }
                    // The one changed branch: apply the answer directly via
                    // setAnswer() (operates on `this`, the persistent
                    // Inviter - never on SIP.js's own buggy
                    // earlyMediaDialog/session tracking) instead of gating
                    // on `this.earlyMedia` and setting
                    // `this.earlyMediaDialog`. Guarded by our own flag on
                    // the Inviter instance so a retransmitted/second 183
                    // doesn't re-apply.
                    const answer = session.answer;
                    if (answer && !this._earlyAnswerApplied) {
                        this._earlyAnswerApplied = true;
                        const options = {
                            sessionDescriptionHandlerModifiers:
                                this.sessionDescriptionHandlerModifiers,
                            sessionDescriptionHandlerOptions:
                                this.sessionDescriptionHandlerOptions,
                        };
                        return this.setAnswer(answer, options).catch((error) => {
                            // Deliberately not terminating the session here,
                            // unlike SIP.js's own earlyMedia error handling
                            // - the 200 OK's own unmodified onAccept path
                            // will still supply a working answer moments
                            // later regardless, so a failed *early* apply
                            // is no longer a reason to kill the whole call.
                            this.logger.warn(
                                `Failed to apply early media answer: ${error.message}`
                            );
                        });
                    }
                    return Promise.resolve();
                }
                case SIP.SignalingState.Closed:
                    return Promise.reject(new Error("Terminated."));
                default:
                    throw new Error("Unknown session signaling state.");
            }
        },
    });
}

patch(VoipAgent.prototype, {
    async connectAgent() {
        const result = await super.connectAgent();
        patchSipInviterEarlyAnswer();
        return result;
    },
});
