from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    # Lien 1-to-1 avec l'utilisateur Django
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        help_text="Utilisateur auquel ce profil est associé."
    )

    # Jusqu'à 3 mots-clés gratuits
    keyword1 = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Premier mot-clé gratuit."
    )
    keyword2 = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Deuxième mot-clé gratuit."
    )
    keyword3 = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Troisième mot-clé gratuit."
    )

    # Prévoir le mode payant (false par défaut)
    is_premium = models.BooleanField(
        default=False,
        help_text="Indique si l'utilisateur a un abonnement premium."
    )

    def __str__(self):
        return f"Profil de {self.user.username}"

