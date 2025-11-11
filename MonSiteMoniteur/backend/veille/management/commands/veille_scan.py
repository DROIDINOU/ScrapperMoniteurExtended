from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from veille.models import Veille, VeilleSociete, VeilleEvenement
from veille.scrapper.annexes_scraper import scrap_annexes
from django.db import IntegrityError
from django.core.mail import send_mail
import re

class Command(BaseCommand):
    help = "Scan une TVA et enregistre les ANNEXES dans VeilleEvenement"

    def add_arguments(self, parser):
        parser.add_argument("--tva", required=True, help="Numéro TVA")
        parser.add_argument("--veille", type=int, help="ID de la veille cible")  # ✅

    def handle(self, *args, **options):
        tva = re.sub(r"\D", "", options["tva"])
        veille_id = options.get("veille")

        self.stdout.write(f"🚀 SCRAP TVA = {tva}")

        if veille_id:
            veille = Veille.objects.get(id=veille_id)
        else:
            raise SystemExit("❌ Veille non fournie. Appelle la commande avec --veille <ID>.")

        # garantir l’existence de la société dans CETTE veille
        VeilleSociete.objects.get_or_create(veille=veille, numero_tva=tva)
        societe = veille.societes.get(numero_tva=tva)

        # Scraper les événements
        events = scrap_annexes(tva)

        saved = 0
        for ev in events:
            print("🔎 EVENT SCRAPÉ →", ev)

            if not ev.get("url") or ev.get("societe") == "INCONNU":
                print("   ⛔ IGNORÉ : événement sans PDF / société inconnue")
                continue

            url = ev.get("url")
            print(f"👉 Tentative insertion : {ev['date_publication']} | {url}")

            try:
                # Essayer de récupérer ou de créer l'événement
                event, created = VeilleEvenement.objects.get_or_create(
                    veille=veille,
                    societe=societe,
                    type="ANNEXE",
                    date_publication=ev["date_publication"],
                    source=url,
                    defaults={
                        "rubrique": ev.get("rubrique") or "",
                        "titre": ev.get("titre") or "",
                    }
                )

                print("   ✅ CREATED" if created else "   ⚠️ ALREADY EXISTS")

                if created:
                    saved += 1

            except IntegrityError as e:
                print("   ⛔ INTEGRITY ERROR →", e)
                continue

        # Envoi d'email, même si aucun événement n'a été ajouté
        if saved > 0:
            self.stdout.write(f"✨ {saved} nouveaux événements ajoutés pour la société {tva}.")
        else:
            self.stdout.write("Aucun nouvel événement ajouté.")

        # Envoi d'un email dans tous les cas (ajout ou pas de nouveaux événements)
        self.send_update_email(veille.user, societe, saved)
    print("on arrive ici au moins?????????????????????????????????????")
    def send_update_email(self, user, societe, saved):
        """Envoie un email à l'utilisateur concernant les événements (même s'il n'y a pas de nouveaux événements)"""
        subject = "🔄 Mise à jour de votre veille"
        if saved > 0:
            message = f"""
            Bonjour {user.username},

            {saved} nouveaux événements ont été ajoutés à votre veille pour la société avec le numéro TVA {societe.numero_tva}.

            Pour plus de détails, consultez votre tableau de bord.
            """
        else:
            message = f"""
            Bonjour {user.username},

            Aucune modification n'a été apportée à votre veille pour la société avec le numéro TVA {societe.numero_tva}.

            Pour plus de détails, consultez votre tableau de bord.
            """

        try:
            send_mail(
                subject,
                message,
                from_email=None,  # Cela prendra la valeur de DEFAULT_FROM_EMAIL
                recipient_list=[user.email],  # L'email du propriétaire de la veille
                fail_silently=False,
            )
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'email : {e}")

        # Envoi de l'email

