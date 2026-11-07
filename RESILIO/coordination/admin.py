from django.contrib import admin
from .models import (
    Profile,
    Category,
    Item,
    Offer,
    HelpRequest,
    Assignment,
    Delivery,
    Notification,
    Report,
    Shelter,
    Audit,
)


# Operations use validated application services; do not bypass allocation invariants.
class OperationalReadOnly(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in [
    Profile,
    Category,
    Item,
    Offer,
    HelpRequest,
    Assignment,
    Delivery,
    Notification,
    Report,
    Shelter,
    Audit,
]:
    admin.site.register(model, OperationalReadOnly)
admin.site.site_header = "RESILIO administration"
