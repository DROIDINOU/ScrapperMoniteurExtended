from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path("", views.home_marketing, name="home"),
    path("app/", views.home, name="app_home"),
    path("confidentialite/", views.privacy, name="privacy"),
    path('charts/', views.charts, name='charts'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path("logout/", views.logout_view, name="logout"),
    path("cgu/", views.cgu, name="cgu"),
    path("veille/fuzzy/", views.veille_fuzzy, name="veille_fuzzy"),
    path('api/search/', views.api_search, name='api_search'),
    path("api/autocomplete/keyword/", views.api_autocomplete_keyword, name="autocomplete_keyword"),
    path("api/search/keyword/", views.api_search_keyword, name="api_search_keyword"),
    # Page de configuration (GET)
    path("veille/<int:veille_id>/recurrence/", views.recurrence_view, name="recurrence_view"),
    # Traitement du POST
    path("veille/<int:veille_id>/recurrence/update/", views.update_veille_recurrence, name="update_veille_recurrence"),
    path("api/societes", views.api_societes, name="api_societes"),
    path("scan/<str:tva>/", views.lancer_scan, name="lancer_scan"),
    path("societe/<str:bce>/", views.fiche_societe, name="fiche_societe"),
    path('veille/supprimer/<int:pk>/', views.supprimer_veille, name='supprimer_veille'),
    path("api/search/rue/", views.api_search_rue, name="api_search_rue"),
    path("api/autocomplete/rue/", views.api_autocomplete_rue, name="autocomplete_rue"),
    path("dashboard/", views.veille_dashboard, name="dashboard_veille"),
    path("scan-decisions/<str:tva>/", views.scan_decisions, name="scan_decisions"),
    path("scan-keywords/<int:veille_id>/", views.scan_decisions_keywords, name="scan_decisions_keywords"),
    path('api/search/tva/', views.api_search_tva, name='api_search_tva'),
    path('contact/', views.contact, name='contact'),
    path('info_utilisation/', views.info_utilisation, name='info_utilisation'),

    path('fonctionnalites/', views.fonctionnalites, name='fonctionnalites'),
    path('recherches/', views.recherches, name='recherches'),
    path('resultats/', views.resultats, name='resultats'),
    path('maveille/', views.maveille, name='maveille'),
    path('premium/', views.premium, name='premium'),

]
