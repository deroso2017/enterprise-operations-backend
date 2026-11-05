from django.urls import path

from .views import (
    AdminOnlyView,
    CurrentUserView,
    LoginView,
    LogoutView,
    ManagerOrAdminView,
    RefreshView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("admin-check/", AdminOnlyView.as_view(), name="admin-check"),
    path(
        "management-check/",
        ManagerOrAdminView.as_view(),
        name="management-check",
    ),
]
