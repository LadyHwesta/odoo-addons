import { _t } from "@web/core/l10n/translation";

/**
 * What the door person sees for a check-in result: a title, a line of
 * detail, and the notification type (green, amber or red).
 */
export function checkinMessage(result) {
    const who = result.name;
    const what = [result.ticket, result.event].filter(Boolean).join(" · ");
    switch (result.status) {
        case "checked_in":
            return { type: "success", title: _t("Checked in: %s", who), message: what };
        case "already":
            return {
                type: "warning",
                title: _t("Already checked in: %s", who),
                message: _t("At %(when)s · %(what)s", { when: result.checked_in_at, what }),
            };
        case "other_day":
            return {
                type: "danger",
                title: _t("Not today: %s", who),
                message: _t("This ticket is for %(event)s on %(date)s.", {
                    event: result.event,
                    date: result.event_date,
                }),
            };
        case "finished":
            return { type: "danger", title: _t("Event is over"), message: what };
        case "cancelled":
            return { type: "danger", title: _t("Cancelled ticket: %s", who), message: what };
        case "unconfirmed":
            return {
                type: "danger",
                title: _t("Not confirmed: %s", who),
                message: _t("This registration was never confirmed (unpaid?). %s", what),
            };
        default:
            return { type: "danger", title: _t("Unknown ticket"), message: "" };
    }
}
