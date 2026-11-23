/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { Component, useState } from "@odoo/owl";

// Lets a form hear its own greeting text in a self-hosted Piper
// voice/speaker without saving the record or placing a real call. It
// reads the record's real text field as it stands (unsaved edits
// included) and never writes anything back. It used to keep its own
// scratch copy of the text, which put the greeting on screen twice.
export class PiperPreviewWidget extends Component {
    static template = "signalwire_voip_piper_tts.PiperPreviewWidget";
    static props = {
        ...standardWidgetProps,
        voiceField: { type: String },
        speakerField: { type: String, optional: true },
        textField: { type: String, optional: true },
    };

    setup() {
        this.notification = useService("notification");
        this.state = useState({ loading: false });
    }

    get text() {
        const { record, textField } = this.props;
        return ((textField && record.data[textField]) || "").trim();
    }

    get voice() {
        return this.props.record.data[this.props.voiceField];
    }

    get speakerId() {
        return this.props.speakerField ? this.props.record.data[this.props.speakerField] : false;
    }

    get canPreview() {
        return Boolean(this.voice) && Boolean(this.text) && !this.state.loading;
    }

    async onPreviewClick() {
        if (!this.canPreview) {
            return;
        }
        this.state.loading = true;
        try {
            const formData = new FormData();
            formData.append("csrf_token", odoo.csrf_token);
            formData.append("text", this.text);
            formData.append("voice", this.voice);
            if (this.speakerId) {
                formData.append("speaker_id", this.speakerId);
            }
            const response = await browser.fetch("/signalwire/piper/preview", {
                method: "POST",
                body: formData,
            });
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                this.notification.add(data.error || _t("Could not synthesize preview audio."), {
                    type: "danger",
                });
                return;
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.addEventListener("ended", () => URL.revokeObjectURL(url));
            audio.addEventListener("error", () => URL.revokeObjectURL(url));
            await audio.play();
        } finally {
            this.state.loading = false;
        }
    }
}

export const piperPreviewWidget = {
    component: PiperPreviewWidget,
    extractProps: ({ options }) => ({
        voiceField: options.voice_field,
        speakerField: options.speaker_field,
        textField: options.text_field,
    }),
};

registry.category("view_widgets").add("piper_preview", piperPreviewWidget);
