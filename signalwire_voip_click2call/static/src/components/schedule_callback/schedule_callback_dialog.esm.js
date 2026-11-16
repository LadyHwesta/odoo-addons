/** @odoo-module **/
import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {useService} from "@web/core/utils/hooks";

const {DateTime} = luxon;

/* Book a callback in the calendar without leaving the screen: from the
 * receptionist panel (any colleague) or a callback alert (yourself).
 * Creates the calendar event through
 * signalwire.callback_request.schedule_signalwire_callback. */
export class ScheduleCallbackDialog extends Component {
    static template = "signalwire_voip_click2call.ScheduleCallbackDialog";
    static components = {Dialog};
    static props = {
        close: Function,
        requestId: {type: Number, optional: true},
        callerName: {type: String, optional: true},
        phoneNumber: {type: String, optional: true},
        partnerId: {optional: true},
        note: {type: String, optional: true},
        users: {type: Array, optional: true},
        userId: {type: Number, optional: true},
        onScheduled: {type: Function, optional: true},
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        // The next quarter hour at least 15 minutes from now.
        const soon = DateTime.now().plus({minutes: 15});
        const start = soon
            .startOf("hour")
            .plus({minutes: Math.ceil(soon.minute / 15) * 15});
        this.state = useState({
            userId: this.props.userId || (this.props.users && this.props.users[0]?.id) || false,
            start: start.toFormat("yyyy-LL-dd'T'HH:mm"),
            duration: 15,
            note: this.props.note || "",
            phoneNumber: this.props.phoneNumber || "",
            emailCaller: false,
            saving: false,
        });
        this.durations = [15, 30, 45, 60];
    }

    get canEmailCaller() {
        return Boolean(this.props.partnerId);
    }

    async save() {
        if (this.state.saving) {
            return;
        }
        const start = DateTime.fromISO(this.state.start);
        if (!start.isValid) {
            this.notification.add("Pick a date and time.", {type: "warning"});
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("signalwire.callback_request", "schedule_signalwire_callback", [
                {
                    request_id: this.props.requestId || false,
                    user_id: Number(this.state.userId),
                    start: start.toUTC().toFormat("yyyy-LL-dd HH:mm:ss"),
                    duration: Number(this.state.duration),
                    note: this.state.note,
                    phone_number: this.state.phoneNumber,
                    partner_id: this.props.partnerId || false,
                    email_caller: this.state.emailCaller,
                },
            ]);
            this.notification.add("Callback booked in the calendar.", {type: "success"});
            if (this.props.onScheduled) {
                this.props.onScheduled();
            }
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }
}
