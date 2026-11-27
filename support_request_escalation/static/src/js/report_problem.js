import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

/** "Report a problem" in the user menu: the questions in a dialog, with the
 * page the person is on filled in for them. */
function reportProblemItem(env) {
    return {
        type: "item",
        id: "report_problem",
        description: _t("Report a problem"),
        callback: async () => {
            const title = document.title || "";
            await env.services.action.doAction("support_request_escalation.action_support_request_report", {
                additionalContext: {
                    default_page_url: browser.location.href,
                    default_page_title: title,
                    default_user_agent: browser.navigator.userAgent,
                },
            });
        },
        sequence: 45,
    };
}

registry.category("user_menuitems").add("report_problem", reportProblemItem);
