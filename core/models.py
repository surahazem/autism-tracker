from django.db import models
from django.contrib.auth.models import AbstractUser


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
    REQUIRED_FIELDS = []

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

class Parent(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')
    phone_number = models.CharField(max_length=20)
    address = models.TextField()

    def __str__(self):
        return f"Parent: {self.user.get_full_name()}"


class Child(BaseModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    parents = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='children')

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

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
    therapist = models.ForeignKey(Therapist, on_delete=models.CASCADE, related_name='managed_plans')
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='treatment_plans')

    def __str__(self):
        return f"Plan for {self.child} by {self.therapist}"

class Diagnosis(BaseModel):
    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='diagnoses')
    status = models.CharField(max_length=100)
    description = models.TextField()

class Session(BaseModel):
    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='sessions')
    date = models.DateTimeField()
    notes = models.TextField()

class Goal(BaseModel):
    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='goals')
    target_description = models.TextField()

class Treatment(BaseModel):
    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='treatments')
    type = models.CharField(max_length=100)
    description = models.TextField()

class Indicator(BaseModel):
    metric_name = models.CharField(max_length=255)

    def __str__(self):
        return self.metric_name

class DrawingImage(BaseModel):
    image_path = models.ImageField(upload_to='drawings/%Y/%m/%d/')
    upload_date = models.DateTimeField(auto_now_add=True)

class ProgressRecord(BaseModel):
    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='progress_records')
    indicator = models.ForeignKey(Indicator, on_delete=models.CASCADE)
    drawing_image = models.ForeignKey(DrawingImage, on_delete=models.CASCADE, related_name='progress_records', null=True)
    indicator_value = models.FloatField()
    date = models.DateField()
    description = models.TextField()
    notes = models.TextField(blank=True, null=True)

