.PHONY: help build up down logs clean init deploy

help: ## Show this help message
	@echo "Aastreli - Industrial Anomaly Detection System"
	@echo "=============================================="
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build all Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d
	@echo "✅ All services started!"
	@echo "   Frontend:     http://localhost:3000"
	@echo "   Backend API:  http://localhost:8000"
	@echo "   ML Service:   http://localhost:8001"
	@echo "   MQTT Ingest:  http://localhost:8002"
	@echo "   MongoDB:      mongodb://localhost:27017"
	@echo "   MQTT Broker:  mqtt://localhost:1883"

down: ## Stop all services
	docker-compose down

restart: down up ## Restart all services

logs: ## Show logs from all services
	docker-compose logs -f

logs-ml: ## Show ML service logs
	docker-compose logs -f ml-service

logs-mqtt: ## Show MQTT ingestion logs
	docker-compose logs -f mqtt-ingestion

logs-backend: ## Show backend API logs
	docker-compose logs -f backend-api

logs-frontend: ## Show frontend logs
	docker-compose logs -f frontend

ps: ## Show running containers
	docker-compose ps

clean: ## Remove all containers and volumes
	docker-compose down -v
	@echo "⚠️  All data has been removed!"

init: ## Initialize the system
	@echo "🚀 Initializing Aastreli..."
	@mkdir -p ml-service/models/current
	@mkdir -p ml-service/models/versions
	@mkdir -p ml-service/feedback_data
	@mkdir -p database/init
	@mkdir -p mqtt-broker/config
	@echo "✅ Directories created"

deploy-model: ## Deploy ML model (copy from /mnt/user-data/outputs)
	@echo "📦 Deploying ML model..."
	@if [ -f "/mnt/user-data/outputs/Industrial_Anomaly_Prediction_XGBoost_KFold_WithFeedback.ipynb" ]; then \
		echo "  ✓ Found model notebook"; \
	fi
	@echo "  Copy your trained models to ml-service/models/current/:"
	@echo "    - xgboost_anomaly_detector.json"
	@echo "    - label_encoder.pkl"
	@echo "    - feature_scaler.pkl"

test: ## Run tests
	@echo "Running tests..."
	cd backend-api && pytest tests/
	cd ml-service && pytest tests/

health: ## Check health of all services
	@echo "🏥 Health Check:"
	@curl -s http://localhost:8000/health | jq '.' || echo "❌ Backend API not responding"
	@curl -s http://localhost:8001/health | jq '.' || echo "❌ ML Service not responding"
	@curl -s http://localhost:8002/health | jq '.' || echo "❌ MQTT Ingestion not responding"

shell-ml: ## Open shell in ML service container
	docker-compose exec ml-service /bin/bash

shell-backend: ## Open shell in backend API container
	docker-compose exec backend-api /bin/bash

shell-mongodb: ## Open MongoDB shell
	docker-compose exec mongodb mongosh aastreli

backup-db: ## Backup MongoDB database
	@echo "📦 Backing up database..."
	docker-compose exec -T mongodb mongodump --db aastreli --archive > backup_$(shell date +%Y%m%d_%H%M%S).archive
	@echo "✅ Backup complete!"

restore-db: ## Restore MongoDB database (use: make restore-db FILE=backup.archive)
	@echo "📦 Restoring database..."
	docker-compose exec -T mongodb mongorestore --archive < $(FILE)
	@echo "✅ Restore complete!"

dev: ## Start in development mode
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

prod: ## Start in production mode
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

stop: down ## Alias for down
