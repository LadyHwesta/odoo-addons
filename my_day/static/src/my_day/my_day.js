import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";

const PICKED_KEY = "my_day.companies";

/** Each section's colour; sections other modules add get one from the rest. */
const SECTION_COLORS = {
    schedule: "#2f6fdb",
    todo: "#7c4dcc",
    phone: "#0f8f84",
    sms: "#0e86a8",
    security: "#c0392b",
    helpdesk: "#e0731a",
    leads: "#d6407a",
    tasks: "#4c5bd4",
    money: "#1e8a4c",
    quotes: "#b7791f",
    events: "#b6389c",
};
const SPARE_COLORS = ["#2a9d8f", "#8a5cd6", "#d1495b", "#3d7dd8", "#c77d1c", "#5a8f29", "#b04aa0", "#1f8fb3"];

/**
 * My Day: the plan for today on the left, what needs attention on the
 * right. The data comes from my.day.get_day(), within the companies
 * selected in the switcher (the context carries them).
 */
export class MyDay extends Component {
    static template = "my_day.MyDay";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ day: null, done: {}, picking: false });
        onWillStart(() => this.load());
    }

    get picked() {
        try {
            return JSON.parse(browser.localStorage.getItem(PICKED_KEY) || "[]");
        } catch {
            return [];
        }
    }

    async load() {
        this.state.day = await this.orm.call("my.day", "get_day", [], { company_ids: this.picked });
    }

    /** Tap a company to see only it (or add it back); none picked = all. */
    async toggleCompany(company) {
        const all = this.state.day.companies;
        let picked = all.filter((c) => c.on).map((c) => c.id);
        if (picked.length === all.length) {
            picked = [company.id];
        } else if (picked.includes(company.id)) {
            picked = picked.filter((id) => id !== company.id);
        } else {
            picked.push(company.id);
        }
        if (!picked.length || picked.length === all.length) {
            picked = [];
        }
        browser.localStorage.setItem(PICKED_KEY, JSON.stringify(picked));
        await this.load();
    }

    sectionColor(section) {
        if (section.color || SECTION_COLORS[section.key]) {
            return section.color || SECTION_COLORS[section.key];
        }
        let hash = 0;
        for (const char of section.key) {
            hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
        }
        return SPARE_COLORS[hash % SPARE_COLORS.length];
    }

    get backgroundStyle() {
        const url = this.state.day?.background;
        return url ? `background-image: url('${url}')` : "";
    }

    async pickBackground(key) {
        this.state.day.background = await this.orm.call("my.day", "set_background", [key]);
        this.state.day.background_key = key;
        this.state.picking = false;
    }

    /** Your own picture: read it in the browser, save it on your user. */
    uploadBackground(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) {
            return;
        }
        if (!file.type.startsWith("image/")) {
            this.notification.add(_t("Pick a picture file (JPEG or PNG)."), { type: "warning" });
            return;
        }
        const reader = new FileReader();
        reader.onload = async () => {
            const image = String(reader.result).split(",")[1];
            this.state.day.background = await this.orm.call("my.day", "set_background", ["custom", image]);
            this.state.day.background_key = "custom";
            this.state.picking = false;
        };
        reader.readAsDataURL(file);
    }

    /** Preferences, on the My Day tab; My Day reloads when it closes. */
    async customize() {
        const action = await this.orm.call("res.users", "action_get", []);
        action.res_id = user.userId; // as the user menu does: your own record
        await this.action.doAction(action, {
            onClose: () => this.load(),
        });
    }

    get plan() {
        return this.state.day.sections.filter((s) => s.column === "plan");
    }

    get attention() {
        return this.state.day.sections.filter((s) => s.column === "attention");
    }

    open(item) {
        if (item.open) {
            return this.openList(item.open);
        }
        const target = item.record || (item.model ? { model: item.model, id: item.id } : null);
        if (!target) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: target.model,
            res_id: target.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openList(more) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: more.name,
            res_model: more.model,
            domain: more.domain,
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    }

    openMore(section) {
        const more = section.more;
        if (more.action) {
            return this.action.doAction(more.action);
        }
        return this.openList(more);
    }

    /** A button on an item: run its method, then dial, remove or reload. */
    async press(item, button, ev) {
        ev.stopPropagation();
        let result = false;
        if (button.method) {
            result = await this.orm.call(button.model, button.method, [[item.id]]);
        }
        if (button.after === "dial") {
            const number = typeof result === "string" && result ? result : button.dial;
            this.dial(number);
            this.state.done[this.key(item)] = true;
        } else if (button.after === "action") {
            if (result && typeof result === "object") {
                await this.action.doAction(result, { onClose: () => this.load() });
            }
        } else if (button.after === "remove") {
            this.state.done[this.key(item)] = true;
            this.notification.add(_t("%(action)s: %(name)s", { action: button.label, name: item.name }), {
                type: "success",
            });
        } else {
            await this.load();
        }
    }

    /** Call through the softphone when there is one, else the device's dialer. */
    dial(number) {
        if (!number) {
            return;
        }
        const agent = this.env.services.voip_agent_oca;
        if (agent) {
            agent.call({ number });
        } else {
            window.location.href = `tel:${number}`;
        }
    }

    key(item) {
        return `${item.model}-${item.id}`;
    }

    isDone(item) {
        return Boolean(this.state.done[this.key(item)]);
    }

    joinCall(item, ev) {
        ev.stopPropagation();
        window.open(item.url, "_blank", "noopener");
    }
}

registry.category("actions").add("my_day.dashboard", MyDay);
