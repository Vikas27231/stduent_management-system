# Use an official Python runtime as the base image
FROM python:3.12-slim

# Set the working directory 
WORKDIR /app

# Copy the requirements file to the working directory
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the contents of the build context (student_management/) directly into /app/
COPY . .

# Debug: List the contents of /app/ to verify structure
RUN ls -la /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port 80 for the application
EXPOSE 80

# Start the application with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:80", "student_management.wsgi:application"]
