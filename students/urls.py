from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('signup/', views.signup, name='signup'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('student/<str:student_id>/', views.student_detail, name='student_detail'),
    path('student/<str:student_id>/edit/', views.student_update, name='student_update'),
    path('student/<str:student_id>/delete/', views.student_delete, name='student_delete'),
    path('students/', views.student_list, name='student_list'),
    path('manage-students/', views.manage_students, name='manage_students'),
    path('courses/', views.courses, name='courses'),
    path('manage-courses/', views.manage_courses, name='manage_courses'),
    path('student-report/', views.student_report, name='student_report'),
    path('profile/', views.profile, name='profile'),
]