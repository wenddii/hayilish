from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.core.paginator import Paginator
import datetime

from accounts.decorators import receptionist_required, owner_required
from .models import Service, Customer, Ticket, TicketService, Payment
from .forms import ServiceForm, AddServiceToTicketForm, PaymentForm, TicketServiceEditForm


# ==========================================
# RECEPTIONIST VIEWS
# ==========================================

@login_required
@receptionist_required
def active_tickets(request):
    """View active/open tickets."""
    tickets = (
        Ticket.objects.filter(status="open")
        .select_related("customer", "created_by")
        .prefetch_related("items__service")
        .order_by("-created_at")
    )
    return render(request, "salon/active_tickets.html", {"tickets": tickets})


@login_required
@receptionist_required
def ticket_create(request):
    """Main receptionist screen: New Ticket."""
    active_services = Service.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        customer_name = request.POST.get("customer_name", "").strip()
        customer_phone = request.POST.get("customer_phone", "").strip()
        service_ids = request.POST.getlist("services[]")

        if not service_ids:
            messages.error(request, "Please select at least one service for the ticket.")
            return render(
                request,
                "salon/ticket_create.html",
                {
                    "active_services": active_services,
                    "customer_name": customer_name,
                    "customer_phone": customer_phone,
                },
            )

        # Handle Customer (Optional)
        customer = None
        if customer_name or customer_phone:
            if customer_phone:
                customer, _ = Customer.objects.get_or_create(
                    phone=customer_phone,
                    defaults={"name": customer_name or "Walk-in Customer"},
                )
                if customer_name and customer.name != customer_name:
                    customer.name = customer_name
                    customer.save()
            else:
                customer = Customer.objects.create(name=customer_name)

        # Create Ticket
        ticket = Ticket.objects.create(
            customer=customer,
            created_by=request.user,
            status="open",
        )

        # Create TicketServices in the order received
        for index, s_id in enumerate(service_ids, start=1):
            try:
                service = Service.objects.get(id=s_id)
                TicketService.objects.create(
                    ticket=ticket,
                    service=service,
                    order=index,
                    price=service.price,  # Snapshot historical price
                )
            except Service.DoesNotExist:
                continue

        messages.success(request, f"Ticket #{ticket.id} created successfully.")

        if "create_and_print" in request.POST:
            return redirect(f"/tickets/{ticket.id}/print/?auto=1")
        return redirect("ticket_detail", ticket_id=ticket.id)

    return render(
        request,
        "salon/ticket_create.html",
        {"active_services": active_services},
    )


@login_required
def ticket_detail(request, ticket_id):
    """View ticket details, services in order, payment status, and actions."""
    ticket = get_object_or_404(
        Ticket.objects.select_related("customer", "created_by").prefetch_related(
            "items__service", "payment"
        ),
        id=ticket_id,
    )
    items = ticket.items.all().order_by("order")
    payment = getattr(ticket, "payment", None)

    add_service_form = AddServiceToTicketForm()
    payment_form = PaymentForm(initial={"amount": ticket.total, "method": "cash"})

    return render(
        request,
        "salon/ticket_detail.html",
        {
            "ticket": ticket,
            "items": items,
            "payment": payment,
            "add_service_form": add_service_form,
            "payment_form": payment_form,
        },
    )


@login_required
@receptionist_required
def ticket_add_service(request, ticket_id):
    """Add another service to an existing ticket (open or completed)."""
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.status == "cancelled":
        messages.error(request, "Cannot add services to a cancelled ticket.")
        return redirect("ticket_detail", ticket_id=ticket.id)

    if request.method == "POST":
        form = AddServiceToTicketForm(request.POST)
        if form.is_valid():
            service = form.cleaned_data["service"]
            max_order = (
                ticket.items.aggregate(max_order=models.Max("order"))["max_order"]
                or 0
            )
            TicketService.objects.create(
                ticket=ticket,
                service=service,
                order=max_order + 1,
                price=service.price,
            )

            # Recalculate ticket total and update payment record if payment exists
            if hasattr(ticket, "payment"):
                ticket.payment.amount = ticket.total
                ticket.payment.save()

            messages.success(
                request, f"Added {service.name} ({service.price} ETB) to Ticket #{ticket.id}."
            )
        else:
            messages.error(request, "Invalid service selected.")

    return redirect("ticket_detail", ticket_id=ticket.id)


@login_required
@receptionist_required
def ticket_remove_service(request, ticket_id, item_id):
    """Remove a service item from a ticket (open or completed)."""
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.status == "cancelled":
        messages.error(request, "Cannot modify a cancelled ticket.")
        return redirect("ticket_detail", ticket_id=ticket.id)

    item = get_object_or_404(TicketService, id=item_id, ticket=ticket)

    if request.method == "POST":
        service_name = item.service.name
        item.delete()

        # Re-sequence remaining items
        for idx, remaining_item in enumerate(ticket.items.all().order_by("order"), start=1):
            if remaining_item.order != idx:
                remaining_item.order = idx
                remaining_item.save()

        # Recalculate ticket total and update payment record if payment exists
        if hasattr(ticket, "payment"):
            ticket.payment.amount = ticket.total
            ticket.payment.save()

        messages.info(request, f"Removed {service_name} from Ticket #{ticket.id}.")

    return redirect("ticket_detail", ticket_id=ticket.id)


