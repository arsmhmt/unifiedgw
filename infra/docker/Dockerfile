# Example Dockerfile for PayCrypt Unified Gateway

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_ENV=production
ENV FLASK_APP=run.py

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "wsgi:app"]
