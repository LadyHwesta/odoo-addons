/** @odoo-module **/
import {Component, onWillStart, onWillUnmount, useState} from "@odoo/owl";
import {deserializeDateTime} from "@web/core/l10n/dates";
import {registry} from "@web/core/registry";
import {useOpenChat} from "@mail/core/web/open_chat_hook";
import {useService} from "@web/core/utils/hooks";
import {ScheduleCallbackDialog} from "../schedule_callback/schedule_callback_dialog.esm";

const {DateTime} = luxon;
const TICK_MS = 15 * 1000;

/* The front desk: calls in progress (with the caller's contact and
 * appointments), callback requests, the team's phone status and what
 * they're in now, and today's agenda. Everything comes from one call,
 * res.users.get_signalwire_receptionist_panel_data, refreshed whenever a
 * call, a callback request or someone's status changes (bus). */
export class SignalWireReceptionistPanel extends Component {
    static template = "signalwire_voip_click2call.ReceptionistPanel";
    static props = {"*": {optional: true}};

    setup() {
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.agent = useService("voip_agent_oca");
        this.openChat = useOpenChat("res.users");
        this.state = useState({
            loaded: false,
            calls: [],
            team: [],
            callbacks: [],
            agenda: [],
            closedUntil: false,
            routeTarget: {},
            now: DateTime.now(),
        });

        this._reloadTimer = null;
        this._onBusUpdate = () => {
            // A burst of updates (a call routed, then answered) loads once.
            clearTimeout(this._reloadTimer);
            this._reloadTimer = setTimeout(() => this.loadData(), 300);
        };
        this.busService.subscribe("signalwire_live_call/updated", this._onBusUpdate);
        this._tick = setInterval(() => (this.state.now = DateTime.now()), TICK_MS);
        onWillUnmount(() => {
            this.busService.unsubscribe("signalwire_live_call/updated", this._onBusUpdate);
            clearInterval(this._tick);
            clearTimeout(this._reloadTimer);
        });

        onWillStart(() => this.loadData());
    }

    async loadData() {
        const data = await this.orm.call(
            "res.users",
            "get_signalwire_receptionist_panel_data",
            []
        );
        Object.assign(this.state, {
            loaded: true,
            calls: data.calls,
            team: data.team,
            callbacks: data.callbacks,
            agenda: data.agenda,
            closedUntil: data.closed_until,
            now: DateTime.now(),
        });
    }

    // ---- formatting -------------------------------------------------------

    time(value) {
        return value ? deserializeDateTime(value).toLocaleString(DateTime.TIME_SIMPLE) : "";
    }

    dayAndTime(value) {
        if (!value) {
            return "";
        }
        const dt = deserializeDateTime(value);
        const day = dt.hasSame(this.state.now, "day")
            ? "Today"
            : dt.toLocaleString({weekday: "short", month: "short", day: "numeric"});
        return `${day} ${dt.toLocaleString(DateTime.TIME_SIMPLE)}`;
    }

    waiting(value) {
        if (!value) {
            return "";
        }
        const seconds = Math.max(0, this.state.now.diff(deserializeDateTime(value), "seconds").seconds);
        if (seconds < 60) {
            return "just now";
        }
        const minutes = Math.floor(seconds / 60);
        return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
    }

    ago(value) {
        const waited = this.waiting(value);
        return waited === "just now" ? waited : `${waited} ago`;
    }

    isPast(event) {
        return deserializeDateTime(event.stop) < this.state.now;
    }

    isNow(event) {
        return (
            deserializeDateTime(event.start) <= this.state.now &&
            this.state.now < deserializeDateTime(event.stop)
        );
    }

    // ---- summary ----------------------------------------------------------

    get availableCount() {
        return this.state.team.filter((u) => ["available", "mobile"].includes(u.status)).length;
    }

    get openCallbacks() {
        return this.state.callbacks.filter((c) => c.state !== "scheduled").length;
    }

    get teamChoices() {
        return this.state.team.map((u) => ({id: u.id, name: u.name}));
    }

    // ---- calls ------------------------------------------------------------

    setRouteTarget(callId, value) {
        this.state.routeTarget[callId] = parseInt(value, 10) || false;
    }

    _target(call) {
        const userId = this.state.routeTarget[call.id];
        if (!userId) {
            this.notification.add("Pick a colleague first.", {type: "warning"});
        }
        return userId;
    }

    async _run(promise) {
        try {
            await promise;
        } catch (error) {
            this.notification.add(error.data ? error.data.message : error.message, {
                type: "danger",
            });
        }
    }

    routeCall(call) {
        const userId = this._target(call);
        if (userId) {
            this._run(
                this.orm.call("signalwire.live_call", "action_route_to_user", [[call.id], userId])
            );
        }
    }

    checkFirst(call) {
        const userId = this._target(call);
        if (!userId) {
            return;
        }
        const colleague = this.state.team.find((u) => u.id === userId);
        this._run(
            this.orm
                .call("signalwire.live_call", "action_park", [[call.id], userId])
                .then(() => colleague && this.agent.call({number: colleague.voip_username}))
        );
    }

    sendToVoicemail(call) {
        const userId = this._target(call);
        if (userId) {
            this._run(
                this.orm.call("signalwire.live_call", "action_send_to_voicemail", [
                    [call.id],
                    userId,
                ])
            );
        }
    }

    scheduleForCall(call) {
        this.dialog.add(ScheduleCallbackDialog, {
            callerName: call.caller || call.from_number,
            phoneNumber: call.from_number,
            partnerId: call.partner_id || false,
            users: this.teamChoices,
            userId: this.state.routeTarget[call.id] || call.assigned_id || undefined,
            onScheduled: () => this.loadData(),
        });
    }

    // ---- callbacks --------------------------------------------------------

    scheduleNew() {
        this.dialog.add(ScheduleCallbackDialog, {
            users: this.teamChoices,
            onScheduled: () => this.loadData(),
        });
    }

    scheduleRequest(req) {
        this.dialog.add(ScheduleCallbackDialog, {
            requestId: req.id,
            callerName: req.caller,
            phoneNumber: req.phone_number,
            partnerId: req.partner_id || false,
            note: req.note,
            users: this.teamChoices,
            userId: req.for_id || undefined,
            onScheduled: () => this.loadData(),
        });
    }

    callBack(req) {
        this._run(
            this.orm
                .call("signalwire.callback_request", "action_call_now", [[req.id]])
                .then((number) => this.agent.call({number}))
        );
    }

    claim(req) {
        this._run(this.orm.call("signalwire.callback_request", "action_claim", [[req.id]]));
    }

    complete(req) {
        this._run(this.orm.call("signalwire.callback_request", "action_complete", [[req.id]]));
    }

    // ---- team -------------------------------------------------------------

    messageUser(userId) {
        this.openChat(userId);
    }

    callUser(member) {
        this.agent.call({number: member.voip_username});
    }
}

registry.category("actions").add("signalwire_receptionist_panel", SignalWireReceptionistPanel);