@login_required
@receptionist_required
def ticket_edit_service(request, ticket_id, item_id):
    """Edit an existing service item on a ticket (service, price, or order)."""
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.status == "cancelled":
        messages.error(request, "Cannot edit a cancelled ticket.")
        return redirect("ticket_detail", ticket_id=ticket.id)

    item = get_object_or_404(TicketService, id=item_id, ticket=ticket)

    if request.method == "POST":
        form = TicketServiceEditForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            # Recalculate ticket total and update payment record if payment exists
            if hasattr(ticket, "payment"):
                ticket.payment.amount = ticket.total
                ticket.payment.save()
            messages.success(request, f"Updated service item #{item.order} on Ticket #{ticket.id}.")
            return redirect("ticket_detail", ticket_id=ticket.id)
    else:
        form = TicketServiceEditForm(instance=item)

    return render(
        request,
        "salon/ticket_service_edit.html",
        {"ticket": ticket, "item": item, "form": form},
    )


@login_required
@receptionist_required
def ticket_complete(request, ticket_id):
    """Record payment and complete/close the ticket."""
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.status != "open":
        messages.error(request, "This ticket is already closed.")
        return redirect("ticket_detail", ticket_id=ticket.id)

    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment, created = Payment.objects.update_or_create(
                ticket=ticket,
                defaults={
                    "amount": form.cleaned_data["amount"],
                    "method": form.cleaned_data["method"],
                },
            )
            ticket.status = "completed"
            ticket.completed_at = timezone.now()
            ticket.save()
            messages.success(
                request,
                f"Ticket #{ticket.id} completed! Payment of {payment.amount} ETB recorded via {payment.get_method_display()}.",
            )
            if "complete_and_print" in request.POST:
                return redirect(f"/tickets/{ticket.id}/print/?auto=1")
            return redirect("ticket_detail", ticket_id=ticket.id)
        else:
            messages.error(request, "Please enter valid payment details.")

    return redirect("ticket_detail", ticket_id=ticket.id)


@login_required
@receptionist_required
def ticket_cancel(request, ticket_id):
    """Cancel an open ticket."""
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.status != "open":
        messages.error(request, "Only open tickets can be cancelled.")
        return redirect("ticket_detail", ticket_id=ticket.id)

    if request.method == "POST":
        ticket.status = "cancelled"
        ticket.completed_at = timezone.now()
        ticket.save()
        messages.info(request, f"Ticket #{ticket.id} has been cancelled.")
        return redirect("active_tickets")

    return redirect("ticket_detail", ticket_id=ticket.id)


@login_required
def ticket_print(request, ticket_id):
    """58mm Thermal receipt print view."""
    ticket = get_object_or_404(
        Ticket.objects.select_related("customer", "created_by").prefetch_related(
            "items__service", "payment"
        ),
        id=ticket_id,
    )
    items = ticket.items.all().order_by("order")
    payment = getattr(ticket, "payment", None)
    auto_print = request.GET.get("auto") == "1"

    return render(
        request,
        "salon/ticket_print.html",
        {
            "ticket": ticket,
            "items": items,
            "payment": payment,
            "auto_print": auto_print,
        },
    )


@login_required
def ticket_history(request):
    """Search and filter historical tickets."""
    status_filter = request.GET.get("status", "all")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    query = request.GET.get("q", "").strip()

    tickets = (
        Ticket.objects.all()
        .select_related("customer", "created_by")
        .prefetch_related("items", "payment")
        .order_by("-created_at")
    )

    if status_filter in ["open", "completed", "cancelled"]:
        tickets = tickets.filter(status=status_filter)

    if date_from:
        try:
            d_from = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
            tickets = tickets.filter(created_at__date__gte=d_from)
        except ValueError:
            pass

    if date_to:
        try:
            d_to = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
            tickets = tickets.filter(created_at__date__lte=d_to)
        except ValueError:
            pass

    if query:
        if query.isdigit():
            tickets = tickets.filter(
                models.Q(id=int(query))
                | models.Q(customer__phone__icontains=query)
            )
        else:
            tickets = tickets.filter(
                models.Q(customer__name__icontains=query)
                | models.Q(customer__phone__icontains=query)
            )

    paginator = Paginator(tickets, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "salon/ticket_history.html",
        {
            "page_obj": page_obj,
            "status_filter": status_filter,
            "date_from": date_from,
            "date_to": date_to,
            "query": query,
        },
    )


# ==========================================
# OWNER VIEWS
# ==========================================

