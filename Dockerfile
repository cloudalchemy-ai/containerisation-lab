FROM python:3.11-slim

# Set a working directory
WORKDIR /app

# Ensure stdout/stderr are not buffered (helpful for logging)
# "Print output/logs immediately."

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install pip requirements first (layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY app /app/app

# Create a non-root user and use it
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Expose the listening port
EXPOSE 8080

# Run the application with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
