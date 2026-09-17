from django.contrib import admin
from .models import Service, Customer, Ticket, TicketService, Payment


class TicketServiceInline(admin.TabularInline):
    model = TicketService
    extra = 0
    ordering = ("order",)


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone")
    search_fields = ("name", "phone")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "status", "created_by", "created_at", "completed_at", "total")
    list_filter = ("status", "created_at")
    search_fields = ("id", "customer__name", "customer__phone")
    inlines = [TicketServiceInline, PaymentInline]


@admin.register(TicketService)
class TicketServiceAdmin(admin.ModelAdmin):
    list_display = ("ticket", "service", "order", "price", "created_at")
    list_filter = ("service", "created_at")
    ordering = ("ticket", "order")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "amount", "method", "paid_at")
    list_filter = ("method", "paid_at")
