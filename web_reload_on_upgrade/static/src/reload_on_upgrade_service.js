import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { clearUncommittedChanges } from "@web/webclient/actions/action_service";

const VERSION_URL = "/web_reload_on_upgrade/version";
const CHECK_INTERVAL = 10 * 60 * 1000;
// Least time between two checks on coming back to the window.
const MIN_GAP = 30 * 1000;
// Odoo's service worker keeps a copy of /odoo for offline use.
const SERVICE_WORKER_CACHE = "odoo-sw-cache";

/**
 * Reloads the web client once the server has been upgraded.
 *
 * The page knows the registry fingerprint it started with
 * (session.registry_hash); the server's changes whenever modules are
 * installed or upgraded. They're compared when the window comes back to the
 * front, when the live connection reconnects (it drops while the server
 * restarts) and every ten minutes.
 *
 * When they differ and the window is just coming back to the front, the open
 * record is saved and the page reloads. If the window is in use at that
 * moment, or something can't be saved, or a dialog is open, a notification
 * offers the reload instead, and the next return to the front does it.
 */
export const reloadOnUpgradeService = {
    dependencies: ["bus_service", "notification"],

    start(env, { bus_service, notification }) {
        let checking = false;
        let outdated = false;
        let closeNotification = null;

        async function serverHash() {
            try {
                const response = await browser.fetch(VERSION_URL, {
                    cache: "no-store",
                    credentials: "same-origin",
                });
                if (!response.ok) {
                    return null;
                }
                return (await response.json()).registry_hash || null;
            } catch {
                return null; // offline, or the server is restarting
            }
        }

        async function clearBrowserCaches() {
            try {
                await window.caches?.delete(SERVICE_WORKER_CACHE);
                // Ask for a fresh service worker without waiting for it: the
                // reloaded page registers it again anyway.
                navigator.serviceWorker
                    ?.getRegistration("/odoo")
                    .then((registration) => registration?.update())
                    .catch(() => {});
            } catch {
                // Nothing to clear, or not allowed: the reload still happens.
            }
        }

        function offerReload() {
            if (closeNotification) {
                return;
            }
            closeNotification = notification.add(
                _t("Odoo has been updated. Reload to get the latest screens."),
                {
                    title: _t("Update available"),
                    type: "info",
                    sticky: true,
                    buttons: [
                        {
                            name: _t("Reload"),
                            primary: true,
                            onClick: () => service.reload({ force: true }),
                        },
                    ],
                    onClose: () => (closeNotification = null),
                }
            );
        }

        const service = {
            get outdated() {
                return outdated;
            },

            /**
             * @param {{ returning?: boolean }} [options] returning: the
             *  window has just come back to the front, so reloading now
             *  interrupts nothing.
             * @returns {Promise<boolean>} whether the server has been upgraded
             */
            async check({ returning = false } = {}) {
                if (checking) {
                    return outdated;
                }
                checking = true;
                try {
                    if (!outdated) {
                        const hash = await serverHash();
                        outdated = Boolean(hash) && hash !== session.registry_hash;
                    }
                    if (outdated) {
                        if (returning) {
                            await service.reload();
                        } else {
                            offerReload();
                        }
                    }
                    return outdated;
                } finally {
                    checking = false;
                }
            },

            /**
             * Saves the open record, clears the caches and reloads. Without
             * force, an open dialog or a record that can't be saved stops it
             * and the notification is offered instead.
             */
            async reload({ force = false } = {}) {
                if (!force && document.querySelector(".modal, .o_dialog")) {
                    offerReload();
                    return false;
                }
                if (!(await clearUncommittedChanges(env))) {
                    offerReload();
                    return false;
                }
                await clearBrowserCaches();
                browser.location.reload();
                return true;
            },
        };

        // Coming back to the window: switching back to the app or tab, or
        // clicking into a window that stayed visible behind another app.
        let lastReturn = 0;
        const onReturn = () => {
            if (document.visibilityState !== "visible" || Date.now() - lastReturn < MIN_GAP) {
                return;
            }
            lastReturn = Date.now();
            service.check({ returning: true });
        };
        document.addEventListener("visibilitychange", onReturn);
        browser.addEventListener("focus", onReturn);
        bus_service.addEventListener("BUS:RECONNECT", () => service.check());
        browser.setInterval(() => {
            if (document.visibilityState === "visible") {
                service.check();
            }
        }, CHECK_INTERVAL);

        return service;
    },
};

registry.category("services").add("web_reload_on_upgrade", reloadOnUpgradeService);
