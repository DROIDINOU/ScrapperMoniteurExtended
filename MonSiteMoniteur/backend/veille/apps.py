from django.apps import AppConfig


class VeilleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'veille'

    def ready(self):
        import veille.signals  # ✅ charge ton fichier signals.py
