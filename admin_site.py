"""
Custom admin site configuration for OpenWISP with build version display
"""
from django.contrib import admin
from django.contrib.admin import AdminSite


# Custom admin site with version
class OpenWISPAdminSite(AdminSite):
    site_header = 'OpenWISP Administration'
    site_title = 'OpenWISP Admin'
    index_title = 'Welcome to OpenWISP'
    
    def each_context(self, request):
        """Add custom context variables to admin"""
        context = super().each_context(request)
        # Add build version
        context['build_version'] = 'v1.0.0'
        return context


# Replace default admin site
admin.site = OpenWISPAdminSite()
admin.sites.site = admin.site
