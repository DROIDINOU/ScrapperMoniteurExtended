from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Mots-clés utilisateurs (veille globale MeiliSearch)
    keyword1 = models.CharField(max_length=100, blank=True, null=True)
    keyword2 = models.CharField(max_length=100, blank=True, null=True)
    keyword3 = models.CharField(max_length=100, blank=True, null=True)

    is_premium = models.BooleanField(default=False)

    def __str__(self):
        return f"Profil de {self.user.username}"

    def clean(self):
        """ Validation des mots-clés """
        max_words = 5  # Limite à 5 mots par mot-clé
        max_length = 100  # Limite à 100 caractères par mot-clé

        # Validation pour chaque mot-clé
        for keyword in [self.keyword1, self.keyword2, self.keyword3]:
            if keyword:
                if len(keyword) > max_length:
                    raise ValidationError(f"Le mot-clé ne doit pas dépasser {max_length} caractères.")
                if len(keyword.split()) > max_words:
                    raise ValidationError(f"Le mot-clé ne doit pas dépasser {max_words} mots.")

    def save(self, *args, **kwargs):
        """ Assurez-vous que les mots-clés respectent les règles avant d'enregistrer l'instance """
        self.clean()  # Appelle la validation personnalisée
        super().save(*args, **kwargs)


class Veille(models.Model):
    TYPE = [
        ("TVA", "Veille TVA"),
        ("KEYWORD", "Veille Mots-clés"),
    ]

    RECURRENCE_CHOICES = [
        ("instant", "Immédiate"),
        ("daily", "Journalier"),
        ("weekly", "Hebdomadaire"),
        ("monthly", "Mensuel"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listes_veille")
    nom = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=TYPE)
    date_creation = models.DateTimeField(auto_now_add=True)
    # 🚀 Ajout pour CRON
    last_scan = models.DateTimeField(null=True, blank=True)

    recurrence = models.CharField(
        max_length=20,
        choices=[
            ("instant", "Immédiate"),
            ("daily", "Tous les jours"),
            ("weekly", "Chaque semaine"),
            ("monthly", "Chaque mois"),
        ],
        default="instant"
    )

    def __str__(self):
        return f"{self.nom} ({self.user.username})"


class VeilleSociete(models.Model):
    veille = models.ForeignKey(Veille, on_delete=models.CASCADE, related_name="societes")
    numero_tva = models.CharField(max_length=20)

    class Meta:
        unique_together = ("veille", "numero_tva")  # ✅ empêche duplicata TVA dans une même veille

    def __str__(self):
        return f"{self.numero_tva}"


class VeilleEvenement(models.Model):
    veille = models.ForeignKey(Veille, on_delete=models.CASCADE, related_name="evenements")
    societe = models.ForeignKey(VeilleSociete, on_delete=models.CASCADE, null=True, blank=True)

    type = models.CharField(max_length=20)  # ANNEXE ou DECISION
    date_publication = models.DateField(null=True, blank=True)
    source = models.URLField(max_length=500)

    rubrique = models.CharField(max_length=500, blank=True, null=True)
    titre = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["veille", "societe", "type", "date_publication", "source"],
                name="uniq_event_by_veille",
            )
        ]

    def __str__(self):
        return f"{self.type} - {self.titre or self.rubrique}"


# *****************************************
# partie insertion scrapper (tu ne touches pas)
# *****************************************
class Decision(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    TVA = models.JSONField(max_length=20, null=True, blank=True)
    date_doc = models.DateField(null=True, blank=True)
    lang = models.TextField(null=True, blank=True)
    text = models.TextField(null=True, blank=True)
    url = models.URLField(unique=True, null=True, blank=True)
    keyword = models.TextField(null=True, blank=True)
    titre = models.TextField(null=True, blank=True)
    extra_keyword = models.JSONField(null=True, blank=True)
    date_jugement = models.JSONField(null=True, blank=True)

    # Informations administrateurs
    administrateur = models.JSONField(null=True, blank=True)

    # Adresses par source
    adresses_by_bce = models.JSONField(null=True, blank=True)
    adresses_by_ejustice = models.JSONField(null=True, blank=True)
    adresses_fallback_bce_flat = models.JSONField(null=True, blank=True)
    adresses_all_flat = models.JSONField(null=True, blank=True)

    # Dénominations par source
    denoms_by_bce = models.JSONField(null=True, blank=True)
    denoms_by_ejustice_flat = models.JSONField(null=True, blank=True)
    denom_fallback_bce = models.JSONField(null=True, blank=True)
    denoms_bce_flat = models.JSONField(null=True, blank=True)
    denoms_fallback_bce_flat = models.JSONField(null=True, blank=True)

    # Autres infos possibles
    adresses_bce_flat = models.JSONField(null=True, blank=True)
    adresses_ejustice_flat = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.titre or f"Décision {self.id}"


class Societe(models.Model):
    bce = models.CharField(max_length=20, unique=True)
    nom = models.TextField(null=True, blank=True)
    adresse = models.TextField(null=True, blank=True)
    source = models.TextField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    json_source = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.nom or self.bce


class Administrateur(models.Model):
    nom = models.TextField()
    role = models.TextField(null=True, blank=True)
    source = models.TextField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.nom


class DecisionSociete(models.Model):
    decision = models.ForeignKey(Decision, on_delete=models.CASCADE)
    societe = models.ForeignKey(Societe, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("decision", "societe")


class SocieteAdmin(models.Model):
    societe = models.ForeignKey(Societe, on_delete=models.CASCADE)
    admin = models.ForeignKey(Administrateur, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("societe", "admin")
