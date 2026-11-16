/** @odoo-module **/
import {browser} from "@web/core/browser/browser";
import {reactive} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {_t} from "@web/core/l10n/translation";

/* Phone presence for a softphone user: Available, Away or Mobile.
 *
 * - Away after the user's own "Away After" minutes without using Odoo,
 *   measured by Odoo's own presence service (shared across tabs).
 * - Alt+Shift+W goes Away at once.
 * - Using Odoo again (mouse, keys, touch) while Away sets Available, after
 *   a short grace so the shortcut's own key press doesn't undo it. Mobile
 *   is only ever changed from the status menu.
 * - The server is the source of truth; every tab follows its bus message.
 */
const CHECK_EVERY_MS = 30 * 1000;
const GRACE_MS = 3000;
const ACTIVITY_EVENTS = ["mousedown", "keydown", "touchstart", "wheel", "mousemove"];

export const signalwirePresenceService = {
    dependencies: ["orm", "presence", "hotkey", "bus_service", "notification"],
    start(env, {orm, presence, hotkey, bus_service, notification}) {
        const state = reactive({
            enabled: false,
            presence: "available",
            autoAwayMinutes: 0,
            hasMobileNumber: false,
        });
        let awaySince = 0;
        let lastActivityCheck = 0;

        async function set(value) {
            if (value === "away") {
                awaySince = Date.now();
            }
            state.presence = value;
            try {
                await orm.silent.call("res.users", "set_signalwire_presence", [value]);
            } catch {
                // Offline for a moment: the next change tries again.
            }
        }

        function onActivity() {
            const now = Date.now();
            if (now - lastActivityCheck < 1000) {
                return;
            }
            lastActivityCheck = now;
            if (state.enabled && state.presence === "away" && now - awaySince > GRACE_MS) {
                set("available");
            }
        }

        function checkIdle() {
            if (
                state.enabled &&
                state.presence === "available" &&
                state.autoAwayMinutes > 0 &&
                presence.getInactivityPeriod() >= state.autoAwayMinutes * 60 * 1000
            ) {
                set("away");
            }
        }

        orm.silent
            .call("res.users", "get_signalwire_presence_info", [])
            .then((info) => {
                if (!info.has_softphone) {
                    return;
                }
                Object.assign(state, {
                    enabled: true,
                    presence: info.presence,
                    autoAwayMinutes: info.auto_away_minutes,
                    hasMobileNumber: info.has_mobile_number,
                });
                awaySince = Date.now();
                for (const name of ACTIVITY_EVENTS) {
                    browser.addEventListener(name, onActivity, {passive: true, capture: true});
                }
                browser.setInterval(checkIdle, CHECK_EVERY_MS);
                hotkey.add(
                    "alt+shift+w",
                    () => {
                        set("away");
                        notification.add(
                            _t("You're Away. Calls skip you until you use Odoo again."),
                            {type: "info"}
                        );
                    },
                    {global: true}
                );
                bus_service.subscribe("signalwire_presence/updated", (payload) => {
                    if (payload.presence === "away" && state.presence !== "away") {
                        awaySince = Date.now();
                    }
                    state.presence = payload.presence;
                });
            })
            .catch(() => {
                // No phone features for this user (or no access): stay off.
            });

        return {state, set};
    },
};

registry.category("services").add("signalwire_presence", signalwirePresenceService);
