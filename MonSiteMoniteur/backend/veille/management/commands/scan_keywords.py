# veille/management/commands/scan_keywords.py

from django.core.management.base import BaseCommand
from veille.models import Veille, VeilleEvenement
from django.conf import settings
from meilisearch import Client as MeiliClient
from django.db import IntegrityError


class Command(BaseCommand):
    help = "Scan MeiliSearch pour une veille mots-clés"

    def add_arguments(self, parser):
        parser.add_argument("--veille", required=True, help="ID de la veille")

    def handle(self, *args, **options):
        veille_id = options["veille"]

        try:
            veille = Veille.objects.get(id=veille_id, type="KEYWORD")
        except Veille.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ Veille mots-clés introuvable."))
            return

        self.stdout.write(f"🔍 Scan mots-clés pour : {veille.nom}")

        profile = veille.user.userprofile
        keywords = [k for k in [profile.keyword1, profile.keyword2, profile.keyword3] if k]

        if not keywords:
            self.stdout.write(self.style.WARNING("⚠️ Aucun mot-clé défini pour cet utilisateur."))
            return

        client = MeiliClient(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
        index = client.index("moniteur_docs")

        saved = 0

        for kw in keywords:
            result = index.search(kw, {"limit": 50, "matchingStrategy": "all"})

            for hit in result.get("hits", []):
                try:
                    _, created = VeilleEvenement.objects.get_or_create(
                        veille=veille,
                        type="DECISION",
                        date_publication=hit.get("date_doc"),
                        source=hit.get("url") or "",
                        defaults={
                            "societe": None,  # ✅ indispensable pour dashboard
                            "rubrique": ", ".join(hit.get("extra_keyword") or []),
                            "titre": hit.get("title") or kw,
                        }
                    )

                    if created:
                        saved += 1

                except IntegrityError:
                    # ⛔ doublon détecté malgré get_or_create
                    continue

        self.stdout.write(self.style.SUCCESS(f"✅ {saved} résultat(s) ajouté(s)"))
