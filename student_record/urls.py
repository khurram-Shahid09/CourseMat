from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('analytics/', views.admin_analytics, name='admin_analytics'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('teacher-dashboard/', views.teacher_dashboard, name='teacher_dashboard'),

    path('login/', views.login_user, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),

    path('student_list', views.student_list, name='student_list'),
    path('new/', views.student_create, name='student_create'),
    path('edit/<int:pk>/', views.student_edit, name='student_edit'),
    path('students/delete/<int:pk>/', views.student_delete, name='student_delete'),
    path('fee_management/', views.fee_management, name='fee_management'),

    path('user_list/', views.user_list, name='user_list'),
    path('updateRole/<int:pk>/', views.user_update_role, name='user_update_role'),
    path('deleteUser/<int:pk>/', views.user_delete, name='user_delete'),

    path("add_teacher/", views.teacher_create, name="teacher_create"),
    path('teacherlist', views.teacher_list, name='teacher_list'),
    path('edit-teacher/<int:pk>/', views.teacher_edit, name='teacher_edit'),
    path("teacher/delete/<int:pk>/", views.teacher_delete, name="teacher_delete"),

    path("send-lesson/", views.send_lesson, name="send-lesson"),
    path('lessons/', views.lesson_list, name='lesson_list'),
    path('lesson/<int:pk>/update/', views.lesson_update, name='lesson_update'),
    path('lesson/<int:pk>/delete/', views.lesson_delete, name='lesson_delete'),

    path('batches/create/', views.create_batch, name='create_batch'),
    path('batches/', views.batch_list, name='batch_list'),
    path('batches/edit/<int:batch_id>/', views.batch_edit, name='batch_edit'),
    path('batches/delete/<int:batch_id>/', views.batch_delete, name='batch_delete'),

    path('ajax/get-batch-students/', views.get_batch_students, name='get_batch_students'),
    path('ajax/get-batch-teachers/', views.get_batch_teachers, name='get_batch_teachers'),

    path('courses/', views.course_list, name='course_list'),
    path('courses/new/', views.course_create, name='course_create'),
    path('courses/edit/<int:course_id>/', views.edit_course, name='edit_course'),
    path('courses/delete/<int:course_id>/', views.delete_course, name='delete_course'),
    path('add_course/', views.add_course, name='add_course'),
    path('course-fee/<int:batch_id>/', views.batch_fee, name='batch_fee'),

    path('enrollments/', views.enrollment_list, name='enrollments'),
    path('enrollments/new/', views.enrollment_create, name='enrollment_create'),
    path('enrollment/<int:enrollment_id>/edit/', views.enrollment_edit, name='enrollment_edit'),
    path('enrollment/<int:enrollment_id>/delete/', views.enrollment_delete, name='enrollment_delete'),

    path('installments/', views.installments_list, name='installments_list'),
    path('installments/paid/<int:installment_id>/', views.mark_installment_paid, name='mark_installment_paid'),

    path('forms/', views.student_create, name='basic_elements'),
]
