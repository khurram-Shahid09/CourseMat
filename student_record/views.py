from django import forms
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Count, Prefetch
from .decorator import role_required
from .models import Course, Enrollment, Student, Teacher, Lesson, Profile, Batch, Installment
from .forms import StudentForm, CourseForm, EnrollmentForm, TeacherForm, LessonForm, LessonFilterForm, LessonImage, \
    BatchForm, UserRoleForm, UserFilterForm, EnrollmentFeeForm
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import render
from django.db.models import Q
from .models import Lesson, Course, Student
from .forms import LessonFilterForm
from django.contrib.auth.decorators import login_required,user_passes_test
from django.db.models import Count
from django.shortcuts import render
from django.utils.timezone import now
from datetime import timedelta
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from datetime import date
from django.shortcuts import render
from django.db.models import Count, Sum, F
from django.utils import timezone

from django.shortcuts import render
from django.utils import timezone
from datetime import datetime
from django.db.models import Count, Sum
from .models import Student, Course, Batch, Enrollment, Installment


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

    # ✅ Fee from installments instead of enrollments
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

        # ✅ Fee from installments
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
           # messages.success(request, f"Role updated to {role} for {user.username}")
        return redirect("user_list")  # adjust to your users list page name

    return render(request, "pages/user_update_role.html", {"user": user})

def user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.delete()
       # messages.success(request, f"{user.username} deleted successfully")
        return redirect('user_list')
    return render(request, 'pages/user_delete_confirm.html', {'user': user})


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


def fee_management(request):
    enrollments = Enrollment.objects.select_related('student', 'batch', 'batch__course') \
        .prefetch_related('installments')

    # ----- Apply filters -----
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

    # Compute total_fee, paid_amount, pending_amount for each enrollment
    for e in enrollments:
        if e.fee_type == 'installment':
            e.total_fee = sum(inst.amount for inst in e.installments.all())
            e.paid_amount_display = sum(inst.paid_amount for inst in e.installments.all())
            e.pending_amount_display = e.total_fee - e.paid_amount_display
        else:
            e.total_fee = e.fee_at_enrollment
            e.paid_amount_display = e.paid_amount
            e.pending_amount_display = e.pending_amount

    # ----- Filter by payment status -----
    if status == "paid":
        enrollments = [e for e in enrollments if e.pending_amount_display == 0]
    elif status == "partial":
        enrollments = [e for e in enrollments if 0 < e.paid_amount_display < e.total_fee]
    elif status == "pending":
        enrollments = [e for e in enrollments if e.paid_amount_display == 0]

    # ----- Handle POST update -----
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
    # Delete old installments if any
    enrollment.installments.all().delete()

    batch = enrollment.batch
    start_date = batch.start_date
    end_date = batch.end_date

    # Calculate number of months between start and end
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1

    if months <= 1:
        # Only one installment if duration <= 1 month
        enrollment.installments.create(
            due_date=start_date,
            amount=enrollment.fee_at_enrollment,
            paid_amount=0,
            status='pending'
        )
    else:
        installment_amount = enrollment.fee_at_enrollment // months
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


from django.db.models import Q, Prefetch, F
from django.shortcuts import render
from .models import Enrollment, Installment, Course, Batch

def installments_list(request):
    # Fetch enrollments with related student, batch, course, and installments
    enrollments = Enrollment.objects.select_related('student', 'batch', 'batch__course') \
        .prefetch_related(
            Prefetch('installments', queryset=Installment.objects.order_by('due_date'))
        )

    # ----- Apply filters -----
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

    # Only include enrollments that have at least 1 installment
    enrollments = [e for e in enrollments if e.installments.exists()]

    # Filter by installment payment status
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

    # Pass all courses and batches for filter dropdowns
    courses = Course.objects.all()
    batches = Batch.objects.all()

    context = {
        'enrollments': enrollments,
        'courses': courses,
        'batches': batches,
        'request': request,  # so template can keep filter values
    }

    return render(request, 'pages/installments_list.html', context)




