// Simple client script for Solve Event Registration
frappe.ready(function() {
    console.log("Solve Event Registration script loaded");
    console.log("User:", frappe.user.name);
    
    // Check if user is logged in
    const isLoggedIn = frappe.user.name && frappe.user.name !== 'Guest';
    console.log("Is logged in:", isLoggedIn);
    
    if (isLoggedIn) {
        console.log("User is logged in, hiding personal fields");
        
        // Hide personal fields for logged-in users
        const personalFields = ['full_name', 'mobile', 'city', 'year_of_birth'];
        
        personalFields.forEach(fieldName => {
            const field = frappe.web_form.fields_dict[fieldName];
            if (field) {
                console.log("Hiding field:", fieldName);
                field.df.hidden = 1;
                field.df.reqd = 0;
                field.refresh();
            }
        });
        
        // Show and populate user field
        if (frappe.web_form.fields_dict.user) {
            console.log("Setting user field to:", frappe.user.name);
            frappe.web_form.fields_dict.user.df.hidden = 0;
            frappe.web_form.fields_dict.user.df.read_only = 1;
            frappe.web_form.fields_dict.user.set_value(frappe.user.name);
            frappe.web_form.fields_dict.user.refresh();
        }
    } else {
        console.log("User is not logged in, showing personal fields");
        
        // Show personal fields for guests
        const personalFields = ['full_name', 'mobile', 'city', 'year_of_birth'];
        
        personalFields.forEach(fieldName => {
            const field = frappe.web_form.fields_dict[fieldName];
            if (field) {
                console.log("Showing field:", fieldName);
                field.df.hidden = 0;
                field.df.reqd = 1;
                field.df.read_only = 0;
                field.refresh();
            }
        });
        
        // Hide user field for guests
        if (frappe.web_form.fields_dict.user) {
            console.log("Hiding user field for guest");
            frappe.web_form.fields_dict.user.df.hidden = 1;
            frappe.web_form.fields_dict.user.refresh();
        }
    }
});








