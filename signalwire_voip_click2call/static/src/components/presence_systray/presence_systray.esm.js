/** @odoo-module **/
import {Component, useState} from "@odoo/owl";
import {Dropdown} from "@web/core/dropdown/dropdown";
import {isMacOS} from "@web/core/browser/feature_detection";
import {DropdownItem} from "@web/core/dropdown/dropdown_item";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

/* The phone status menu in the top bar: shows Available / Away / Mobile
 * and changes it. Only shown to users with a softphone. */
export class SignalwirePresenceSystray extends Component {
    static template = "signalwire_voip_click2call.PresenceSystray";
    static components = {Dropdown, DropdownItem};
    static props = {};

    setup() {
        this.presence = useService("signalwire_presence");
        // Subscribe: the service fills this in after start-up.
        this.state = useState(this.presence.state);
        this.options = [
            {value: "available", label: "Available", hint: "Calls ring as usual."},
            {value: "away", label: "Away", hint: `Calls skip you. ${isMacOS() ? "Control" : "Alt"}+Shift+W.`},
            {value: "mobile", label: "Mobile", hint: "Rings the mobile app and your mobile number."},
        ];
    }

    get current() {
        return this.options.find((o) => o.value === this.state.presence) || this.options[0];
    }
}

registry
    .category("systray")
    .add("signalwire_presence_systray", {Component: SignalwirePresenceSystray}, {sequence: 25});
