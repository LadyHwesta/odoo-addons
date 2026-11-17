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

    async markDone(item, ev) {
        ev.stopPropagation();
        await this.orm.call(item.done.model, item.done.method, [[item.id]]);
        this.state.done[`${item.done.model}-${item.id}`] = true;
        this.notification.add(_t("%(action)s: %(name)s", { action: item.done.label, name: item.name }), {
            type: "success",
        });
    }

    isDone(item) {
        return item.done && this.state.done[`${item.done.model}-${item.id}`];
    }

    joinCall(item, ev) {
        ev.stopPropagation();
        window.open(item.url, "_blank", "noopener");
    }
}

registry.category("actions").add("my_day.dashboard", MyDay);
