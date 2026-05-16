from django.urls import path
from . import views
app_name = 'core'

urlpatterns = [
    path('auth/register/', views.register_parent_view, name='register'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('parent/profile/', views.parent_profile_view, name='parent_profile'),
    path('parent/dashboard/', views.parent_dashboard_view, name='parent_dashboard'),
    path('parent/children/', views.my_children_view, name='my_children'),
    path('parent/assessment/', views.assessment_view, name='assessment'),
    path('therapist/dashboard/', views.therapist_dashboard_view, name='therapist_dashboard'),
    path('therapist/profile/', views.therapist_profile_view, name='therapist_profile'),
    path('therapist/children/', views.therapist_children_view, name='therapist_children'),
    path('therapist/sessions/', views.therapist_sessions_view, name='therapist_sessions'),
    path('therapist/sessions/<int:session_id>/cancel/', views.therapist_cancel_session_view, name='therapist_cancel_session'),
    path('therapist/sessions/<int:session_id>/submit/', views.therapist_submit_session_view, name='therapist_submit_session'),
   
  
]
