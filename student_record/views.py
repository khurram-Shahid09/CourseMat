from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, F, Prefetch
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import now
from .decorator import role_required
from .forms import (
    BatchForm,
    CourseForm,
    EnrollmentFeeForm,
    EnrollmentForm,
    LessonFilterForm,
    LessonForm,
    LessonImage,
    StudentForm,
    TeacherForm,
    UserFilterForm,
    UserRoleForm,
)
from .models import (
    Batch,
    Course,
    Enrollment,
    Installment,
    Lesson,
    Profile,
    Student,
    Teacher,
)

@role_required('admin')
def admin_analytics(request):
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    course_id = request.GET.get('course')
    batch_id = request.GET.get('batch')

    students = Student.objects.all()
    courses = Course.objects.all()
    batches = Batch.objects.all()
    enrollments = Enrollment.objects.all()
    installments = Installment.objects.all()

    if course_id:
        batches = batches.filter(course_id=course_id)
        enrollments = enrollments.filter(batch__course_id=course_id)
        installments = installments.filter(enrollment__batch__course_id=course_id)

    if batch_id:
        batches = batches.filter(id=batch_id)
        enrollments = enrollments.filter(batch_id=batch_id)
        installments = installments.filter(enrollment__batch_id=batch_id)

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        enrollments = enrollments.filter(enrolled_on__gte=start_dt)
        installments = installments.filter(due_date__gte=start_dt)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        enrollments = enrollments.filter(enrolled_on__lte=end_dt)
        installments = installments.filter(due_date__lte=end_dt)

    total_students = students.count()
    active_students = students.filter(enrollments__isnull=False).distinct().count()
    total_courses = courses.count()
    active_courses = courses.filter(batches__isnull=False).distinct().count()
    total_batches = batches.count()
    ongoing_batches = batches.filter(start_date__lte=today, end_date__gte=today).count()
    total_enrollments = enrollments.count()
    enrollments_this_month = enrollments.filter(
        enrolled_on__year=today.year,
        enrolled_on__month=today.month
    ).count()

    total_fee_collected = installments.aggregate(total=Sum('paid_amount'))['total'] or 0
    total_pending_fee = installments.aggregate(total=Sum('amount'))['total'] or 0
    total_pending_fee -= total_fee_collected

    fee_collected_this_month = installments.filter(
        paid_date__year=today.year,
        paid_date__month=today.month
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    # Prepare charts
    months = []
    enrollments_data = []
    collected = []
    pending = []

    for i in range(5, -1, -1):
        month = (today.replace(day=1) - timezone.timedelta(days=i * 30))
        month_start = month.replace(day=1)
        month_end = (month_start + timezone.timedelta(days=31)).replace(day=1) - timezone.timedelta(days=1)

        # Enrollment count
        count = Enrollment.objects.filter(enrolled_on__gte=month_start, enrolled_on__lte=month_end).count()
        enrollments_data.append(count)
        months.append(month.strftime("%b %Y"))

        month_installments = Installment.objects.filter(due_date__gte=month_start, due_date__lte=month_end)
        collected.append(month_installments.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0)
        pending_amount = month_installments.aggregate(Sum('amount'))['amount__sum'] or 0
        collected_amount = month_installments.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
        pending.append((pending_amount or 0) - (collected_amount or 0))

    enrollment_chart = {
        'labels': months,
        'data': enrollments_data
    }

    fee_chart = {
        'labels': months,
        'collected': collected,
        'pending': pending
    }

    top_courses = Course.objects.annotate(num_enroll=Count('batches__enrollments')).order_by('-num_enroll')[:5]
    top_courses_chart = {
        'labels': [c.title for c in top_courses],
        'data': [c.num_enroll for c in top_courses]
    }

    students_per_course = Course.objects.annotate(students_count=Count('batches__enrollments__student', distinct=True))
    students_per_course_chart = {
        'labels': [c.title for c in students_per_course],
        'data': [c.students_count for c in students_per_course]
    }

    recent_enrollments = enrollments.order_by('-enrolled_on')[:10]

    context = {
        'total_students': total_students,
        'active_students': active_students,
        'total_courses': total_courses,
        'active_courses': active_courses,
        'total_batches': total_batches,
        'ongoing_batches': ongoing_batches,
        'total_enrollments': total_enrollments,
        'enrollments_this_month': enrollments_this_month,
        'total_fee_collected': total_fee_collected,
        'total_pending_fee': total_pending_fee,
        'fee_collected_this_month': fee_collected_this_month,
        'enrollment_chart': enrollment_chart,
        'fee_chart': fee_chart,
        'top_courses_chart': top_courses_chart,
        'students_per_course_chart': students_per_course_chart,
        'recent_enrollments': recent_enrollments,
        'courses': courses,
        'batches': batches,
    }
    return render(request, 'pages/analytics_dashboard.html', context)

@role_required('admin')
def dashboard(request):
    students_count = Student.objects.count()
    courses_count = Course.objects.count()
    batches_count = Batch.objects.count()
    enrollments_count = Enrollment.objects.count()
    teachers_count = Teacher.objects.count()

    recent_enrollments = Enrollment.objects.select_related(
        'student', 'batch', 'batch__course', 'batch__teacher'
    ).order_by('-enrolled_on')[:10]

    # Top 5 Courses by Enrollments
    top_courses = Course.objects.annotate(
        enrollments_count=Count('batches__enrollments')
    ).order_by('-enrollments_count')[:5]

    # Top 5 Teachers by Students
    top_teachers = Teacher.objects.annotate(
        students_count=Count('batches__enrollments')
    ).order_by('-students_count')[:5]

    # Enrollment Trend (last 6 months)
    last_6_months = now().date() - timedelta(days=180)
    monthly_enrollments = (
        Enrollment.objects.filter(enrolled_on__gte=last_6_months)
        .extra(select={'month': "strftime('%%Y-%%m', enrolled_on)"})
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    enrollment_labels = [m['month'] for m in monthly_enrollments]
    enrollment_data = [m['count'] for m in monthly_enrollments]

    context = {
        "students_count": students_count,
        "courses_count": courses_count,
        "batches_count": batches_count,
        "enrollments_count": enrollments_count,
        "teachers_count": teachers_count,
        "recent_enrollments": recent_enrollments,
        "top_courses": top_courses,
        "top_teachers": top_teachers,

        # Graph Data
        "top_courses_labels": [c.title for c in top_courses],
        "top_courses_data": [c.enrollments_count for c in top_courses],

        "top_teachers_labels": [t.name for t in top_teachers],
        "top_teachers_data": [t.students_count for t in top_teachers],

        "enrollment_labels": enrollment_labels,
        "enrollment_data": enrollment_data,
    }
    return render(request, 'pages/dashboard.html', context)

@login_required
def teacher_dashboard(request):
    teacher = Teacher.objects.get(email=request.user.email)
    batches = Batch.objects.filter(teacher=teacher).select_related('course')
    total_batches_count = batches.count()
    courses = Course.objects.filter(batches__teacher=teacher).distinct()
    total_courses_count = courses.count()
    students = Student.objects.filter(
        enrollments__batch__in=batches
    ).distinct()
    total_students_count = students.count()
    recent_lessons = Lesson.objects.filter(teacher=teacher).order_by('-created_at')[:5]
    total_lessons_count = Lesson.objects.filter(teacher=teacher).count()
    batch_stats = batches.annotate(
        students_count=Count('enrollments')
    ).order_by('-students_count')

    context = {
        "total_courses_count": total_courses_count,
        "total_batches_count": total_batches_count,
        "total_students_count": total_students_count,
        "total_lessons_count": total_lessons_count,
        "recent_lessons": recent_lessons,
        "my_courses": courses,
        "my_batches": batches,
        "my_students": students,
        "batch_stats": batch_stats,
    }
    return render(request, "pages/teacher_dashboard.html", context)

def student_dashboard(request):
    student = Student.objects.get(user=request.user)

    all_enrollments = Enrollment.objects.select_related(
        'batch', 'batch__course', 'batch__teacher'
    ).filter(student=student).order_by('-enrolled_on')

    completed_course_ids = all_enrollments.filter(status='completed')\
                                         .values_list('batch__course_id', flat=True)

    pending_lessons_count = Lesson.objects.filter(
        course__in=all_enrollments.values_list('batch__course', flat=True)
    ).exclude(
        students=student
    ).count()
    my_enrollments = all_enrollments[:5]

    batch_progress = []
    for enrollment in my_enrollments:
        total_lessons = Lesson.objects.filter(course=enrollment.batch.course).count()
        completed_lessons = Lesson.objects.filter(
            course=enrollment.batch.course,
            students=student
        ).count()

        batch_progress.append({
            'batch_number': enrollment.roll_number,
            'course_title': enrollment.batch.course.title,
            'status': enrollment.status.capitalize(),
            'start_date': enrollment.batch.start_date,
            'completed_lessons': completed_lessons,
            'total_lessons': total_lessons,
        })

    context = {
        'my_enrollments_count': all_enrollments.count(),
        'completed_courses_count': all_enrollments.filter(status='completed').count(),
        'pending_lessons_count': pending_lessons_count,
        'my_recent_enrollments': my_enrollments,
        'batch_progress': batch_progress,
    }

    return render(request, 'pages/student_dashboard.html', context)

def login_user(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if not remember:
                request.session.set_expiry(0)

            return redirect('home')
        else:
            return redirect('login')

    return render(request, 'pages/login.html')

def home_redirect(request):
    if request.user.is_anonymous:
        return redirect('login')

    if request.user.is_superuser:
        return redirect('admin_analytics')

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

def logout_view(request):
    logout(request)
    return redirect('login')

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
            username = email.split("@")[0]
            password = f"{username}123"
            if User.objects.filter(email=email).exists():
                return render(request, "pages/create_student.html", {"form": form})
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                Profile.objects.create(
                    user=user,
                    full_name=name,
                    role="student"
                )
                Student.objects.create(
                    user=user,
                    name=name,
                    age=age,
                    email=email,
                    phone_number=phone_number,
                    date_of_birth=date_of_birth,
                )

                credentials = {"username": username, "password": password}

                return render(request, "pages/create_student.html", {
                    "form": StudentForm(),
                    "credentials": credentials
                })
            except Exception as e:
                return render(request, "pages/create_student.html", {"form": form})
    else:
        form = StudentForm()

    return render(request, "pages/create_student.html", {"form": form})

def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            return redirect('student_list')
    else:
        form = StudentForm(instance=student)
    return render(request, 'pages/create_student.html', {'form': form})

def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        student.delete()
        return redirect('student_list')
    return render(request, 'students/student_confirm_delete.html', {'student': student})

@role_required('admin')
def user_list(request):
    form = UserFilterForm(request.GET or None)
    users = User.objects.select_related('profile').all().order_by('username')

    if form.is_valid():
        name_or_email = form.cleaned_data.get('name_or_email')
        role = form.cleaned_data.get('role')

        if name_or_email:
            users = users.filter(
                Q(username__icontains=name_or_email) |
                Q(email__icontains=name_or_email)
            )
        if role:
            users = users.filter(profile__role=role)

    return render(request, 'pages/user_list.html', {'users': users, 'form': form})

def user_update_role(request, pk):
    user = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        role = request.POST.get("role")
        if role:
            user.profile.role = role
            user.profile.save()
        return redirect("user_list")

    return render(request, "pages/user_update_role.html", {"user": user})

def user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.delete()
        return redirect('user_list')
    return render(request, 'pages/user_delete_confirm.html', {'user': user})

def basic_elements(request):
    return render(request, "content.html")


def teacher_create(request):
    credentials = None

    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            teacher = form.save(commit=False)


            if not hasattr(teacher, 'user') or not teacher.user:
                email = form.cleaned_data['email']
                name = form.cleaned_data['name']
                username = email.split('@')[0]
                password = username + "123"
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )

                Profile.objects.create(
                    user=user,
                    full_name=name,
                    role='teacher'
                )

                teacher.user = user

                credentials = {'username': username, 'password': password}

            teacher.save()
            return render(request, 'pages/create_teacher.html', {
                'form': TeacherForm(),
                'credentials': credentials
            })
    else:
        form = TeacherForm()

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
            return redirect('teacher_list')
    else:
        form = TeacherForm(instance=teacher)

    return render(request, 'pages/create_teacher.html', {'form': form, 'edit': True})

def course_create(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('course_list')
    else:
        form = CourseForm()
    return render(request, 'course/course_form.html', {'form': form})

def course_list(request):
    courses = Course.objects.all()
    return render(request, 'pages/course_list.html', {'courses': courses})

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

def add_course(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('course_list')
    else:
        form = CourseForm()
    return render(request, 'pages/add_course.html', {'form': form})

@role_required('admin')
def create_batch(request):
    if request.method == 'POST':
        form = BatchForm(request.POST)
        if form.is_valid():
            batch = form.save()
            return redirect('batch_list')
        else:
            print(form.errors)
    else:
        form = BatchForm()

    return render(request, 'pages/create_batch.html', {'form': form})

@role_required('admin')
def batch_list(request):
    batches = Batch.objects.select_related('course', 'teacher').order_by('course__title', 'number')
    context = {
        'batches': batches,
        'today': timezone.now().date(),
    }
    return render(request, 'pages/batch_list.html', context)

@role_required('admin')
def batch_edit(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    if request.method == 'POST':
        form = BatchForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            return redirect('batch_list')
    else:
        form = BatchForm(instance=batch)
    return render(request, 'pages/create_batch.html', {'form': form})

@role_required('admin')
def batch_delete(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    if request.method == 'POST':
        batch.delete()
        return redirect('batch_list')
    return render(request, 'pages/batch_list.html', {'batch': batch})

@login_required
def get_batch_students(request):
    batch_id = request.GET.get('batch_id')
    students = []
    if batch_id:
        try:
            batch = Batch.objects.get(pk=batch_id)
            students = [{'id': e.student.id, 'name': e.student.name} for e in batch.enrollments.all()]
        except Batch.DoesNotExist:
            students = []
    return JsonResponse({'students': students})

@login_required
def get_batch_teachers(request):
    batch_id = request.GET.get('batch_id')
    teachers = []
    if batch_id:
        try:
            batch = Batch.objects.get(pk=batch_id)
            teachers = [{'id': batch.teacher.id, 'name': batch.teacher.name}] if batch.teacher else []
        except Batch.DoesNotExist:
            teachers = []
    return JsonResponse({'teachers': teachers})

def add_student(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('student_list')
    else:
        form = StudentForm()

    return render(request, 'pages/create_student.html', {'form': form})

def batch_fee(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    return JsonResponse({
        'fee': batch.fee,
        'start_date': batch.start_date.isoformat(),
        'end_date': batch.end_date.isoformat()
    })

def enrollment_create(request):
    if request.method == 'POST':
        form = EnrollmentForm(request.POST, user=request.user)
        if form.is_valid():
            enrollment = form.save()
            if enrollment.fee_type == 'installment':
                enrollment.paid_amount = 0
                enrollment.save(update_fields=["paid_amount"])
                generate_installments(enrollment)

            if getattr(request.user.profile, 'role', None) == 'student':
                return redirect('student_dashboard')
            else:
                return redirect('dashboard')
        else:
            print(form.errors)
    else:
        form = EnrollmentForm(user=request.user)

    return render(request, 'pages/enrollments.html', {
        'form': form
    })

@login_required
def enrollment_list(request):
    user = request.user
    if user.is_superuser or user.profile.role == 'admin':
        enrollments = Enrollment.objects.select_related('student', 'batch__course').all()
    else:
        enrollments = (
            Enrollment.objects
            .filter(student=user.student)
            .select_related('batch__course')
        )
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

@login_required
def send_lesson(request, lesson_id=None):
    user = request.user
    teacher = getattr(user, 'teacher_profile', None)
    is_admin = user.profile.role == 'admin'
    lesson = None
    selected_students = []

    if lesson_id:
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            selected_students = list(lesson.students.values_list('id', flat=True))
        except Lesson.DoesNotExist:
            lesson = None

    if request.method == "POST":
        form = LessonForm(request.POST, request.FILES, teacher=teacher if teacher else None, user=user, instance=lesson)
        batch_id = request.POST.get('batch')

        if batch_id:
            try:
                batch = Batch.objects.get(pk=batch_id)
                form.fields['students'].queryset = Student.objects.filter(enrollments__batch=batch)
            except Batch.DoesNotExist:
                form.fields['students'].queryset = Student.objects.none()

        if form.is_valid():
            lesson_obj = form.save(commit=False)

            if teacher:
                lesson_obj.teacher = teacher
            elif is_admin:
                lesson_obj.teacher = None

            lesson_obj.save()
            form.save_m2m()

            images = request.FILES.getlist("images")
            for img in images:
                LessonImage.objects.create(lesson=lesson_obj, image=img)

            return redirect("send-lesson")

    else:
        form = LessonForm(teacher=teacher if teacher else None, user=user, instance=lesson)

        if is_admin:
            form.fields['batch'].queryset = Batch.objects.all()
            form.fields['students'].queryset = Student.objects.all()
            form.fields.pop('teacher', None)
        elif teacher:
            form.fields['batch'].queryset = Batch.objects.filter(teacher=teacher)

    return render(request, "pages/send_lesson.html", {
        "form": form,
        "is_admin": is_admin,
        "lesson": lesson,
        "selected_students": selected_students
    })

@login_required
def lesson_list(request):
    form = LessonFilterForm(request.GET or None)

    if request.user.profile.role == 'student':
        student = Student.objects.get(user=request.user)
        enrolled_batches = Batch.objects.filter(enrollments__student=student)
        form.fields['batch'].queryset = enrolled_batches
        form.fields['student'].initial = student.id

        lessons = Lesson.objects.filter(batch__in=enrolled_batches).filter(
            Q(students=student) | Q(students__isnull=True)
        ).distinct().order_by('-created_at')

    elif request.user.profile.role == 'teacher':
        teacher = Teacher.objects.get(user=request.user)
        batches_taught = Batch.objects.filter(teacher=teacher)
        form.fields['batch'].queryset = batches_taught
        enrolled_students = Student.objects.filter(enrollments__batch__in=batches_taught).distinct()
        form.fields['student'].queryset = enrolled_students
        lessons = Lesson.objects.filter(batch__in=batches_taught).order_by('-created_at')

    else:  # Admin
        form.fields['batch'].queryset = Batch.objects.all()
        form.fields['student'].queryset = Student.objects.all()
        lessons = Lesson.objects.all().order_by('-created_at')

    if form.is_valid():
        batch = form.cleaned_data.get('batch')
        student = form.cleaned_data.get('student')
        if batch:
            lessons = lessons.filter(batch=batch)
        if student:
            lessons = lessons.filter(Q(students=student) | Q(students__isnull=True)).distinct()

    return render(request, 'pages/lessons.html', {'form': form, 'lessons': lessons})

def is_teacher_or_admin(user):
    return user.is_superuser or user.profile.role in ['teacher', 'admin']

@login_required
@user_passes_test(is_teacher_or_admin)
# views.py
def lesson_update(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)

    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, instance=lesson, user=request.user)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.save()
            students_ids = request.POST.getlist('students')
            lesson.students.set(students_ids)
            return redirect('lesson_list')
    else:
        form = LessonForm(instance=lesson, user=request.user)
    selected_students = lesson.students.values_list('id', flat=True)
    form.fields['students'].initial = selected_students

    return render(request, 'pages/send_lesson.html', {
        'form': form,
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

@role_required('admin')
def fee_management(request):
    enrollments = Enrollment.objects.select_related('student', 'batch', 'batch__course') \
        .prefetch_related('installments')

    search = request.GET.get('search')
    course_id = request.GET.get('course')
    batch_id = request.GET.get('batch')
    fee_type = request.GET.get('fee_type')
    status = request.GET.get('status')

    if search:
        enrollments = enrollments.filter(
            Q(student__name__icontains=search) |
            Q(student__email__icontains=search)
        )
    if course_id:
        enrollments = enrollments.filter(batch__course__id=course_id)
    if batch_id:
        enrollments = enrollments.filter(batch__id=batch_id)
    if fee_type:
        enrollments = enrollments.filter(fee_type=fee_type)

    enrollments = list(enrollments)

    for e in enrollments:
        if e.fee_type == 'installment':
            e.total_fee = sum(inst.amount for inst in e.installments.all())
            e.paid_amount_display = sum(inst.paid_amount for inst in e.installments.all())
            e.pending_amount_display = e.total_fee - e.paid_amount_display
        else:
            e.total_fee = e.fee_at_enrollment
            e.paid_amount_display = e.paid_amount
            e.pending_amount_display = e.pending_amount

    if status == "paid":
        enrollments = [e for e in enrollments if e.pending_amount_display == 0]
    elif status == "partial":
        enrollments = [e for e in enrollments if 0 < e.paid_amount_display < e.total_fee]
    elif status == "pending":
        enrollments = [e for e in enrollments if e.paid_amount_display == 0]

    if request.method == 'POST':
        enrollment_id = request.POST.get('enrollment_id')
        enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
        form = EnrollmentFeeForm(request.POST, instance=enrollment)
        if form.is_valid():
            enrollment = form.save()
            if enrollment.fee_type == 'installment':
                generate_installments(enrollment)
            return redirect('fee_management')

    courses = Course.objects.all()
    batches = Batch.objects.all()

    context = {
        'enrollments': enrollments,
        'courses': courses,
        'batches': batches,
    }
    return render(request, 'pages/fee_management.html', context)

def generate_installments(enrollment):
    enrollment.installments.all().delete()
    batch = enrollment.batch
    start_date = batch.start_date
    end_date = batch.end_date
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1

    if months <= 1:
        enrollment.installments.create(
            due_date=start_date,
            amount=enrollment.fee_at_enrollment,
            paid_amount=0,
            status='pending'
        )
    else:
        installment_amount = enrollment.fee_at_enrollment
        remainder = enrollment.fee_at_enrollment % months

        for i in range(months):
            installment_date = start_date + relativedelta(months=i)
            amount = installment_amount + (remainder if i == months - 1 else 0)

            enrollment.installments.create(
                due_date=installment_date,
                amount=amount,
                paid_amount=0,
                status='pending'
            )

@role_required('admin')
def installments_list(request):
    enrollments = Enrollment.objects.select_related('student', 'batch', 'batch__course') \
        .prefetch_related(
        Prefetch('installments', queryset=Installment.objects.order_by('due_date'))
    )

    search = request.GET.get('search')
    course_id = request.GET.get('course')
    batch_id = request.GET.get('batch')
    fee_type = request.GET.get('fee_type')
    status = request.GET.get('status')

    if search:
        enrollments = enrollments.filter(
            Q(student__name__icontains=search) |
            Q(student__email__icontains=search)
        )

    if course_id:
        enrollments = enrollments.filter(batch__course__id=course_id)

    if batch_id:
        enrollments = enrollments.filter(batch__id=batch_id)

    if fee_type:
        enrollments = enrollments.filter(fee_type=fee_type)

    enrollments = [e for e in enrollments if e.installments.exists()]

    if status:
        filtered_enrollments = []
        for e in enrollments:
            total_installments = sum(inst.amount for inst in e.installments.all())
            paid_installments = sum(inst.paid_amount for inst in e.installments.all())

            if status == 'paid' and paid_installments >= total_installments:
                filtered_enrollments.append(e)
            elif status == 'pending' and paid_installments == 0:
                filtered_enrollments.append(e)
            elif status == 'partial' and 0 < paid_installments < total_installments:
                filtered_enrollments.append(e)
        enrollments = filtered_enrollments

    courses = Course.objects.all()
    batches = Batch.objects.all()

    context = {
        'enrollments': enrollments,
        'courses': courses,
        'batches': batches,
        'request': request,
    }

    return render(request, 'pages/installments_list.html', context)

def mark_installment_paid(request, installment_id):
    installment = get_object_or_404(Installment, id=installment_id)
    if request.method == 'POST':
        installment.status = 'paid'
        installment.paid_amount = installment.amount
        installment.paid_date = timezone.now().date()
        installment.save()
    return redirect('installments_list')