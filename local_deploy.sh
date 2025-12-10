#!/bin/bash

# Ensure script stops on error
set -euo pipefail

# --- 1. Minikube Setup and Docker Context ---

echo "Checking Minikube status..."
if ! minikube status | grep 'host: Running' > /dev/null; then
    echo "Minikube not running. Starting now..."
    minikube start || { echo "Minikube failed to start."; exit 1; }
fi

echo "Setting Docker context to Minikube..."
eval $(minikube docker-env)

# --- 2. Build the Docker Image inside Minikube ---

IMAGE_TAG="mini-erp-uv:v1"
echo "Building Docker image: $IMAGE_TAG (inside Minikube's daemon)..."
# Uses the Dockerfile which now defaults to entrypoint-k8s.sh
docker build -t $IMAGE_TAG . || { echo "Docker image build failed."; exit 1; }
echo "Build complete."

# --- 3. Dynamic Secret Creation from .env ---

if [ ! -f .env ]; then
    echo "Error: .env file not found. Cannot create Kubernetes Secret."
    exit 1
fi

echo "Reading secrets from .env and creating Kubernetes Secret..."

# Extract DB_USER and DB_PASSWORD from .env
POSTGRES_USER=$(grep DB_USER .env | cut -d '=' -f 2)
POSTGRES_PASSWORD=$(grep DB_PASSWORD .env | cut -d '=' -f 2)
DJANGO_SECRET_KEY=$(grep SECRET_KEY .env | cut -d '=' -f 2)

SU_USER=$(grep DJANGO_SUPERUSER_USERNAME .env | cut -d '=' -f 2)
SU_EMAIL=$(grep DJANGO_SUPERUSER_EMAIL .env | cut -d '=' -f 2)
SU_PASSWORD=$(grep DJANGO_SUPERUSER_PASSWORD .env | cut -d '=' -f 2)
DEBUG=$(grep DEBUG .env | cut -d '=' -f 2)

# Cleanup: Delete the old secret before creating a new one
kubectl delete secret mini-erp-db-secret --ignore-not-found

# Create the new secret. Keys are POSTGRES_USER/PASSWORD, values come from .env
kubectl create secret generic mini-erp-db-secret \
    --from-literal=POSTGRES_USER="$POSTGRES_USER" \
    --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    --from-literal=SECRET_KEY="$DJANGO_SECRET_KEY" \
    --from-literal=DJANGO_SUPERUSER_USERNAME="$SU_USER" \
    --from-literal=DJANGO_SUPERUSER_EMAIL="$SU_EMAIL" \
    --from-literal=DJANGO_SUPERUSER_PASSWORD="$SU_PASSWORD" \
    --from-literal=DEBUG="$DEBUG" \
    || { echo "Failed to create Kubernetes Secret."; exit 1; }
    
echo "Kubernetes Secret 'mini-erp-db-secret' created successfully."

# --- 4. Deploy Manifests and Force Restart ---

echo "Deploying Kubernetes manifests..."

# Apply database manifests
kubectl apply -f k8s/postgres.yaml || { echo "Postgres deployment failed."; exit 1; }

# Apply application manifests
kubectl apply -f k8s/django-app.yaml || { echo "Django app deployment failed."; exit 1; }

# Force a rollout restart to ensure the new image is pulled and running
echo "Forcing deployment restart to pull new image..."
kubectl rollout restart deployment/django-app-deployment || { echo "Deployment restart failed."; exit 1; }


# --- 5. Final Status and Access ---

echo "Deployment complete. Waiting for services to become ready..."

# Wait for the rollout to finish
kubectl rollout status deployment/django-app-deployment --timeout=120s

# Wait for deployments to be available
kubectl wait --for=condition=available deployment/postgres-deployment --timeout=120s
kubectl wait --for=condition=available deployment/django-app-deployment --timeout=120s

SERVICE_URL=$(minikube service django-app-service --url)

echo "---------------------------------------------------------"
echo "Your Mini-ERP Application is running on Minikube!"
echo "Access URL: $SERVICE_URL"
echo "Note: K8s DB Host/Port are hardcoded to 'postgres-service:5432'."
echo "---------------------------------------------------------"