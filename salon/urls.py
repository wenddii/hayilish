from django.urls import path
from . import views

urlpatterns = [
    # Default root: receptionist dashboard / active tickets
    path("", views.active_tickets, name="active_tickets"),
    
    # Receptionist Ticket Workflows
    path("tickets/new/", views.ticket_create, name="ticket_create"),
    path("tickets/active/", views.active_tickets, name="active_tickets_alias"),
    path("tickets/history/", views.ticket_history, name="ticket_history"),
    path("tickets/<int:ticket_id>/", views.ticket_detail, name="ticket_detail"),
    path("tickets/<int:ticket_id>/add-service/", views.ticket_add_service, name="ticket_add_service"),
    path("tickets/<int:ticket_id>/items/<int:item_id>/edit/", views.ticket_edit_service, name="ticket_edit_service"),
    path("tickets/<int:ticket_id>/items/<int:item_id>/remove/", views.ticket_remove_service, name="ticket_remove_service"),
    path("tickets/<int:ticket_id>/complete/", views.ticket_complete, name="ticket_complete"),
    path("tickets/<int:ticket_id>/cancel/", views.ticket_cancel, name="ticket_cancel"),
    path("tickets/<int:ticket_id>/print/", views.ticket_print, name="ticket_print"),

    # Owner Dashboard, Reports, and Services
    path("owner/", views.owner_dashboard, name="owner_dashboard"),
    path("owner/reports/", views.owner_reports, name="owner_reports"),
    path("owner/services/", views.service_list, name="service_list"),
    path("owner/services/<int:service_id>/edit/", views.service_edit, name="service_edit"),
    path("owner/services/<int:service_id>/toggle/", views.service_toggle, name="service_toggle"),
]
