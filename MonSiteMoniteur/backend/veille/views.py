from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login

from django.http import JsonResponse, Http404
from django.conf import settings
from psycopg2.extras import RealDictCursor

from meilisearch import Client as MeiliClient

import re
import psycopg2
from django.db import connection

from .models import UserProfile
from .keywords import KEYWORD_GROUPS, KEYWORD_LABELS
from BaseDeDonnees.connexion_postgre import get_postgre_connection


# ------------------------------------------------------------
# ✅ AUTOCOMPLETE RUE
# ------------------------------------------------------------
def api_autocomplete_rue(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse([], safe=False)

    client = MeiliClient(settings.MEILI_URL, settings.MEILI_SEARCH_KEY)

    try:
        response = client.index(settings.INDEX_RUE_NAME).search(query, {"limit": 7})
    except Exception as e:
        print("❌ ERREUR connexion MeiliSearch :", e)
        return JsonResponse([], safe=False)

    hits = response.get("hits", [])

    return JsonResponse(
        [{"label": h.get("label", "").split("-")[0].strip()} for h in hits],
        safe=False
    )


# ------------------------------------------------------------
# ✅ FICHE SOCIETÉ (BCE)
# ------------------------------------------------------------
def fiche_societe(request, bce):
    """
    Affiche la fiche d’une société (nom, adresse, administrateurs, décisions liées)
    """
    with connection.cursor() as cur:
        # récupérer la société
        cur.execute("""
            SELECT id, bce, nom, adresse, source, confidence
            FROM societe
            WHERE bce = %s
        """, [bce])
        row = cur.fetchone()

        if not row:
            return render(request, "veille/fiche_societe.html", {"not_found": True})

        societe = {
            "id": row[0],
            "bce": row[1],
            "nom": row[2],
            "adresse": row[3],
            "source": row[4],
            "confidence": row[5],
        }

        # administrateurs liés
        cur.execute("""
            SELECT a.nom, a.role, a.confidence
            FROM administrateur a
            JOIN societe_admin sa ON sa.admin_id = a.id
            WHERE sa.societe_id = %s
        """, [societe["id"]])
        admins = [
            {"nom": nom, "role": role, "confidence": conf}
            for (nom, role, conf) in cur.fetchall()
        ]

        # ✅ décisions liées
        cur.execute("""
            SELECT d.id, d.date_doc, d.titre, d.url
            FROM decision d
            JOIN decision_societe ds ON ds.decision_id = d.id
            WHERE ds.societe_id = %s
            ORDER BY d.date_doc DESC
        """, [societe["id"]])
        decisions = [
            {"id": id, "date": date, "titre": titre, "url": url}
            for (id, date, titre, url) in cur.fetchall()
        ]

    societe["administrateurs"] = admins
    societe["decisions"] = decisions

    return render(request, "veille/fiche_societe.html", {"societe": societe})

# ------------------------------------------------------------
# ✅ AUTOCOMPLETE MOT-CLÉ
# ------------------------------------------------------------
def api_autocomplete_keyword(request):
    query = request.GET.get("q", "").strip().lower()

    suggestions = []
    for category, keywords in KEYWORD_GROUPS.items():
        for kw in keywords:
            if not query or query in kw.lower():
                suggestions.append({
                    "value": kw,
                    "label": KEYWORD_LABELS.get(kw, kw),
                    "category": category,
                })

    # suppression doublons
    final = []
    seen = set()
    for sug in suggestions:
        if sug["value"] not in seen:
            final.append(sug)
            seen.add(sug["value"])

    return JsonResponse(final, safe=False)


# ------------------------------------------------------------
# ✅ SEARCH - MOT CLÉ
# ------------------------------------------------------------
def api_search_keyword(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({"moniteur": []})

    client = MeiliClient(settings.MEILI_URL, settings.MEILI_SEARCH_KEY)
    hits = client.index(settings.INDEX_NAME).search(
        query, {"attributesToSearchOn": ["extra_keyword"], "limit": 50}
    ).get("hits", [])

    return JsonResponse({
        "moniteur": [
            {
                "text": h.get("text", ""),
                "url": h.get("url", ""),
                "title": h.get("title", ""),
                "date_document": h.get("date_doc", ""),
                "extra_keyword": h.get("extra_keyword", []),

                # ✅ LA BONNE INJECTION
                "bce": h.get("TVA")[0] if h.get("TVA") else None,
                "num_tva": h.get("TVA"),

                "societe_id": h.get("societe_id"),
            }
            for h in hits
        ]
    })


# ------------------------------------------------------------
# ✅ SEARCH - RUE
# ------------------------------------------------------------
def api_search_rue(request):
    import unicodedata

    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"moniteur": []})

    def norm(s):
        if not isinstance(s, str):
            return ""
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", s).lower().strip()

    query_norm = norm(query)

    client = MeiliClient(settings.MEILI_URL, settings.MEILI_SEARCH_KEY)
    raw_hits = client.index(settings.INDEX_NAME).search(
        query, {"attributesToSearchOn": ["adresses_all_flat"], "limit": 200}
    ).get("hits", [])

    hits = [
        h for h in raw_hits
        if any(query_norm in norm(addr) for addr in h.get("adresses_all_flat") or [])
    ]

    return JsonResponse({
        "moniteur": [
            {
                "text": h.get("text", ""),
                "url": h.get("url", ""),
                "title": h.get("title", ""),
                "date_document": h.get("date_doc", ""),

                "adresses_all_flat": h.get("adresses_all_flat", []),

                # ✅ BON CHAMP
                "bce": h.get("TVA")[0] if h.get("TVA") else None,
                "num_tva": h.get("TVA"),

                "societe_id": h.get("societe_id"),
            }
            for h in hits
        ]
    })


