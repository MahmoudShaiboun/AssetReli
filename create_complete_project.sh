#!/bin/bash

echo "🏗️  Creating complete Aastreli microservices architecture..."

# Create all necessary directories
mkdir -p ml-service/app
mkdir -p ml-service/models/{current,versions}
mkdir -p ml-service/feedback_data
mkdir -p mqtt-ingestion/app
mkdir -p backend-api/app/routes
mkdir -p backend-api/app/models
mkdir -p frontend/src/{components,pages,services,hooks,types}
mkdir -p frontend/public
mkdir -p database/init
mkdir -p shared/{schemas,utils}
mkdir -p docs

echo "✅ Directory structure created"

