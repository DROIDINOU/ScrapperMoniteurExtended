from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('charts/', views.charts, name='charts'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('api/search/', views.api_search, name='api_search'),
    #path('search_gerant_risque/', views.search_gerant_risque, name='search_gerant_risque'),
    path('api/search/tva/', views.api_search_tva, name='api_search_tva'),
    path('api/search/niss/', views.api_search_niss, name='api_search_niss'),
    path('contact/', views.contact, name='contact'),
    path('fonctionnalites/', views.fonctionnalites, name='fonctionnalites'),
    path('recherches/', views.recherches, name='recherches'),
    path('resultats/', views.resultats, name='resultats'),
    path('maveille/', views.maveille, name='maveille'),
    path('premium/', views.premium, name='premium'),

]
