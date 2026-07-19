from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('words/', views.words, name='words'),
    path('numbers/', views.numbers, name='numbers'),
    path('profile/', views.profile, name='profile'),
    path('users/<str:user_id>/', views.user_profile, name='user_profile'),
    path('dev/', views.dev, name='dev'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-email/', views.verify_email, name='verify_email'),
    # Legacy redirects
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('friends/', views.friends, name='friends'),
    path('trophies/', views.trophies, name='trophies'),
]
