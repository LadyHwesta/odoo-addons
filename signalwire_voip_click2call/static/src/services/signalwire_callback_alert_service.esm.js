/** @odoo-module **/
import {registry} from "@web/core/registry";
import {user} from "@web/core/user";
import {ScheduleCallbackDialog} from "../components/schedule_callback/schedule_callback_dialog.esm";

/* "Callback requested" alerts. The server sends one when a caller asked
 * for this user (or their call group) and they're free: right away, or as
 * soon as their call or Away ends. The alert stays until acted on: Call
 * now dials from the softphone, Schedule books it in the calendar. When
 * someone else takes it, the server closes it here too. */
export const signalwireCallbackAlertService = {
    dependencies: ["bus_service", "notification", "orm", "dialog", "voip_agent_oca"],
    start(env, {bus_service, notification, orm, dialog, voip_agent_oca: agent}) {
        const open = new Map();

        function close(id) {
            const closeFn = open.get(id);
            open.delete(id);
            if (closeFn) {
                closeFn();
            }
        }

        bus_service.subscribe("signalwire_callback/alert", (payload) => {
            if (open.has(payload.id)) {
                return;
            }
            const lines = [`${payload.caller} asked to be called back`];
            if (payload.for) {
                lines[0] += ` (for ${payload.for})`;
            }
            if (payload.note) {
                lines.push(payload.note);
            }
            const closeFn = notification.add(lines.join(". ") + ".", {
                title: "Callback requested",
                type: "warning",
                sticky: true,
                buttons: [
                    {
                        name: "Call now",
                        primary: true,
                        onClick: async () => {
                            close(payload.id);
                            const number = await orm.call(
                                "signalwire.callback_request",
                                "action_call_now",
                                [[payload.id]]
                            );
                            agent.call({number});
                        },
                    },
                    {
                        name: "Schedule",
                        onClick: () => {
                            close(payload.id);
                            dialog.add(ScheduleCallbackDialog, {
                                requestId: payload.id,
                                callerName: payload.caller,
                                phoneNumber: payload.phone_number,
                                partnerId: payload.partner_id || false,
                                note: payload.note,
                                userId: user.userId,
                            });
                        },
                    },
                ],
                onClose: () => open.delete(payload.id),
            });
            open.set(payload.id, closeFn);
        });

        bus_service.subscribe("signalwire_callback/closed", (payload) => close(payload.id));
        return {};
    },
};

registry.category("services").add("signalwire_callback_alert", signalwireCallbackAlertService);
