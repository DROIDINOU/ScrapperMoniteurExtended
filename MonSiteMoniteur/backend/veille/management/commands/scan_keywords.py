from django.core.management.base import BaseCommand
from django.conf import settings
from veille.models import Veille, VeilleEvenement
from meilisearch import Client as MeiliClient
from django.db import IntegrityError

from ...keywords import KEYWORD_GROUPS


DECISION_MAP = {
    "ouverture": [k for ks in KEYWORD_GROUPS.values() for k in ks if k.startswith("ouverture_")],
    "cloture":   [k for ks in KEYWORD_GROUPS.values() for k in ks if k.startswith("cloture_")],
    "faillite":  [k for ks in KEYWORD_GROUPS.values() for k in ks if "faillite" in k],
    "liquidation": [
        k for ks in KEYWORD_GROUPS.values()
        for k in ks
        if "liquidation" in k and not k.startswith("ouverture_") and not k.startswith("cloture_")
    ],
    "dissolution": [k for ks in KEYWORD_GROUPS.values() for k in ks if "dissolution" in k],
    "effacement":  [k for ks in KEYWORD_GROUPS.values() for k in ks if "effacement" in k],
    "radiation":   [k for ks in KEYWORD_GROUPS.values() for k in ks if "radiation" in k],
    "condamnation":[k for ks in KEYWORD_GROUPS.values() for k in ks if k == "condamnation"],
}


class Command(BaseCommand):
    help = "Scan MeiliSearch optimisé avec filtres complets"

    def add_arguments(self, parser):
        parser.add_argument("--veille_id", required=True)
        parser.add_argument("--keyword", type=str, default="")
        parser.add_argument("--decision_type", type=str)
        parser.add_argument("--date_from", type=str)
        parser.add_argument("--rue", type=str)

    def handle(self, *args, **options):

        veille_id = options["veille_id"]
        decision_type = (options.get("decision_type") or "").lower().strip()
        date_from = options.get("date_from") or ""
        rue_filter = (options.get("rue") or "").lower().strip()

        print(f"\n🔍 VEILLE ID = {veille_id}")
        print(f"decision_type = {decision_type}")
        print(f"date_from = {date_from}")
        print(f"rue = {rue_filter}")

        try:
            veille = Veille.objects.get(id=veille_id, type="KEYWORD")
        except Veille.DoesNotExist:
            print("❌ Veille introuvable")
            return

        client = MeiliClient(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
        index = client.index("moniteur_docs")

        inserted = 0

        possible_keywords = DECISION_MAP.get(decision_type, [])

        # ---------- construction du filter Meili (SANS IN) ----------
        meili_filters = []

        if date_from:
            meili_filters.append(f"date_doc >= {date_from}")

        if decision_type and possible_keywords:
            # extra_keyword est un array → on fait un OR sur chaque valeur possible
            if len(possible_keywords) == 1:
                meili_filters.append(f"extra_keyword = {possible_keywords[0]}")
            else:
                or_group = [f"extra_keyword = {kw}" for kw in possible_keywords]
                meili_filters.append(or_group)

        params = {
            "limit": 200,
        }

        if meili_filters:
            params["filter"] = meili_filters

        print("🔧 Filters envoyés à MeiliSearch :")
        print(params.get("filter"))

        # match-all côté texte
        result = index.search("*", params)
        hits = result.get("hits", [])

        print(f"🟧 Meili renvoie {len(hits)} documents (après filtres décision/date)")

        filtered_hits = []

        for hit in hits:
            text_full = (
                    (hit.get("title") or "") + " " +
                    (hit.get("text") or "") + " " +
                    ", ".join(hit.get("adresses_all_flat") or [])
            ).lower()

            match = True

            # on garde le filtre rue côté Python (pas de LIKE natif simple et fiable)
            if rue_filter and rue_filter not in text_full:
                match = False

            if match:
                filtered_hits.append(hit)

        for hit in filtered_hits:
            try:
                _, created = VeilleEvenement.objects.get_or_create(
                    veille=veille,
                    societe=None,
                    type="DECISION",
                    date_publication=hit.get("date_doc"),
                    source=hit.get("url"),
                    defaults={
                        "rubrique": ", ".join(hit.get("extra_keyword") or []),
                        "titre": hit.get("title") or "",
                        "tva_list": hit.get("TVA") or [],
                    }
                )
                if created:
                    inserted += 1

            except IntegrityError:
                pass
                # ---------------------------------------------------------------------
                # 🟪 PHASE 2 — FALLBACK MEILI FULL-TEXT INTELLIGENT SUR LA RUE
                # ---------------------------------------------------------------------

                if rue_filter:
                    print("\n🟣 Fallback rue : recherche Meili full-text renforcée")

                    # Query renforcée : rue + decision keyword
                    fallback_query = f"{rue_filter} {decision_type}" if decision_type else rue_filter

                    fallback_params = {
                        "limit": 200,
                        "filter": meili_filters,  # garde date + keywords
                    }

                    fallback_res = index.search(fallback_query, fallback_params)
                    fallback_hits = fallback_res.get("hits", [])

                    print(f"🟪 Fallback Meili renvoie {len(fallback_hits)} docs potentiels")

                    for hit in fallback_hits:

                        # anti-bruit minimal : la rue doit apparaître dans le texte brut Meili
                        text_small = ((hit.get("title") or "") + " " + (hit.get("text") or "")).lower()
                        if rue_filter not in text_small:
                            continue

                        # éviter les doublons
                        if VeilleEvenement.objects.filter(veille=veille, source=hit.get("url")).exists():
                            continue

                        try:
                            _, created = VeilleEvenement.objects.get_or_create(
                                veille=veille,
                                societe=None,
                                type="DECISION",
                                date_publication=hit.get("date_doc"),
                                source=hit.get("url"),
                                defaults={
                                    "rubrique": ", ".join(hit.get("extra_keyword") or []),
                                    "titre": hit.get("title") or "",
                                    "tva_list": hit.get("TVA") or [],
                                }
                            )
                            if created:
                                inserted += 1
                        except IntegrityError:
                            pass

        print(f"\n✅ {inserted} décisions ajoutées")

