/** @odoo-module */
/*
    Backs the voicemail systray: fetches the current user's unread
    voicemail count + a short preview list, and refreshes instantly
    when the server pings this user's own bus channel (see
    signalwire.voicemail's own _notify_systray - the same
    user._bus_send()-to-partner-channel mechanism core's own
    mail.activity systray badge relies on) rather than polling.
*/
import {registry} from "@web/core/registry";
import {reactive} from "@odoo/owl";

export const signalwireVoicemailService = {
    dependencies: ["orm", "bus_service"],
    start(env, {orm, bus_service}) {
        const state = reactive({count: 0, voicemails: []});

        const refresh = async () => {
            const data = await orm.call("signalwire.voicemail", "get_systray_data", []);
            Object.assign(state, data);
        };

        bus_service.subscribe("signalwire_voicemail/updated", () => refresh());
        refresh();

        return {state, refresh};
    },
};

registry.category("services").add("signalwire_voicemail", signalwireVoicemailService);
