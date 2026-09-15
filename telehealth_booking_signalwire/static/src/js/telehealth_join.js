/**
 * Plain script, deliberately NOT an Odoo/Owl module and NOT loaded
 * through web.assets_frontend - the vendored SignalWire SDK is 221KB
 * and only this one join page ever needs it, so both scripts are
 * loaded directly by the join page's own QWeb template instead of
 * site-wide. Reads its config from data-* attributes on the root
 * element rather than inline-templated JS, keeping the actual script
 * a plain static file.
 */
(function () {
    'use strict';

    function init() {
        var root = document.getElementById('telehealth-video-root');
        if (!root) {
            return;
        }
        var token = root.dataset.roomToken;
        if (!token || typeof SignalWire === 'undefined') {
            root.textContent = 'Could not start the video call - please refresh the page.';
            return;
        }

        var statusEl = document.getElementById('telehealth-video-status');
        var roomSession = new SignalWire.Video.RoomSession({
            token: token,
            rootElement: root,
        });

        roomSession.on('room.joined', function () {
            if (statusEl) {
                statusEl.textContent = '';
            }
        });
        roomSession.on('destroy', function () {
            if (statusEl) {
                statusEl.textContent = 'Call ended.';
            }
        });

        roomSession.join().catch(function (error) {
            if (statusEl) {
                statusEl.textContent = 'Could not join the call: ' + (error && error.message ? error.message : error);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
