# monapp/signals.py
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from veille.models import UserProfile  # ⚠️ adapte au nom de ton app


@receiver(user_logged_in)
def ensure_user_profile(sender, user, request, **kwargs):
    """
    Crée automatiquement un UserProfile pour tout utilisateur qui se connecte,
    s'il n'existe pas encore.
    """
    UserProfile.objects.get_or_create(
        user=user,
        defaults={'is_premium': user.is_superuser}
    )
