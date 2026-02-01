FROM python:3.13-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8005

CMD ["gunicorn", "AutismTracker.wsgi:application", "--bind", "0.0.0.0:8005"]
