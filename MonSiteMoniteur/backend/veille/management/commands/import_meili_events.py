from django.core.management.base import BaseCommand
from django.conf import settings
from veille.models import VeilleSociete, VeilleEvenement
import meilisearch


class Command(BaseCommand):
    help = "Importe depuis MeiliSearch les décisions judiciaires et crée des événements liés aux TVA surveillées"

    def handle(self, *args, **kwargs):

        client = meilisearch.Client(
            settings.MEILI_URL,
            settings.MEILI_MASTER_KEY
        )

        index_name = getattr(settings, "MEILI_INDEX_DECISIONS", "moniteur_docs")
        index = client.index(index_name)

        self.stdout.write("📡 Chargement des sociétés surveillées…")

        societes = VeilleSociete.objects.all()

        count_total = 0
        count_created = 0

        for societe in societes:
            tva = societe.numero_tva.replace(".", "").replace(" ", "")

            results = index.search("", {"filter": f'TVA = "{tva}"'})
            hits = results.get("hits", [])
            count_total += len(hits)

            for doc in hits:
                evenement, created = VeilleEvenement.objects.get_or_create(
                    societe=societe,
                    date_publication=doc.get("date_doc"),
                    type="DECISION",
                    source=doc.get("url"),
                    defaults={
                        "rubrique": ", ".join(doc.get("extra_keyword") or []),
                        "titre": doc.get("title", "")[:500],
                    }
                )

                if created:
                    count_created += 1
                    self.stdout.write(self.style.SUCCESS(f"✅ TVA {tva} — nouvelle décision"))
                else:
                    self.stdout.write("⏩ déjà existant")

        self.stdout.write(self.style.SUCCESS(
            f"\n✨ Import terminé : {count_created}/{count_total} événements ajoutés."
        ))
