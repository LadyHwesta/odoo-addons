/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { Component, useState } from "@odoo/owl";

// Lets a form preview a self-hosted Piper voice/speaker against typed
// sample text without saving the record or placing a real call.
// Deliberately never writes anything back to the record - the sample
// text here is a throwaway scratch box, seeded once from the real
// greeting field for convenience, not kept in sync with it.
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
        const { record, textField } = this.props;
        this.state = useState({
            text: (textField && record.data[textField]) || "",
            loading: false,
        });
    }

    get voice() {
        return this.props.record.data[this.props.voiceField];
    }

    get speakerId() {
        return this.props.speakerField ? this.props.record.data[this.props.speakerField] : false;
    }

    get canPreview() {
        return Boolean(this.voice) && Boolean(this.state.text.trim()) && !this.state.loading;
    }

    async onPreviewClick() {
        if (!this.canPreview) {
            return;
        }
        this.state.loading = true;
        try {
            const formData = new FormData();
            formData.append("csrf_token", odoo.csrf_token);
            formData.append("text", this.state.text);
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
