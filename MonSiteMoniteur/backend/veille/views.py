from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from .models import UserProfile
from django.contrib.auth import authenticate, login
import re
from django.http import JsonResponse
from meilisearch import Client
from sentence_transformers import SentenceTransformer
from django.http import JsonResponse
from meilisearch import Client as MeiliClient
import psycopg2
import numpy as np

# Chargement du modèle d'embedding
model = SentenceTransformer(
    "dangvantuan/sentence-camembert-large",
    trust_remote_code=True,
    use_auth_token=False
)

def api_search(request):
    query = request.GET.get('q', '').strip()
    print(f"[🔍] Requête utilisateur : {query}")

    is_meili = query.startswith('=')
    search_term = query.lstrip('=').lower()

    results = {
        "moniteur": []
    }

    if is_meili:
        # 🚀 Recherche rapide MeiliSearch
        print("[🔎] Mode MeiliSearch (texte)")
        try:
            client = MeiliClient('http://127.0.0.1:7700')
            hits = client.index("moniteur_documents").search(
                search_term,
                {
                    "limit": 20
                }
            ).get("hits", [])

            print(f"[📄] Résultats MeiliSearch : {len(hits)}")
            results["moniteur"] = [
                {
                    "text": h.get("text", ""),
                    "url": h.get("url", ""),
                    "title": h.get("title", ""),
                    "subtitle": h.get("subtitle", ""),
                    "date_document": h.get("date_document", "")
                }
                for h in hits
            ]
        except Exception as e:
            print("[❌ MeiliSearch] Erreur :", e)

    else:
        # 🧠 Recherche vectorielle sémantique
        print("[🧠] Mode Embedding PostgreSQL (vectoriel)")
        try:
            embedding = model.encode(search_term).tolist()
            print("[📐] Embedding généré avec succès")

            conn = psycopg2.connect(
                dbname="monsite_db",
                user="postgres",
                password="Jamesbond007colibri+",
                host="localhost",
                port="5432"
            )
            cur = conn.cursor()

            cur.execute("""
                SELECT texte, url, title, subtitle, date_document
                FROM moniteur_documents
                ORDER BY embedding <-> %s
                LIMIT 20;
            """, (embedding,))
            rows = cur.fetchall()
            print(f"[📦] Résultats PostgreSQL : {len(rows)}")

            results["moniteur"] = [
                {
                    "texte": r[0],
                    "url": r[1],
                    "title": r[2],
                    "subtitle": r[3],
                    "date_document": str(r[4])
                }
                for r in rows
            ]

            cur.close()
            conn.close()
        except Exception as e:
            print("[❌ PostgreSQL] Erreur :", e)
            return JsonResponse({"error": f"PostgreSQL error: {str(e)}"}, status=500)

    print("[✅] Résultats renvoyés :", {k: len(v) for k, v in results.items()})
    return JsonResponse(results)

def api_search_niss(request):
    query = request.GET.get('q', '').strip()
    print(f"NISS query: {query}")
    client = Client('http://127.0.0.1:7700')

    # Ne modifie pas la structure
    search_term = query  # Pas de transformation ici

    indexes = {
        'moniteur': 'moniteur_documents',
        #'eurlex': 'eurlex_docs',
        #'CEtat': 'conseil_etat_arrets100',
        #'CA': 'constcourtjudgments2025',
        #'Annexe': 'annexes_juridique'
    }

    results = {}

    for key, index_name in indexes.items():
        try:
            raw_hits = client.index(index_name).search(search_term).get('hits', [])
        except Exception as e:
            print(f"[ERREUR] Index '{key}' → {e}")
            raw_hits = []

        # Match textuellement
        filtered_hits = [
            hit for hit in raw_hits
            if search_term in hit.get("text", "")
        ]

        results[key] = filtered_hits

    return JsonResponse(results)



def api_search_tva(request):
    query = request.GET.get('q', '').strip()
    print(f"TVA query: {query}")
    client = Client('http://127.0.0.1:7700')

    search_term = query.lstrip('=').lower()

    indexes = {
        'moniteur': 'moniteur_documents',
        #'eurlex': 'eurlex_docs',
        #'CEtat': 'conseil_etat_arrets100',
        #'CA': 'constcourtjudgments2025',
        #'Annexe': 'annexes_juridique'
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
            if search_term in hit.get("text", "").lower()
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
