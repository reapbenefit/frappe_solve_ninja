// Client script for Solve Event Registration Web Form
frappe.ready(function() {
    // Check if user is logged in
    const isLoggedIn = frappe.user.name && frappe.user.name !== 'Guest';
    
    if (isLoggedIn) {
        // User is logged in - populate user data and hide personal fields
        populateLoggedInUserData();
    } else {
        // User is not logged in - show personal fields and make them required
        showPersonalFieldsForGuest();
    }
});

function populateLoggedInUserData() {
    // Get current user data
    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "User",
            name: frappe.user.name
        },
        callback: function(response) {
            if (response.message) {
                const user = response.message;
                
                // Populate user field
                if (frappe.web_form.fields_dict.user) {
                    frappe.web_form.fields_dict.user.set_value(user.name);
                }
                
                // Get user metadata for additional info
                frappe.call({
                    method: "frappe.client.get_value",
                    args: {
                        doctype: "User Metadata",
                        filters: { user: user.name },
                        fieldname: ["city", "year_of_birth"]
                    },
                    callback: function(metadata_response) {
                        if (metadata_response.message) {
                            const metadata = metadata_response.message;
                            
                            // Populate hidden fields with user data
                            if (frappe.web_form.fields_dict.full_name) {
                                frappe.web_form.fields_dict.full_name.set_value(user.full_name || user.first_name);
                            }
                            
                            if (frappe.web_form.fields_dict.mobile) {
                                frappe.web_form.fields_dict.mobile.set_value(user.mobile_no);
                            }
                            
                            if (frappe.web_form.fields_dict.city && metadata.city) {
                                frappe.web_form.fields_dict.city.set_value(metadata.city);
                            }
                            
                            if (frappe.web_form.fields_dict.year_of_birth && metadata.year_of_birth) {
                                frappe.web_form.fields_dict.year_of_birth.set_value(metadata.year_of_birth);
                            }
                        }
                    }
                });
            }
        }
    });
}

function showPersonalFieldsForGuest() {
    // Show personal fields for non-logged-in users
    const personalFields = ['full_name', 'mobile', 'city', 'year_of_birth'];
    
    personalFields.forEach(fieldName => {
        const field = frappe.web_form.fields_dict[fieldName];
        if (field) {
            // Show the field
            field.df.hidden = 0;
            field.df.reqd = 1;
            field.df.read_only = 0;
            
            // Refresh the field
            field.refresh();
        }
    });
    
    // Hide user field for guests
    if (frappe.web_form.fields_dict.user) {
        frappe.web_form.fields_dict.user.df.hidden = 1;
        frappe.web_form.fields_dict.user.refresh();
    }
}

// Override form validation to handle different user states
frappe.web_form.on('before_save', function(doc) {
    const isLoggedIn = frappe.user.name && frappe.user.name !== 'Guest';
    
    if (isLoggedIn) {
        // For logged-in users, ensure user field is set
        if (!doc.user) {
            doc.user = frappe.user.name;
        }
        
        // Get user data to populate hidden fields
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "User",
                name: frappe.user.name
            },
            callback: function(response) {
                if (response.message) {
                    const user = response.message;
                    
                    // Populate hidden fields
                    if (!doc.full_name) {
                        doc.full_name = user.full_name || user.first_name;
                    }
                    if (!doc.mobile) {
                        doc.mobile = user.mobile_no;
                    }
                }
            }
        });
    } else {
        // For guests, validate required fields
        const requiredFields = ['full_name', 'mobile', 'city', 'year_of_birth'];
        const missingFields = [];
        
        requiredFields.forEach(fieldName => {
            if (!doc[fieldName]) {
                missingFields.push(fieldName.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()));
            }
        });
        
        if (missingFields.length > 0) {
            frappe.msgprint({
                title: __('Required Fields Missing'),
                message: __('Please fill in the following required fields: ') + missingFields.join(', '),
                indicator: 'red'
            });
            return false; // Prevent form submission
        }
    }
    
    return true; // Allow form submission
});








