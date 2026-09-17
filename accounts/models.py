from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("receptionist", "Receptionist"),
        ("owner", "Owner"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="receptionist",
    )

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_owner(self):
        return self.role == "owner" or self.user.is_superuser

    @property
    def is_receptionist(self):
        return self.role == "receptionist" or self.user.is_superuser


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        default_role = "owner" if instance.is_superuser else "receptionist"
        UserProfile.objects.create(user=instance, role=default_role)
    else:
        if hasattr(instance, "profile"):
            instance.profile.save()
        else:
            default_role = "owner" if instance.is_superuser else "receptionist"
            UserProfile.objects.create(user=instance, role=default_role)