def mark_installment_paid(request, installment_id):
    installment = get_object_or_404(Installment, id=installment_id)
    if request.method == 'POST':
        installment.status = 'paid'
        installment.paid_amount = installment.amount
        installment.paid_date = timezone.now().date()
        installment.save()
        #messages.success(request, f'Installment for {installment.enrollment.student.name} marked as paid.')
    return redirect('installments_list')

def enrollment_create(request):
    if request.method == 'POST':
        form = EnrollmentForm(request.POST, user=request.user)
        if form.is_valid():
            enrollment = form.save()

            if enrollment.fee_type == 'installment':
                # For installment-based enrollment → reset paid_amount at enrollment level
                enrollment.paid_amount = 0
                enrollment.save(update_fields=["paid_amount"])

                # Generate installments
                generate_installments(enrollment)

            # Redirect based on role
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
            # Save students from POST
            students_ids = request.POST.getlist('students')
            lesson.students.set(students_ids)
            return redirect('lesson_list')
    else:
        form = LessonForm(instance=lesson, user=request.user)

    # Preselect students for the form
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


@login_required
def teacher_dashboard(request):
    teacher = Teacher.objects.get(email=request.user.email)

    # Batches taught by this teacher
    batches = Batch.objects.filter(teacher=teacher).select_related('course')
    total_batches_count = batches.count()

    # Courses this teacher is teaching (via batches)
    courses = Course.objects.filter(batches__teacher=teacher).distinct()
    total_courses_count = courses.count()

    # Unique students across teacher's batches
    students = Student.objects.filter(
        enrollments__batch__in=batches
    ).distinct()
    total_students_count = students.count()

    # Lessons created by this teacher
    recent_lessons = Lesson.objects.filter(teacher=teacher).order_by('-created_at')[:5]
    total_lessons_count = Lesson.objects.filter(teacher=teacher).count()

    # Enrollment stats per batch (for chart/table)
    batch_stats = batches.annotate(
        students_count=Count('enrollments')
    ).order_by('-students_count')

    context = {
        "total_courses_count": total_courses_count,
        "total_batches_count": total_batches_count,
        "total_students_count": total_students_count,
        "total_lessons_count": total_lessons_count,
        "recent_lessons": recent_lessons,
        "my_courses": courses,         # Courses taught by this teacher
        "my_batches": batches,         # Batches taught by this teacher
        "my_students": students,       # Unique students enrolled in their batches
        "batch_stats": batch_stats,    # For showing chart or table
    }
    return render(request, "pages/teacher_dashboard.html", context)




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



@role_required('admin')
def create_batch(request):
    if request.method == 'POST':
        form = BatchForm(request.POST)
        if form.is_valid():
            batch = form.save()
            return redirect('batch_list')
        else:
            print(form.errors)  # <--- print actual errors to debug
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
            #messages.success(request, "Batch updated successfully!")
            return redirect('batch_list')
    else:
        form = BatchForm(instance=batch)
    return render(request, 'pages/create_batch.html', {'form': form})

@role_required('admin')
def batch_delete(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    if request.method == 'POST':
        batch.delete()
        #messages.success(request, "Batch deleted successfully!")
        return redirect('batch_list')
    return render(request, 'pages/batch_list.html', {'batch': batch})

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


def batch_fee(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    return JsonResponse({
        'fee': batch.fee,
        'start_date': batch.start_date.isoformat(),  # e.g., '2025-08-25'
        'end_date': batch.end_date.isoformat()
    })


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
def student_dashboard(request):
    student = Student.objects.get(user=request.user)

    all_enrollments = Enrollment.objects.select_related(
        'batch', 'batch__course', 'batch__teacher'
    ).filter(student=student).order_by('-enrolled_on')

    completed_course_ids = all_enrollments.filter(status='completed')\
                                         .values_list('batch__course_id', flat=True)

    # Pending lessons are lessons in enrolled courses not yet completed by the student
    pending_lessons_count = Lesson.objects.filter(
        course__in=all_enrollments.values_list('batch__course', flat=True)
    ).exclude(
        students=student
    ).count()

    # Limit recent enrollments to last 5
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