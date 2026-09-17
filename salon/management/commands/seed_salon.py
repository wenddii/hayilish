from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal

from salon.models import Service
from accounts.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Seed initial salon services and receptionist/owner user accounts"

    def handle(self, *args, **options):
        # 1. Ensure receptionist user exists
        rec_user, rec_created = User.objects.get_or_create(
            username="receptionist",
            defaults={
                "first_name": "Salon",
                "last_name": "Receptionist",
                "is_staff": False,
            }
        )
        if rec_created:
            rec_user.set_password("receptionist123")
            rec_user.save()
            self.stdout.write(self.style.SUCCESS("Created user 'receptionist' with password 'receptionist123'."))

        rec_profile, _ = UserProfile.objects.get_or_create(user=rec_user)
        rec_profile.role = "receptionist"
        rec_profile.save()

        # 2. Ensure owner user exists (or update first user)
        first_user = User.objects.filter(is_superuser=True).first()
        if first_user:
            profile, _ = UserProfile.objects.get_or_create(user=first_user)
            profile.role = "owner"
            profile.save()
            self.stdout.write(self.style.SUCCESS(f"Configured '{first_user.username}' as Owner."))

        # 3. Seed Services
        initial_services = [
            ("Hair Wash", Decimal("150.00")),
            ("Hair Cut", Decimal("300.00")),
            ("Hair Color", Decimal("800.00")),
            ("Blow Dry", Decimal("250.00")),
            ("Eyebrow", Decimal("100.00")),
            ("Hair Treatment", Decimal("500.00")),
            ("Facial", Decimal("600.00")),
        ]

        created_count = 0
        for name, price in initial_services:
            svc, created = Service.objects.get_or_create(
                name=name,
                defaults={"price": price, "is_active": True}
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} services (total services: {Service.objects.count()})."))
