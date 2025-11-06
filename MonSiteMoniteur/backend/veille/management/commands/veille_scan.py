from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from veille.models import VeilleSociete, VeilleEvenement
from veille.scrapper.annexes_scraper import scrap_annexes
import re


class Command(BaseCommand):
    help = "Scan une TVA et enregistre les événements du Moniteur"

    def add_arguments(self, parser):
        parser.add_argument("--tva", required=True, help="Numéro TVA/BCE")

    def handle(self, *args, **options):
        tva = re.sub(r"\D", "", options["tva"])

        self.stdout.write(f"🔍 Scan TVA: {tva}")

        # ✅ si la société existe déjà, on la récupère
        societe = VeilleSociete.objects.filter(numero_tva=tva).first()

        # ✅ sinon on la crée et on l’associe à un utilisateur
        if not societe:
            default_user = User.objects.first()
            if not default_user:
                self.stdout.write(self.style.ERROR("❌ Aucun utilisateur trouvé en base !"))
                return

            societe = VeilleSociete.objects.create(
                numero_tva=tva,
                user=default_user
            )
            self.stdout.write(self.style.SUCCESS(f"✅ Société créée et associée à {default_user.username}"))

        # ✅ Scraping Moniteur
        events = scrap_annexes(tva)

        if not events:
            self.stdout.write(self.style.WARNING("⚠️ Aucun événement trouvé."))
            return

        saved = 0
        for ev in events:
            VeilleEvenement.objects.get_or_create(
                societe=societe,
                type="ANNEXE",  # ✅ source = scraping moniteur
                date_publication=ev["date_publication"],
                source=ev.get("url") or "",
                defaults={
                    "rubrique": ev["rubrique"],
                    "titre": ev.get("titre") or ev.get("societe") or "",
                }
            )

            saved += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {saved} événement(s) enregistré(s)."))
