from django_filters import rest_framework as filters
from student_record.models import Enrollment, Profile, Installment
from django.db.models import F

class EnrollmentFilter(filters.FilterSet):
    student_name = filters.CharFilter(field_name="student__name", lookup_expr="icontains")
    batch_code = filters.CharFilter(field_name="batch__batch_code", lookup_expr="icontains")
    course_title = filters.CharFilter(field_name="batch__course__title", lookup_expr="icontains")
    roll_number = filters.CharFilter(field_name="roll_number", lookup_expr="icontains")
    status = filters.CharFilter(field_name="status", lookup_expr="exact")
    fee_type = filters.CharFilter(field_name="fee_type", lookup_expr="exact")
    is_fully_paid = filters.BooleanFilter(method='filter_is_fully_paid')

    class Meta:
        model = Enrollment
        fields = []

    def filter_is_fully_paid(self, queryset, name, value):
        if value:
            return queryset.filter(paid_amount__gte=F('fee_at_enrollment'))
        else:
            return queryset.exclude(paid_amount__gte=F('fee_at_enrollment'))

class ProfileFilter(filters.FilterSet):
    username = filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    email = filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    full_name = filters.CharFilter(field_name='full_name', lookup_expr='icontains')
    role = filters.CharFilter(field_name='role', lookup_expr='exact')

    class Meta:
        model = Profile
        fields = []

class InstallmentFilter(filters.FilterSet):
    enrollment_roll_number = filters.CharFilter(
        field_name="enrollment__roll_number", lookup_expr="icontains"
    )
    student_name = filters.CharFilter(
        field_name="enrollment__student__name", lookup_expr="icontains"
    )
    batch_code = filters.CharFilter(
        field_name="enrollment__batch__batch_code", lookup_expr="icontains"
    )
    status = filters.CharFilter(field_name="status", lookup_expr="exact")
    min_due_date = filters.DateFilter(field_name="due_date", lookup_expr="gte")
    max_due_date = filters.DateFilter(field_name="due_date", lookup_expr="lte")
    min_paid_amount = filters.NumberFilter(field_name="paid_amount", lookup_expr="gte")
    max_paid_amount = filters.NumberFilter(field_name="paid_amount", lookup_expr="lte")
    min_amount = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = filters.NumberFilter(field_name="amount", lookup_expr="lte")
    min_paid_date = filters.DateFilter(field_name="paid_date", lookup_expr="gte")
    max_paid_date = filters.DateFilter(field_name="paid_date", lookup_expr="lte")

    class Meta:
        model = Installment
        fields = []