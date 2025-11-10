#!/usr/bin/env python3
"""
Script to create Home Page Content DocType in Frappe
Run this from your frappe-bench directory
"""

import os
import sys

# Add frappe-bench to Python path
frappe_bench_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, frappe_bench_path)

# Add sites to path
sites_path = os.path.join(frappe_bench_path, 'sites')
sys.path.insert(0, sites_path)

def create_home_page_doctype():
    """Create the Home Page Content DocType"""
    
    try:
        # Import frappe
        import frappe
       
        
        print("🚀 Creating Home Page Content DocType...")
        
        # Home Page Content DocType data - Simple structure matching en.js
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
                "hero_subtitle",
                "hero_title",
                "hero_title_highlight",
                "hero_description",
                "hero_cta",
                "section_break_features",
                "features_title",
                "features_learn_image",
                "features_learn_title",
                "features_learn_description",
                "features_learn_link_cta",
                "features_connect_image",
                "features_connect_title",
                "features_connect_description",
                "features_connect_link_cta",
                "features_lead_image",
                "features_lead_title",
                "features_lead_description",
                "features_lead_link_cta",
                "section_break_testimonials",
                "testimonials_title",
                "testimonials_view_profile_cta",
                "testimonials_view_story_cta",
                "testimonials_hide_story_cta",
                "testimonials_liked_profiles",
                "testimonials_create_portfolio",
                "testimonials_no_ninjas_message",
                "testimonials_story_title",
                "section_break_city_leaderboard",
                "city_leaderboard_title",
                "city_leaderboard_month",
                "city_leaderboard_year",
                "city_leaderboard_all_time",
                "city_leaderboard_city",
                "city_leaderboard_active_ninjas",
                "city_leaderboard_hours_invested",
                "city_leaderboard_actions_taken",
                "city_leaderboard_explore_actions",
                "city_leaderboard_explore_actions_cta",
                "section_break_opportunities",
                "opportunities_title",
                "opportunities_filters",
                "opportunities_location",
                "opportunities_skills",
                "opportunities_type",
                "opportunities_clear_all",
                "opportunities_apply",
                "opportunities_know_more",
                "opportunities_view_all",
                "opportunities_show_less",
                "opportunities_no_results",                
                "section_break_opportunities_detail_labels",
                "opportunities_detail_labels_apply_by",
                "section_break_footer",
                "footer_follow",
                "footer_instagram",
                "footer_youtube",
                "footer_linkedin",
                "footer_twitter",
                "footer_facebook",
                "footer_contact",
                "footer_email",
                "footer_phone",
                "footer_address",
                "footer_accessibility",
                "footer_privacy",
                "footer_help_text",
                "footer_home",
                "footer_programs",
                "footer_opportunities",
                "footer_profile",
                "footer_copyright"
            ],
            "fields": [
                {
                    "fieldname": "section_break_basic_info",
                    "fieldtype": "Section Break",
                    "label": "Basic Information"
                },
                {
                    "fieldname": "language",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Language",
                    "options": "Language",
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
                    "fieldname": "hero_subtitle",
                    "fieldtype": "Small Text",
                    "label": "Hero Subtitle",
                    "default": "Reap Benefit Change Maker Portfolio",
                    "description": "Main subtitle for the hero section"
                },
                {
                    "fieldname": "hero_title",
                    "fieldtype": "Small Text",
                    "label": "Hero Title",
                    "default": "Want to Build Real-Life Skills?",
                    "description": "Main title for the hero section"
                },
                {
                    "fieldname": "hero_title_highlight",
                    "fieldtype": "Small Text",
                    "label": "Hero Title Highlight",
                    "default": "Become a Solve Ninja Today!",
                    "description": "Highlighted part of the title"
                },
                {
                    "fieldname": "hero_description",
                    "fieldtype": "Text",
                    "label": "Hero Description",
                    "default": "Build skills, redefine civic and climate leadership, one action at a time.",
                    "description": "Description text for the hero section"
                },
                {
                    "fieldname": "hero_cta",
                    "fieldtype": "Small Text",
                    "label": "Hero CTA",
                    "default": "Check out your Skill Portfolio Now →",
                    "description": "Call-to-action button text"
                },
                {
                    "fieldname": "section_break_features",
                    "fieldtype": "Section Break",
                    "label": "Features Section"
                },
                {
                    "fieldname": "features_title",
                    "fieldtype": "Small Text",
                    "label": "Features Title",
                    "default": "Explore the Program",
                    "description": "Title for features section"
                },
                {
                    "fieldname": "features_learn_image",
                    "fieldtype": "Attach Image",
                    "label": "Learn Image",
                    "description": "Image for learn feature"
                },
                {
                    "fieldname": "features_learn_title",
                    "fieldtype": "Small Text",
                    "label": "Learn Title",
                    "default": "Learn",
                    "description": "Title for learn feature"
                },
                {
                    "fieldname": "features_learn_description",
                    "fieldtype": "Text",
                    "label": "Learn Description",
                    "default": "Build new skills, gain knowledge, and access expert mentorship.",
                    "description": "Description for learn feature"
                },
                {
                    "fieldname": "features_learn_link_cta",
                    "fieldtype": "Small Text",
                    "label": "Learn Link CTA",
                    "default": "Start Learning",
                    "description": "Call-to-action text for learn feature"
                },
                {
                    "fieldname": "features_connect_image",
                    "fieldtype": "Attach Image",
                    "label": "Connect Image",
                    "description": "Image for connect feature"
                },
                {
                    "fieldname": "features_connect_title",
                    "fieldtype": "Small Text",
                    "label": "Connect Title",
                    "default": "Connect",
                    "description": "Title for connect feature"
                },
                {
                    "fieldname": "features_connect_description",
                    "fieldtype": "Text",
                    "label": "Connect Description",
                    "default": "Meet, collaborate, and share ideas with other changemakers.",
                    "description": "Description for connect feature"
                },
                {
                    "fieldname": "features_connect_link_cta",
                    "fieldtype": "Small Text",
                    "label": "Connect Link CTA",
                    "default": "Meet Peers",
                    "description": "Call-to-action text for connect feature"
                },
                {
                    "fieldname": "features_lead_image",
                    "fieldtype": "Attach Image",
                    "label": "Lead Image",
                    "description": "Image for lead feature"
                },
                {
                    "fieldname": "features_lead_title",
                    "fieldtype": "Small Text",
                    "label": "Lead Title",
                    "default": "Lead",
                    "description": "Title for lead feature"
                },
                {
                    "fieldname": "features_lead_description",
                    "fieldtype": "Text",
                    "label": "Lead Description",
                    "default": "Take on leadership roles, represent youth voices, and influence change.",
                    "description": "Description for lead feature"
                },
                {
                    "fieldname": "features_lead_link_cta",
                    "fieldtype": "Small Text",
                    "label": "Lead Link CTA",
                    "default": "Explore Opportunities",
                    "description": "Call-to-action text for lead feature"
                },
                {
                    "fieldname": "section_break_testimonials",
                    "fieldtype": "Section Break",
                    "label": "Testimonials Section (Ninjas)"
                },
                {
                    "fieldname": "testimonials_title",
                    "fieldtype": "Small Text",
                    "label": "Testimonials Title",
                    "default": "Ninjas in Focus",
                    "description": "Title for testimonials section"
                },
                {
                    "fieldname": "testimonials_view_profile_cta",
                    "fieldtype": "Small Text",
                    "label": "View Profile CTA",
                    "default": "View Profile",
                    "description": "Call-to-action text for view profile button"
                },
                {
                    "fieldname": "testimonials_view_story_cta",
                    "fieldtype": "Small Text",
                    "label": "View Story CTA",
                    "default": "View their Story",
                    "description": "Call-to-action text for view story button"
                },
                {
                    "fieldname": "testimonials_hide_story_cta",
                    "fieldtype": "Small Text",
                    "label": "Hide Story CTA",
                    "default": "Hide their Story",
                    "description": "Call-to-action text for hide story button"
                },
                {
                    "fieldname": "testimonials_liked_profiles",
                    "fieldtype": "Small Text",
                    "label": "Liked Profiles",
                    "default": "Liked these profiles?",
                    "description": "Text for liked profiles question"
                },
                {
                    "fieldname": "testimonials_create_portfolio",
                    "fieldtype": "Small Text",
                    "label": "Create Portfolio",
                    "default": "Create Your Portfolio",
                    "description": "Text for create portfolio button"
                },
                {
                    "fieldname": "testimonials_no_ninjas_message",
                    "fieldtype": "Small Text",
                    "label": "No Ninjas Message",
                    "default": "No ninjas in focus at the moment. Check back later!",
                    "description": "Message when no ninjas are available"
                },
                {
                    "fieldname": "testimonials_story_title",
                    "fieldtype": "Small Text",
                    "label": "Story Title",
                    "default": "{name}'s Story",
                    "description": "Template for story title (use {name} for placeholder)"
                },
                {
                    "fieldname": "section_break_city_leaderboard",
                    "fieldtype": "Section Break",
                    "label": "City Leaderboard Section"
                },
                {
                    "fieldname": "city_leaderboard_title",
                    "fieldtype": "Small Text",
                    "label": "City Leaderboard Title",
                    "default": "Cities In Action",
                    "description": "Title for city leaderboard section"
                },
                {
                    "fieldname": "city_leaderboard_month",
                    "fieldtype": "Small Text",
                    "label": "Month",
                    "default": "Month",
                    "description": "Text for month filter"
                },
                {
                    "fieldname": "city_leaderboard_year",
                    "fieldtype": "Small Text",
                    "label": "Year",
                    "default": "Year",
                    "description": "Text for year filter"
                },
                {
                    "fieldname": "city_leaderboard_all_time",
                    "fieldtype": "Small Text",
                    "label": "All Time",
                    "default": "All-Time",
                    "description": "Text for all time filter"
                },
                {
                    "fieldname": "city_leaderboard_city",
                    "fieldtype": "Small Text",
                    "label": "City",
                    "default": "City",
                    "description": "Text for city column header"
                },
                {
                    "fieldname": "city_leaderboard_active_ninjas",
                    "fieldtype": "Small Text",
                    "label": "Active Ninjas",
                    "default": "Active Ninjas",
                    "description": "Text for active ninjas column header"
                },
                {
                    "fieldname": "city_leaderboard_hours_invested",
                    "fieldtype": "Small Text",
                    "label": "Hours Invested",
                    "default": "Hours Invested",
                    "description": "Text for hours invested column header"
                },
                {
                    "fieldname": "city_leaderboard_actions_taken",
                    "fieldtype": "Small Text",
                    "label": "Actions Taken",
                    "default": "Actions Taken",
                    "description": "Text for actions taken column header"
                },
                {
                    "fieldname": "city_leaderboard_explore_actions",
                    "fieldtype": "Small Text",
                    "label": "Explore Actions",
                    "default": "Explore Actions",
                    "description": "Text for explore actions link"
                },
                {
                    "fieldname": "city_leaderboard_explore_actions_cta",
                    "fieldtype": "Small Text",
                    "label": "Explore Actions CTA",
                    "default": "Explore Actions",
                    "description": "Call-to-action text for explore actions"
                },
                {
                    "fieldname": "section_break_opportunities",
                    "fieldtype": "Section Break",
                    "label": "Opportunities Section"
                },
                {
                    "fieldname": "opportunities_title",
                    "fieldtype": "Small Text",
                    "label": "Opportunities Title",
                    "default": "Opportunities for Youth",
                    "description": "Title for opportunities section"
                },
                {
                    "fieldname": "opportunities_filters",
                    "fieldtype": "Small Text",
                    "label": "Filters",
                    "default": "Filters",
                    "description": "Text for filters button"
                },
                {
                    "fieldname": "opportunities_location",
                    "fieldtype": "Small Text",
                    "label": "Location",
                    "default": "Location",
                    "description": "Text for location filter"
                },
                {
                    "fieldname": "opportunities_skills",
                    "fieldtype": "Small Text",
                    "label": "Skills",
                    "default": "Skills",
                    "description": "Text for skills filter"
                },
                {
                    "fieldname": "opportunities_type",
                    "fieldtype": "Small Text",
                    "label": "Type",
                    "default": "Type",
                    "description": "Text for type filter"
                },
                {
                    "fieldname": "opportunities_clear_all",
                    "fieldtype": "Small Text",
                    "label": "Clear All",
                    "default": "Clear All",
                    "description": "Text for clear all button"
                },
                {
                    "fieldname": "opportunities_apply",
                    "fieldtype": "Small Text",
                    "label": "Apply",
                    "default": "Apply",
                    "description": "Text for apply button"
                },
                {
                    "fieldname": "opportunities_know_more",
                    "fieldtype": "Small Text",
                    "label": "Know More",
                    "default": "Know More",
                    "description": "Text for know more button"
                },
                {
                    "fieldname": "opportunities_view_all",
                    "fieldtype": "Small Text",
                    "label": "View All",
                    "default": "View All Opportunities",
                    "description": "Text for view all button"
                },
                {
                    "fieldname": "opportunities_show_less",
                    "fieldtype": "Small Text",
                    "label": "Show Less",
                    "default": "Show Less",
                    "description": "Text for show less button"
                },
                {
                    "fieldname": "opportunities_no_results",
                    "fieldtype": "Text",
                    "label": "No Results",
                    "default": "No opportunities match your current filters. Try adjusting your selection.",
                    "description": "Text when no opportunities match filters"
                },
                {
                    "fieldname": "section_break_opportunities_detail_labels",
                    "fieldtype": "Section Break",
                    "label": "Opportunities Detail Labels"
                },
                {
                    "fieldname": "opportunities_detail_labels_apply_by",
                    "fieldtype": "Small Text",
                    "label": "Apply By Label",
                    "default": "Apply by:",
                    "description": "Label text for apply by date in details"
                },
                {
                    "fieldname": "section_break_footer",
                    "fieldtype": "Section Break",
                    "label": "Footer Section"
                },
                {
                    "fieldname": "footer_follow",
                    "fieldtype": "Small Text",
                    "label": "Follow",
                    "default": "Follow",
                    "description": "Text for follow section"
                },
                {
                    "fieldname": "footer_instagram",
                    "fieldtype": "Small Text",
                    "label": "Instagram",
                    "default": "Instagram",
                    "description": "Text for Instagram link"
                },
                {
                    "fieldname": "footer_youtube",
                    "fieldtype": "Small Text",
                    "label": "YouTube",
                    "default": "YouTube",
                    "description": "Text for YouTube link"
                },
                {
                    "fieldname": "footer_linkedin",
                    "fieldtype": "Small Text",
                    "label": "LinkedIn",
                    "default": "LinkedIn",
                    "description": "Text for LinkedIn link"
                },
                {
                    "fieldname": "footer_twitter",
                    "fieldtype": "Small Text",
                    "label": "Twitter",
                    "default": "X",
                    "description": "Text for Twitter link"
                },
                {
                    "fieldname": "footer_facebook",
                    "fieldtype": "Small Text",
                    "label": "Facebook",
                    "default": "Facebook",
                    "description": "Text for Facebook link"
                },
                {
                    "fieldname": "footer_contact",
                    "fieldtype": "Small Text",
                    "label": "Contact",
                    "default": "Contact",
                    "description": "Text for contact section"
                },
                {
                    "fieldname": "footer_email",
                    "fieldtype": "Small Text",
                    "label": "Email",
                    "default": "hello@solveninja.org",
                    "description": "Email address text"
                },
                {
                    "fieldname": "footer_phone",
                    "fieldtype": "Small Text",
                    "label": "Phone",
                    "default": "+91 00000 00000",
                    "description": "Phone number text"
                },
                {
                    "fieldname": "footer_address",
                    "fieldtype": "Small Text",
                    "label": "Address",
                    "default": "12 Civic Lane, Bengaluru 560001",
                    "description": "Address text"
                },
                {
                    "fieldname": "footer_accessibility",
                    "fieldtype": "Small Text",
                    "label": "Accessibility",
                    "default": "Accessibility Statement",
                    "description": "Text for accessibility link"
                },
                {
                    "fieldname": "footer_privacy",
                    "fieldtype": "Small Text",
                    "label": "Privacy",
                    "default": "Privacy",
                    "description": "Text for privacy link"
                },
                {
                    "fieldname": "footer_help_text",
                    "fieldtype": "Small Text",
                    "label": "Help Text",
                    "default": "Need help? Check guidelines before publishing.",
                    "description": "Text for help message"
                },
                {
                    "fieldname": "footer_home",
                    "fieldtype": "Small Text",
                    "label": "Home",
                    "default": "Home",
                    "description": "Text for home link"
                },
                {
                    "fieldname": "footer_programs",
                    "fieldtype": "Small Text",
                    "label": "Programs",
                    "default": "Programs",
                    "description": "Text for programs link"
                },
                {
                    "fieldname": "footer_opportunities",
                    "fieldtype": "Small Text",
                    "label": "Opportunities",
                    "default": "Opportunities",
                    "description": "Text for opportunities link"
                },
                {
                    "fieldname": "footer_profile",
                    "fieldtype": "Small Text",
                    "label": "Profile",
                    "default": "Profile",
                    "description": "Text for profile link"
                },
                {
                    "fieldname": "footer_copyright",
                    "fieldtype": "Small Text",
                    "label": "Copyright",
                    "default": "© 2024 Solve Ninja. All rights reserved.",
                    "description": "Text for copyright notice"
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
            "name": "Home Page Content",
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
        
        print("✅ Home Page Content DocType created successfully!")
        print("📋 You can now create records for:")
        print("   - English: name = 'home-en'")
        print("   - Hindi: name = 'home-hi'")
        print("🎯 Total fields: 60+ fields with default values from en.js")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating DocType: {str(e)}")
        return False

if __name__ == "__main__":
    success = create_home_page_doctype()
    if success:
        print("\n🎉 Script completed successfully!")
    else:
        print("\n💥 Script failed. Please check the error message above.")
