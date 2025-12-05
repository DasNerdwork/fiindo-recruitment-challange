# Base image
FROM python:3.11-slim

# Working directory
WORKDIR /app

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest
COPY . .

# Standard command
CMD ["python", "app/main.py"]
