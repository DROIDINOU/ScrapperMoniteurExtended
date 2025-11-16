from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib.auth import logout
from django.http import JsonResponse
from django.db import connection
from .models import UserProfile
from .keywords import KEYWORD_GROUPS, KEYWORD_LABELS
# views.py
from django.db.models import Prefetch
import meilisearch
from .models import VeilleSociete, VeilleEvenement
import re
from django.utils.timezone import now
from django.core.management import call_command
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from .models import Veille
from meilisearch import Client as MeiliClient
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required


def home_marketing(request):
    if request.user.is_authenticated:
        return redirect("dashboard_veille")
    return render(request, "veille/home_marketing.html")


def privacy(request):
    return render(request, "veille/privacy.html", {
        "now": now().strftime("%d/%m/%Y"),
        "site_name": "Moniteur AI",
        "contact_email": "contact@moniteur-ai.com"
    })

def cgu(request):
    return render(request, "veille/cgu.html")


def send_test_email():
    send_mail(
        'Test Email Subject',  # Sujet de l'email
        'Here is the message.',  # Contenu de l'email
        'from@example.com',  # Adresse de l'expéditeur (peut être l'email du domaine configuré sur Mailgun)
        ['to@example.com'],  # Liste des destinataires
        fail_silently=False,
    )


@login_required
def veille_fuzzy(request):
    profile = request.user.userprofile

    if request.method == "POST":
        print(">>> POST =", request.POST)
        # ✅ Sauvegarde des mots-clés
        profile.keyword1 = request.POST.get("keyword1")
        profile.keyword2 = request.POST.get("keyword2")
        profile.keyword3 = request.POST.get("keyword3")
        profile.save()

        # ✅ Nom de la veille
        veille_nom = request.POST.get("veille_nom", "").strip()
        if not veille_nom:
            veille_nom = f"Veille Mots-clés — {request.user.username}"

        # ✅ Filtres
        decision_type = request.POST.get("decision_type")
        date_from = request.POST.get("date_from")

        # ✅ Création de la veille
        veille_obj = Veille.objects.create(
            user=request.user,
            nom=veille_nom,
            type="KEYWORD",
            last_scan=now()
        )

        try:
            # ✅ Appel direct à ta commande `scan_keywords`
            print(">>> Lancement du scan_keywords depuis la vue Django...")
            call_command(
                "scan_keywords",
                veille_id=veille_obj.id,
                decision_type=decision_type,
                date_from=date_from,
            )

            # ✅ Email de confirmation
            send_mail(
                'Veille juridique créée avec succès',
                f'Votre veille juridique a été créée avec succès.\nNom de la veille : {veille_nom}\n\nVous pouvez dès à présent consulter votre dashboard pour vérifier les éventuels résultats',
                settings.EMAIL_HOST_USER,
                [request.user.email],
                fail_silently=False,
            )

            messages.success(request, "✅ Veille créée et scan lancé avec succès.")
            return redirect("dashboard_veille")

        except Exception as e:
            messages.error(request, f"❌ Une erreur s'est produite lors du lancement du scan : {e}")
            return redirect("dashboard_veille")

    return render(request, "veille/fuzzy_veille.html", {"profile": profile})


@login_required
def update_veille_recurrence(request, veille_id):
    veille = get_object_or_404(Veille, pk=veille_id, user=request.user)

    if request.method == "POST":
        recurrence = request.POST.get("recurrence")
        if recurrence in ["instant", "daily", "weekly", "monthly"]:
            veille.recurrence = recurrence
            veille.save()
            messages.success(request, "Fréquence des alertes mise à jour.")
        else:
            messages.error(request, "Valeur de récurrence invalide.")

    return redirect("dashboard_veille")



@login_required
def maveille(request):

    if request.method == "POST":
        raw = request.POST.get("tva_list", "")
        nom_veille = request.POST.get("nom_veille", "").strip()

        if not nom_veille:
            from datetime import datetime
            nom_veille = f"Veille TVA {datetime.now().strftime('%d/%m/%Y')} - {request.user.username}"

        # ✅ Rechercher une veille existante AVANT de créer
        veille_obj, created = Veille.objects.get_or_create(
            user=request.user,
            type="TVA",
            nom=nom_veille,  # ou tu peux utiliser f"Veille TVA {tva}"
        )

        if created:
            veille_obj.last_scan = now()
            veille_obj.save()

        # ✅ Ajouts des sociétés surveillées + scan automatique
        # ✅ Ajouts des sociétés surveillées + scan automatique
        for tva in raw.split():
            tva = re.sub(r"\D", "", tva)

            societe, _ = VeilleSociete.objects.get_or_create(
                numero_tva=tva,
                veille=veille_obj
            )

            print(f"🚀 lancement du scan TVA pour {tva}")  # DEBUG

            # ✅ ON PASSE L'ID DE LA VEILLE À LA COMMANDE
            call_command("veille_scan", tva=tva, veille=veille_obj.id)
            # Envoi de l'email de notification à l'utilisateur
            send_mail(
                'Veille juridique créée avec succès',  # Sujet
                f'Votre veille juridique a été créée avec succès.\nNom de la veille : {nom_veille}\n\nVous pouvez dès à présent consulter votre dashboard pour vérifier les éventuels résultats',
                # Corps du message
                settings.EMAIL_HOST_USER,  # Expéditeur
                [request.user.email],  # Destinataire
                fail_silently=False,
            )

        messages.success(request, "✅ Veille TVA créée et scan lancé automatiquement !")
        return redirect("dashboard_veille")

    return render(request, "veille/maveille.html")

