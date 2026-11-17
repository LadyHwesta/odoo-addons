import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { scanBarcode } from "@web/core/barcode/barcode_dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { checkinMessage } from "../checkin_utils";

/**
 * The door list: today's attendees, a search, a camera scan, and how many
 * are in. Checking someone in uses the same rules as scanning a ticket.
 */
export class CheckInPopup extends Component {
    static template = "pos_event_checkin.CheckInPopup";
    static components = { Dialog };
    static props = ["close"];

    setup() {
        this.pos = usePos();
        this.notification = useService("notification");
        this.state = useState({ query: "", events: [], attendees: [], loading: true, last: null });
        this._timer = null;
        onWillStart(() => this.load());
    }

    get title() {
        return _t("Check In");
    }

    async load() {
        const data = await this.pos.data.call("pos.config", "event_checkin_list", [
            this.pos.config.id,
            this.state.query,
        ]);
        this.state.events = data.events;
        this.state.attendees = data.attendees;
        this.state.loading = false;
    }

    onInput(ev) {
        this.state.query = ev.target.value;
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.load(), 250);
    }

    show(result) {
        this.state.last = { ...checkinMessage(result), status: result.status };
    }

    async checkIn(attendee) {
        const result = await this.pos.data.call("pos.config", "event_checkin_registration", [
            this.pos.config.id,
            attendee.id,
        ]);
        this.show(result);
        await this.load();
    }

    async scanWithCamera() {
        let code;
        try {
            code = await scanBarcode(this.env);
        } catch {
            return; // closed, or no camera
        }
        if (!code) {
            return;
        }
        const result = await this.pos.data.call("pos.config", "event_checkin_scan", [
            this.pos.config.id,
            code,
        ]);
        this.show(result);
        await this.load();
    }

    statusLabel(status) {
        return {
            to_check_in: _t("Not in yet"),
            already: _t("In"),
            unconfirmed: _t("Not confirmed"),
        }[status];
    }
}
