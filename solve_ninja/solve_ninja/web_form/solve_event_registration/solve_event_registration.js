// Handle form discard
frappe.web_form.discard_form = function() {
    if (frappe.form_dirty) {
        frappe.confirm(
            'Are you sure you want to discard changes?',
            function() {
                window.location.href = '/';
            }
        );
    } else {
        window.location.href = '/';
    }
    return false;
};

// Handle logged-in user auto-population and field visibility
frappe.ready(function() {
    // Wait for web form to be fully loaded
    if (frappe.web_form && frappe.web_form.ready) {
        frappe.web_form.ready(function() {
            setupUserFields();
        });
    } else {
        // Fallback if ready event isn't available
        $(document).on('web_form_loaded', function() {
            setupUserFields();
        });
        
        // Additional fallback with timeout
        setTimeout(function() {
            setupUserFields();
        }, 1000);
    }
});

function setupUserFields() {
    // Ensure web form is initialized
    if (!frappe.web_form || !frappe.web_form.fields_dict) {
        return;
    }
    
    // Check if user is logged in (not Guest)
    if (frappe.session.user && frappe.session.user !== 'Guest') {
        // For logged-in users
        
        // Wait for the user field to be ready, then set value
        const userField = frappe.web_form.get_field('user');
        if (userField) {
            // Ensure the field is initialized before setting value
            if (userField.get_value() !== frappe.session.user) {
                // Small delay to ensure Link field is ready
                setTimeout(function() {
                    frappe.web_form.set_value('user', frappe.session.user);
                }, 200);
            }
            
            // Show user field (readonly)
            userField.$wrapper.show();
        }
        
        // Hide personal info fields for logged-in users
        const fieldsToHide = ['full_name', 'mobile', 'city', 'year_of_birth'];
        fieldsToHide.forEach(function(fieldname) {
            const field = frappe.web_form.get_field(fieldname);
            if (field) {
                field.$wrapper.hide();
                // Remove mandatory requirement
                field.df.reqd = 0;
                field.refresh();
            }
        });
        
    } else {
        // For guest users
        
        // Hide user field
        const userField = frappe.web_form.get_field('user');
        if (userField) {
            userField.$wrapper.hide();
        }
        
        // Show personal info fields
        const fieldsToShow = ['full_name', 'mobile', 'city', 'year_of_birth'];
        fieldsToShow.forEach(function(fieldname) {
            const field = frappe.web_form.get_field(fieldname);
            if (field) {
                field.$wrapper.show();
                // Make them mandatory
                field.df.reqd = 1;
                field.refresh();
            }
        });
    }
}

// Override validation
frappe.web_form.validate = function() {
    // If user is logged in
    if (frappe.session.user && frappe.session.user !== 'Guest') {
        // Ensure user field has the correct value
        const userField = frappe.web_form.get_field('user');
        if (userField && userField.get_value() !== frappe.session.user) {
            frappe.web_form.set_value('user', frappe.session.user);
        }
        return true;
    }
    
    // For non-logged-in users, validate required fields
    const requiredFields = ['full_name', 'mobile', 'city', 'year_of_birth'];
    for (let fieldname of requiredFields) {
        const value = frappe.web_form.get_value(fieldname);
        if (!value) {
            const field = frappe.web_form.get_field(fieldname);
            if (field) {
                const label = field.df.label || fieldname;
                frappe.msgprint(__('Please fill in: ' + label));
            }
            return false;
        }
    }
    
    // Ensure solve_event is selected
    if (!frappe.web_form.get_value('solve_event')) {
        frappe.msgprint(__('Please select a Solve Event'));
        return false;
    }
    
    return true;
};

// Alternative: Use field change event to setup once the form is ready
$(document).ready(function() {
    let setupComplete = false;
    
    // Watch for when the solve_event field is rendered (last visible field)
    const checkInterval = setInterval(function() {
        if (frappe.web_form && frappe.web_form.fields_dict && frappe.web_form.fields_dict.solve_event) {
            if (!setupComplete) {
                setupComplete = true;
                clearInterval(checkInterval);
                setupUserFields();
            }
        }
    }, 100);
    
    // Clear interval after 5 seconds to prevent infinite loop
    setTimeout(function() {
        clearInterval(checkInterval);
    }, 5000);
});