# management/commands/veille_scan.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from veille.models import Veille, VeilleSociete, VeilleEvenement
from veille.scrapper.annexes_scraper import scrap_annexes
from django.db import IntegrityError
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
            # ✅ Utiliser la veille demandée (celle du user connecté via la vue)
            veille = Veille.objects.get(id=veille_id)
        else:
            # ⚠️ fallback (dev uniquement) – évite de polluer un autre user
            # mieux vaut lever une erreur si pas de veille explicitement fournie
            raise SystemExit("❌ Veille non fournie. Appelle la commande avec --veille <ID>.")

        # garantir l’existence de la société dans CETTE veille
        VeilleSociete.objects.get_or_create(veille=veille, numero_tva=tva)
        societe = veille.societes.get(numero_tva=tva)

        events = scrap_annexes(tva)

        saved = 0
        for ev in events:
            print("🔎 EVENT SCRAPÉ →", ev)
            url = ev.get("url") or f"no-url-{ev['date_publication']}"
            print(f"👉 Tentative insertion : {ev['date_publication']} | {url}")

            try:
                event, created = VeilleEvenement.objects.get_or_create(
                    veille=veille,
                    societe=societe,  # ✅ associe à la bonne société de la bonne veille
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

        print(f"💾 TOTAL AJOUTÉS = {saved}")
