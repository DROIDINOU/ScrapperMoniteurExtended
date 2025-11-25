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
import threading
from django.core.exceptions import ValidationError
from datetime import datetime


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


def parse_date_doc(raw_date):
    """Convertit une string ISO 'YYYY-MM-DD' en objet date, sinon renvoie la valeur brute."""
    if not raw_date:
        return None
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except Exception:
        return raw_date


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
def recurrence_view(request, veille_id):
    veille = get_object_or_404(Veille, pk=veille_id, user=request.user)
    return render(request, "veille/recurrencealerte.html", {"veille": veille})


@login_required
def veille_fuzzy(request):
    profile = request.user.userprofile

    if request.method == "POST":

        # 🔹 Nom de la veille
        veille_nom = request.POST.get("veille_nom", "").strip()
        if not veille_nom:
            veille_nom = f"Veille Mots-clés — {request.user.username}"

        # 🔹 Récupération des filtres
        keyword = request.POST.get("keyword", "").strip()          # 🟢 MANQUAIT !
        decision_type = request.POST.get("decision_type", "").strip()
        date_from = request.POST.get("date_from", "").strip()
        rue_value = request.POST.get("rue", "").strip()

        # 🔥 Vérification minimale
        if not (keyword or decision_type or date_from or rue_value):
            messages.error(
                request,
                "Vous devez sélectionner au moins un filtre (mot-clé, type de décision, date ou rue)."
            )
            return redirect("veille_fuzzy")

        # 🔹 Création de la veille AVEC les bons champs
        veille_obj = Veille(
            user=request.user,
            nom=veille_nom,
            type="KEYWORD",
            last_scan=now(),

            keyword=keyword or None,
            decision_type=decision_type or None,
            date_from=date_from or None,
            rue=rue_value or None,
        )

        try:
            veille_obj.full_clean()
            veille_obj.save()
        except ValidationError as e:
            messages.error(request, e.messages[0])
            return redirect("veille_fuzzy")

        # 🔥 Lancement correct du scan
        try:
            call_command(
                "scan_keywords",
                veille_id=veille_obj.id,
                keyword=keyword or "",
                decision_type=decision_type or "",
                date_from=date_from or "",
                rue=rue_value or "",
            )

            send_mail(
                'Veille juridique créée avec succès',
                f'Votre veille "{veille_nom}" a bien été créée.',
                settings.EMAIL_HOST_USER,
                [request.user.email],
                fail_silently=False,
            )

            return redirect("recurrence_view", veille_id=veille_obj.id)

        except Exception as e:
            messages.error(request, f"❌ Erreur lors du lancement du scan : {e}")
            return redirect("recurrence_view", veille_id=veille_obj.id)

    # GET → affichage
    veilles = Veille.objects.filter(user=request.user)
    tableau = []
    for veille in veilles:
        decisions = VeilleEvenement.objects.filter(veille=veille, type="DECISION")
        tableau.append({
            "veille": veille,
            "decisions": [
                {
                    "titre": d.titre,
                    "rubrique": d.rubrique,
                    "date_publication": d.date_publication,
                    "source": d.source,
                    "tva_list": d.tva_list,
                }
                for d in decisions
            ],
            "total_decisions": decisions.count(),
        })

    return render(request, "veille/fuzzy_veille.html", {
        "profile": profile,
        "tableau": tableau,
    })


@login_required
def update_veille_recurrence(request, veille_id):
    veille = get_object_or_404(Veille, pk=veille_id, user=request.user)

    print("\n" + "="*80)
    print("🟦 DEBUG update_veille_recurrence")
    print(f"➡️ Veille ID   : {veille.id}")
    print(f"➡️ Avant update : recurrence={veille.recurrence}, weekday={veille.recurrence_weekday}")
    print("="*80)

    if request.method == "POST":

        print("📥 POST reçu :", request.POST)

        recurrence = request.POST.get("recurrence")
        weekday = request.POST.get("weekday")
        weekday = weekday if weekday else None

        print(f"➡️ Valeur POST recurrence = {recurrence}")
        print(f"➡️ Valeur POST weekday    = {weekday}")

        allowed = ["none", "daily", "weekly", "monthly"]

        if recurrence not in allowed:
            print("❌ ERREUR : recurrence NON reconnue")
            messages.error(request, f"Valeur de récurrence invalide : {recurrence}")
            return redirect("dashboard_veille")

        # appliquer la récurrence
        veille.recurrence = recurrence

        if recurrence == "weekly":
            veille.recurrence_weekday = weekday
        else:
            veille.recurrence_weekday = None

        veille.save()

        print("✔️ Mise à jour FAITE !")
        print(f"➡️ Après update : recurrence={veille.recurrence}, weekday={veille.recurrence_weekday}")
        print("="*80 + "\n")

        messages.success(request, "Fréquence des alertes mise à jour.")

    return redirect("dashboard_veille")



