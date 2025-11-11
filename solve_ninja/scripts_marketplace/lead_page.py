#!/usr/bin/env python3
"""
Script to create Lead Page Content DocType in Frappe
This script creates a DocType for managing Lead page content with all fields and default values
"""

import sys
import os

# Add frappe-bench to Python path
sys.path.append('/home/frappe/frappe-bench')
sys.path.append('/home/frappe/frappe-bench/sites')

import frappe
from frappe import _

def create_lead_page_doctype():
    """Create Lead Page Content DocType"""
    
   
    # Define the DocType
    doctype = {
        "doctype": "DocType",
        "name": "Lead Page Content",
        "module": "Solve Ninja",
        "custom": 1,
        "fields": [
            # Basic Info
            {
                "fieldname": "content_language",
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
            # Hero Section
            {
                "fieldname": "lead_hero_title",
                "fieldtype": "Data",
                "label": "Lead Hero - Title",
                "default": "Lead. Inspire. Shape the Future of Changemaking."
            },
            {
                "fieldname": "lead_hero_description",
                "fieldtype": "Text",
                "label": "Lead Hero - Description",
                "default": "Take your ideas further, guide peers, and represent youth voices at scale."
            },
            {
                "fieldname": "lead_hero_primary_button",
                "fieldtype": "Data",
                "label": "Lead Hero - Primary Button",
                "default": "Step Up and Lead →"
            },
            
            # Mentorship Network Section
            {
                "fieldname": "mentorship_network_title",
                "fieldtype": "Data",
                "label": "Mentorship Network - Title",
                "default": "Every leader needs guidance."
            },
            {
                "fieldname": "mentorship_network_description",
                "fieldtype": "Text",
                "label": "Mentorship Network - Description",
                "default": "Over 5,000 Ninjas have been mentored by 100+ experts in sustainability, policy, and innovation."
            },
            {
                "fieldname": "mentorship_network_primary_button",
                "fieldtype": "Data",
                "label": "Mentorship Network - Primary Button",
                "default": "Request Mentorship →"
            },
            {
                "fieldname": "mentorship_network_secondary_button",
                "fieldtype": "Data",
                "label": "Mentorship Network - Secondary Button",
                "default": "Go to Learn Page →"
            },
            {
                "fieldname": "mentorship_network_card_title",
                "fieldtype": "Data",
                "label": "Mentorship Network - Card Title",
                "default": "Mentorship Network"
            },
            {
                "fieldname": "mentorship_network_card_description",
                "fieldtype": "Text",
                "label": "Mentorship Network - Card Description",
                "default": "Tap into domain experts who will accelerate your leadership journey."
            },
            # Changemaker Fund Section
            {
                "fieldname": "changemaker_fund_title",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Title",
                "default": "Fuel Your Ideas with the Changemaker Fund"
            },
            {
                "fieldname": "changemaker_fund_description",
                "fieldtype": "Text",
                "label": "Changemaker Fund - Description",
                "default": "Turn your changemaking projects into reality with micro-grants and support."
            },
            {
                "fieldname": "changemaker_fund_funded_badge",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Funded Badge",
                "default": "Funded"
            },
            {
                "fieldname": "changemaker_fund_cta_button",
                "fieldtype": "Data",
                "label": "Changemaker Fund - CTA Button",
                "default": "Apply for the Fund →"
            },
            {
                "fieldname": "changemaker_fund_ninja_label",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Ninja Label",
                "default": "Ninja"
            },
            {
                "fieldname": "changemaker_fund_grant_label",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Grant Label",
                "default": "Grant"
            },
            {
                "fieldname": "changemaker_fund_outcome_label",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Outcome Label",
                "default": "Outcome"
            },
            
            # Changemaker Fund Stats
            {
                "fieldname": "changemaker_fund_stat_1_label",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Stat 1 Label",
                "default": "Disbursed"
            },
            {
                "fieldname": "changemaker_fund_stat_1_value",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Stat 1 Value",
                "default": "INR 10+ Lakhs"
            },
            {
                "fieldname": "changemaker_fund_stat_1_description",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Stat 1 Description",
                "default": "already disbursed"
            },
            {
                "fieldname": "changemaker_fund_stat_2_label",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Stat 2 Label",
                "default": "Projects Funded"
            },
            {
                "fieldname": "changemaker_fund_stat_2_value",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Stat 2 Value",
                "default": "150+ projects"
            },
            {
                "fieldname": "changemaker_fund_stat_2_description",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Stat 2 Description",
                "default": "funded across India"
            },
            {
                "fieldname": "changemaker_fund_stat_3_label",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Stat 3 Label",
                "default": "Average Cost"
            },
            {
                "fieldname": "changemaker_fund_stat_3_value",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Stat 3 Value",
                "default": "₹25,000"
            },
            {
                "fieldname": "changemaker_fund_stat_3_description",
                "fieldtype": "Data",
                "label": "Changemaker Fund - Stat 3 Description",
                "default": "per project"
            },
            
            # City Chapters Section
            {
                "fieldname": "city_chapters_title",
                "fieldtype": "Data",
                "label": "City Chapters - Title",
                "default": "Be the Spark in Your City"
            },
            {
                "fieldname": "city_chapters_description",
                "fieldtype": "Text",
                "label": "City Chapters - Description",
                "default": "Take Solve Ninja to the next level — launch or lead a City Chapter in your community. Shape how young people organize, act, and sustain change."
            },
            {
                "fieldname": "city_chapters_pathways_title",
                "fieldtype": "Data",
                "label": "City Chapters - Pathways Title",
                "default": "Pathways"
            },
            {
                "fieldname": "city_chapters_start_chapter_button",
                "fieldtype": "Data",
                "label": "City Chapters - Start Chapter Button",
                "default": "Start a Chapter →"
            },
            {
                "fieldname": "city_chapters_lead_chapter_button",
                "fieldtype": "Data",
                "label": "City Chapters - Lead Chapter Button",
                "default": "Lead a Chapter →"
            },
            {
                "fieldname": "city_chapters_community_highlight_title",
                "fieldtype": "Data",
                "label": "City Chapters - Community Highlight Title",
                "default": "Community Highlight"
            },
            
            
            # City Chapters Stats
            {
                "fieldname": "city_chapters_stat_1_label",
                "fieldtype": "Data",
                "label": "City Chapters - Stat 1 Label",
                "default": "Active Chapters"
            },
            {
                "fieldname": "city_chapters_stat_1_value",
                "fieldtype": "Data",
                "label": "City Chapters - Stat 1 Value",
                "default": "12"
            },
            {
                "fieldname": "city_chapters_stat_2_label",
                "fieldtype": "Data",
                "label": "City Chapters - Stat 2 Label",
                "default": "Events Last Year"
            },
            {
                "fieldname": "city_chapters_stat_2_value",
                "fieldtype": "Data",
                "label": "City Chapters - Stat 2 Value",
                "default": "100+"
            },
            {
                "fieldname": "city_chapters_stat_3_label",
                "fieldtype": "Data",
                "label": "City Chapters - Stat 3 Label",
                "default": "Ninjas Supported"
            },
            {
                "fieldname": "city_chapters_stat_3_value",
                "fieldtype": "Data",
                "label": "City Chapters - Stat 3 Value",
                "default": "5,000+"
            },
            
            # City Chapters Mobile Stats
            {
                "fieldname": "city_chapters_mobile_stat_1_label",
                "fieldtype": "Data",
                "label": "City Chapters - Mobile Stat 1 Label",
                "default": "active city communities"
            },
            {
                "fieldname": "city_chapters_mobile_stat_1_value",
                "fieldtype": "Data",
                "label": "City Chapters - Mobile Stat 1 Value",
                "default": "12"
            },
            {
                "fieldname": "city_chapters_mobile_stat_2_label",
                "fieldtype": "Data",
                "label": "City Chapters - Mobile Stat 2 Label",
                "default": "events last year"
            },
            {
                "fieldname": "city_chapters_mobile_stat_2_value",
                "fieldtype": "Data",
                "label": "City Chapters - Mobile Stat 2 Value",
                "default": "100+"
            },
            {
                "fieldname": "city_chapters_mobile_stat_3_label",
                "fieldtype": "Data",
                "label": "City Chapters - Mobile Stat 3 Label",
                "default": "Ninjas supported"
            },
            {
                "fieldname": "city_chapters_mobile_stat_3_value",
                "fieldtype": "Data",
                "label": "City Chapters - Mobile Stat 3 Value",
                "default": "5,000+"
            },
            {
                "fieldname": "city_chapters_mobile_stat_4_label",
                "fieldtype": "Data",
                "label": "City Chapters - Mobile Stat 4 Label",
                "default": "pathways to lead"
            },
            {
                "fieldname": "city_chapters_mobile_stat_4_value",
                "fieldtype": "Data",
                "label": "City Chapters - Mobile Stat 4 Value",
                "default": "2"
            },
            
            # CTA Section
            {
                "fieldname": "lead_cta_title",
                "fieldtype": "Data",
                "label": "Lead CTA - Title",
                "default": "Leadership isn't given. It's built — one action at a time."
            },
            {
                "fieldname": "lead_cta_button_text",
                "fieldtype": "Data",
                "label": "Lead CTA - Button Text",
                "default": "Step Up and Lead"
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
        
        print("✅ Successfully created 'Lead Page Content' DocType!")
        print(f"📋 DocType ID: {doc.name}")
        print(f"📁 Module: {doc.module}")
        print(f"🔢 Total Fields: {len(doc.fields)}")
        
    except Exception as e:
        print(f"❌ Error creating DocType: {str(e)}")
        frappe.db.rollback()

if __name__ == "__main__":
    # Initialize Frappe
    frappe.init(site='your-site-name.localhost')  # Replace with your site name
    frappe.connect()
    
    # Create the DocType
    create_lead_page_doctype()
    
    print("\n🎉 Lead Page Content DocType creation completed!")
