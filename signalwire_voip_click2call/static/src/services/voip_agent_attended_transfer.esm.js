/** @odoo-module **/
/* global SIP */
import {VoipAgent} from "@voip_oca/services/voip_agent_service.esm";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";

/* Attended ("warm") transfer: hold the primary call, place a second,
 * separate consultation call to a colleague to confirm availability,
 * then complete the transfer via SIP.js's own REFER-with-Replaces
 * support - Session.refer() accepts another Session as its target
 * for exactly this (confirmed by reading its own source,
 * voip_oca/static/lib/sip.js's Session.refer()); the target session
 * must already be Established (answered) or refer() rejects with a
 * clear error, which is why completeAttendedTransfer() below guards
 * on consultationSession.dialog rather than just its existence.
 *
 * voip_oca's own VoipAgent tracks exactly one call via `this.session`
 * everywhere (onInvite even auto-rejects a second *incoming* call
 * with 486 while one is active). This patch adds a second,
 * independent `this.consultationSession` slot alongside it for a
 * call *we* place, rather than touching that single-session
 * assumption anywhere else in the class - the existing hold()/
 * call()/hangup() methods are reused as-is, never overridden.
 *
 * Not live-tested end to end (two real provisioned softphones) as of
 * writing - see this module's own README for exactly what that
 * means is and isn't confirmed working yet.
 */
patch(VoipAgent.prototype, {
    async startAttendedTransfer({number, partner}) {
        if (!this.session || this.consultationSession || this.voip.mode !== "prod") {
            return;
        }
        const phoneNumber = number || (partner && partner.phone);
        if (!phoneNumber) {
            return;
        }
        await this.hold();
        this.playTone("dialtone");
        const destination = SIP.UserAgent.makeURI(
            `sip:${phoneNumber.replace(/\D/g, "")}@${this.voip.pbx_domain}`
        );
        this.consultationSession = new SIP.Inviter(this.agent, destination);
        this.consultationSession.delegate = {
            onBye: this._onConsultationEnded.bind(this),
        };
        this.consultationSession.stateChange.addListener(
            this._onConsultationStateChange.bind(this)
        );
        this.consultationSession
            .invite({
                requestDelegate: {
                    onAccept: this._onConsultationAccepted.bind(this),
                    onReject: this._onConsultationRejected.bind(this),
                },
            })
            .catch((error) => {
                this.notification.add(
                    _t("Failed to reach the colleague:\n\n%(error)s", {error: error.message})
                );
                this.consultationSession = null;
            });
    },
    _onConsultationStateChange(newState) {
        if (!this.consultationSession) {
            return;
        }
        switch (newState) {
            case SIP.SessionState.Terminated:
                this.stopTone();
                break;
            case SIP.SessionState.Established: {
                this.stopTone();
                const session = this.consultationSession;
                this._setCallAudioForSession(session);
                session.sessionDescriptionHandler.remoteMediaStream.onaddtrack = () =>
                    this._setCallAudioForSession(session);
                break;
            }
        }
    },
    _setCallAudioForSession(session) {
        const stream = new MediaStream();
        for (const receiver of session.sessionDescriptionHandler.peerConnection.getReceivers()) {
            if (receiver.track) {
                stream.addTrack(receiver.track);
            }
        }
        this.callAudio.srcObject = stream;
        this.callAudio.play();
    },
    _onConsultationAccepted() {
        this.stopTone();
    },
    _onConsultationRejected(response) {
        this.stopTone();
        this.notification.add(
            _t("The colleague didn't answer. Reason:\n\n%(reason)s", {
                reason: response.message.reasonPhrase,
            })
        );
        this.consultationSession = null;
    },
    _onConsultationEnded() {
        this.consultationSession = null;
    },
    async completeAttendedTransfer() {
        if (!this.session || !this.consultationSession?.dialog) {
            return;
        }
        const primary = this.session;
        const consultation = this.consultationSession;
        try {
            await primary.refer(consultation, {
                requestDelegate: {
                    onAccept: () => {
                        primary.bye();
                        consultation.bye();
                        this.consultationSession = null;
                        this._onHanghup();
                    },
                },
            });
        } catch (error) {
            this.notification.add(
                _t("Failed to complete the transfer:\n\n%(error)s", {error: error.message})
            );
        }
    },
    async cancelAttendedTransfer() {
        if (this.consultationSession) {
            this.consultationSession.bye().catch(() => {});
            this.consultationSession = null;
        }
        if (this.session) {
            await this.hold(); // toggles isHolded back off
            this._setCallAudioForSession(this.session);
        }
    },
});
