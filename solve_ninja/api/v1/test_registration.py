import frappe
from samaaja.api.common import custom_response

@frappe.whitelist(allow_guest=True)
def test_solve_event_registration():
    """
    Test endpoint to verify solve event registration functionality.
    """
    try:
        # Get current user info
        user_info = {
            "current_user": frappe.session.user,
            "is_guest": frappe.session.user == 'Guest',
            "is_logged_in": frappe.session.user not in ['Guest', 'Administrator']
        }
        
        # Test form data
        test_data = {
            "solve_event": "Test Event",
            "source": "Web Form"
        }
        
        # If user is logged in, add user field
        if user_info["is_logged_in"]:
            test_data["user"] = frappe.session.user
        
        # If user is guest, add personal fields
        else:
            test_data.update({
                "full_name": "Test User",
                "mobile": "9876543210",
                "city": "Mumbai",
                "year_of_birth": 1990
            })
        
        return custom_response(
            message="Test data prepared successfully",
            data={
                "user_info": user_info,
                "test_data": test_data,
                "form_url": "https://dev.solveninja.org/solve-event-registration"
            },
            status_code=200
        )
        
    except Exception as e:
        return custom_response(
            message="Test failed",
            data=None,
            status_code=500,
            error=str(e)
        )








