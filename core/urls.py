from django.urls import path
from . import views
app_name = 'core'

urlpatterns = [
    path('register/', views.register_parent_view, name='register'),
    path('login/', views.login_view, name='login'),
]
