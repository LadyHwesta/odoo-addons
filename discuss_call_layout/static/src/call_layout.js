import { reactive, useState } from "@odoo/owl";

import { ACTION_TAGS } from "@mail/core/common/action";
import { Call } from "@mail/discuss/call/common/call";
import { registerCallAction } from "@mail/discuss/call/common/call_actions";
import { CallParticipantCard } from "@mail/discuss/call/common/call_participant_card";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

const STORAGE_KEY = "discuss_call_layout";

/** "gallery" (everyone tiled, the default) or "speaker" (whoever talks fills the screen). */
export const callLayout = reactive({
    value: browser.localStorage.getItem(STORAGE_KEY) === "speaker" ? "speaker" : "gallery",
});

/** Channels where someone clicked a video to pin it: left alone until unpinned. */
const pinnedChannels = new Set();

function isSharingScreen(session) {
    return Boolean(session?.is_screen_sharing_on && session.mainVideoStreamType === "screen");
}

function speakerFor(channel, selfSession) {
    return (
        channel.focusStack?.at?.(-1) ||
        channel.rtc_session_ids.find((s) => s.notEq(selfSession) && s.hasVideo) ||
        channel.rtc_session_ids.find((s) => s.notEq(selfSession)) ||
        selfSession
    );
}

/**
 * Brings the call to the chosen view: gallery clears the spotlight unless a
 * screen is being shared or someone was pinned; speaker puts whoever spoke
 * last (or anyone else) in it.
 */
export function applyCallLayout(channel, store) {
    if (!channel || !store.rtc?.selfSession || channel.notEq(store.rtc.channel)) {
        return;
    }
    const active = channel.activeRtcSession;
    if (callLayout.value === "gallery") {
        if (active && !isSharingScreen(active) && !pinnedChannels.has(channel.id)) {
            channel.activeRtcSession = undefined;
        }
    } else if (!active) {
        const speaker = speakerFor(channel, store.rtc.selfSession);
        if (speaker) {
            channel.activeRtcSession = speaker;
            speaker.mainVideoStreamType = "camera";
        }
    }
}

registerCallAction("call-layout", {
    condition: ({ owner, thread }) => !owner.env.inCallMenu && thread?.isSelfInCall,
    name: () => (callLayout.value === "gallery" ? _t("Speaker view") : _t("Gallery view")),
    icon: () => (callLayout.value === "gallery" ? "fa fa-user" : "fa fa-th-large"),
    onSelected: ({ store, thread }) => {
        callLayout.value = callLayout.value === "gallery" ? "speaker" : "gallery";
        browser.localStorage.setItem(STORAGE_KEY, callLayout.value);
        pinnedChannels.delete(thread.id);
        if (callLayout.value === "speaker") {
            store.settings.useCallAutoFocus = true;
        } else if (!isSharingScreen(thread.activeRtcSession)) {
            thread.activeRtcSession = undefined;
        }
        applyCallLayout(thread, store);
    },
    sequence: 75,
    tags: ACTION_TAGS.CALL_LAYOUT,
});

patch(Call.prototype, {
    setup() {
        super.setup(...arguments);
        this.callLayout = useState(callLayout);
    },
    get visibleMainCards() {
        // Read here so the call re-renders when the view changes, and so the
        // view is put right whenever a screen share starts or stops.
        void this.callLayout.value;
        if (this.isActiveCall) {
            const active = this.channel.activeRtcSession;
            void active?.is_screen_sharing_on;
            void active?.mainVideoStreamType;
            Promise.resolve().then(() => applyCallLayout(this.channel, this.store));
        }
        return super.visibleMainCards;
    },
});

patch(CallParticipantCard.prototype, {
    async onClick(ev) {
        const result = await super.onClick(...arguments);
        const channel = this.rtcSession?.channel;
        if (channel) {
            if (channel.activeRtcSession && !isSharingScreen(channel.activeRtcSession)) {
                pinnedChannels.add(channel.id);
            } else {
                pinnedChannels.delete(channel.id);
            }
        }
        return result;
    },
});
