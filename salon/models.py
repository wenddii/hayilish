from django.conf import settings
from django.db import models


class Service(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Customer(models.Model):
    name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.name or self.phone or "Walk-in Customer"


class Ticket(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tickets",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Ticket #{self.id}"

    @property
    def total(self):
        return sum(item.price for item in self.items.all())


class TicketService(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="items",
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="ticket_items",
    )

    order = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.ticket} - {self.service}"


class Payment(models.Model):
    PAYMENT_METHODS = [
        ("cash", "Cash"),
        ("telebirr", "Telebirr"),
        ("bank", "Bank"),
    ]

    ticket = models.OneToOneField(
        Ticket,
        on_delete=models.CASCADE,
        related_name="payment",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
    )

    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for Ticket #{self.ticket.id}"