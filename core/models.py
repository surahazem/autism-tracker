from django.db import models
from django.contrib.auth.models import AbstractUser
import random

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class User(AbstractUser):
    email = models.EmailField(
        "email address",
        max_length=255,
        unique=True,
    )
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

class Clinic(BaseModel):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Therapist(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='therapist_profile')
    specialization = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='therapists')

    def __str__(self):
        return f"Therapist: {self.user.get_full_name()}"



def generate_parent_id():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return 'PAR-' + ''.join(random.choices(chars, k=6))


class Parent(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')
    phone_number = models.CharField(max_length=20)
    address = models.TextField()
    parent_shared_id = models.CharField(max_length=15, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.parent_shared_id:
            while True:
                new_id = generate_parent_id()
                if not Parent.objects.filter(parent_shared_id=new_id).exists():
                    self.parent_shared_id = new_id
                    break
        super().save(*args, **kwargs)


class Child(BaseModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    parents = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='children')

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def active_plan(self):
        return self.treatment_plans.filter(status='active').first()

    @property
    def active_plans_count(self):
        return self.treatment_plans.filter(status='active').count()

    @property
    def latest_drawing(self):
        return self.drawings.order_by('-upload_date').first()

    @property
    def total_sessions(self):
        return Session.objects.filter(treatment_plan__child=self).count()

class Form(BaseModel):
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.title

class Question(BaseModel):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()

    def __str__(self):
        return self.text[:50]

class Answer(BaseModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='form_answers')
    text = models.TextField()


class TreatmentPlan(BaseModel):
    PLAN_STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    ]
    therapist = models.ForeignKey(Therapist, on_delete=models.CASCADE, related_name='managed_plans')
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='treatment_plans')
    status = models.CharField(max_length=20, choices=PLAN_STATUS_CHOICES, default='active')

    def __str__(self):
        return f"Plan for {self.child} by {self.therapist}"

class Diagnosis(BaseModel):
    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='diagnoses')
    status = models.CharField(max_length=100)
    description = models.TextField()

SESSION_STATUS_CHOICES = [
    ('scheduled', 'Scheduled'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

class Session(BaseModel):
    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='sessions')
    date = models.DateTimeField()
    notes = models.TextField()
    status = models.CharField(max_length=20, choices=SESSION_STATUS_CHOICES, default='scheduled')

class Goal(BaseModel):
    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='goals')
    target_description = models.TextField()

class Treatment(BaseModel):
    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='treatments')
    type = models.CharField(max_length=100)
    description = models.TextField()

class Indicator(BaseModel):
    metric_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.metric_name


class TreatmentPlanIndicator(BaseModel):
    """Junction table linking a TreatmentPlan to a specific Indicator.
    The therapist adds indicators here when submitting a session."""
    treatment_plan = models.ForeignKey(
        TreatmentPlan, on_delete=models.CASCADE, related_name='plan_indicators'
    )
    indicator = models.ForeignKey(
        Indicator, on_delete=models.CASCADE, related_name='plan_indicators'
    )
    # Optional description the therapist writes for the parent
    description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('treatment_plan', 'indicator')

    def __str__(self):
        return f"{self.indicator.metric_name} – {self.treatment_plan}"


class DrawingImage(BaseModel):
    EMOTIONAL_STATES = [
        ('calm', 'Calm'),
        ('happy', 'Happy'),
        ('energetic', 'Energetic'),
        ('overwhelmed', 'Overwhelmed'),
        ('withdrawn', 'Withdrawn'),
        ('anxious', 'Anxious'),
    ]
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='drawings')
    image_path = models.ImageField(upload_to='drawings/%Y/%m/%d/')
    upload_date = models.DateTimeField(auto_now_add=True)
    draw_date = models.DateField(null=True, blank=True)  # enforces one-per-day

    # Core analysis fields
    stroke_density = models.FloatField(default=0.0)
    emotional_state = models.CharField(max_length=20, choices=EMOTIONAL_STATES, null=True, blank=True)
    confidence = models.FloatField(default=0.0)
    analysis_notes = models.TextField(blank=True, null=True)



    class Meta:
        # Enforce one drawing per child per day
        constraints = [
            models.UniqueConstraint(fields=['child', 'draw_date'], name='one_drawing_per_child_per_day')
        ]

    def __str__(self):
        return f"Drawing by {self.child} on {self.upload_date.date()}"


class ProgressRecord(BaseModel):
    """One entry per indicator per day. The parent submits this daily."""
    treatment_plan_indicator = models.ForeignKey(
        TreatmentPlanIndicator,
        on_delete=models.CASCADE,
        related_name='progress_records',
    )
    drawing_image = models.ForeignKey(
        DrawingImage, on_delete=models.SET_NULL,
        related_name='progress_records', null=True, blank=True
    )

    # Value on a 0-100 scale entered by the parent
    indicator_value = models.FloatField(default=0.0)
    date = models.DateField()

    # Parent's free-text note for the day
    notes = models.TextField(blank=True, null=True)

    # Whether the parent has submitted the record for the day
    is_submitted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['treatment_plan_indicator', 'date'], name='one_record_per_indicator_per_day')
        ]

    def __str__(self):
        ind = self.treatment_plan_indicator.indicator.metric_name
        child = self.treatment_plan_indicator.treatment_plan.child
        return f"{ind} – {self.date} ({child})"

