/** @odoo-module **/
import {Transfer} from "@voip_oca/components/transfer/transfer.esm";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

/* voip_oca's own Transfer popover is a raw text box - whatever's
 * typed goes straight into the SIP URI as-is. Adds a colleague
 * search (backed by res.users.search_signalwire_colleagues) so
 * picking a name resolves to that colleague's real SIP username,
 * and a second "Check First" action alongside the existing immediate
 * "Transfer" (blind) button - completing an attended transfer's own
 * consultation-call flow is driven from the softphone's own active-
 * call view (see call.esm.js's own patch), not from this popover,
 * which only starts it.
 */
patch(Transfer.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.colleagues = [];
    },
    async onFocusInput() {
        if (this.colleagues.length) {
            return;
        }
        this.colleagues = await this.orm.call(
            "res.users",
            "search_signalwire_colleagues",
            [""]
        );
    },
    _resolveNumber() {
        const typed = this.state.value.trim();
        const match = this.colleagues.find(
            (colleague) => colleague.name.toLowerCase() === typed.toLowerCase()
        );
        return match ? match.voip_username : typed;
    },
    transfer() {
        this.props.onTransfer(this._resolveNumber());
        this.props.close();
    },
    checkFirst() {
        this.props.onCheckFirst(this._resolveNumber());
        this.props.close();
    },
});
