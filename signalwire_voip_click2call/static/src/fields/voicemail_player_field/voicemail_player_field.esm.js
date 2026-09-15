/** @odoo-module */
/*
    Field widget for signalwire.voicemail's own recording_download_url
    (a plain Char, computed from the ir.attachment) - renders the
    reusable VoicemailAudioPlayer, and marks the record read the
    moment someone actually presses play, mirroring how most mail/
    voicemail clients treat "opened it and listened" as read.
*/
import {Component} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {VoicemailAudioPlayer} from "../../components/voicemail_audio_player/voicemail_audio_player.esm";

export class VoicemailPlayerField extends Component {
    static template = "signalwire_voip_click2call.VoicemailPlayerField";
    static components = {VoicemailAudioPlayer};
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
    }

    get url() {
        return this.props.record.data[this.props.name] || false;
    }

    async onPlay() {
        if (this.props.record.data.is_read) {
            return;
        }
        await this.orm.call("signalwire.voicemail", "action_mark_read", [[this.props.record.resId]]);
        await this.props.record.load();
    }
}

registry.category("fields").add("signalwire_voicemail_player", {
    component: VoicemailPlayerField,
    supportedTypes: ["char"],
});
