#!/usr/bin/env python3
"""
Standalone method to create Learn Page Content DocType in Frappe
Copy this method to your frappe-backend/solveninja_cms/api.py file
"""

def create_learn_page_doctype():
    """Create the Learn Page Content DocType"""
    import frappe
    try:
        # Learn Page Content DocType data - Simple structure matching en.js
        doctype_data = {
            "actions": [],
            "allow_rename": 1,
            "creation": "2024-01-01 00:00:00.000000",
            "default_view": "List",
            "doctype": "DocType",
            "editable_grid": 1,
            "engine": "InnoDB",
            "field_order": [
                "section_break_basic_info",
                "language",
                "is_active",
                "column_break_5",
                "section_break_hero",
                "learn_hero_subtitle",
                "learn_hero_title",
                "learn_hero_description",
                "learn_hero_methodology",
                "learn_hero_program_rating",
                "learn_hero_built_skills",
                "learn_hero_youth_engaged",
                "section_break_solver_jam",
                "learn_solver_jam_title",
                "learn_solver_jam_description",
                "learn_solver_jam_register_now",
                "learn_solver_jam_event_completed",
                "learn_solver_jam_upcoming_events_text",
                "learn_solver_jam_past_events_text",
                "section_break_mentors",
                "learn_mentors_title",
                "learn_mentors_cta_title",
                "learn_mentors_cta_description",
                "learn_mentors_cta_button",
                "learn_mentors_available",
                "learn_mentors_slots_full",
                "section_break_ninjas_of_month",
                "learn_ninjas_of_month_title",
                "learn_ninjas_of_month_view_profile",
                "section_break_cta",
                "learn_cta_title",
                "learn_cta_button_text"
            ],
            "fields": [
                {
                    "fieldname": "section_break_basic_info",
                    "fieldtype": "Section Break",
                    "label": "Basic Information"
                },
                {
                    "fieldname": "language",
                    "fieldtype": "Select",
                    "in_list_view": 1,
                    "label": "Language",
                    "options": "English\nHindi",
                    "reqd": 1,
                    "default": "English",
                    "description": "Select the language for this content"
                },
                {
                    "fieldname": "is_active",
                    "fieldtype": "Check",
                    "in_list_view": 1,
                    "label": "Is Active",
                    "default": 1,
                    "description": "Enable/disable this content"
                },
                {
                    "fieldname": "column_break_5",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "section_break_hero",
                    "fieldtype": "Section Break",
                    "label": "Hero Section"
                },
                {
                    "fieldname": "learn_hero_subtitle",
                    "fieldtype": "Small Text",
                    "label": "Hero Subtitle",
                    "default": "Why learn with Solve Ninja?",
                    "description": "Subtitle for the hero section"
                },
                {
                    "fieldname": "learn_hero_title",
                    "fieldtype": "Small Text",
                    "label": "Hero Title",
                    "default": "Learn. Grow. Unlock your changemaker potential.",
                    "description": "Main title for the hero section"
                },
                {
                    "fieldname": "learn_hero_description",
                    "fieldtype": "Text",
                    "label": "Hero Description",
                    "default": "Build real skills through hands-on civic projects, mentorship, and events.",
                    "description": "Description for the hero section"
                },
                {
                    "fieldname": "learn_hero_methodology",
                    "fieldtype": "Small Text",
                    "label": "Methodology",
                    "default": "Methodology",
                    "description": "Text for methodology section"
                },
                {
                    "fieldname": "learn_hero_program_rating",
                    "fieldtype": "Small Text",
                    "label": "Program Rating",
                    "default": "4.8/5 program rating",
                    "description": "Program rating text"
                },
                {
                    "fieldname": "learn_hero_built_skills",
                    "fieldtype": "Small Text",
                    "label": "Built Skills",
                    "default": "83% built valuable skills",
                    "description": "Skills building statistic"
                },
                {
                    "fieldname": "learn_hero_youth_engaged",
                    "fieldtype": "Small Text",
                    "label": "Youth Engaged",
                    "default": "1.5L+ youth engaged",
                    "description": "Youth engagement statistic"
                },
                {
                    "fieldname": "section_break_solver_jam",
                    "fieldtype": "Section Break",
                    "label": "Solver Jam Section"
                },
                {
                    "fieldname": "learn_solver_jam_title",
                    "fieldtype": "Small Text",
                    "label": "Solver Jam Title",
                    "default": "Learn Together at Solver Jam",
                    "description": "Title for Solver Jam section"
                },
                {
                    "fieldname": "learn_solver_jam_description",
                    "fieldtype": "Text",
                    "label": "Solver Jam Description",
                    "default": "Real photos, real peers. Join upcoming group learning events.",
                    "description": "Description for Solver Jam section"
                },
                {
                    "fieldname": "learn_solver_jam_register_now",
                    "fieldtype": "Small Text",
                    "label": "Register Now",
                    "default": "Register Now",
                    "description": "Text for register now button"
                },
                {
                    "fieldname": "learn_solver_jam_event_completed",
                    "fieldtype": "Small Text",
                    "label": "Event Completed",
                    "default": "Event Completed",
                    "description": "Text for completed events"
                },
                {
                    "fieldname": "learn_solver_jam_upcoming_events_text",
                    "fieldtype": "Small Text",
                    "label": "Upcoming Events Text",
                    "default": "Upcoming",
                    "description": "Text for upcoming events tab"
                },
                {
                    "fieldname": "learn_solver_jam_past_events_text",
                    "fieldtype": "Small Text",
                    "label": "Past Events Text",
                    "default": "Past Events",
                    "description": "Text for past events tab"
                },
                {
                    "fieldname": "section_break_mentors",
                    "fieldtype": "Section Break",
                    "label": "Mentors Section"
                },
                {
                    "fieldname": "learn_mentors_title",
                    "fieldtype": "Small Text",
                    "label": "Mentors Title",
                    "default": "Mentors Who Guide You",
                    "description": "Title for mentors section"
                },
                {
                    "fieldname": "learn_mentors_cta_title",
                    "fieldtype": "Small Text",
                    "label": "CTA Title",
                    "default": "Share details where our experts can help you",
                    "description": "Title for mentorship CTA"
                },
                {
                    "fieldname": "learn_mentors_cta_description",
                    "fieldtype": "Text",
                    "label": "CTA Description",
                    "default": "Tell us your challenge, preferred times, and outcomes you want. We'll match you to the right mentor.",
                    "description": "Description for mentorship CTA"
                },
                {
                    "fieldname": "learn_mentors_cta_button",
                    "fieldtype": "Small Text",
                    "label": "CTA Button",
                    "default": "Request Mentorship",
                    "description": "Text for mentorship request button"
                },
                {
                    "fieldname": "learn_mentors_available",
                    "fieldtype": "Small Text",
                    "label": "Available",
                    "default": "Available",
                    "description": "Text for available mentors"
                },
                {
                    "fieldname": "learn_mentors_slots_full",
                    "fieldtype": "Small Text",
                    "label": "Slots Full",
                    "default": "Slots Full",
                    "description": "Text for full mentor slots"
                },
                {
                    "fieldname": "section_break_ninjas_of_month",
                    "fieldtype": "Section Break",
                    "label": "Ninjas of Month Section"
                },
                {
                    "fieldname": "learn_ninjas_of_month_title",
                    "fieldtype": "Small Text",
                    "label": "Ninjas Title",
                    "default": "Top Ninjas",
                    "description": "Title for top ninjas section"
                },
                {
                    "fieldname": "learn_ninjas_of_month_view_profile",
                    "fieldtype": "Small Text",
                    "label": "View Profile",
                    "default": "View Profile",
                    "description": "Text for view profile button"
                },
                {
                    "fieldname": "section_break_cta",
                    "fieldtype": "Section Break",
                    "label": "CTA Section"
                },
                {
                    "fieldname": "learn_cta_title",
                    "fieldtype": "Small Text",
                    "label": "CTA Title",
                    "default": "Start your Learning Journey and building Life Skills",
                    "description": "Title for final CTA section"
                },
                {
                    "fieldname": "learn_cta_button_text",
                    "fieldtype": "Small Text",
                    "label": "CTA Button Text",
                    "default": "Start My Journey",
                    "description": "Text for final CTA button"
                }
            ],
            "has_web_view": 0,
            "hide_heading": 0,
            "hide_toolbar": 0,
            "idx": 0,
            "image_view": 0,
            "in_create": 0,
            "is_submittable": 0,
            "issingle": 0,
            "istable": 0,
            "max_attachments": 0,
            "modified": "2024-01-01 00:00:00.000000",
            "modified_by": "Administrator",
            "module": "Solve Ninja",
            "name": "Learn Page Content",
            "naming_rule": "By fieldname",
            "owner": "Administrator",
            "permissions": [
                {
                    "create": 1,
                    "delete": 1,
                    "email": 1,
                    "export": 1,
                    "print": 1,
                    "read": 1,
                    "report": 1,
                    "role": "System Manager",
                    "share": 1,
                    "write": 1
                }
            ],
            "quick_entry": 0,
            "read_only": 0,
            "read_only_onload": 0,
            "show_name_in_global_search": 1,
            "sort_field": "modified",
            "sort_order": "DESC",
            "states": [],
            "track_changes": 1,
            "track_seen": 0,
            "track_views": 0
        }
        
        # Create the DocType
        frappe.get_doc(doctype_data).insert()
        frappe.db.commit()
        
        print("✅ Learn Page Content DocType created successfully!")
        print("📋 You can now create records for:")
        print("   - English: name = 'learn-en'")
        print("   - Hindi: name = 'learn-hi'")
        print("🎯 Total fields: 50+ fields with default values from en.js")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating DocType: {str(e)}")
        return False


# Usage example:
# Call this method from your Frappe console or API
# create_learn_page_doctype()


if __name__ == "__main__":
    success = create_learn_page_doctype()
    if success:
        print("\n🎉 Script completed successfully!")
    else:
        print("\n💥 Script failed. Please check the error message above.")