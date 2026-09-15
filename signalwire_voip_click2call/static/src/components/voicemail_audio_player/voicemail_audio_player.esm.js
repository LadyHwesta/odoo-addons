/** @odoo-module */
/*
    A plain <audio> wrapper, reused both by the voicemail_player field
    widget (backend list/form) and the voicemail systray dropdown - one
    component so both surfaces stay visually/behaviorally identical.
    `preload="none"` means the recording is only actually fetched once
    someone presses play, not the moment the row/systray renders.
*/
import {Component} from "@odoo/owl";

export class VoicemailAudioPlayer extends Component {
    static template = "signalwire_voip_click2call.VoicemailAudioPlayer";
    static props = {
        url: {type: [String, Boolean], optional: true},
        onPlay: {type: Function, optional: true},
    };

    onPlay() {
        if (this.props.onPlay) {
            this.props.onPlay();
        }
    }
}
