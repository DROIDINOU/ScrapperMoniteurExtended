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
    """Calcule une similarité entre deux chaînes (0 à 1)."""
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

class Command(BaseCommand):
    help = "Scan MeiliSearch pour une veille mots-clés avec filtres"

    def add_arguments(self, parser):
        parser.add_argument("--veille_id", required=True, help="ID de la veille")
        parser.add_argument("--decision_type", type=str, help="Filtrer par type de décision (extra_keyword)")
        parser.add_argument("--date_from", type=str, help="Filtrer par date (YYYY-MM-DD)")
        parser.add_argument("--rue", action="store_true", help="Activer la recherche sur les champs d'adresse")

    def handle(self, *args, **options):
        veille_id = options["veille_id"]
        decision_type = options["decision_type"]
        date_from = options["date_from"]
        rue_filter = options["rue"]

        self.stdout.write(f"🔍 Veille ID : {veille_id}")

        try:
            veille = Veille.objects.get(id=veille_id, type="KEYWORD")
        except Veille.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ Veille introuvable"))
            return

        profile = veille.user.userprofile
        keywords = [k.strip() for k in [profile.keyword1, profile.keyword2, profile.keyword3] if k]
        if not keywords:
            keywords = [""]

        client = MeiliClient(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
        index = client.index("moniteur_docs")

        saved = 0
        is_fulltext = not (decision_type or date_from or rue_filter)

        for kw in keywords:
            filters = []
            if decision_type:
                decision_type = decision_type.lower()
                possible_keywords = [
                    key for group_keywords in KEYWORD_GROUPS.values()
                    for key in group_keywords if decision_type in key.lower()
                ]
                if possible_keywords:
                    filter_extra = " OR ".join([f"extra_keyword = '{p}'" for p in possible_keywords])
                    filters.append(f"({filter_extra})")

            if date_from:
                filters.append(f"date_doc >= {date_from}")

            filter_string = " AND ".join(filters) if filters else ""
            query = kw or ""

            # -------------------------
            # Cas 1 : plein texte
            # -------------------------
            if is_fulltext:
                result = index.search(query, {"limit": 200})
                hits = result.get("hits", [])
                N = len(hits)

                for i, hit in enumerate(hits):
                    try:
                        score_display = round(1.0 - (i / max(N - 1, 1)), 3) if N > 1 else 1.0
                        obj, created = VeilleEvenement.objects.get_or_create(
                            veille=veille,
                            societe=None,
                            type="DECISION",
                            date_publication=hit.get("date_doc"),
                            source=hit.get("url") or "",
                            defaults={
                                "rubrique": ", ".join(hit.get("extra_keyword") or []),
                                "titre": hit.get("title") or query,
                                "score": score_display,
                                "rank_position": i,
                                "tva_list": hit.get("TVA") or [],  # ✅ ajout TVA
                            },
                        )
                        if not created:
                            obj.score = score_display
                            obj.rank_position = i
                            obj.save(update_fields=["score", "rank_position", "tva_list"])
                        else:
                            saved += 1
                    except IntegrityError:
                        continue
                continue

            # -------------------------
            # Cas 2 : filtré par type/date (sans rue)
            # -------------------------
            elif not rue_filter:
                params = {"limit": 200}
                if filter_string:
                    params["filter"] = filter_string
                result = index.search(query, params)
                hits = result.get("hits", [])

                for hit in hits:
                    try:
                        obj, created = VeilleEvenement.objects.get_or_create(
                            veille=veille,
                            societe=None,
                            type="DECISION",
                            date_publication=hit.get("date_doc"),
                            source=hit.get("url") or "",
                            defaults={
                                "rubrique": ", ".join(hit.get("extra_keyword") or []),
                                "titre": hit.get("title") or query,
                                "score": None,  # pas de similarité calculée
                                "tva_list": hit.get("TVA") or [],  # ✅ ajout TVA
                            },
                        )
                        if created:
                            saved += 1
                    except IntegrityError:
                        continue

            # -------------------------
            # Cas 3 : filtré par rue
            # -------------------------
            else:
                attrs = ["adresses_all_flat", "adresses_ejustice_flat", "adresses_bce_flat"]

                params_flat = {"limit": 200, "matchingStrategy": "last", "attributesToSearchOn": attrs}
                if filter_string:
                    params_flat["filter"] = filter_string
                result_flat = index.search(query, params_flat)

                params_ejustice = {"limit": 200, "matchingStrategy": "last", "attributesToSearchOn": attrs}
                if filter_string:
                    params_ejustice["filter"] = filter_string
                result_ejustice = index.search(query, params_ejustice)

                hits = result_flat.get("hits", []) + result_ejustice.get("hits", [])

                for hit in hits:
                    try:
                        score_flat = 0
                        score_ejustice = 0
                        score_bce = 0

                        addr_field_flat = hit.get("adresses_all_flat") or []
                        if isinstance(addr_field_flat, list):
                            scores = [similarity(query, addr) for addr in addr_field_flat if isinstance(addr, str)]
                            score_flat = max(scores) if scores else 0
                        elif isinstance(addr_field_flat, str):
                            score_flat = similarity(query, addr_field_flat)

                        addr_field_ejustice = hit.get("adresses_by_ejustice") or []
                        if isinstance(addr_field_ejustice, list):
                            scores_ejustice = [
                                similarity(query, clean_address_raw(addr_obj.get("adresse", "")))
                                for addr_obj in addr_field_ejustice if isinstance(addr_obj, dict)
                            ]
                            score_ejustice = max(scores_ejustice) if scores_ejustice else 0
                        elif isinstance(addr_field_ejustice, dict):
                            score_ejustice = similarity(query,
                                                        clean_address_raw(addr_field_ejustice.get("adresse", "")))

                        addr_field_bce = hit.get("adresses_by_bce") or []
                        if isinstance(addr_field_bce, list):
                            scores_bce = [
                                similarity(query, clean_address_raw(addr_obj.get("adresse", "")))
                                for addr_obj in addr_field_bce if isinstance(addr_obj, dict)
                            ]
                            score_bce = max(scores_bce) if scores_bce else 0

                        final_score = max(score_flat, score_ejustice, score_bce)
                        add_result = (
                            score_flat >= threshold_flat or
                            score_ejustice >= threshold_ejustice or
                            score_bce >= threshold_flat
                        )

                        if add_result:
                            obj, created = VeilleEvenement.objects.get_or_create(
                                veille=veille,
                                societe=None,
                                type="DECISION",
                                date_publication=hit.get("date_doc"),
                                source=hit.get("url") or "",
                                defaults={
                                    "rubrique": ", ".join(hit.get("extra_keyword") or []),
                                    "titre": hit.get("title") or query,
                                    "score": round(final_score, 3),
                                    "tva_list": hit.get("TVA") or [],
                                },
                            )
                            if not created:
                                obj.score = round(final_score, 3)
                                obj.save(update_fields=["score"])
                            else:
                                saved += 1
                    except IntegrityError:
                        continue

        self.stdout.write(self.style.SUCCESS(f"✅ {saved} résultat(s) ajouté(s)"))
