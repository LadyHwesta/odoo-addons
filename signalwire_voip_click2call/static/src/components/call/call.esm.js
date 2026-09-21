/** @odoo-module **/
import {Call} from "@voip_oca/components/call/call.esm";
import {patch} from "@web/core/utils/patch";

/* Wires the Transfer popover's new "Check First" button to
 * VoipAgent.startAttendedTransfer (see voip_agent_attended_transfer.
 * esm.js), and adds Complete/Cancel controls for an in-progress
 * consultation call - shown directly on the active-call view since
 * the agent stays on their own call with the colleague the whole
 * time, not inside the transfer popover itself.
 */
patch(Call.prototype, {
    onTransfer(event) {
        if (this.transferPopover.isOpen) {
            return;
        }
        this.transferPopover.open(event.currentTarget, {
            onTransfer: this.onTransferCall.bind(this),
            onCheckFirst: this.onCheckFirstCall.bind(this),
        });
    },
    onCheckFirstCall(number) {
        if (number) {
            this.agent.startAttendedTransfer({number});
        }
    },
    onCompleteAttendedTransfer() {
        this.agent.completeAttendedTransfer();
    },
    onCancelAttendedTransfer() {
        this.agent.cancelAttendedTransfer();
    },
});
