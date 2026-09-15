/** @odoo-module */
/*
    The "quick way to check voicemail" itself: a topbar icon with an
    unread-count badge, whose dropdown lists recent unread voicemail
    (caller, duration, transcript snippet if transcription's already
    landed, and an inline player) - so a user can decide whether to
    listen in full, play it right there, or open the full record,
    all without leaving whatever screen they're on.
*/
import {Component} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {useDropdownState} from "@web/core/dropdown/dropdown_hooks";
import {Dropdown} from "@web/core/dropdown/dropdown";
import {VoicemailAudioPlayer} from "../voicemail_audio_player/voicemail_audio_player.esm";

export class SignalwireVoicemailSystray extends Component {
    static template = "signalwire_voip_click2call.VoicemailSystray";
    static components = {Dropdown, VoicemailAudioPlayer};
    static props = {};

    setup() {
        this.voicemail = useService("signalwire_voicemail");
        this.orm = useService("orm");
        this.action = useService("action");
        this.dropdown = useDropdownState();
    }

    get state() {
        return this.voicemail.state;
    }

    onBeforeOpen() {
        this.voicemail.refresh();
    }

    async onPlay(voicemail) {
        // Every voicemail in this preview list is unread by
        // construction (get_systray_data only returns unread ones),
        // so pressing play always means "mark it read".
        await this.orm.call("signalwire.voicemail", "action_mark_read", [[voicemail.id]]);
        await this.voicemail.refresh();
    }

    onOpen(voicemail) {
        this.dropdown.close();
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "signalwire.voicemail",
            res_id: voicemail.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onViewAll() {
        this.dropdown.close();
        this.action.doAction("signalwire_voip_click2call.action_signalwire_voicemail");
    }
}

registry
    .category("systray")
    .add("signalwire_voicemail_systray", {Component: SignalwireVoicemailSystray}, {sequence: 24});
