/**
 * The public meeting room page.
 *
 * A plain script (not an Odoo module): only this page loads it, with the
 * vendored video SDK, so neither is added to every website page. Settings
 * come from data- attributes on #wrap.
 *
 * - Lobby: speakers check camera, microphone and speaker before joining;
 *   viewers press Start watching (which also lets the browser play sound).
 * - In the room: mute, camera, screen share, settings (switch devices), the
 *   side panel, leave.
 * - Side panel: speakers' chat and viewers' questions (kept in Odoo; speakers'
 *   pages ask for new ones every few seconds, viewers' pages never poll), and
 *   the meeting's documents. Speakers can add documents.
 * - Things everyone must see at once (a question put on screen, "documents
 *   changed") travel as the room's shared notes (meta) on the video service,
 *   so hundreds of viewers never poll Odoo.
 */
(function () {
    "use strict";

    var POLL_MS = 3000;
    var POLL_HIDDEN_MS = 10000;

    function $(selector, scope) {
        return (scope || document).querySelector(selector);
    }
    function $all(selector, scope) {
        return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
    }
    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (text !== undefined && text !== null) {
            node.textContent = text;
        }
        return node;
    }
    function timeOf(utc) {
        // Odoo sends "YYYY-MM-DD HH:MM:SS" in UTC.
        var date = new Date(String(utc).replace(" ", "T") + "Z");
        return isNaN(date) ? "" : date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }

    function init() {
        var page = document.getElementById("wrap");
        var root = document.getElementById("o_meeting_root");
        if (!page || !root || !page.dataset.seat) {
            return;
        }
        var state = {
            page: page,
            root: root,
            speaker: page.dataset.role === "speaker",
            seat: page.dataset.seat,
            documentsVersion: page.dataset.documentsVersion || "",
            maxUploadMb: parseInt(page.dataset.maxUploadMb, 10) || 25,
            room: null,
            meta: {},
            lastMessageId: 0,
            questions: {},
            seenChat: 0,
            pollTimer: null,
            left: false,
        };
        state.say = function (text) {
            $("#o_meeting_status").textContent = text || "";
        };
        if (!root.dataset.roomToken || typeof SignalWire === "undefined") {
            state.say("The meeting couldn't start. Please reload the page.");
            return;
        }
        tabs(state);
        devices(state);
        documents(state);
        if (state.speaker) {
            chat(state);
        } else {
            ask(state);
        }
        var enter = $('[data-action="enter"]');
        enter.addEventListener("click", function () {
            enter.disabled = true;
            join(state).catch(function () {
                enter.disabled = false;
            });
        });
    }

    // -- Tabs and the side panel ------------------------------------------------

    function tabs(state) {
        $all(".o_mr_tab").forEach(function (tab) {
            tab.addEventListener("click", function () {
                showTab(tab.dataset.tab);
                if (tab.dataset.tab === "chat") {
                    state.seenChat = state.chatCount || 0;
                    setCount("chat", 0);
                }
            });
        });
    }
    function showTab(name) {
        $all(".o_mr_tab").forEach(function (tab) {
            tab.setAttribute("aria-selected", tab.dataset.tab === name ? "true" : "false");
        });
        $all(".o_mr_tabpanel").forEach(function (panel) {
            panel.hidden = panel.dataset.panel !== name;
        });
    }
    function activeTab() {
        var tab = $('.o_mr_tab[aria-selected="true"]');
        return tab ? tab.dataset.tab : "";
    }
    function setCount(name, value) {
        var badge = $('[data-count="' + name + '"]');
        if (badge) {
            badge.textContent = value ? String(value) : "";
            badge.hidden = !value;
        }
    }

    // -- Devices: lobby preview, level meter, settings ----------------------------

    function devices(state) {
        state.choice = {
            videoinput: localStorage.getItem("o_meeting_videoinput") || "",
            audioinput: localStorage.getItem("o_meeting_audioinput") || "",
            audiooutput: localStorage.getItem("o_meeting_audiooutput") || "",
        };
        var canPickSpeaker = "setSinkId" in HTMLMediaElement.prototype;
        $all(".o_mr_speaker_field").forEach(function (field) {
            field.hidden = !canPickSpeaker;
        });
        $all("select[data-device]").forEach(function (select) {
            select.addEventListener("change", function () {
                pickDevice(state, select.dataset.device, select.value);
            });
        });
        navigator.mediaDevices && navigator.mediaDevices.addEventListener &&
            navigator.mediaDevices.addEventListener("devicechange", function () {
                fillDevices(state);
            });
        if (state.speaker) {
            $("#o_meeting_join_cam").addEventListener("change", function () {
                startPreview(state);
            });
            startPreview(state);
        } else {
            fillDevices(state);
        }
        var dialog = $("#o_meeting_settings");
        $('[data-action="settings"]').addEventListener("click", function () {
            fillDevices(state);
            if (dialog.showModal) {
                dialog.showModal();
            } else {
                dialog.setAttribute("open", "open");
            }
            if (state.speaker && state.room && state.room.localStream) {
                meter(state, state.room.localStream);
            }
        });
        dialog.addEventListener("close", function () {
            if (state.room) {
                stopMeter(state);
            }
        });
    }

    function fillDevices(state) {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
            return Promise.resolve();
        }
        return navigator.mediaDevices.enumerateDevices().then(function (list) {
            $all("select[data-device]").forEach(function (select) {
                var kind = select.dataset.device;
                var options = list.filter(function (d) {
                    return d.kind === kind;
                });
                select.textContent = "";
                if (!options.length) {
                    select.appendChild(el("option", "", kind === "videoinput" ? "No camera found"
                        : kind === "audioinput" ? "No microphone found" : "Default speaker"));
                    select.value = "";
                    return;
                }
                options.forEach(function (d, i) {
                    var label = d.label || (kind === "videoinput" ? "Camera " : kind === "audioinput"
                        ? "Microphone " : "Speaker ") + (i + 1);
                    var option = el("option", "", label);
                    option.value = d.deviceId;
                    select.appendChild(option);
                });
                var wanted = state.choice[kind];
                if (wanted && options.some(function (d) { return d.deviceId === wanted; })) {
                    select.value = wanted;
                } else {
                    state.choice[kind] = select.value;
                }
            });
        });
    }

    function pickDevice(state, kind, deviceId) {
        state.choice[kind] = deviceId;
        localStorage.setItem("o_meeting_" + kind, deviceId);
        $all('select[data-device="' + kind + '"]').forEach(function (select) {
            select.value = deviceId;
        });
        var room = state.room;
        if (!room) {
            if (kind !== "audiooutput") {
                startPreview(state);
            }
            return;
        }
        var done;
        if (kind === "videoinput") {
            done = room.updateCamera({ deviceId: deviceId });
        } else if (kind === "audioinput") {
            done = room.updateMicrophone({ deviceId: deviceId }).then(function () {
                if (room.localStream) {
                    meter(state, room.localStream);
                }
            });
        } else {
            done = room.updateSpeaker({ deviceId: deviceId });
        }
        Promise.resolve(done).catch(function () {
            state.say("Couldn't switch to that device. Is it still connected?");
        });
    }

    function constraint(state, kind) {
        var id = state.choice[kind];
        return id ? { deviceId: { exact: id } } : true;
    }

    function stopPreview(state) {
        if (state.preview) {
            state.preview.getTracks().forEach(function (t) { t.stop(); });
            state.preview = null;
        }
        stopMeter(state);
    }

    function startPreview(state) {
        stopPreview(state);
        var camOn = $("#o_meeting_join_cam").checked;
        var video = $("#o_meeting_preview");
        $(".o_mr_preview_off").hidden = camOn;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            state.say("This browser can't use a camera or microphone. Try Chrome, Edge, Firefox or Safari.");
            return;
        }
        navigator.mediaDevices.getUserMedia({
            audio: constraint(state, "audioinput"),
            video: camOn ? constraint(state, "videoinput") : false,
        }).then(function (stream) {
            state.preview = stream;
            video.srcObject = camOn ? stream : null;
            meter(state, stream);
            state.say("");
            return fillDevices(state);
        }).catch(function (error) {
            if (state.choice.videoinput || state.choice.audioinput) {
                // A remembered device that's gone: try the defaults once.
                state.choice.videoinput = "";
                state.choice.audioinput = "";
                return startPreview(state);
            }
            state.say(error && error.name === "NotAllowedError"
                ? "Your browser blocked the camera or microphone. Allow them (the icon in the address bar), then reload."
                : "Couldn't open your camera or microphone. Check it's connected and not used by another app.");
            fillDevices(state);
        });
    }

    /** The green bar under Microphone: shows the mic is picking you up. */
    function meter(state, stream) {
        stopMeter(state);
        var track = stream && stream.getAudioTracks()[0];
        var Context = window.AudioContext || window.webkitAudioContext;
        if (!track || !Context) {
            return;
        }
        var context = new Context();
        var analyser = context.createAnalyser();
        analyser.fftSize = 512;
        context.createMediaStreamSource(new MediaStream([track])).connect(analyser);
        var data = new Uint8Array(analyser.fftSize);
        var bars = $all(".o_mr_level_bar");
        var tick = function () {
            analyser.getByteTimeDomainData(data);
            var peak = 0;
            for (var i = 0; i < data.length; i++) {
                peak = Math.max(peak, Math.abs(data[i] - 128));
            }
            var width = Math.min(100, Math.round(peak / 128 * 250)) + "%";
            bars.forEach(function (bar) { bar.style.width = width; });
            state.meterFrame = requestAnimationFrame(tick);
        };
        state.meterContext = context;
        if (context.state === "suspended") {
            // Browsers start sound only after a click on the page.
            context.resume().catch(function () {});
            document.addEventListener("click", function () {
                context.state === "suspended" && context.resume().catch(function () {});
            }, { once: true });
        }
        tick();
    }
    function stopMeter(state) {
        if (state.meterFrame) {
            cancelAnimationFrame(state.meterFrame);
            state.meterFrame = null;
        }
        if (state.meterContext) {
            state.meterContext.close();
            state.meterContext = null;
        }
        $all(".o_mr_level_bar").forEach(function (bar) { bar.style.width = "0"; });
    }

    // -- Joining the room -----------------------------------------------------------

    function join(state) {
        var micOn = state.speaker && $("#o_meeting_join_mic").checked;
        var camOn = state.speaker && $("#o_meeting_join_cam").checked;
        stopPreview(state);
        state.say("Connecting...");
        var room = new SignalWire.Video.RoomSession({
            token: state.root.dataset.roomToken,
            rootElement: state.root,
            // Viewers don't send anything, so they aren't asked for a camera or microphone.
            audio: state.speaker ? constraint(state, "audioinput") : false,
            video: state.speaker ? constraint(state, "videoinput") : false,
        });
        state.room = room;
        // Shown before joining, so the video lays out at its real size.
        $("#o_meeting_lobby").hidden = true;
        state.root.hidden = false;
        room.on("room.joined", function (event) {
            $(".o_mr_controls").hidden = false;
            state.say(state.speaker ? "You're in. Others can see and hear you." : "");
            var session = event && (event.room_session || event.room);
            applyMeta(state, (session && session.meta) || {});
            if (state.choice.audiooutput && "setSinkId" in HTMLMediaElement.prototype) {
                Promise.resolve(room.updateSpeaker({ deviceId: state.choice.audiooutput })).catch(function () {});
            }
            if (state.speaker) {
                if (!micOn) {
                    room.audioMute().then(function () { setMic(state, true); });
                }
                if (!camOn) {
                    room.videoMute().then(function () { setCamera(state, true); });
                }
                poll(state);
            }
        });
        room.on("room.updated", function (event) {
            if (event && event.room && event.room.meta) {
                applyMeta(state, event.room.meta);
            }
        });
        room.on("member.talking", function (event) {
            var member = event && event.member;
            if (member && member.id === room.memberId) {
                var mic = $('[data-action="mic"]');
                mic && mic.classList.toggle("o_mr_talking", !!member.talking);
            }
        });
        room.on("destroy", function () {
            if (!state.left) {
                state.say("The meeting has ended.");
                stopPolling(state);
            }
        });
        controls(state);
        return room.join().catch(function (error) {
            state.room = null;
            state.root.hidden = true;
            $("#o_meeting_lobby").hidden = false;
            state.say(state.speaker
                ? "Couldn't join the meeting. Check your camera and microphone are allowed, then try again."
                : "Couldn't join: the meeting may be full or not started yet. Please try again in a few minutes.");
            if (state.speaker) {
                startPreview(state);
            }
            throw error;
        });
    }

    // -- Control bar ------------------------------------------------------------------

    function setMic(state, muted) {
        state.muted = muted;
        var button = $('[data-action="mic"]');
        button.setAttribute("aria-pressed", muted ? "true" : "false");
        button.classList.toggle("o_mr_off", muted);
        $("i", button).className = muted ? "fa fa-microphone-slash" : "fa fa-microphone";
        $("span", button).textContent = muted ? "Unmute" : "Mute";
    }
    function setCamera(state, off) {
        state.cameraOff = off;
        var button = $('[data-action="camera"]');
        button.setAttribute("aria-pressed", off ? "true" : "false");
        button.classList.toggle("o_mr_off", off);
        $("span", button).textContent = off ? "Start Camera" : "Stop Camera";
    }

    function controls(state) {
        if (state.controlsReady) {
            return;
        }
        state.controlsReady = true;
        var on = function (action, handler) {
            var button = $('.o_mr_controls [data-action="' + action + '"]');
            if (!button) {
                return;
            }
            button.addEventListener("click", function () {
                if (!state.room) {
                    return;
                }
                button.disabled = true;
                Promise.resolve(handler(state.room, button)).catch(function () {
                    state.say("That didn't work. Please try again.");
                }).finally(function () {
                    button.disabled = false;
                });
            });
        };
        on("mic", function (room) {
            return (state.muted ? room.audioUnmute() : room.audioMute()).then(function () {
                setMic(state, !state.muted);
            });
        });
        on("camera", function (room) {
            return (state.cameraOff ? room.videoUnmute() : room.videoMute()).then(function () {
                setCamera(state, !state.cameraOff);
            });
        });
        on("screen", function (room, button) {
            var label = $("span", button);
            if (state.screen) {
                return state.screen.leave().then(function () {
                    state.screen = null;
                    label.textContent = "Share Screen";
                    button.setAttribute("aria-pressed", "false");
                });
            }
            return room.startScreenShare({ audio: false, video: true }).then(function (share) {
                state.screen = share;
                label.textContent = "Stop Sharing";
                button.setAttribute("aria-pressed", "true");
                // Stopped from the browser's own "Stop sharing" bar.
                share.on && share.on("room.left", function () {
                    state.screen = null;
                    label.textContent = "Share Screen";
                    button.setAttribute("aria-pressed", "false");
                });
            });
        });
        $('[data-action="panel"]').addEventListener("click", function (event) {
            var closed = state.page.classList.toggle("o_mr_panel_closed");
            event.currentTarget.setAttribute("aria-pressed", closed ? "false" : "true");
        });
        on("leave", function (room) {
            state.left = true;
            return room.leave().then(function () {
                stopPolling(state);
                state.root.hidden = true;
                $(".o_mr_controls").hidden = true;
                state.say("You've left the meeting. Reload the page to join again.");
            });
        });
    }

    // -- Shared notes: questions on screen, documents changed ------------------------

    function applyMeta(state, meta) {
        state.meta = meta || {};
        var banner = $("#o_meeting_banner");
        var shown = state.meta.on_screen;
        if (shown && shown.body) {
            $('[data-field="author"]', banner).textContent = shown.author || "";
            $('[data-field="body"]', banner).textContent = shown.body;
            banner.hidden = false;
        } else {
            banner.hidden = true;
        }
        $all(".o_mr_msg[data-id]").forEach(function (item) {
            item.classList.toggle("o_mr_on_screen", !!shown && String(shown.id) === item.dataset.id);
        });
        var version = state.meta.documents_version;
        if (version !== undefined && version !== state.documentsVersion && !state.speaker) {
            // Spread hundreds of viewers' requests over a few seconds.
            setTimeout(function () { refreshDocuments(state); }, Math.random() * 5000);
        }
    }

    function updateMeta(state, changes) {
        if (!state.room) {
            return Promise.resolve();
        }
        return Promise.resolve(state.room.updateMeta(changes)).then(function () {
            Object.assign(state.meta, changes);
            applyMeta(state, state.meta);
        });
    }

    // -- Speakers: chat and questions -------------------------------------------------

    function api(state, action, body) {
        return fetch("/meeting/room/" + state.seat + "/" + action, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body || {}),
            credentials: "same-origin",
        }).then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (data) {
                data.status = response.status;
                return data;
            });
        });
    }

    function chat(state) {
        var form = $('[data-form="chat"]');
        var box = $("textarea", form);
        form.addEventListener("submit", function (event) {
            event.preventDefault();
            sendFrom(state, form, box);
        });
        box.addEventListener("keydown", function (event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendFrom(state, form, box);
            }
        });
        var clear = $('[data-action="clear-banner"]');
        clear && clear.addEventListener("click", function () {
            updateMeta(state, { on_screen: false }).catch(function () {
                state.say("Couldn't take the question down. Please try again.");
            });
        });
    }

    function sendFrom(state, form, box) {
        var text = box.value.trim();
        var button = $('button[type="submit"]', form);
        if (!text || button.disabled) {
            return;
        }
        button.disabled = true;
        api(state, "send", { body: text }).then(function (data) {
            if (data.status === 429) {
                state.say(state.speaker ? "One moment..." : "Please wait a few seconds before asking again.");
                return;
            }
            if (!data.message) {
                state.say("Couldn't send. Please try again.");
                return;
            }
            box.value = "";
            state.say(state.speaker ? "" : "Sent. The speakers will see your question.");
            if (state.speaker) {
                addMessages(state, [data.message]);
            } else {
                var item = el("li", "o_mr_msg");
                var head = el("div", "o_mr_msg_head");
                head.appendChild(el("b", "", "You asked"));
                head.appendChild(el("span", "", timeOf(data.message.time)));
                item.appendChild(head);
                item.appendChild(el("p", "", data.message.body));
                $('[data-list="mine"]').prepend(item);
            }
        }).catch(function () {
            state.say("Couldn't send. Check your connection and try again.");
        }).finally(function () {
            button.disabled = false;
        });
    }

    function poll(state) {
        if (state.left) {
            return;
        }
        api(state, "poll", { after: state.lastMessageId, documents_version: state.documentsVersion })
            .then(function (data) {
                if (data.status === 403) {
                    stopPolling(state);
                    return;
                }
                addMessages(state, data.messages || []);
                (data.answered || []).forEach(function (id) {
                    markAnswered(state, id, true);
                });
                if (data.documents) {
                    showDocuments(state, data.documents, data.documents_version);
                }
                if (data.documents_version !== undefined && state.room
                        && state.meta.documents_version !== data.documents_version) {
                    // Tell viewers' pages to fetch the new list.
                    updateMeta(state, { documents_version: data.documents_version }).catch(function () {});
                }
            })
            .catch(function () {})
            .finally(function () {
                if (!state.left) {
                    state.pollTimer = setTimeout(function () { poll(state); },
                        document.hidden ? POLL_HIDDEN_MS : POLL_MS);
                }
            });
    }
    function stopPolling(state) {
        clearTimeout(state.pollTimer);
        state.left = true;
    }

    function addMessages(state, messages) {
        messages.forEach(function (m) {
            state.lastMessageId = Math.max(state.lastMessageId, m.id);
            if ($('.o_mr_msg[data-id="' + m.id + '"]')) {
                return;
            }
            var item = el("li", "o_mr_msg");
            item.dataset.id = String(m.id);
            var head = el("div", "o_mr_msg_head");
            head.appendChild(el("b", "", m.author));
            head.appendChild(el("span", "", timeOf(m.time)));
            item.appendChild(head);
            item.appendChild(el("p", "", m.body));
            if (m.kind === "question") {
                var actions = el("div", "o_mr_msg_actions");
                var show = el("button", "o_mr_btn", "Show everyone");
                show.type = "button";
                show.addEventListener("click", function () {
                    updateMeta(state, { on_screen: { id: m.id, author: m.author, body: m.body } })
                        .catch(function () {
                            state.say("Couldn't show the question. Please try again.");
                        });
                });
                var done = el("button", "o_mr_btn o_mr_btn_quiet", "Mark answered");
                done.type = "button";
                done.addEventListener("click", function () {
                    var answered = !state.questions[m.id];
                    api(state, "answered", { id: m.id, answered: answered }).then(function () {
                        markAnswered(state, m.id, answered);
                    });
                });
                actions.appendChild(show);
                actions.appendChild(done);
                item.appendChild(actions);
                $('[data-list="questions"]').appendChild(item);
                $('[data-empty="questions"]').hidden = true;
                state.questions[m.id] = false;
                if (m.answered) {
                    markAnswered(state, m.id, true);
                }
            } else {
                var list = $('[data-list="chat"]');
                list.appendChild(item);
                list.scrollTop = list.scrollHeight;
                state.chatCount = (state.chatCount || 0) + 1;
                if (activeTab() !== "chat") {
                    setCount("chat", state.chatCount - state.seenChat);
                } else {
                    state.seenChat = state.chatCount;
                }
            }
            if (state.meta.on_screen && state.meta.on_screen.id === m.id) {
                item.classList.add("o_mr_on_screen");
            }
        });
        updateQuestionCount(state);
    }

    function markAnswered(state, id, answered) {
        if (!(id in state.questions)) {
            return;
        }
        state.questions[id] = answered;
        var item = $('.o_mr_msg[data-id="' + id + '"]');
        if (item) {
            item.classList.toggle("o_mr_answered", answered);
            $(".o_mr_btn_quiet", item).textContent = answered ? "Not answered" : "Mark answered";
        }
        updateQuestionCount(state);
    }
    function updateQuestionCount(state) {
        var open = Object.keys(state.questions).filter(function (id) { return !state.questions[id]; }).length;
        setCount("questions", open);
    }

    // -- Viewers: asking ----------------------------------------------------------------

    function ask(state) {
        var form = $('[data-form="ask"]');
        var box = $("textarea", form);
        form.addEventListener("submit", function (event) {
            event.preventDefault();
            sendFrom(state, form, box);
        });
    }

    // -- Documents ------------------------------------------------------------------------

    function documents(state) {
        var form = $('[data-form="upload"]');
        if (!form) {
            return;
        }
        var input = $('input[type="file"]', form);
        input.addEventListener("change", function () {
            var file = input.files && input.files[0];
            if (!file) {
                return;
            }
            if (file.size > state.maxUploadMb * 1024 * 1024) {
                state.say("That file is too large: the limit is " + state.maxUploadMb + " MB.");
                input.value = "";
                return;
            }
            var data = new FormData();
            data.append("file", file);
            state.say("Adding " + file.name + "...");
            fetch("/meeting/room/" + state.seat + "/upload", {
                method: "POST", body: data, credentials: "same-origin",
            }).then(function (response) {
                return response.json().then(function (json) {
                    if (!response.ok || !json.documents) {
                        throw new Error(json.error || "upload");
                    }
                    showDocuments(state, json.documents, json.documents_version);
                    state.say("Added " + file.name + ". Everyone in the meeting can open it.");
                    if (state.room) {
                        updateMeta(state, { documents_version: json.documents_version }).catch(function () {});
                    }
                });
            }).catch(function () {
                state.say("Couldn't add that document. Please try again.");
            }).finally(function () {
                input.value = "";
            });
        });
    }

    function refreshDocuments(state) {
        fetch("/meeting/room/" + state.seat + "/documents", { credentials: "same-origin" })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.documents) {
                    showDocuments(state, data.documents, data.documents_version);
                }
            })
            .catch(function () {});
    }

    function showDocuments(state, docs, version) {
        state.documentsVersion = version;
        var list = $('[data-list="documents"]');
        list.textContent = "";
        docs.forEach(function (doc) {
            var item = el("li");
            var link = el("a", "", doc.name);
            link.href = doc.url;
            link.target = "_blank";
            link.rel = "noopener";
            item.appendChild(link);
            list.appendChild(item);
        });
        $('[data-empty="documents"]').hidden = docs.length > 0;
        setCount("documents", docs.length);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
