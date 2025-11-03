from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from .models import UserProfile
from django.contrib.auth import authenticate, login
import re
from django.http import JsonResponse
from meilisearch import Client
from django.http import JsonResponse
from django.conf import settings
from meilisearch import Client as MeiliClient
import os
import psycopg2
from .keywords import KEYWORD_GROUPS, KEYWORD_LABELS


def api_search_keyword(request):
    query = request.GET.get("q", "").strip()
    print(f"🔍 SEARCH KEYWORD — reçu : {query}")

    if not query:
        return JsonResponse({"moniteur": []})

    client = MeiliClient(settings.MEILI_URL, settings.MEILI_SEARCH_KEY)

    try:
        response = client.index(settings.INDEX_NAME).search(
            query,
            {
                "attributesToSearchOn": ["extra_keyword"],   # ✅ essentiel
                "limit": 50
            }
        )

    except Exception as e:
        print("❌ ERREUR MeiliSearch :", e)
        return JsonResponse({"moniteur": []})

    hits = response.get("hits", [])

    results = {
        "moniteur": [
            {
                "text": h.get("text", ""),
                "url": h.get("url", ""),
                "title": h.get("title", ""),
                "date_document": h.get("date_doc", ""),
                "extra_keyword": h.get("extra_keyword", []),   # ✅ retourne la liste telle quelle
                "denoms_bce_flat": h.get("denoms_bce_flat"),
                "num_tva": h.get("num_tva"),
                "denoms_by_ejustice_flat": h.get("denoms_by_ejustice_flat"),
                "denoms_fallback_bce_flat": h.get("denoms_fallback_bce_flat"),
            }
            for h in hits
        ]
    }

    print(f"✅ {len(results['moniteur'])} résultats trouvés pour keyword")

    return JsonResponse(results)


def api_autocomplete_rue(request):
    query = request.GET.get("q", "").strip()

    print("🔍 AUTOCOMPLETE RUE - Query reçue :", query)

    if not query:
        return JsonResponse([], safe=False)

    client = MeiliClient(settings.MEILI_URL, settings.MEILI_SEARCH_KEY)

    try:
        response = client.index(settings.INDEX_RUE_NAME).search(
            query,
            {"limit": 7}
        )
    except Exception as e:
        print("❌ ERREUR connexion MeiliSearch :", e)
        return JsonResponse([], safe=False)

    hits = response.get("hits", [])

    suggestions = []
    for h in hits:
        label = h.get("label", "")

        # ✅ NE PREND QUE LA PARTIE AVANT LE "-"
        clean_label = label.split("-")[0].strip()

        suggestions.append({"label": clean_label})

    print("📤 AUTOCOMPLETE RETOURNÉ :", suggestions)

    return JsonResponse(suggestions, safe=False)


def api_search_rue(request):
    import unicodedata, re

    query = request.GET.get("q", "").strip()
    print(f"🏠 SEARCH RUE — reçu : {query}")

    if not query:
        return JsonResponse({"moniteur": []})

    # ✅ Normalisation (minuscules + suppression accents + espaces uniformisés)
    def norm(s: str) -> str:
        if not isinstance(s, str):
            return ""
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))  # enlève les accents
        s = re.sub(r"\s+", " ", s)  # espaces multiples -> espace unique
        return s.lower().strip()

    query_norm = norm(query)

    client = MeiliClient(settings.MEILI_URL, settings.MEILI_SEARCH_KEY)

    try:
        response = client.index(settings.INDEX_NAME).search(
            query,  # 🟢 recherche large
            {
                "attributesToSearchOn": ["adresses_all_flat"],
                "limit": 200
            }
        )
    except Exception as e:
        print("❌ ERREUR MeiliSearch :", e)
        return JsonResponse({"moniteur": []})

    raw_hits = response.get("hits", [])

    # 🔥 Post-filter strict (contient exactement la chaîne tapée ou sélectionnée)
    filtered_hits = []
    for h in raw_hits:
        adresses = h.get("adresses_all_flat") or []

        if any(query_norm in norm(addr) for addr in adresses):
            filtered_hits.append(h)

    print(f"✅ {len(filtered_hits)} résultats après filtre strict insensible à la casse/accents")

    return JsonResponse({
        "moniteur": [
            {
                "text": h.get("text", ""),
                "url": h.get("url", ""),
                "title": h.get("title", ""),
                "date_document": h.get("date_doc", ""),
                "adresses_all_flat": h.get("adresses_all_flat", []),
                "denoms_by_bce": h.get("denoms_by_bce", []),
                "denoms_by_ejustice": h.get("denoms_by_ejustice", []),
                "denoms_bce_flat": h.get("denoms_bce_flat"),
                "num_tva": h.get("num_tva"),
            }
            for h in filtered_hits
        ]
    })


