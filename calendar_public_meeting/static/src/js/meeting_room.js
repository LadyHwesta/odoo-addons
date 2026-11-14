/**
 * A plain script (not an Odoo module): only the meeting room page loads it,
 * with the vendored video SDK, so neither is added to every website page.
 * Settings come from data- attributes on the room element.
 */
(function () {
    "use strict";

    function init() {
        var root = document.getElementById("o_meeting_root");
        var status = document.getElementById("o_meeting_status");
        if (!root) {
            return;
        }
        var say = function (text) {
            if (status) {
                status.textContent = text;
            }
        };
        if (!root.dataset.roomToken || typeof SignalWire === "undefined") {
            say("The meeting couldn't start. Please reload the page.");
            return;
        }
        var viewer = root.dataset.role === "viewer";
        var room = new SignalWire.Video.RoomSession({
            token: root.dataset.roomToken,
            rootElement: root,
            // Viewers don't send anything, so they aren't asked for a camera or microphone.
            audio: !viewer,
            video: !viewer,
        });
        room.on("room.joined", function () {
            say(viewer ? "" : "You're in. Others can see and hear you.");
        });
        controls(room, say);
        room.on("destroy", function () {
            say("The meeting has ended.");
        });
        room.join().catch(function () {
            say(viewer
                ? "Couldn't join: the meeting may be full or not started yet. Please try again in a few minutes."
                : "Couldn't join the meeting. Please reload the page and try again.");
        });
    }

    /** The buttons under the video: mute, camera, screen share, leave. */
    function controls(room, say) {
        var muted = false, cameraOff = false, screen = null;
        var button = function (action) {
            return document.querySelector('.o_meeting_controls [data-action="' + action + '"]');
        };
        var on = function (action, handler) {
            var el = button(action);
            if (el) {
                el.addEventListener("click", function () {
                    el.disabled = true;
                    Promise.resolve(handler(el)).catch(function () {
                        say("That didn't work. Please try again.");
                    }).finally(function () {
                        el.disabled = false;
                    });
                });
            }
        };
        on("mic", function (el) {
            return (muted ? room.audioUnmute() : room.audioMute()).then(function () {
                muted = !muted;
                el.textContent = muted ? "Unmute" : "Mute";
            });
        });
        on("camera", function (el) {
            return (cameraOff ? room.videoUnmute() : room.videoMute()).then(function () {
                cameraOff = !cameraOff;
                el.textContent = cameraOff ? "Start Camera" : "Stop Camera";
            });
        });
        on("screen", function (el) {
            if (screen) {
                return screen.leave().then(function () {
                    screen = null;
                    el.textContent = "Share Screen";
                });
            }
            return room.startScreenShare({ audio: false, video: true }).then(function (share) {
                screen = share;
                el.textContent = "Stop Sharing Screen";
            });
        });
        on("leave", function () {
            return room.leave().then(function () {
                say("You've left the meeting.");
                document.querySelectorAll(".o_meeting_controls button").forEach(function (b) {
                    b.classList.add("d-none");
                });
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
