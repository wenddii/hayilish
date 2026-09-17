from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from salon.models import Service, Customer, Ticket, TicketService, Payment

User = get_user_model()


class SalonWorkflowTests(TestCase):
    def setUp(self):
        # Create users
        self.receptionist = User.objects.create_user(
            username="test_rec", password="password123"
        )
        UserProfile.objects.filter(user=self.receptionist).update(role="receptionist")

        self.owner = User.objects.create_user(
            username="test_owner", password="password123"
        )
        UserProfile.objects.filter(user=self.owner).update(role="owner")

        # Create Services
        self.s1 = Service.objects.create(name="Hair Wash", price=Decimal("150.00"), is_active=True)
        self.s2 = Service.objects.create(name="Hair Cut", price=Decimal("300.00"), is_active=True)
        self.s3 = Service.objects.create(name="Hair Color", price=Decimal("800.00"), is_active=True)
        self.s4 = Service.objects.create(name="Blow Dry", price=Decimal("250.00"), is_active=True)
        self.s_inactive = Service.objects.create(name="Old Style", price=Decimal("50.00"), is_active=False)

        self.client = Client()

    def test_create_ticket_workflow(self):
        """Test creating a ticket with services in a specific order."""
        self.client.login(username="test_rec", password="password123")
        response = self.client.post(
            reverse("ticket_create"),
            {
                "customer_name": "Abebe Bikila",
                "customer_phone": "0911223344",
                "services[]": [str(self.s1.id), str(self.s2.id), str(self.s3.id), str(self.s4.id)],
            },
        )
        self.assertEqual(response.status_code, 302)

        ticket = Ticket.objects.latest("id")
        self.assertEqual(ticket.customer.name, "Abebe Bikila")
        self.assertEqual(ticket.customer.phone, "0911223344")
        self.assertEqual(ticket.status, "open")
        self.assertEqual(ticket.items.count(), 4)

        # Verify ordering is strictly preserved: 1, 2, 3, 4
        items = list(ticket.items.all().order_by("order"))
        self.assertEqual(items[0].service, self.s1)
        self.assertEqual(items[0].order, 1)
        self.assertEqual(items[0].price, Decimal("150.00"))

        self.assertEqual(items[1].service, self.s2)
        self.assertEqual(items[1].order, 2)
        self.assertEqual(items[1].price, Decimal("300.00"))

        self.assertEqual(items[2].service, self.s3)
        self.assertEqual(items[2].order, 3)
        self.assertEqual(items[2].price, Decimal("800.00"))

        self.assertEqual(items[3].service, self.s4)
        self.assertEqual(items[3].order, 4)
        self.assertEqual(items[3].price, Decimal("250.00"))

        # Verify total calculation
        self.assertEqual(ticket.total, Decimal("1500.00"))

    def test_historical_price_integrity(self):
        """Test that changing a service price does NOT change past ticket service price."""
        ticket = Ticket.objects.create(created_by=self.receptionist, status="open")
        item = TicketService.objects.create(
            ticket=ticket, service=self.s1, order=1, price=self.s1.price
        )
        self.assertEqual(item.price, Decimal("150.00"))

        # Owner changes service price
        self.s1.price = Decimal("250.00")
        self.s1.save()

        # Ticket item price remains unchanged
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal("150.00"))
        self.assertEqual(ticket.total, Decimal("150.00"))

    def test_add_service_to_existing_ticket(self):
        """Test adding another service later increments order properly."""
        self.client.login(username="test_rec", password="password123")
        ticket = Ticket.objects.create(created_by=self.receptionist, status="open")
        TicketService.objects.create(ticket=ticket, service=self.s1, order=1, price=self.s1.price)

        # Add second service via view
        response = self.client.post(
            reverse("ticket_add_service", args=[ticket.id]),
            {"service": self.s2.id},
        )
        self.assertEqual(response.status_code, 302)

        items = ticket.items.all().order_by("order")
        self.assertEqual(items.count(), 2)
        self.assertEqual(items[1].service, self.s2)
        self.assertEqual(items[1].order, 2)
        self.assertEqual(items[1].price, Decimal("300.00"))
        self.assertEqual(ticket.total, Decimal("450.00"))

    def test_complete_ticket_and_record_payment(self):
        """Test completing a ticket with payment method."""
        self.client.login(username="test_rec", password="password123")
        ticket = Ticket.objects.create(created_by=self.receptionist, status="open")
        TicketService.objects.create(ticket=ticket, service=self.s2, order=1, price=self.s2.price)

        response = self.client.post(
            reverse("ticket_complete", args=[ticket.id]),
            {"method": "telebirr", "amount": "300.00"},
        )
        self.assertEqual(response.status_code, 302)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "completed")
        self.assertIsNotNone(ticket.completed_at)
        self.assertTrue(hasattr(ticket, "payment"))
        self.assertEqual(ticket.payment.method, "telebirr")
        self.assertEqual(ticket.payment.amount, Decimal("300.00"))

    def test_58mm_print_view(self):
        """Test that the 58mm thermal print view loads successfully."""
        self.client.login(username="test_rec", password="password123")
        ticket = Ticket.objects.create(created_by=self.receptionist, status="open")
        TicketService.objects.create(ticket=ticket, service=self.s1, order=1, price=self.s1.price)

        response = self.client.get(reverse("ticket_print", args=[ticket.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HAYILISH COLOR BAR")
        self.assertContains(response, f"Ticket #{ticket.id}")
        self.assertContains(response, "Hair Wash")
        self.assertContains(response, "150.00 ETB")

    def test_role_permissions(self):
        """Test that receptionists cannot access owner dashboard or reports."""
        self.client.login(username="test_rec", password="password123")
        resp = self.client.get(reverse("owner_dashboard"))
        # Should redirect to ticket_create
        self.assertEqual(resp.status_code, 302)

        resp2 = self.client.get(reverse("owner_reports"))
        self.assertEqual(resp2.status_code, 302)

        # Owner can access owner pages
        self.client.login(username="test_owner", password="password123")
        resp3 = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(resp3.status_code, 200)

        resp4 = self.client.get(reverse("owner_reports"))
        self.assertEqual(resp4.status_code, 200)

    def test_owner_service_toggle(self):
        """Test owner deactivating and reactivating a service."""
        self.client.login(username="test_owner", password="password123")
        self.assertTrue(self.s1.is_active)

        response = self.client.post(reverse("service_toggle", args=[self.s1.id]))
        self.assertEqual(response.status_code, 302)
        self.s1.refresh_from_db()
        self.assertFalse(self.s1.is_active)

        # Toggle back
        self.client.post(reverse("service_toggle", args=[self.s1.id]))
        self.s1.refresh_from_db()
        self.assertTrue(self.s1.is_active)

    def test_post_payment_service_modifications(self):
        """Test adding, editing, and removing services on a completed/paid ticket."""
        self.client.login(username="test_rec", password="password123")
        ticket = Ticket.objects.create(created_by=self.receptionist, status="open")
        item1 = TicketService.objects.create(ticket=ticket, service=self.s1, order=1, price=self.s1.price) # 150
        item2 = TicketService.objects.create(ticket=ticket, service=self.s2, order=2, price=self.s2.price) # 300

        # 1. Complete ticket with Telebirr payment
        self.client.post(
            reverse("ticket_complete", args=[ticket.id]),
            {"method": "telebirr", "amount": "450.00"},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "completed")
        self.assertEqual(ticket.payment.amount, Decimal("450.00"))

        # 2. Add service post-payment (s3 = 800 ETB)
        add_resp = self.client.post(
            reverse("ticket_add_service", args=[ticket.id]),
            {"service": self.s3.id},
        )
        self.assertEqual(add_resp.status_code, 302)
        ticket.refresh_from_db()
        ticket.payment.refresh_from_db()
        self.assertEqual(ticket.items.count(), 3)
        self.assertEqual(ticket.total, Decimal("1250.00"))
        self.assertEqual(ticket.payment.amount, Decimal("1250.00"))

        # 3. Edit service item post-payment (change price of item1 to 200.00)
        edit_resp = self.client.post(
            reverse("ticket_edit_service", args=[ticket.id, item1.id]),
            {"service": self.s1.id, "price": "200.00", "order": 1},
        )
        self.assertEqual(edit_resp.status_code, 302)
        ticket.refresh_from_db()
        ticket.payment.refresh_from_db()
        self.assertEqual(ticket.total, Decimal("1300.00"))
        self.assertEqual(ticket.payment.amount, Decimal("1300.00"))

        # 4. Remove service item post-payment (remove item2 = 300.00)
        del_resp = self.client.post(
            reverse("ticket_remove_service", args=[ticket.id, item2.id]),
        )
        self.assertEqual(del_resp.status_code, 302)
        ticket.refresh_from_db()
        ticket.payment.refresh_from_db()
        self.assertEqual(ticket.items.count(), 2)
        self.assertEqual(ticket.total, Decimal("1000.00"))
        self.assertEqual(ticket.payment.amount, Decimal("1000.00"))
