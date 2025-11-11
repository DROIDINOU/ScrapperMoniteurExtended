from django.core.management.base import BaseCommand
from django.conf import settings
from veille.models import VeilleSociete, VeilleEvenement, Veille
import meilisearch
from django.core.mail import send_mail


class Command(BaseCommand):
    help = "Importe depuis MeiliSearch les décisions judiciaires et crée des événements liés aux TVA surveillées"

    def handle(self, *args, **kwargs):
        client = meilisearch.Client(
            settings.MEILI_URL,
            settings.MEILI_MASTER_KEY
        )

        index_name = getattr(settings, "MEILI_INDEX_DECISIONS", "moniteur_docs")
        index = client.index(index_name)

        self.stdout.write("📡 Chargement des sociétés surveillées…")

        societes = VeilleSociete.objects.all()

        count_total = 0
        count_created = 0
        count_before = 0  # Compteur des événements avant l'exécution

        for societe in societes:
            tva = societe.numero_tva.replace(".", "").replace(" ", "")

            # Compte les événements existants pour cette société avant l'exécution du scraper
            count_before = VeilleEvenement.objects.filter(societe=societe).count()
            print(f"voici le count avant {count_before}")
            # Recherche des résultats MeiliSearch
            results = index.search("", {"filter": f'TVA = "{tva}"'})
            hits = results.get("hits", [])
            count_total += len(hits)

            for doc in hits:
                # Vérifie si l'événement existe déjà dans la base de données
                evenement_exists = VeilleEvenement.objects.filter(
                    societe=societe,
                    date_publication=doc.get("date_doc"),
                    type="DECISION",  # ou "ANNEXE", selon le type
                    source=doc.get("url")
                ).exists()

                if evenement_exists:
                    self.stdout.write("⏩ Événement déjà existant.")  # Si l'événement existe déjà, on passe à l'événement suivant
                    continue

                # Si l'événement n'existe pas, on le crée
                evenement = VeilleEvenement.objects.create(
                    societe=societe,
                    date_publication=doc.get("date_doc"),
                    type="DECISION",  # ou "ANNEXE", selon le type
                    source=doc.get("url"),
                    rubrique=", ".join(doc.get("extra_keyword") or []),
                    titre=doc.get("title", "")[:500],
                )

                count_created += 1
                self.stdout.write(self.style.SUCCESS(f"✅ TVA {tva} — nouvelle décision"))

            # Après avoir exécuté le scraper, on compte à nouveau les événements pour cette société
            count_after = VeilleEvenement.objects.filter(societe=societe).count()
            print(f"voici le count apres {count_after}")

            # Si le nombre d'événements a augmenté, on envoie une notification
            if count_after > count_before:
                self.stdout.write(self.style.SUCCESS(f"✨ Nouveau(s) événement(s) ajouté(s) pour la société {tva}"))
                self.send_new_event_email(societe)  # Envoie une notification pour cette société

        self.stdout.write(self.style.SUCCESS(
            f"\n✨ Import terminé : {count_created}/{count_total} événements ajoutés."
        ))

    def send_new_event_email(self, societe):
        """Envoie un email à l'utilisateur concernant un ou plusieurs nouveaux événements"""
        veille = Veille.objects.filter(societes=societe).first()  # Récupère la veille associée à cette société
        user = veille.user  # L'utilisateur (propriétaire de la veille)

        subject = f"🆕 Nouveaux événements détectés pour votre veille '{veille.nom}'"
        message = f"""
        Bonjour {user.username},

        De nouveaux événements ont été ajoutés à votre veille pour la société {societe.nom} :
        - Type : Décision ou Annexe
        - Société : {societe.nom}
        - TVA : {societe.numero_tva}

        Vous pouvez consulter ces événements dans votre tableau de bord.
        """

        # Envoi de l'email
        send_mail(
            subject,
            message,
            from_email=None,  # Cela prendra la valeur de DEFAULT_FROM_EMAIL
            recipient_list=[user.email],  # L'email du propriétaire de la veille
            fail_silently=False,
        )
