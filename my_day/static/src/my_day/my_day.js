import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";

const PICKED_KEY = "my_day.companies";

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
        this.state = useState({ day: null, done: {} });
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
