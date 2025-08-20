from django import forms
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Count
from .decorator import role_required
from .models import Course, Enrollment, Student, Teacher, Lesson, Profile
from .forms import StudentForm, CourseForm, EnrollmentForm, TeacherForm, LessonForm, LessonFilterForm, LessonImage
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import render
from django.db.models import Q
from .models import Lesson, Course, Student
from .forms import LessonFilterForm
from django.contrib.auth.decorators import login_required,user_passes_test

@role_required('admin')
def dashboard(request):
    students_count = Student.objects.count()
    courses_count = Course.objects.count()
    enrollments_count = Enrollment.objects.count()
    teachers_count = Teacher.objects.count()

    recent_enrollments = Enrollment.objects.select_related('student', 'course').order_by('-enrolled_on')[:10]

    top_courses = Course.objects.annotate(
        enrollments_count=Count('enrollments')
    ).order_by('-enrollments_count')[:5]

    top_teachers = Teacher.objects.annotate(
        courses_count=Count('courses')
    ).order_by('-courses_count')[:5]

    context = {
        "students_count": students_count,
        "courses_count": courses_count,
        "enrollments_count": enrollments_count,
        "teachers_count": teachers_count,
        "recent_enrollments": recent_enrollments,
        "top_courses": top_courses,
        "top_teachers": top_teachers,
    }
    return render(request, 'pages/dashboard.html', context)


def index(request):
    return render(request, 'student_record/index.html')

def basic_elements(request):
    return render(request, "content.html")

def student_list(request):
    students = Student.objects.all()
    return render(request, 'pages/student_list.html', {'students': students})


def student_create(request):
    credentials = None

    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            email = form.cleaned_data["email"]
            age = form.cleaned_data["age"]
            phone_number = form.cleaned_data["phone_number"]
            date_of_birth = form.cleaned_data["date_of_birth"]

            # Create username from email
            username = email.split("@")[0]
            password = f"{username}123"   # auto-generated

            if User.objects.filter(email=email).exists():
                #messages.error(request, "A user with this email already exists.")
                return render(request, "pages/create_student.html", {"form": form})

            try:
                # Create User
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )

                # Create Profile with role 'student'
                Profile.objects.create(
                    user=user,
                    full_name=name,
                    role="student"
                )

                # Create Student record
                Student.objects.create(
                    user=user,
                    name=name,
                    age=age,
                    email=email,
                    phone_number=phone_number,
                    date_of_birth=date_of_birth,
                )

                credentials = {"username": username, "password": password}
               # messages.success(request, "Student created successfully!")

                return render(request, "pages/create_student.html", {
                    "form": StudentForm(),
                    "credentials": credentials
                })
            except Exception as e:
                #messages.error(request, f"Error creating student: {e}")
                return render(request, "pages/create_student.html", {"form": form})
    else:
        form = StudentForm()

    return render(request, "pages/create_student.html", {"form": form})

def teacher_create(request):
    credentials = None

    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            teacher = form.save(commit=False)

            # If no user exists, create one
            if not hasattr(teacher, 'user') or not teacher.user:
                email = form.cleaned_data['email']
                name = form.cleaned_data['name']

                # generate username from email
                username = email.split('@')[0]

                # generate default password
                password = username + "123"

                # create user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )

                # create profile with role 'teacher'
                Profile.objects.create(
                    user=user,
                    full_name=name,
                    role='teacher'
                )

                # link teacher with user
                teacher.user = user

                credentials = {'username': username, 'password': password}

            teacher.save()
            #messages.success(request, "Teacher created successfully!")
            return render(request, 'pages/create_teacher.html', {
                'form': TeacherForm(),
                'credentials': credentials
            })
    else:
        form = TeacherForm()

    return render(request, 'pages/create_teacher.html', {'form': form}) # should be TeacherForm, not StudentForm

    return render(request, 'pages/create_teacher.html', {'form': form})
