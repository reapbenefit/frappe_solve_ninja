frappe.ui.form.on('Mentorship Request', {
    refresh(frm) {
        frm.set_query("assigned_mentor", () => ({
            filters: {
                is_mentor: 1,
                mentor_status: "Available"
            }
        }));

        frm.toggle_reqd(
            'assigned_mentor',
            frm.doc.workflow_state === 'Valid Request'
        );

        frm.trigger('hide_workflow_actions');
    },

    workflow_state(frm) {
        frm.trigger('hide_workflow_actions');
    },

    after_workflow_action(frm) {
        frm.trigger('hide_workflow_actions');
    },

    hide_workflow_actions(frm) {
        if (
            frm.doc.workflow_state === 'Valid Request' &&
            !frm.doc.assigned_mentor
        ) {
            setTimeout(() => {
                frm.page.clear_actions_menu();
                frm.page.clear_primary_action();
            }, 150);
        }
    }
});
