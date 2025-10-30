from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('charts/', views.charts, name='charts'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('api/search/', views.api_search, name='api_search'),
    path("api/autocomplete/keyword/", views.api_autocomplete_keyword, name="autocomplete_keyword"),
    path("api/search/keyword/", views.api_search_keyword, name="api_search_keyword"),
    path("api/search/rue/", views.api_search_rue, name="api_search_rue"),
    path("api/autocomplete/rue/", views.api_autocomplete_rue, name="autocomplete_rue"),
    path('api/search/tva/', views.api_search_tva, name='api_search_tva'),
    path('api/search/niss/', views.api_search_niss, name='api_search_niss'),
    path('contact/', views.contact, name='contact'),
    path('fonctionnalites/', views.fonctionnalites, name='fonctionnalites'),
    path('recherches/', views.recherches, name='recherches'),
    path('resultats/', views.resultats, name='resultats'),
    path('maveille/', views.maveille, name='maveille'),
    path('premium/', views.premium, name='premium'),

]
