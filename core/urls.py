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
    path('therapist/children/<int:child_id>/add-session/', views.therapist_add_session_view, name='therapist_add_session'),
    path('therapist/treatment-plans/', views.therapist_treatment_plans_view, name='therapist_treatment_plans'),
    path('therapist/treatment-plans/<int:plan_id>/', views.therapist_treatment_plan_detail_view, name='therapist_treatment_plan_detail'),
    path('therapist/treatment-plans/<int:plan_id>/complete/', views.therapist_complete_plan_view, name='therapist_complete_plan'),
    path('therapist/treatment-plans/create/', views.therapist_create_plan_view, name='therapist_create_plan'),
    path('parent/treatment-plans/<int:plan_id>/progress/', views.parent_progress_view, name='parent_progress'),
    path('parent/progress/<int:record_id>/submit/', views.parent_progress_submit_view, name='parent_progress_submit'),
    path('therapist/children/<int:child_id>/add-plan/', views.therapist_add_plan_view, name='therapist_add_plan'),
    path('parent/treatment-plans/', views.treatment_plans_view, name='treatment_plans'),
    path('parent/treatment-plans/<int:plan_id>/', views.treatment_plan_detail_view, name='treatment_plan_detail'),
    path('parent/drawings/<int:drawing_id>/results/', views.drawing_results_view, name='drawing_results'),
    path('parent/drawings/<int:drawing_id>/reanalyze/', views.drawing_reanalyze_view, name='drawing_reanalyze'),
  
]
