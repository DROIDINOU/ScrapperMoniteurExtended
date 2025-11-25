from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from veille.models import Veille
from django.core.management import call_command


class Command(BaseCommand):
    help = "Exécute automatiquement les veilles selon leur récurrence"

    def handle(self, *args, **kwargs):
        today = now().date()

        for veille in Veille.objects.all():

            # ⚠️ Si aucune récurrence définie
            if not veille.recurrence or veille.recurrence == "none":
                continue

            # Instantané → pas de cron
            if veille.recurrence == "instant":
                continue

            last = veille.last_scan.date() if veille.last_scan else None

            # DAILY : une fois par jour
            if veille.recurrence == "daily":
                need_run = (last != today)

            # WEEKLY : au moins 7 jours
            elif veille.recurrence == "weekly":
                need_run = (not last) or ((today - last) >= timedelta(days=7))

            # MONTHLY : au moins 30 jours
            elif veille.recurrence == "monthly":
                need_run = (not last) or ((today - last) >= timedelta(days=30))

            else:
                continue

            if not need_run:
                continue

            self.stdout.write(f"⏳ Scan automatique → {veille.nom}")

            # TVA
            if veille.type == "TVA":
                for soc in veille.societes.all():
                    call_command("veille_scan", tva=soc.numero_tva, veille=veille.id)

            # KEYWORD
            elif veille.type == "KEYWORD":
                call_command(
                    "scan_keywords",
                    veille_id=veille.id,
                    decision_type="",
                    date_from="",
                    rue=""
                )

            veille.last_scan = now()
            veille.save()

            self.stdout.write(f"✔ OK → {veille.nom}")
