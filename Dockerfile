# CONTAINER RECIPE: installs the dependencies, copies the app in, and starts the
# FastAPI server. The EC2 box builds this image and runs it.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# REQUIREMENT: 0.0.0.0 not 127.0.0.1, or the container only listens to itself
# and nothing outside can reach it.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]