from django.contrib import admin
from .models import Student, Course, Enrollment, Teacher, Lesson, Profile,Installment

admin.site.register(Student)
admin.site.register(Course)
admin.site.register(Enrollment)
admin.site.register(Teacher)
admin.site.register(Lesson)
admin.site.register(Profile)
admin.site.register(Installment)