@login_required
@owner_required
def owner_dashboard(request):
    """Owner dashboard: Today's summary and open tickets."""
    today = timezone.localdate()

    # Today's metrics
    today_tickets = Ticket.objects.filter(created_at__date=today)
    today_tickets_count = today_tickets.count()

    today_revenue = (
        Payment.objects.filter(ticket__status="completed", paid_at__date=today)
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    today_services_count = (
        TicketService.objects.filter(created_at__date=today).count()
    )

    open_tickets_count = Ticket.objects.filter(status="open").count()

    recent_tickets_today = (
        today_tickets.select_related("customer", "created_by")
        .prefetch_related("items", "payment")
        .order_by("-created_at")[:10]
    )

    return render(
        request,
        "salon/owner_dashboard.html",
        {
            "today": today,
            "today_tickets_count": today_tickets_count,
            "today_revenue": today_revenue,
            "today_services_count": today_services_count,
            "open_tickets_count": open_tickets_count,
            "recent_tickets": recent_tickets_today,
        },
    )


@login_required
@owner_required
def owner_reports(request):
    """Owner reports: Revenue breakdowns, counts, and service performance."""
    today = timezone.localdate()
    # Default date range: last 30 days
    default_start = today - datetime.timedelta(days=29)
    start_date_str = request.GET.get("start_date", default_start.strftime("%Y-%m-%d"))
    end_date_str = request.GET.get("end_date", today.strftime("%Y-%m-%d"))

    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        start_date = default_start

    try:
        end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        end_date = today

    # Filtered base queries
    completed_payments = Payment.objects.filter(
        ticket__status="completed",
        paid_at__date__gte=start_date,
        paid_at__date__lte=end_date,
    )

    filtered_tickets = Ticket.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )

    # Metrics
    total_revenue = (
        completed_payments.aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    total_tickets = filtered_tickets.count()
    completed_tickets_count = filtered_tickets.filter(status="completed").count()

    total_customers = (
        filtered_tickets.filter(customer__isnull=False)
        .values("customer")
        .distinct()
        .count()
    )

    # Daily revenue breakdown (ordered newest first)
    daily_revenue = (
        completed_payments.annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(total=Sum("amount"), ticket_count=Count("id"))
        .order_by("-day")
    )

    # Weekly revenue breakdown
    weekly_revenue = (
        completed_payments.annotate(week=TruncWeek("paid_at"))
        .values("week")
        .annotate(total=Sum("amount"), ticket_count=Count("id"))
        .order_by("-week")[:8]
    )

    # Monthly revenue breakdown
    monthly_revenue = (
        completed_payments.annotate(month=TruncMonth("paid_at"))
        .values("month")
        .annotate(total=Sum("amount"), ticket_count=Count("id"))
        .order_by("-month")[:12]
    )

    # Most-used services in this range
    service_stats = (
        TicketService.objects.filter(
            ticket__created_at__date__gte=start_date,
            ticket__created_at__date__lte=end_date,
            ticket__status="completed",
        )
        .values("service__name")
        .annotate(
            usage_count=Count("id"),
            total_revenue=Sum("price"),
        )
        .order_by("-usage_count", "-total_revenue")
    )

    # Payment method breakdown
    payment_methods = (
        completed_payments.values("method")
        .annotate(total_amount=Sum("amount"), count=Count("id"))
        .order_by("-total_amount")
    )

    return render(
        request,
        "salon/owner_reports.html",
        {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "total_revenue": total_revenue,
            "total_tickets": total_tickets,
            "completed_tickets_count": completed_tickets_count,
            "total_customers": total_customers,
            "daily_revenue": daily_revenue,
            "weekly_revenue": weekly_revenue,
            "monthly_revenue": monthly_revenue,
            "service_stats": service_stats,
            "payment_methods": payment_methods,
        },
    )


@login_required
@owner_required
def service_list(request):
    """Manage salon services (List, Add, Toggle Active)."""
    services = Service.objects.all().order_by("-is_active", "name")
    form = ServiceForm()

    if request.method == "POST":
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save()
            messages.success(request, f"Service '{service.name}' added successfully.")
            return redirect("service_list")
        else:
            messages.error(request, "Please correct the errors below.")

    return render(
        request,
        "salon/service_list.html",
        {"services": services, "form": form},
    )


@login_required
@owner_required
def service_edit(request, service_id):
    """Edit service name, price, or active status."""
    service = get_object_or_404(Service, id=service_id)

    if request.method == "POST":
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, f"Service '{service.name}' updated successfully.")
            return redirect("service_list")
    else:
        form = ServiceForm(instance=service)

    return render(
        request,
        "salon/service_edit.html",
        {"service": service, "form": form},
    )


@login_required
@owner_required
def service_toggle(request, service_id):
    """Toggle service active status (never delete to protect ticket history)."""
    service = get_object_or_404(Service, id=service_id)
    if request.method == "POST":
        service.is_active = not service.is_active
        service.save()
        status_str = "activated" if service.is_active else "deactivated"
        messages.info(request, f"Service '{service.name}' has been {status_str}.")
    return redirect("service_list")
