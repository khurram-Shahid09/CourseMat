from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    RegisterAPIView,
    LoginAPIView,
    CourseViewSet,
    EnrollmentViewSet,
    StudentViewSet,
    BatchViewSet,
    TeacherViewSet,
    LessonViewSet,
    ProfileViewSet,
    InstallmentViewSet
)

router = DefaultRouter()
router.register("students", StudentViewSet, basename="student")
router.register("courses", CourseViewSet, basename="course")
router.register("batches", BatchViewSet, basename="batch")
router.register("enrollments", EnrollmentViewSet, basename="enrollment")
router.register("teachers", TeacherViewSet, basename="teacher")
router.register("lessons", LessonViewSet, basename="lesson")
router.register("profiles", ProfileViewSet, basename="profile")
router.register("installments", InstallmentViewSet, basename="installment")

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("v1/", include(router.urls)),
]
