import {KanbanController} from "@web/views/kanban/kanban_controller";
import {ListController} from "@web/views/list/list_controller";
import {patch} from "@web/core/utils/patch";

const newDocumentButton = {
    async onNewOnlyofficeDocument() {
        // Files passes the selected folder through the domain, which is where
        // DMS's own upload button finds it too.
        const selected = (this.props.domain || []).find(
            (item) =>
                item.length === 3 &&
                item[0] === "directory_id" &&
                ["=", "child_of"].includes(item[1])
        );
        await this.actionService.doAction("dms_onlyoffice.action_new_document", {
            additionalContext: selected ? {default_directory_id: selected[2]} : {},
            // Must not return the promise: the dialog stays open until this
            // settles, and a reload never settles once the editor has replaced
            // this view.
            onClose: (closeParams) => {
                if (!closeParams?.noReload) {
                    this.model.root.load();
                }
            },
        });
    },
};

patch(KanbanController.prototype, newDocumentButton);
patch(ListController.prototype, newDocumentButton);
