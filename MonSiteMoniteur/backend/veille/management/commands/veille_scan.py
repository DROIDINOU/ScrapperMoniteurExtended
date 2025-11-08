from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from veille.models import Veille, VeilleSociete, VeilleEvenement
from veille.scrapper.annexes_scraper import scrap_annexes
import re
from django.db import IntegrityError

class Command(BaseCommand):
    help = "Scan une TVA et enregistre les ANNEXES liées dans la veille TVA"

    def add_arguments(self, parser):
        parser.add_argument("--tva", required=True, help="Numéro TVA/BCE à scanner")

    def handle(self, *args, **options):
        tva = re.sub(r"\D", "", options["tva"])
        self.stdout.write(f"🔎 Scan TVA : {tva}")

        veille = Veille.objects.filter(type="TVA", societes__numero_tva=tva).first()

        if not veille:
            user = User.objects.first()
            veille = Veille.objects.create(
                user=user,
                nom=f"Veille TVA auto — {tva}",
                type="TVA",
            )
            VeilleSociete.objects.create(veille=veille, numero_tva=tva)

        societe = VeilleSociete.objects.get(veille=veille, numero_tva=tva)

        events = scrap_annexes(tva)
        saved = 0

        for ev in events:
            try:
                obj, created = VeilleEvenement.objects.get_or_create(
                    veille=veille,
                    type="ANNEXE",
                    date_publication=ev["date_publication"],
                    source=ev.get("url") or "",
                    defaults={"societe": societe, "rubrique": ev.get("rubrique") or "", "titre": ev.get("titre") or ""},
                )

                if created:
                    saved += 1

            except IntegrityError:
                # insertion concurrente ou doublon → on récupère l'objet existant
                obj = VeilleEvenement.objects.get(
                    veille=veille,
                    type="ANNEXE",
                    date_publication=ev["date_publication"],
                    source=ev.get("url") or "",
                )

        self.stdout.write(self.style.SUCCESS(f"✅ {saved} événement(s) enregistré(s)."))
