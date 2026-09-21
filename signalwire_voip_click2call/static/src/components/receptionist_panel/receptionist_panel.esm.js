/** @odoo-module **/
import {Component, onWillStart, onWillUnmount, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useOpenChat} from "@mail/core/web/open_chat_hook";
import {useService} from "@web/core/utils/hooks";

const CALL_STATE_LABELS = {idle: "Available", ringing: "Ringing", on_call: "On a Call"};

export class SignalWireReceptionistPanel extends Component {
    static template = "signalwire_voip_click2call.ReceptionistPanel";
    static props = {"*": {optional: true}};

    setup() {
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.notification = useService("notification");
        this.agent = useService("voip_agent_oca");
        this.openChat = useOpenChat("res.users");
        this.state = useState({roster: [], calls: [], routeTarget: {}});
        this.callStateLabels = CALL_STATE_LABELS;

        this._onBusUpdate = () => this.loadData();
        this.busService.subscribe("signalwire_live_call/updated", this._onBusUpdate);
        onWillUnmount(() =>
            this.busService.unsubscribe("signalwire_live_call/updated", this._onBusUpdate)
        );

        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.state.roster = await this.orm.call(
            "res.users",
            "get_signalwire_receptionist_roster",
            []
        );
        this.state.calls = await this.orm.searchRead(
            "signalwire.live_call",
            [["state", "in", ["ringing", "parked", "connected"]]],
            ["from_number", "assigned_user_id", "state"],
            {order: "create_date desc"}
        );
    }

    get availableRoster() {
        return this.state.roster.filter((user) => user.has_softphone);
    }

    messageUser(userId) {
        this.openChat(userId);
    }

    setRouteTarget(callId, userId) {
        this.state.routeTarget[callId] = userId;
    }

    async routeCall(call) {
        const userId = this.state.routeTarget[call.id];
        if (!userId) {
            return;
        }
        try {
            await this.orm.call("signalwire.live_call", "action_route_to_user", [
                [call.id],
                userId,
            ]);
        } catch (error) {
            this.notification.add(error.data ? error.data.message : error.message, {
                type: "danger",
            });
        }
    }

    async checkFirst(call) {
        const userId = this.state.routeTarget[call.id];
        if (!userId) {
            return;
        }
        const colleague = this.state.roster.find((u) => u.id === userId);
        try {
            await this.orm.call("signalwire.live_call", "action_park", [[call.id]]);
            if (colleague && colleague.has_softphone) {
                this.agent.call({number: colleague.voip_username});
            }
        } catch (error) {
            this.notification.add(error.data ? error.data.message : error.message, {
                type: "danger",
            });
        }
    }

    async sendToVoicemail(call) {
        const userId = this.state.routeTarget[call.id];
        if (!userId) {
            return;
        }
        try {
            await this.orm.call("signalwire.live_call", "action_send_to_voicemail", [
                [call.id],
                userId,
            ]);
        } catch (error) {
            this.notification.add(error.data ? error.data.message : error.message, {
                type: "danger",
            });
        }
    }
}

registry.category("actions").add("signalwire_receptionist_panel", SignalWireReceptionistPanel);
