import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { CheckInPopup } from "../checkin_popup/checkin_popup";

patch(ControlButtons.prototype, {
    clickEventCheckIn() {
        this.dialog.add(CheckInPopup, {});
    },
});
