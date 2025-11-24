from django.core.management.base import BaseCommand
from django.conf import settings
from veille.models import Veille, VeilleEvenement
from meilisearch import Client as MeiliClient
from django.db import IntegrityError
from difflib import SequenceMatcher
import re

from ...keywords import KEYWORD_GROUPS

threshold_flat = 0.6
threshold_ejustice = 0.6


def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def clean_address_raw(addr: str) -> str:
    if not addr:
        return ""
    addr = addr.upper()
    stop_keywords = [
        "COMPTES ANNUELS", "STATUTS", "DEMISSION", "CESSATION",
        "RUBRIQUE", "IMAGE", "OBJET", "DENOMINATION", "SIEGE SOCIAL",
        "NOMINATION", "ANNULATION", "NULLITE", "CONSTITUTION"
    ]
    for kw in stop_keywords:
        if kw in addr:
            addr = addr.split(kw)[0]
            break

    addr = re.sub(r"\d{3}\.\d{3}\.\d{3}", "", addr)
    addr = re.sub(r"\d{4}-\d{2}-\d{2}", "", addr)
    addr = re.sub(r"\d{2}/\d{2}/\d{4}", "", addr)
    addr = re.sub(r"\d{5}-\d{4}-\d{3}", "", addr)

    return addr.strip()


# ===========================================================
#  TABLE DE MAPPING ENTRE MOTS-CLÉS "HUMAINS"
#  ET LES KEYWORDS TECHNIQUES DE MEILISEARCH
# ===========================================================

DECISION_MAP = {
    "ouverture": [
        k for ks in KEYWORD_GROUPS.values()
        for k in ks
        if k.startswith("ouverture_")
    ],

    "cloture": [
        k for ks in KEYWORD_GROUPS.values()
        for k in ks
        if k.startswith("cloture_")
    ],

    "faillite": [
        k for ks in KEYWORD_GROUPS.values()
        for k in ks
        if "faillite" in k
    ],

    "liquidation": [
        k for ks in KEYWORD_GROUPS.values()
        for k in ks
        if "liquidation" in k and not k.startswith("ouverture_") and not k.startswith("cloture_")
    ],

    "dissolution": [
        k for ks in KEYWORD_GROUPS.values()
        for k in ks
        if "dissolution" in k
    ],

    "effacement": [
        k for ks in KEYWORD_GROUPS.values()
        for k in ks
        if "effacement" in k
    ],

    "radiation": [
        k for ks in KEYWORD_GROUPS.values()
        for k in ks
        if "radiation" in k
    ],

    "condamnation": [
        k for ks in KEYWORD_GROUPS.values()
        for k in ks
        if k == "condamnation"
    ],
}


class Command(BaseCommand):
    help = "Scan MeiliSearch pour une veille mots-clés avec filtres"

    def add_arguments(self, parser):
        parser.add_argument("--veille_id", required=True)
        parser.add_argument("--decision_type", type=str)
        parser.add_argument("--date_from", type=str)
        parser.add_argument("--rue", action="store_true")

    def handle(self, *args, **options):
        veille_id = options["veille_id"]
        decision_type = options["decision_type"]
        date_from = options["date_from"]
        rue_filter = options["rue"]

        print(f"\n\n🔍 VEILLE ID = {veille_id}")
        print(f"decision_type = {decision_type}")
        print(f"date_from = {date_from}")
        print(f"rue = {rue_filter}")

        try:
            veille = Veille.objects.get(id=veille_id, type="KEYWORD")
        except Veille.DoesNotExist:
            print("❌ Veille introuvable")
            return

        profile = veille.user.userprofile
        keywords = [k.strip() for k in [profile.keyword1, profile.keyword2, profile.keyword3] if k]

        if not keywords:
            keywords = [" "]
        # Un score Meili n’a de sens que si un vrai mot-clé texte a été entré
        has_real_keyword = any(k.strip() for k in [profile.keyword1, profile.keyword2, profile.keyword3])

        client = MeiliClient(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
        index = client.index("moniteur_docs")

        print("\n⚠️ Meili ne sait PAS filtrer sur extra_keyword (ARRAY). Filtrage Python activé.")

        VeilleEvenement.objects.filter(veille=veille).delete()
        inserted = 0

        # --- NOUVEAU SYSTÈME DE FILTRAGE ---
        decision_key = (decision_type or "").lower()
        possible_keywords = DECISION_MAP.get(decision_key, [])

        print("\n🟦 TYPE DEMANDÉ =", decision_key)
        print("🟩 possible_keywords =", possible_keywords)

        # -----------------------------------------
        # 🔄 boucle sur les mots-clés utilisateur
        # -----------------------------------------
        for query in keywords:

            params = {"limit": 200, "showRankingScore": True}

            if date_from:
                params["filter"] = f"date_doc >= {date_from}"

            result = index.search(query, params)
            hits = result.get("hits", [])
            print(result["hits"][0])

            print(f"\n🟧 Meili a renvoyé {len(hits)} documents")

            # -------- FILTRE PYTHON STRICT --------
            filtered_hits = []
            for hit in hits:
                extra = hit.get("extra_keyword") or []
                extra_lower = [x.lower() for x in extra]

                python_pass = True
                if decision_type:
                    python_pass = any(e in possible_keywords for e in extra_lower)

                print("\n---- HIT ----")
                print("URL:", hit.get("url"))
                print("EXTRA:", extra)
                print("PYTHON MATCH:", python_pass)

                if python_pass:
                    filtered_hits.append(hit)
                else:
                    print("❌ rejeté")

            # -----------------------------------------
            # 🔄 insertion en base
            # -----------------------------------------
            for hit in filtered_hits:

                extra = hit.get("extra_keyword") or []

                try:
                    obj, created = VeilleEvenement.objects.get_or_create(
                        veille=veille,
                        societe=None,
                        type="DECISION",
                        date_publication=hit.get("date_doc"),
                        source=hit.get("url") or "",
                        defaults={
                            "rubrique": ", ".join(extra),
                            "titre": hit.get("title") or query,
                            "score": hit.get("_rankingScore") if has_real_keyword else None,
                            "tva_list": hit.get("TVA") or [],
                        },
                    )
                    if created:
                        inserted += 1

                except IntegrityError:
                    continue

        print(f"\n\n✅ {inserted} décision(s) réellement ajoutée(s)")
