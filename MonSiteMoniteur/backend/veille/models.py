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


class VeilleSociete(models.Model):
    numero_tva = models.CharField(max_length=20, unique=True, db_index=True)   # ✅ UNIQUE
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="veilles"
    )
    date_ajout = models.DateTimeField(auto_now_add=True)


class VeilleEvenement(models.Model):
    TYPE = [
        ("ANNEXE", "Annexe Moniteur (PDF / publication officielle)"),
        ("DECISION", "Décision judiciaire MeiliSearch"),
    ]

    societe = models.ForeignKey(
        VeilleSociete,
        on_delete=models.CASCADE,
        related_name="evenements"
    )
    type = models.CharField(max_length=10, choices=TYPE)        # ✅ <--- nouveau
    rubrique = models.CharField(max_length=255)
    titre = models.CharField(max_length=500, blank=True)
    date_publication = models.DateField()
    source = models.URLField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["societe", "type", "date_publication", "source"],
                name="uniq_event_by_source_type_date"
            )
        ]
