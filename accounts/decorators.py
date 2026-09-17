from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


def receptionist_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        
        # Superusers or users with receptionist role can access
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        profile = getattr(request.user, "profile", None)
        if profile and profile.role in ["receptionist", "owner"]:
            return view_func(request, *args, **kwargs)
        
        messages.error(request, "You do not have permission to access that page.")
        return redirect("login")

    return _wrapped_view


def owner_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        profile = getattr(request.user, "profile", None)
        if profile and profile.role == "owner":
            return view_func(request, *args, **kwargs)
        
        messages.error(request, "Owner access required.")
        return redirect("ticket_create")

    return _wrapped_view
