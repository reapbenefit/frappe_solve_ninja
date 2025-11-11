#!/usr/bin/env python3
"""
Script to create Connect Page Content DocType in Frappe
This script creates a DocType for managing Connect page content with all fields and default values
"""

import os
import sys

# Add frappe-bench to Python path
frappe_bench_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, frappe_bench_path)

# Add sites to path
sites_path = os.path.join(frappe_bench_path, 'sites')
sys.path.insert(0, sites_path)

def create_connect_page_doctype():
    """Create Connect Page Content DocType"""
    import frappe
    # Define the DocType
    doctype = {
        "doctype": "DocType",
        "name": "Connect Page Content",
        "module": "Solve Ninja",
        "custom": 1,
        "fields": [
            # Basic Info
            {
                    "fieldname": "language",
                    "fieldtype": "Link",
                    "label": "Language",
                    "options": "Language",
                    "reqd": 1,
                    "default": "English",
                    "description": "Select the language for this content"
            },
            {
                "fieldname": "is_active",
                "fieldtype": "Check",
                "label": "Is Active",
                "default": 1
            },
            
            # Ways to Connect Section
            {
                "fieldname": "ways_to_connect_title",
                "fieldtype": "Data",
                "label": "Ways to Connect - Title",
                "default": "Connect through Events"
            },
            {
                "fieldname": "ways_to_connect_description",
                "fieldtype": "Text",
                "label": "Ways to Connect - Description",
                "default": "Two ways to meet, learn and grow with fellow Ninjas."
            },
            
            # SolveCon Section
            {
                "fieldname": "solvecon_title",
                "fieldtype": "Data",
                "label": "SolveCon - Title",
                "default": "SolveCon"
            },
            {
                "fieldname": "solvecon_description",
                "fieldtype": "Text",
                "label": "SolveCon - Description",
                "default": "Connect with changemakers at a city-wide in-person festival. Join workshops and hear impact stories."
            },
            {
                "fieldname": "solvecon_tag_in_person",
                "fieldtype": "Data",
                "label": "SolveCon - In Person Tag",
                "default": "In-person"
            },
            {
                "fieldname": "solvecon_tag_workshops",
                "fieldtype": "Data",
                "label": "SolveCon - Workshops Tag",
                "default": "Workshops"
            },
            {
                "fieldname": "solvecon_tag_talks",
                "fieldtype": "Data",
                "label": "SolveCon - Talks Tag",
                "default": "Talks"
            },
            {
                "fieldname": "solvecon_link",
                "fieldtype": "Data",
                "label": "SolveCon - Link Text",
                "default": "See SolveCon Dates →"
            },
            
            # Changemaker Adda Section
            {
                "fieldname": "changemaker_adda_title",
                "fieldtype": "Data",
                "label": "Changemaker Adda - Title",
                "default": "Changemaker Adda"
            },
            {
                "fieldname": "changemaker_adda_description",
                "fieldtype": "Text",
                "label": "Changemaker Adda - Description",
                "default": "Interact with young people about their journeys and share your wins."
            },
            {
                "fieldname": "changemaker_adda_tag_online",
                "fieldtype": "Data",
                "label": "Changemaker Adda - Online Tag",
                "default": "Online"
            },
            {
                "fieldname": "changemaker_adda_tag_stories",
                "fieldtype": "Data",
                "label": "Changemaker Adda - Stories Tag",
                "default": "Stories"
            },
            {
                "fieldname": "changemaker_adda_tag_community",
                "fieldtype": "Data",
                "label": "Changemaker Adda - Community Tag",
                "default": "Community"
            },
            {
                "fieldname": "changemaker_adda_link",
                "fieldtype": "Data",
                "label": "Changemaker Adda - Link Text",
                "default": "Upcoming Addas →"
            },
            
            # Experience the Energy Section
            {
                "fieldname": "experience_energy_title",
                "fieldtype": "Data",
                "label": "Experience Energy - Title",
                "default": "Experience the Energy"
            },
            {
                "fieldname": "experience_energy_subtitle",
                "fieldtype": "Data",
                "label": "Experience Energy - Subtitle",
                "default": "SolveCon talks • Adda discussions • SolverJam workshops"
            },
            {
                "fieldname": "experience_energy_explore_button",
                "fieldtype": "Data",
                "label": "Experience Energy - Explore Button",
                "default": "Explore Full Library →"
            },
            
            
            # Gatherings Section
            {
                "fieldname": "gatherings_title",
                "fieldtype": "Data",
                "label": "Gatherings - Title",
                "default": "Be Part of the Next Gathering"
            },
            {
                "fieldname": "gatherings_select_city",
                "fieldtype": "Data",
                "label": "Gatherings - Select City",
                "default": "Select a City"
            },
            {
            "fieldname": "gatherings_tab_all_events",
            "fieldtype": "Data",
            "label": "Gatherings - All Events Tab",
            "default": "All Events"
            },
            {
                "fieldname": "event_registration_button",
                "fieldtype": "Data",
                "label": "Event Registration Button",
                "default": "Register"
            },
            
            # Want SolveCon Section
            {
                "fieldname": "want_solvecon_title",
                "fieldtype": "Data",
                "label": "Want SolveCon - Title",
                "default": "Want SolveCon to Your City?"
            },
            {
                "fieldname": "want_solvecon_description",
                "fieldtype": "Text",
                "label": "Want SolveCon - Description",
                "default": "Help bring the flagship event - SolveCon to your city where young changemakers gather to exchange ideas, showcase impact projects, attend workshops and create connections!"
            },
            {
                "fieldname": "want_solvecon_mobile_description",
                "fieldtype": "Text",
                "label": "Want SolveCon - Mobile Description",
                "default": "Let young changemakers gather to exchange ideas, showcase impact projects, attend workshops and create connections!"
            },
            
            # Request Option
            {
                "fieldname": "request_option_title",
                "fieldtype": "Data",
                "label": "Request Option - Title",
                "default": "Tell us details about your city and we'll come!"
            },
            {
                "fieldname": "request_button",
                "fieldtype": "Data",
                "label": "Request Button",
                "default": "Request SolveCon"
            },
            
           
            {
                "fieldname": "organize_button",
                "fieldtype": "Data",
                "label": "Organize Button",
                "default": "Organise it Yourself"
            },
            
            # Map Section
            {
                "fieldname": "map_title",
                "fieldtype": "Data",
                "label": "Map - Title",
                "default": "SolveCon Events"
            },
            {
                "fieldname": "map_description",
                "fieldtype": "Text",
                "label": "Map - Description",
                "default": "Join our community events across different cities"
            },
            
            # Map Events
            {
                "fieldname": "map_event_mumbai_name",
                "fieldtype": "Data",
                "label": "Map Event Mumbai - Name",
                "default": "SolveCon Mumbai"
            },
            {
                "fieldname": "map_event_mumbai_details",
                "fieldtype": "Data",
                "label": "Map Event Mumbai - Details",
                "default": "12 Jan 2025 • 850+ attendees"
            },
            {
                "fieldname": "map_event_delhi_name",
                "fieldtype": "Data",
                "label": "Map Event Delhi - Name",
                "default": "SolveCon Delhi"
            },
            {
                "fieldname": "map_event_delhi_details",
                "fieldtype": "Data",
                "label": "Map Event Delhi - Details",
                "default": "15 Feb 2025 • 650+ attendees"
            },
            {
                "fieldname": "map_event_bangalore_name",
                "fieldtype": "Data",
                "label": "Map Event Bangalore - Name",
                "default": "SolveCon Bangalore"
            },
            {
                "fieldname": "map_event_bangalore_details",
                "fieldtype": "Data",
                "label": "Map Event Bangalore - Details",
                "default": "20 Mar 2025 • 720+ attendees"
            },
            
           
            # Footer
            {
                "fieldname": "footer_text",
                "fieldtype": "Text",
                "label": "Footer - Text",
                "default": "No matter where you are – there's a Solve Ninja community waiting for you."
            },
            {
                "fieldname": "footer_button",
                "fieldtype": "Data",
                "label": "Footer - Button",
                "default": "Join the Movement →"
            },
            {
                "fieldname": "pathways_title",
                "fieldtype": "Data",
                "label": "Pathways Title",
                "default": "Tell us details about your city and we'll come!"
            }
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1,
                "write": 1,
                "create": 1,
                "delete": 1,
                "submit": 0,
                "cancel": 0,
                "amend": 0
            }
        ],
        "sort_field": "modified",
        "sort_order": "DESC",
        "track_changes": 1
    }
    
    try:
        # Create the DocType
        doc = frappe.get_doc(doctype)
        doc.insert()
        frappe.db.commit()
        
        print("✅ Successfully created 'Connect Page Content' DocType!")
        print(f"📋 DocType ID: {doc.name}")
        print(f"📁 Module: {doc.module}")
        print(f"🔢 Total Fields: {len(doc.fields)}")
        
        
    except Exception as e:
        print(f"❌ Error creating DocType: {str(e)}")
        frappe.db.rollback()

if __name__ == "__main__":

    # Create the DocType
    create_connect_page_doctype()
    
    print("\n🎉 Connect Page Content DocType creation completed!")
