from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView, RegisterView, PendingRegistrationsView,
    ApproveUserView, RejectUserView,
    LogoutView, MeView, UserListView,
)

urlpatterns = [
    path('login/',                LoginView.as_view(),                name='auth-login'),
    path('register/',             RegisterView.as_view(),             name='auth-register'),
    path('registrations/pending/',PendingRegistrationsView.as_view(), name='auth-pending'),
    path('registrations/<int:pk>/approve/', ApproveUserView.as_view(), name='auth-approve'),
    path('registrations/<int:pk>/reject/',  RejectUserView.as_view(),  name='auth-reject'),
    path('logout/',               LogoutView.as_view(),               name='auth-logout'),
    path('refresh/',              TokenRefreshView.as_view(),         name='auth-refresh'),
    path('me/',                   MeView.as_view(),                   name='auth-me'),
    path('users/',                UserListView.as_view(),             name='auth-users'),
]
