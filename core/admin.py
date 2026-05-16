from django.contrib import admin
from .models import (
    Clinic, Therapist, Parent, Child, Form, Question,
    Answer, TreatmentPlan, Diagnosis, Session, Goal,
    Treatment, Indicator, TreatmentPlanIndicator, DrawingImage,
    ProgressRecord
)

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1

class DiagnosisInline(admin.TabularInline):
    model = Diagnosis
    extra = 1

class SessionInline(admin.TabularInline):
    model = Session
    extra = 1

class GoalInline(admin.TabularInline):
    model = Goal
    extra = 1

class TreatmentInline(admin.TabularInline):
    model = Treatment
    extra = 1


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'created_at')
    search_fields = ('name', 'location')

@admin.register(Therapist)
class TherapistAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialization', 'clinic', 'license_number')
    search_fields = ('user__first_name', 'user__last_name', 'license_number')
    list_filter = ('clinic', 'specialization')

@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'phone_number')

@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'date_of_birth', 'parents')
    search_fields = ('first_name', 'last_name')
    list_filter = ('date_of_birth',)

@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')
    inlines = [QuestionInline]

@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    list_display = ('child', 'therapist', 'created_at')
    list_filter = ('therapist', 'created_at')
    search_fields = ('child__first_name', 'child__last_name')
    inlines = [DiagnosisInline, SessionInline, GoalInline, TreatmentInline]

@admin.register(Indicator)
class IndicatorAdmin(admin.ModelAdmin):
    list_display = ('metric_name', 'description', 'created_at')
    search_fields = ('metric_name',)

@admin.register(TreatmentPlanIndicator)
class TreatmentPlanIndicatorAdmin(admin.ModelAdmin):
    list_display = ('treatment_plan', 'indicator', 'description', 'created_at')
    list_filter = ('treatment_plan__therapist', 'indicator')
    search_fields = ('indicator__metric_name', 'treatment_plan__child__first_name')

@admin.register(ProgressRecord)
class ProgressRecordAdmin(admin.ModelAdmin):
    list_display = ('treatment_plan_indicator', 'indicator_value', 'date')
    list_filter = ('date',)
    date_hierarchy = 'date'
    search_fields = ('treatment_plan_indicator__indicator__metric_name', 'treatment_plan_indicator__treatment_plan__child__first_name')

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('child', 'question', 'text', 'created_at')
    list_filter = ('child', 'question__form')

@admin.register(DrawingImage)
class DrawingImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'child', 'draw_date', 'upload_date', 'image_path', 'emotional_state', 'confidence')
    readonly_fields = ('upload_date',)


admin.site.register(Question)
admin.site.register(Diagnosis)
admin.site.register(Session)
admin.site.register(Goal)
admin.site.register(Treatment)