def maveille(request):
    if request.method == "POST":
        raw = request.POST.get("tva_list", "")
        nom_veille = request.POST.get("nom_veille", "").strip()

        if not nom_veille:
            from datetime import datetime
            nom_veille = f"Veille TVA {datetime.now().strftime('%d/%m/%Y')} - {request.user.username}"

        # On prépare l'objet veille (NON sauvegardé)
        veille_obj = Veille(
            user=request.user,
            type="TVA",
            nom=nom_veille,
        )

        try:
            # 1️⃣ Appelle clean() + validations Django
            veille_obj.full_clean()

            # 2️⃣ Sauvegarde seulement si propre
            veille_obj.save()

        except ValidationError as e:
            messages.error(request, e.messages[0])
            return redirect("maveille")

        # 3️⃣ Maintenant on ajoute les sociétés
        for tva in raw.split():
            tva = re.sub(r"\D", "", tva)
            VeilleSociete.objects.get_or_create(numero_tva=tva, veille=veille_obj)

        # 4️⃣ Lancement du scan en thread
        def run_scan():
            for tva in raw.split():
                tva = re.sub(r"\D", "", tva)
                call_command("veille_scan", tva=tva, veille=veille_obj.id)

            send_mail(
                'Veille juridique créée avec succès',
                f'Votre veille juridique a été créée avec succès.\nNom de la veille : {nom_veille}',
                settings.EMAIL_HOST_USER,
                [request.user.email],
                fail_silently=False,
            )

        threading.Thread(target=run_scan).start()

        return redirect("recurrence_view", veille_id=veille_obj.id)

    return render(request, "veille/maveille.html")


@login_required
def veille_dashboard(request):
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

    tableau = []

    # Initialisation du client MeiliSearch
    client = meilisearch.Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
    index = client.index(settings.INDEX_NAME)

    for veille in veilles:

        if veille.type == "KEYWORD":
            annexes = veille.evenements.filter(type="ANNEXE", societe__isnull=True)

            decisions_queryset = veille.evenements.filter(
                type="DECISION",
                societe__isnull=True
            )

            decisions = []
            total_decisions = 0

            for ev in decisions_queryset:
                # 🔥 Filtrage : si veille mots‐clés → score obligatoire > 0.9
                decisions.append({
                    "titre": ev.titre or "Titre non disponible",
                    "date_publication": ev.date_publication,
                    "source": ev.source,
                    "rubrique": ev.rubrique,
                    "tva_list": ev.tva_list,
                    "extra_keyword": ev.rubrique,
                })
                total_decisions += 1

            # TRIER LES DÉCISIONS PAR SCORE (haut -> bas)
            # 🟢 CORRIGÉ : en dehors de la boucle
            veille.total_decisions = total_decisions
            veille.total_annexes = annexes.count()

            tableau.append({
                "veille": veille,
                "societe": None,
                "annexes": annexes,
                "decisions": decisions,
                "total_decisions": total_decisions,
            })


        elif veille.type == "TVA":

            total_decisions = 0
            total_annexes = 0

            for societe in veille.societes.all():
                soc_annexes = veille.evenements.filter(
                    type="ANNEXE",
                    societe=societe
                )

                soc_decisions_db = veille.evenements.filter(
                    type="DECISION",
                    societe=societe
                )

                # Ajoute au tableau
                tableau.append({
                    "veille": veille,
                    "societe": societe,
                    "annexes": soc_annexes,
                    "decisions": [
                        {
                            "titre": d.titre,
                            "rubrique": d.rubrique,
                            "date_publication": d.date_publication,
                            "source": d.source,
                            "tva_list": d.tva_list,
                        }
                        for d in soc_decisions_db
                    ],
                    "total_annexes": soc_annexes.count(),
                    "total_decisions": soc_decisions_db.count(),
                })

                total_annexes += soc_annexes.count()
                total_decisions += soc_decisions_db.count()

            veille.total_annexes = total_annexes
            veille.total_decisions = total_decisions

    # Debug : Afficher le contenu final du tableau avant de rendre la page
    print("\n====== DEBUG TVA DB ======")

    for ev in VeilleEvenement.objects.filter(type="DECISION"):
        print(f"[DECISION] veille={ev.veille.id} societe={ev.societe} date={ev.date_publication} titre={ev.titre}")

    print("====== FIN DEBUG ======\n")
    # 🔥 UNE FOIS que tableau est complètement rempli
    for veille in veilles:
        if veille.type == "TVA":
            veille.total_decisions = sum(
                entry["total_decisions"]
                for entry in tableau
                if entry["veille"].id == veille.id
            )

    return render(
        request,
        "veille/dashboard.html",
        {"tableau": tableau, "veilles": veilles},
    )


@login_required
def scan_decisions_keywords(request, veille_id):
    call_command("scan_keywords", veille=veille_id)
    messages.success(request, "✅ Scan mots-clés lancé.")
    return redirect("dashboard_veille")


@login_required
def lancer_scan(request, tva):
    try:
        # ✅ retrouver la veille de l'utilisateur liée à cette TVA
        soc = VeilleSociete.objects.filter(
            veille__user=request.user,
            numero_tva=re.sub(r"\D", "", tva)
        ).select_related("veille").first()

        if not soc:
            messages.error(request, "❌ Cette TVA n'est pas dans vos veilles.")
            return redirect("dashboard_veille")

        # ✅ on passe l'ID de la veille
        call_command("veille_scan", tva=soc.numero_tva, veille=soc.veille.id)

        messages.success(
            request,
            f"✅ Scan lancé pour TVA {soc.numero_tva} (Veille : {soc.veille.nom})"
        )

    except Exception as e:
        messages.error(request, f"❌ Erreur lors du scan TVA : {e}")

    return redirect("dashboard_veille")


def scan_decisions(request, tva):
    client = meilisearch.Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
    index = client.index(settings.INDEX_NAME)

    results = index.search("", {"filter": f'TVA = "{tva}"'})
    societes = VeilleSociete.objects.filter(numero_tva=tva)

    count = 0

    for soc in societes:
        for doc in results.get("hits", []):
            VeilleEvenement.objects.get_or_create(
                veille=soc.veille,
                societe=soc,  # ✅ FIX ICI !!!
                type="DECISION",
                date_publication=parse_date_doc(doc.get("date_doc")),
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


def info_utilisation(request): return render(request, "veille/info.html")


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
