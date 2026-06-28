# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create a non-root user with UID 1000 for Hugging Face Spaces compatibility
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# Install python dependencies
COPY --chown=user:user requirements.txt /home/user/app/
RUN pip install --no-cache-dir --user -r requirements.txt

# Add user bin to PATH (since packages are installed with --user)
ENV PATH="/home/user/.local/bin:${PATH}"

# Copy the rest of the application code
COPY --chown=user:user . /home/user/app/

# Switch to the non-root user
USER user

# Expose port 7860
EXPOSE 7860

# Command to run
CMD ["gunicorn", "core_project.wsgi:application", "--bind", "0.0.0.0:7860", "--workers", "2"]