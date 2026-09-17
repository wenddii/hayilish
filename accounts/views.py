from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard_redirect")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get("next")
            if next_url:
                return redirect(next_url)
            return redirect("dashboard_redirect")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")


@login_required
def dashboard_redirect(request):
    user = request.user
    if user.is_superuser:
        return redirect("owner_dashboard")
    
    profile = getattr(user, "profile", None)
    if profile and profile.role == "owner":
        return redirect("owner_dashboard")
    
    return redirect("ticket_create")
