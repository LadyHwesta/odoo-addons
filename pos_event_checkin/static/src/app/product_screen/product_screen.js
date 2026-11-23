import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { checkinMessage } from "../checkin_utils";

patch(ProductScreen.prototype, {
    /**
     * A scanned code that isn't a product may be an event ticket: check
     * the person in. Anything else gets the till's usual "not found".
     */
    async _barcodeProductAction(code) {
        const product = await this._getProductByBarcode(code);
        if (!product && code?.code) {
            const result = await this.pos.data.call("pos.config", "event_checkin_scan", [
                this.pos.config.id,
                code.code,
            ]);
            if (result.status !== "invalid_ticket") {
                const { type, title, message } = checkinMessage(result);
                this.sound.play(type === "success" ? "beep" : "scan-error");
                this.notification.add(message || title, { title, type, sticky: type === "danger" });
                return;
            }
        }
        return super._barcodeProductAction(...arguments);
    },
});
