/** @odoo-module **/
import {Component, onMounted, onWillStart, onWillUnmount, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

// Refresh this often while the page is open (calls in progress change
// quickly; SignalWire's call counts are cached on the server for 5 minutes).
const REFRESH_MS = 60000;

/**
 * The VoIP dashboard: the whole phone system on one page. Draws whatever
 * signalwire.dashboard.get_dashboard_data returns - a status banner,
 * tiles and tables - without knowing which modules supplied them.
 */
export class SignalWireVoipDashboard extends Component {
    static template = "signalwire_voip.VoipDashboard";
    static props = {"*": {optional: true}};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({data: null, loading: false, switching: false});

        onWillStart(() => this.load());
        onMounted(() => {
            this.timer = setInterval(() => this.load(), REFRESH_MS);
        });
        onWillUnmount(() => clearInterval(this.timer));
    }

    async load(refresh = false) {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "signalwire.dashboard",
                "get_dashboard_data",
                [],
                {refresh}
            );
        } finally {
            this.state.loading = false;
        }
    }

    openTile(tile) {
        if (tile.action) {
            this.action.doAction(tile.action);
        }
    }

    openRow(row) {
        if (row.open) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: row.open.res_model,
                res_id: row.open.res_id,
                views: [[row.open.view_id || false, "form"]],
            });
        }
    }

    async setClosed(closed) {
        this.state.switching = true;
        try {
            await this.orm.call("signalwire.dashboard", "set_phones_closed", [closed]);
            await this.load();
        } catch (error) {
            this.notification.add(error.data ? error.data.message : error.message, {
                type: "danger",
            });
        } finally {
            this.state.switching = false;
        }
    }
}

registry.category("actions").add("signalwire_voip_dashboard", SignalWireVoipDashboard);
