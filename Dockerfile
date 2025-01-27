# Use a Python base image
FROM python

# Set the working directory
WORKDIR /app

# Create a virtual environment
RUN python -m venv .venv

# Activate the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Copy requirements.txt and install dependencies
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of your application code
COPY . .

# Run your application
CMD ["python", "src/main.py"]