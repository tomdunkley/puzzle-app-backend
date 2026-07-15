from django.shortcuts import render
from django.conf import settings


def _ctx():
    return {
        'api_base_url': settings.API_BASE_URL,
        'google_client_id': settings.GOOGLE_CLIENT_ID,
    }


def home(request):
    return render(request, 'games/home.html', _ctx())

def words(request):
    return render(request, 'games/boggle.html', _ctx())

def numbers(request):
    return render(request, 'games/numbers.html', _ctx())

def leaderboard(request):
    return render(request, 'games/leaderboard.html', _ctx())

def friends(request):
    return render(request, 'games/friends.html', _ctx())

def trophies(request):
    return render(request, 'games/trophies.html', _ctx())

def login(request):
    return render(request, 'games/login.html', _ctx())

def register(request):
    return render(request, 'games/register.html', _ctx())

def forgot_password(request):
    return render(request, 'games/forgot_password.html', _ctx())

def verify_email(request):
    return render(request, 'games/verify_email.html', _ctx())
