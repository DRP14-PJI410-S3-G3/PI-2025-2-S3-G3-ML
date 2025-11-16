.PHONY: help build start stop restart shell push-gcp update-gcp

PORT=8000
IMAGE_NAME="univesp.pi20250-2-s3g3-ml"
IMAGE_BASE="univesp.pi20250-2-s3g3-ml-base-image"

PROJECT_NAME=univesp-420315
SERVICE_NAME=univesp-pi20250s2g3-ml
SERVICE_REGION=us-central1
container=$(docker ps -a -q --filter ancestor=${IMAGE_NAME} --format="{{.ID}}")

help: ## Print help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

build: ## Build Application
	@docker build -t ${IMAGE_NAME} --no-cache . -f ./Dockerfile

build-app: ## Build Application
	@docker build -t ${IMAGE_NAME} --no-cache . -f ./Dockerfile.app-only

build-base: ## Build Base Image
	@docker build -t ${IMAGE_BASE} --no-cache . -f ./Dockerfile.base

start: ## Start container
	@echo "Starting container at http://localhost:${PORT}..."
	@docker run -e PORT=${PORT} -p ${PORT}:${PORT} --env-file ./src/.env ${IMAGE_NAME}

stop: ## Stop container
	@echo "Stopping container..."
	@docker rm $(shell docker stop $(shell docker ps -a -q --filter ancestor=${IMAGE_NAME} --format="{{.ID}}"))

restart: stop start ## Restart container

shell: ## SSH into container
	@docker exec -it $(shell docker ps -a -q --filter ancestor=${IMAGE_NAME} --format="{{.ID}}") /bin/bash

push-gcp: ##Push application image to Container Registry on GCP
	#make build-base
	#make build-app
	gcloud config set project ${PROJECT_NAME}
	docker tag ${IMAGE_NAME} gcr.io/${PROJECT_NAME}/${IMAGE_NAME}
	docker push gcr.io/${PROJECT_NAME}/${IMAGE_NAME}

create-gcr: ##Create Google Cloud Run Service with new image
	gcloud config set project ${PROJECT_NAME}
	gcloud run deploy ${SERVICE_NAME} --image=gcr.io/${PROJECT_NAME}/${IMAGE_NAME}:latest --set-env-vars PORT=${PORT} --platform managed --region=${SERVICE_REGION} --allow-unauthenticated --cpu 1 --memory 512Mi --min-instances 0 --max-instances 2

update-gcr: ##Update Google Cloud Run Service with new image
	gcloud config set project ${PROJECT_NAME}
	gcloud run services update ${SERVICE_NAME} --image=gcr.io/${PROJECT_NAME}/${IMAGE_NAME}:latest --region=${SERVICE_REGION}
