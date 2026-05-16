from django.urls import path
from . import views
app_name = 'core'

urlpatterns = [
    path('auth/register/', views.register_parent_view, name='register'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('parent/profile/', views.parent_profile_view, name='parent_profile'),
    path('therapist/profile/', views.therapist_profile_view, name='therapist_profile'),
  
]