# ------------------------------------------------------------
# ✅ SEARCH - GLOBAL
# ------------------------------------------------------------
def api_search(request):
    query = request.GET.get("q", "").strip()
    search_term = query.lstrip("=")

    client = MeiliClient(settings.MEILI_URL, settings.MEILI_SEARCH_KEY)
    hits = client.index(settings.INDEX_NAME).search(search_term, {"limit": 20}).get("hits", [])

    return JsonResponse({
        "moniteur": [
            {
                "text": h.get("text", ""),
                "url": h.get("url", ""),
                "title": h.get("title", ""),
                "subtitle": h.get("subtitle", ""),
                "date_document": h.get("date_doc", ""),

                # ✅ BCE récupéré via TVA[0]
                "bce": h.get("TVA")[0] if h.get("TVA") else None,
                "num_tva": h.get("TVA"),

                "societe_id": h.get("societe_id"),
            }
            for h in hits
        ]
    })


# ------------------------------------------------------------
# ✅ SEARCH - TVA
# ------------------------------------------------------------
def api_search_tva(request):
    query = request.GET.get("q", "").strip()
    search_term = query.replace(".", "").replace(" ", "")

    client = MeiliClient(settings.MEILI_URL, settings.MEILI_SEARCH_KEY)
    hits = client.index(settings.INDEX_NAME).search(search_term).get("hits", [])

    filtered = []
    for h in hits:
        if search_term in h.get("text", "").replace(".", "").replace(" ", ""):
            filtered.append({
                "text": h.get("text", ""),
                "url": h.get("url", ""),
                "title": h.get("title", ""),
                "date_document": h.get("date_doc", ""),

                "bce": h.get("TVA")[0] if h.get("TVA") else None,
                "num_tva": h.get("TVA"),

                "societe_id": h.get("societe_id"),
            })

    return JsonResponse({"moniteur": filtered})


# ------------------------------------------------------------
# ✅ PAGES
# ------------------------------------------------------------
def home(request): return render(request, "veille/home.html")
def charts(request): return render(request, "veille/charts.html")
def contact(request): return render(request, "veille/contact.html")
def fonctionnalites(request): return render(request, "veille/fonctionnalites.html")
def recherches(request): return render(request, "veille/recherches.html")
def resultats(request): return render(request, "veille/resultats.html")
def maveille(request): return render(request, "veille/maveille.html")
def premium(request): return render(request, "veille/premium.html")


# ------------------------------------------------------------
# ✅ REGISTER & LOGIN
# ------------------------------------------------------------
def register(request):
    if request.method == "POST":
        first = request.POST.get("first_name")
        last = request.POST.get("last_name")
        email = request.POST.get("email")
        pwd = request.POST.get("password")
        pwd2 = request.POST.get("password_confirm")

        if pwd != pwd2:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, "veille/register.html")

        if User.objects.filter(username=email).exists():
            messages.error(request, "Un compte existe déjà avec cet email.")
            return render(request, "veille/register.html")

        user = User.objects.create_user(username=email, email=email, password=pwd, first_name=first, last_name=last)
        UserProfile.objects.create(user=user)

        messages.success(request, "Compte créé ✅")
        return redirect("login")

    return render(request, "veille/register.html")


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)

        if user:
            login(request, user)
            return redirect("home")

        messages.error(request, "Email ou mot de passe incorrect.")

    return render(request, "veille/login.html")
