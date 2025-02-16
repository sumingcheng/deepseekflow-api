DOCKER_IMAGE_NAME := ds-api
DOCKER_IMAGE_TAG := v1.0.1
DOCKERFILE_PATH := deploy/Dockerfile
DOCKER_COMPOSE_FILE := deploy/docker-compose.yaml

.PHONY: build start stop

build:
	@docker build -t $(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG) -f $(DOCKERFILE_PATH) .

up:
	@docker compose -f $(DOCKER_COMPOSE_FILE) up -d

down:
	@docker compose -f $(DOCKER_COMPOSE_FILE) down