def api_autocomplete_keyword(request):
    query = request.GET.get("q", "").strip().lower()

    suggestions = []

    for category, keywords in KEYWORD_GROUPS.items():
        for kw in keywords:

            # si rien tapé → retourne tout
            if not query or query in kw.lower():
                suggestions.append({
                    "value": kw,                         # identifiant interne envoyé au backend
                    "label": KEYWORD_LABELS.get(kw, kw), # affiché à l'utilisateur
                    "category": category,                # pour regrouper visuellement
                })

    # Suppression des doublons
    seen = set()
    final = []
    for sug in suggestions:
        if sug["value"] not in seen:
            seen.add(sug["value"])
            final.append(sug)

    return JsonResponse(final, safe=False)


def api_search(request):
    query = request.GET.get('q', '').strip()
    print(f"[🔍] Requête utilisateur brute : {query}")

    # ✅ Recherche globale : conserver espaces pour la fuzzy search
    search_term = query.lstrip('=')  # juste enlever "=" mais garder les espaces

    print(f"[🔎] Terme envoyé à MeiliSearch : {search_term}")

    client = MeiliClient(
        settings.MEILI_URL,
        settings.MEILI_SEARCH_KEY
    )

    hits = client.index(settings.INDEX_NAME).search(
        search_term,
        {"limit": 20}
    ).get("hits", [])

    results = {
        "moniteur": [
            {
                "text": h.get("text", ""),
                "url": h.get("url", ""),
                "title": h.get("title", ""),
                "subtitle": h.get("subtitle", ""),
                "date_document": h.get("date_document", ""),
                "denoms_bce_flat": h.get("denoms_bce_flat"),
                "num_tva": h.get("num_tva"),
            }
            for h in hits
        ]
    }

    return JsonResponse(results)


def api_search_tva(request):
    query = request.GET.get('q', '').strip()
    print(f"TVA query (entrant) : {query}")

    # 🔧 Normalisation complète du format TVA pour la recherche
    search_term = (
        query.lstrip('=')      # enlève "=" au début
             .replace('.', '') # enlève les . entre les chiffres
             .replace(' ', '') # enlève les espaces
    )

    print(f"TVA envoyée à MeiliSearch : {search_term}")

    client = Client(
        settings.MEILI_URL,
        settings.MEILI_SEARCH_KEY
    )

    indexes = {
        'moniteur': settings.INDEX_NAME,
    }

    results = {}
    for key, index_name in indexes.items():
        try:
            raw_hits = client.index(index_name).search(search_term).get('hits', [])
        except Exception as e:
            print(f"[ERREUR] Index '{key}' → {e}")
            raw_hits = []

        filtered_hits = [
            hit for hit in raw_hits
            if search_term in hit.get("text", "").replace('.', '').replace(' ', '')
        ]

        results[key] = filtered_hits

    return JsonResponse(results)

def home(request):
    return render(request, 'veille/home.html')

def charts(request):
    return render(request, 'veille/charts.html')

def contact(request):
    return render(request, 'veille/contact.html')

def fonctionnalites(request):
    return render(request, 'veille/fonctionnalites.html')

def recherches(request):
    return render(request, 'veille/recherches.html')

def resultats(request):
    return render(request, 'veille/resultats.html')

def maveille(request):
    return render(request, 'veille/maveille.html')

def premium(request):
    return render(request, 'veille/premium.html')






def register(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")
        username = email  # Ici, on prend l'email comme username

        # Vérifie mot de passe identique
        if password != password_confirm:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, "veille/register.html")

        # Vérifie si le compte existe déjà
        if User.objects.filter(username=username).exists():
            messages.error(request, "Un compte avec cet email existe déjà.")
            return render(request, "veille/register.html")

        # Crée le User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Crée le UserProfile
        UserProfile.objects.create(user=user)

        messages.success(request, "Votre compte a été créé. Vous pouvez vous connecter.")
        return redirect("login")

    return render(request, "veille/register.html")

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Rappel: on utilise l'email comme username
        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            return redirect("home")  # À remplacer par le nom de ton URL d'accueil
        else:
            messages.error(request, "Email ou mot de passe invalide.")
    return render(request, "veille/login.html")
