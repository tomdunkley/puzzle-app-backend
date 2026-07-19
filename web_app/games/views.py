from django.shortcuts import render, redirect
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

def profile(request):
    return render(request, 'games/profile.html', _ctx())

def user_profile(request, user_id):
    ctx = _ctx()
    ctx['profile_user_id'] = user_id
    return render(request, 'games/user_profile.html', ctx)

def dev(request):
    return render(request, 'games/dev.html', _ctx())

def login(request):
    return render(request, 'games/login.html', _ctx())

def register(request):
    return render(request, 'games/register.html', _ctx())

def forgot_password(request):
    return render(request, 'games/forgot_password.html', _ctx())

def verify_email(request):
    return render(request, 'games/verify_email.html', _ctx())

# Old pages redirect to profile (now merged there)
def leaderboard(request):
    return redirect('/words/')

def friends(request):
    return redirect('/profile/')

def trophies(request):
    return redirect('/profile/')
