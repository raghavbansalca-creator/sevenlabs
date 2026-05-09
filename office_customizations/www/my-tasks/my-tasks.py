import frappe

no_cache = 1
sitemap = 0

def get_context(context):
    # Redirect guests to login
    if frappe.session.user == "Guest":
        frappe.throw("Please login to access this page", frappe.AuthenticationError)

    context.show_sidebar = False
    context.no_header = True
    context.title = "My Tasks"
