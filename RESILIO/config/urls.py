from django.contrib import admin
from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from coordination import views
from coordination.forms import PortalAuthenticationForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        LoginView.as_view(authentication_form=PortalAuthenticationForm),
        name="login",
    ),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("register/", views.register),
    path("access/", views.access),
    path("", views.home),
    path("api/<str:action>/", views.api),
    path("sw.js", views.worker),
]
