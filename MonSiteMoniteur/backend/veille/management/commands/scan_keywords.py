from django.core.management.base import BaseCommand
from django.conf import settings
from veille.models import Veille, VeilleEvenement
from meilisearch import Client as MeiliClient
from django.db import IntegrityError
from datetime import datetime

# ✅ import du fichier situé à la racine de "back"
from ...keywords import KEYWORD_GROUPS


class Command(BaseCommand):
    help = "Scan MeiliSearch pour une veille mots-clés avec filtres"
    print("COMMANDE APPELEE")
    def add_arguments(self, parser):
        parser.add_argument("--veille_id", required=True, help="ID de la veille")
        parser.add_argument("--decision_type", type=str, help="Filtrer par type de décision (extra_keyword)")
        parser.add_argument("--date_from", type=str, help="Filtrer les décisions à partir de cette date (format: YYYY-MM-DD)")

    def handle(self, *args, **options):
        veille_id = options["veille_id"]
        decision_type = options["decision_type"]
        date_from = options["date_from"]

        print(f"🔍 Récupération des informations pour la veille ID : {veille_id}")

        try:
            veille = Veille.objects.get(id=veille_id, type="KEYWORD")
        except Veille.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ Veille mots-clés introuvable."))
            return

        self.stdout.write(f"🔍 Scan mots-clés pour : {veille.nom}")

        profile = veille.user.userprofile
        keywords = [k.strip() for k in [profile.keyword1, profile.keyword2, profile.keyword3] if k]

        if not keywords and not (decision_type or date_from):
            self.stdout.write(self.style.WARNING("⚠️ Aucun mot-clé défini et aucun filtre fourni."))
            return

        client = MeiliClient(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
        index = client.index("moniteur_docs")

        saved = 0

        # Si aucun mot-clé mais des filtres → recherche textuelle vide avec filtres actifs
        if not keywords:
            print("recherche sans keyword")
            keywords = [""]

        for kw in keywords:
            filters = []
            print(f"desision type: {decision_type}")
            # ✅ Filtres : utilise le mapping intelligent depuis back/keywords.py
            if decision_type:
                decision_type = decision_type.lower()

                # Récupère tous les extra_keywords qui contiennent ce mot dans le mapping
                possible_keywords = [
                    key
                    for group_keywords in KEYWORD_GROUPS.values()
                    for key in group_keywords
                    if decision_type in key.lower()
                ]

                print(f"voici les possibilites: {possible_keywords}")

                if possible_keywords:
                    print(possible_keywords)
                    filter_extra = " OR ".join([f"extra_keyword = '{p}'" for p in possible_keywords])
                    filters.append(f"({filter_extra})")
                    print(f"✅ Filtre appliqué sur '{decision_type}' → {possible_keywords}")
                else:
                    print(f"⚠️ Aucun extra_keyword trouvé pour le type '{decision_type}'")

            # ✅ Filtre sur les dates
            if date_from:
                filters.append(f"date_doc >= '{date_from}'")
                print(f"📆 Filtre date début : {date_from}")

            filter_string = " AND ".join(filters) if filters else ""
            print(f"🔎 Filtre final MeiliSearch : {filter_string}")

            # 🔥 Recherche Meili
            result = index.search(
                kw,
                {
                    "limit": 200,
                    "filter": filter_string,
                    "matchingStrategy": "all"
                }
            )

            hits = result.get("hits", [])
            print(f"📈 {len(hits)} résultat(s) trouvé(s) pour '{kw}' avec filtres.")

            # 🔁 Enregistrement des résultats
            for hit in hits:
                try:
                    _, created = VeilleEvenement.objects.get_or_create(
                        veille=veille,
                        societe=None,
                        type="DECISION",
                        date_publication=hit.get("date_doc"),
                        source=hit.get("url") or "",
                        defaults={
                            "rubrique": ", ".join(hit.get("extra_keyword") or []),
                            "titre": hit.get("title") or kw,
                        },
                    )
                    if created:
                        saved += 1
                except IntegrityError:
                    continue

        self.stdout.write(self.style.SUCCESS(f"✅ {saved} résultat(s) ajouté(s)"))
        print(f"✅ Résultats ajoutés : {saved}")