@login_required
def veille_dashboard(request):
    print("\n----------------------------------------")
    print("🟦 DASHBOARD : chargement des veilles…")
    print("----------------------------------------")

    veilles = (
        Veille.objects.filter(user=request.user)
        .prefetch_related(
            "societes",
            Prefetch(
                "evenements",
                queryset=VeilleEvenement.objects.select_related("societe").order_by("-date_publication")
            ),
        )
        .order_by("-date_creation")
    )

    print(f"✅ Nombre de veilles trouvées : {veilles.count()}")

    tableau = []

    # Initialisation du client MeiliSearch
    client = meilisearch.Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
    index = client.index(settings.INDEX_NAME)

    for veille in veilles:
        print(f"\n🔔 Veille ID={veille.id} ({veille.type}) : {veille.nom}")

        if veille.type == "KEYWORD":
            annexes = veille.evenements.filter(type="ANNEXE", societe__isnull=True)
            decisions_queryset = veille.evenements.filter(type="DECISION", societe__isnull=True)

            decisions = []

            for ev in decisions_queryset:
                hit_data = None

                # Recherche du document correspondant dans MeiliSearch via l'URL
                try:
                    search_res = index.search("", {"filter": f'url = "{ev.source}"'})
                    hits = search_res.get("hits", [])
                    print(f"🔍 Recherche Meili pour URL={ev.source} → {len(hits)} résultat(s)")
                    if hits:
                        print("Premier hit:", hits[0])
                    if hits:
                        hit_data = hits[0]
                except Exception as e:
                    print(f"⚠️ Erreur Meili pour {ev.source}: {e}")

                decision = {
                    "titre": ev.titre or "Titre non disponible",
                    "date_publication": ev.date_publication or "Date non disponible",
                    "source": ev.source,
                    # Champs enrichis Meili
                    "TVA": hit_data.get("TVA") if hit_data else None,
                    "extra_keyword": hit_data.get("extra_keyword") if hit_data else None,
                    "date_jugement": hit_data.get("date_jugement") if hit_data else None,
                    "administrateur": hit_data.get("administrateur") if hit_data else None,
                    "adresses_by_bce": hit_data.get("adresses_by_bce") if hit_data else None,
                    "adresses_by_ejustice": hit_data.get("adresses_by_ejustice") if hit_data else None,
                    "adresses_all_flat": hit_data.get("adresses_all_flat") if hit_data else None,
                    "denoms_by_bce": hit_data.get("denoms_by_bce") if hit_data else None,
                    "denoms_by_ejustice_flat": hit_data.get("denoms_by_ejustice_flat") if hit_data else None,
                }

                decisions.append(decision)

            veille.result_count = annexes.count() + len(decisions)

            tableau.append({
                "veille": veille,
                "societe": None,
                "annexes": annexes,
                "decisions": decisions,
            })

        elif veille.type == "TVA":
            print(f"    -> TVA : {veille.societes.count()} sociétés surveillées")
            total_annexes = 0  # Initialisation du total des annexes pour la TVA
            total_decisions = 0  # Initialisation du total des décisions pour la TVA
            veille.result_count = 0  # Initialisation du total des événements (annexes + décisions)

            for societe in veille.societes.all():
                print(f"        🔎 Société : {societe.numero_tva} (ID={societe.id})")

                # Récupérer les annexes pour cette société
                annexes = veille.evenements.filter(type="ANNEXE", societe=societe)

                # Recherche des décisions judiciaires dans MeiliSearch
                tva = societe.numero_tva
                results = index.search("", {"filter": f'TVA IN ["{tva}"]'})  # Recherche de décisions pour cette TVA
                decisions = []
                for hit in results.get("hits", []):  # Utilisation de .get pour éviter une erreur si "hits" n'existe pas
                    decision = {
                        "titre": hit.get("title", "Titre non disponible"),
                        "date_publication": hit.get("date_doc", "Date non disponible"),
                        "source": hit.get("url", "URL non disponible"),
                        # 🧠 Champs additionnels (pour modale)
                        "TVA": hit.get("TVA"),
                        "extra_keyword": hit.get("extra_keyword"),
                        "date_jugement": hit.get("date_jugement"),
                        "administrateur": hit.get("administrateur"),
                        "adresses_by_bce": hit.get("adresses_by_bce"),
                        "adresses_by_ejustice": hit.get("adresses_by_ejustice"),
                        "adresses_all_flat": hit.get("adresses_all_flat"),
                        "denoms_by_bce": hit.get("denoms_by_bce"),
                        "denoms_by_ejustice_flat": hit.get("denoms_by_ejustice_flat"),
                    }

                    decisions.append(decision)

                # Mise à jour des totaux pour la veille de type "TVA"
                total_annexes += annexes.count()
                total_decisions += len(decisions)

                print(f"           ➤ annexes = {annexes.count()} | décisions = {len(decisions)}")
                print(f"Résultat brut MeiliSearch pour {tva}: {results}")

                tableau.append({
                    "veille": veille,
                    "societe": societe,
                    "annexes": annexes,
                    "decisions": decisions,  # Ajout des décisions récupérées de MeiliSearch
                })

            # Mettre à jour le résultat total pour la veille de type "TVA"
            veille.result_count = total_annexes + total_decisions
            # Ajouter les totaux dans le tableau pour cette veille
            tableau.append({
                "veille": veille,
                "societe": None,
                "total_annexes": total_annexes,
                "total_decisions": total_decisions,
                "annexes": None,
                "decisions": None,
            })

    # Debug : Afficher le contenu final du tableau avant de rendre la page
    print("\n✅ FIN DASHBOARD (tableau généré)")
    print(f"Tableau final: {tableau}")
    print("\n✅ FIN DASHBOARD (tableau généré)\n")

    return render(
        request,
        "veille/dashboard.html",
        {"tableau": tableau, "veilles": veilles},
    )



