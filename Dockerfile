# Use an official lightweight Python image as the base
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the application port
# EXPOSE 8000

# Command to run the ADK API server using the "shell form".
# This allows the shell to correctly substitute ${PORT} and ${DB_URI}
# with the values provided by Cloud Run before the command is executed.
CMD adk api_server . --host=0.0.0.0 --port=${PORT} --session_service_uri=${DB_URI}