def teacher_delete(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        teacher.delete()
        messages.success(request, f'Teacher "{teacher.name}" has been deleted successfully.')
        return redirect('teacher_list')
    else:
        messages.error(request, 'Invalid request method.')
        return redirect('teacher_list')
def teacher_list(request):
    teachers = Teacher.objects.all()
    return render(request, 'pages/teacher_list.html', {'teachers': teachers})
def teacher_edit(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)

    if request.method == 'POST':
        form = TeacherForm(request.POST, instance=teacher)
        if form.is_valid():
            form.save()
            return redirect('teacher_list')  # redirect to teacher list after save
    else:
        form = TeacherForm(instance=teacher)  # important to prefill values

    return render(request, 'pages/create_teacher.html', {'form': form, 'edit': True})

def course_list(request):
    courses = Course.objects.all()
    return render(request, 'pages/course_list.html', {'courses': courses})

def course_create(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('course_list')
    else:
        form = CourseForm()
    return render(request, 'course/course_form.html', {'form': form})

@login_required
def edit_course(request, course_id):
    if not (request.user.is_superuser or request.user.profile.role == 'admin'):
        return HttpResponseForbidden("You are not allowed to edit courses")
    
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            return redirect('course_list')
    else:
        form = CourseForm(instance=course)
    
    return render(request, 'pages/add_course.html', {'form': form, 'title': 'Edit Course'})

@login_required
def delete_course(request, course_id):
    if not (request.user.is_superuser or request.user.profile.role == 'admin'):
        return HttpResponseForbidden("You are not allowed to delete courses")
    
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        course.delete()
        return redirect('course_list')
    
    return render(request, 'pages/course_list.html', {'course': course})

def enrollment_create(request):
    if request.method == 'POST':
        form = EnrollmentForm(request.POST)
        
        if form.is_valid():
            form.save()
            if request.user.profile.role == 'student':
                return redirect('student_dashboard')
            else:
                return redirect('dashboard')
    else:
        form = EnrollmentForm()
    return render(request, 'pages/enrollments.html', {'form': form})

@login_required
def enrollment_list(request):
    user = request.user
    if user.is_superuser or user.profile.role == 'admin':
        enrollments = Enrollment.objects.select_related('student', 'course').all()
    else:
        enrollments = Enrollment.objects.filter(student=user.student).select_related('course')
    return render(request, 'pages/enrollment_list.html', {'enrollments': enrollments})

@login_required
def enrollment_edit(request, enrollment_id):
    if not (request.user.is_superuser or request.user.profile.role == 'admin'):
        return HttpResponseForbidden("You are not allowed to edit enrollments")

    enrollment = get_object_or_404(Enrollment, id=enrollment_id)

    if request.method == "POST":
        form = EnrollmentForm(request.POST, instance=enrollment)
        if form.is_valid():
            form.save()
            return redirect('enrollments')
    else:
        form = EnrollmentForm(instance=enrollment)

    return render(request, 'pages/enrollments.html', {'form': form, 'enrollment': enrollment})


@login_required
def enrollment_delete(request, enrollment_id):
    if not (request.user.is_superuser or request.user.profile.role == 'admin'):
        return HttpResponseForbidden("You are not allowed to delete enrollments")

    enrollment = get_object_or_404(Enrollment, id=enrollment_id)

    if request.method == "POST":
        enrollment.delete()
        return redirect('enrollments')

    # Optional: show confirmation page (can also skip if using JS confirm)
    return render(request, 'pages/enrollments.html', {'enrollment': enrollment})



def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            #messages.success(request, "Student updated successfully.")
            return redirect('student_list')
    else:
        form = StudentForm(instance=student)
    return render(request, 'pages/create_student.html', {'form': form})
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        student.delete()
       # messages.success(request, "Student deleted successfully.")
        return redirect('student_list')
    return render(request, 'students/student_confirm_delete.html', {'student': student})

@login_required
def send_lesson(request):
    user = request.user
    teacher = getattr(user, 'teacher_profile', None)
    is_admin = user.profile.role == 'admin'

    if request.method == "POST":
        form = LessonForm(request.POST, teacher=teacher if teacher else None)

        course_id = request.POST.get('course')
        if course_id:
            form.fields['students'].queryset = Student.objects.filter(enrollments__course_id=course_id)

        if form.is_valid():
            lesson = form.save(commit=False)

            if teacher:
                lesson.teacher = teacher  # Assign teacher
            elif is_admin:
                lesson.teacher = None  # Admin sent
            lesson.save()
            form.save_m2m()

            # Handle multiple images
            images = request.FILES.getlist("images")
            for img in images:
                LessonImage.objects.create(lesson=lesson, image=img)

            return redirect("send-lesson")
    else:
        form = LessonForm(teacher=teacher if teacher else None)

        if is_admin:
            form.fields['course'].queryset = Course.objects.all()
            form.fields['students'].queryset = Student.objects.all()
            form.fields.pop('teacher', None)  # Remove teacher field for admin

        elif teacher:
            form.fields['course'].queryset = teacher.courses.all()

    return render(request, "pages/send_lesson.html", {"form": form, "is_admin": is_admin})


@login_required
def lesson_list(request):
    form = LessonFilterForm(request.GET or None)

    if request.user.profile.role == 'student':
        student = Student.objects.get(user=request.user)
        enrolled_courses = Enrollment.objects.filter(student=student).values_list('course', flat=True)

        # Limit courses dropdown only to student’s enrolled courses
        form.fields['course'].queryset = Course.objects.filter(id__in=enrolled_courses)

        # Hide student field completely (we already know who they are)
        form.fields['student'].widget = forms.HiddenInput()
        form.fields['student'].initial = student.id

        lessons = Lesson.objects.filter(
            Q(course__in=enrolled_courses),
            Q(students=student) | Q(students__isnull=True)   # lessons for this student OR for all
        ).distinct().order_by('-created_at')

        # Apply extra filter only for course (student is fixed)
        if form.is_valid():
            course = form.cleaned_data.get('course')
            if course:
                lessons = lessons.filter(course=course)

    elif request.user.profile.role == 'teacher':
        teacher = Teacher.objects.get(user=request.user)
        courses_taught = teacher.courses.all()

        form.fields['course'].queryset = courses_taught
        enrolled_students = Student.objects.filter(
            enrollments__course__in=courses_taught
        ).distinct()
        form.fields['student'].queryset = enrolled_students

        lessons = Lesson.objects.filter(course__in=courses_taught).order_by('-created_at')

        if form.is_valid():
            course = form.cleaned_data.get('course')
            student = form.cleaned_data.get('student')
            if course:
                lessons = lessons.filter(course=course)
            if student:
                lessons = lessons.filter(Q(students=student) | Q(students__isnull=True)).distinct()

    else:  # Admin
        lessons = Lesson.objects.all().order_by('-created_at')
        if form.is_valid():
            course = form.cleaned_data.get('course')
            student = form.cleaned_data.get('student')
            if course:
                lessons = lessons.filter(course=course)
            if student:
                lessons = lessons.filter(Q(students=student) | Q(students__isnull=True)).distinct()

    context = {
        'form': form,
        'lessons': lessons
    }
    return render(request, 'pages/lessons.html', context)


def is_teacher_or_admin(user):
    return user.is_superuser or user.profile.role in ['teacher', 'admin']

@login_required
@user_passes_test(is_teacher_or_admin)
# views.py
def lesson_update(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)

    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, instance=lesson)
        if form.is_valid():
            lesson = form.save()
            # Save students
            students_ids = request.POST.getlist('students')
            lesson.students.set(students_ids)
            return redirect('lesson_list')
    else:
        form = LessonForm(instance=lesson)

    # Pass existing students
    selected_students = lesson.students.values_list('id', flat=True)
    return render(request, 'pages/send_lesson.html', {
        'form': form,
        'selected_students': list(selected_students),
        'lesson': lesson
    })


@login_required
@user_passes_test(is_teacher_or_admin)
def lesson_delete(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    if request.method == 'POST':
        lesson.delete()
        return redirect('lesson_list')
    return render(request, 'pages/lessons.html', {'lesson': lesson})


@login_required
def teacher_dashboard(request):
    teacher = Teacher.objects.get(email=request.user.email)
    courses = teacher.courses.all()
    total_courses_count = courses.count()

    # Count unique students across teacher's courses
    students = Student.objects.filter(
        enrollments__course__in=courses
    ).distinct()
    total_students_count = students.count()

    # Lessons by teacher
    recent_lessons = Lesson.objects.filter(teacher=teacher).order_by('-created_at')[:5]
    total_lessons_count = Lesson.objects.filter(teacher=teacher).count()

    context = {
        'total_courses_count': total_courses_count,
        'total_students_count': total_students_count,
        'total_lessons_count': total_lessons_count,
        'recent_lessons': recent_lessons,
        'my_courses': courses,       # Courses taught by this teacher
        'my_students': students,     # Students enrolled in their courses
    }
    print(students)
    return render(request, 'pages/teacher_dashboard.html', context)



def get_course_students(request):
    course_id = request.GET.get('course_id')
    students = []
    if course_id:
        enrollments = Enrollment.objects.filter(course_id=course_id)
        students = [{'id': e.student.id, 'name': e.student.name} for e in enrollments]
    return JsonResponse({'students': students})

def get_course_teachers(request):
    course_id = request.GET.get('course_id')
    teachers = []
    if course_id:
        teachers = Teacher.objects.filter(courses__id=course_id).values('id', 'name')
    return JsonResponse({'teachers': list(teachers)})



def buttons(request):
    return render(request, 'buttons.html')

def dropdowns(request):
    return render(request, 'dropdowns.html')

def typography(request):
    return render(request, 'typography.html')

def add_course(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('course_list')
    else:
        form = CourseForm()
    return render(request, 'pages/add_course.html', {'form': form})

def add_student(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('student_list')
    else:
        form = StudentForm()  

    return render(request, 'pages/create_student.html', {'form': form})
def course_fee(request, course_id):
    try:
        course = Course.objects.get(pk=course_id)
        return JsonResponse({'fees': course.fees})
    except Course.DoesNotExist:
        return JsonResponse({'fees': None})

def charts(request):
    return render(request, 'charts.html')

def tables(request):
    return render(request, 'tables.html')

def blank_page(request):
    return render(request, 'blank_page.html')

def login_user(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # If "Remember me" is NOT checked, session expires on browser close
            if not remember:
                request.session.set_expiry(0)

           # messages.success(request, f"Welcome back, {user.username}!")
            return redirect('home')
        #redirect('dashboard')  # replace 'index' with your home/dashboard url
        else:
            #messages.error(request, "Invalid username or password.")
            return redirect('login')

    return render(request, 'pages/login.html')
 
from django.shortcuts import redirect

def home_redirect(request):
    if request.user.is_anonymous:
        return redirect('login')

    if request.user.is_superuser:
        return redirect('dashboard')

    role = getattr(request.user.profile, 'role', None)
    if role == 'student':
        return redirect('student_dashboard')
    elif role == 'teacher':
        return redirect('teacher_dashboard')
    else:
        return redirect('login')


def register(request):
    credentials = None

    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        age = request.POST.get("age")
        phone_number = request.POST.get("phone_number")
        date_of_birth = request.POST.get("date_of_birth")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 != password2:
            return redirect('register')

        if User.objects.filter(email=email).exists():
            return redirect('register')

        # Create username from email
        username = email.split('@')[0]

        # Create User
        user = User.objects.create_user(username=username, email=email, password=password1)

        # Create Profile with role='student'
        Profile.objects.create(
            user=user,
            full_name=name,
            role='student'
        )

        # Optionally create Student record if you keep Student model
        Student.objects.create(
            user=user,
            name=name,
            age=age,
            email=email,
            phone_number=phone_number,
            date_of_birth=date_of_birth,
        )

        credentials = {'username': username, 'password': password1}

    return render(request, 'pages/register.html', {
        'credentials': credentials
    })
def student_dashboard(request):
    profile = request.user.profile
    student = Student.objects.get(user=request.user)

    all_enrollments = Enrollment.objects.filter(student=student).order_by('-enrolled_on')

    completed_course_ids = all_enrollments.filter(status='completed').values_list('course_id', flat=True)

    pending_lessons_count = Lesson.objects.filter(
    course__enrollments__student=student
     ).exclude(
      course_id__in=completed_course_ids
     ).count()

# Take recent 5 for display
    my_enrollments = all_enrollments[:5]

    context = {
    'my_enrollments_count': all_enrollments.count(),
    'completed_courses_count': all_enrollments.filter(status='completed').count(),
    'pending_lessons_count': pending_lessons_count,
    'my_recent_enrollments': my_enrollments,
            }

    return render(request, 'pages/student_dashboard.html', context)



def error_404(request):
    return render(request, 'error_404.html')

def error_500(request):
    return render(request, 'error_500.html')

def settings(request):
    return render(request, 'settings.html')

def tour(request):
    return render(request, 'tour.html')

def logout_view(request):
    logout(request)
    #messages.success(request, "You have been logged out successfully.")
    return redirect('login')

def search(request):
    return render(request, 'search.html')

def report_pdf(request):
    return render(request, 'report_pdf.html')

def report_excel(request):
    return render(request, 'report_excel.html')

def report_doc(request):
    return render(request, 'report_doc.html')

def view_project(request):
    return render(request, 'view_project.html')

def edit_project(request):
    return render(request, 'edit_project.html')

def language_ar(request):
    return render(request, 'language_ar.html')

def language_en(request):
    return render(request, 'language_en.html')

def inbox(request):
    return render(request, 'inbox.html')

def profile(request):
    return render(request, 'profile.html')

def lock_account(request):
    return render(request, 'lock_account.html')

def messages(request):
    return render(request, 'messages.html')

def message_detail(request):
    return render(request, 'message_detail.html')

def notifications(request):
    return render(request, 'notifications.html')

def notification_detail(request):
    return render(request, 'notification_detail.html')