@login_required
def scan_decisions_keywords(request, veille_id):
    print(">>> SCAN KEYWORDS", veille_id)
    call_command("scan_keywords", veille=veille_id)
    messages.success(request, "✅ Scan mots-clés lancé.")
    return redirect("dashboard_veille")


@login_required
def lancer_scan(request, tva):
    print(">>> lancer_scan VUE APPELÉE")
    print(f">>> TVA reçue = {tva}")

    try:
        # ✅ retrouver la veille de l'utilisateur liée à cette TVA
        soc = VeilleSociete.objects.filter(
            veille__user=request.user,
            numero_tva=re.sub(r"\D", "", tva)
        ).select_related("veille").first()

        if not soc:
            messages.error(request, "❌ Cette TVA n'est pas dans vos veilles.")
            return redirect("dashboard_veille")

        print(f"➡️ Scan déclenché pour TVA {soc.numero_tva} sur veille ID={soc.veille.id}")

        # ✅ on passe l'ID de la veille
        call_command("veille_scan", tva=soc.numero_tva, veille=soc.veille.id)

        messages.success(
            request,
            f"✅ Scan lancé pour TVA {soc.numero_tva} (Veille : {soc.veille.nom})"
        )

    except Exception as e:
        print(f"❌ ERREUR veille_scan : {e}")
        messages.error(request, f"❌ Erreur lors du scan TVA : {e}")

    return redirect("dashboard_veille")


def scan_decisions(request, tva):

    client = meilisearch.Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
    index = client.index(settings.INDEX_NAME)

    results = index.search("", {"filter": f'TVA = "{tva}"'})
    societes = VeilleSociete.objects.filter(numero_tva=tva)

    count = 0

    for soc in societes:
        for doc in results["hits"]:
            VeilleEvenement.objects.get_or_create(
                veille=soc.veille,
                societe=soc,  # ✅ c’est CE paramètre qui manque
                type="DECISION",
                date_publication=doc.get("date_doc"),
                source=doc.get("url") or f"no-url-{doc.get('date_doc')}",
                defaults={
                    "rubrique": ", ".join(doc.get("extra_keyword") or []),
                    "titre": doc.get("title") or "",
                }
            )

            count += 1

    messages.success(request, f"⚖️ {count} décision(s) trouvée(s) pour TVA {tva}")
    return redirect("dashboard_veille")


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


@login_required
def supprimer_veille(request, pk):
    veille = get_object_or_404(Veille, pk=pk, user=request.user)

    if request.method == "POST":
        veille.delete()
        messages.success(request, "La veille a bien été supprimée.")
        return redirect('dashboard_veille')

    return redirect('dashboard_veille')

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
# ✅ API : renvoie la liste des sociétés (JSON)
# ------------------------------------------------------------
def api_societes(request):
    bces = request.GET.get("n", "").split(",")

    if not bces or bces == [""]:
        return JsonResponse([], safe=False)

    with connection.cursor() as cur:
        cur.execute("""
            SELECT bce, nom
            FROM societe
            WHERE bce = ANY(%s)
        """, [bces])

        data = [{"bce": row[0], "nom": row[1]} for row in cur.fetchall()]

    return JsonResponse(data, safe=False)

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
def home(request): return render(request, "veille/app_home.html")
def charts(request): return render(request, "veille/charts.html")
def contact(request): return render(request, "veille/contact.html")
def fonctionnalites(request): return render(request, "veille/fonctionnalites.html")
def recherches(request): return render(request, "veille/recherches.html")
def resultats(request): return render(request, "veille/resultats.html")

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
            return redirect("dashboard_veille")  # ✅ ENFIN LA BONNE ROUTE

        messages.error(request, "Email ou mot de passe incorrect.")

    return render(request, "veille/login.html")


def logout_view(request):
    logout(request)
    return redirect("/")
