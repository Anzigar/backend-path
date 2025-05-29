#!/bin/bash

echo "FastAPI Service Deployment Script"
echo "================================="

# Check if Docker is running
if ! docker info &>/dev/null; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Function to create .env file if it doesn't exist
create_env_file() {
    if [ ! -f .env ]; then
        echo "Creating .env file with default settings..."
        cat > .env << EOF
# Database settings
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_SERVER=db
POSTGRES_PORT=5432
POSTGRES_DB=website_db

# Application settings
APP_ENV=development
DEBUG=true

# AWS S3 settings (update with your credentials)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_NAME=your_bucket_name
AWS_REGION=us-east-1
EOF
        echo ".env file created. Please update it with your actual credentials."
    else
        echo ".env file already exists."
    fi
}

# Create docker-compose file
create_docker_compose() {
    echo "Creating docker-compose.yml file..."
    cat > docker-compose.yml << EOF
version: '3'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - db
    env_file:
      - .env
    volumes:
      - ./:/app
    restart: always
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:14
    volumes:
      - postgres_data:/var/lib/postgresql/data
    env_file:
      - .env
    environment:
      - POSTGRES_PASSWORD=\${POSTGRES_PASSWORD}
      - POSTGRES_USER=\${POSTGRES_USER}
      - POSTGRES_DB=\${POSTGRES_DB}
    ports:
      - "5432:5432"

  pgadmin:
    image: dpage/pgadmin4
    environment:
      - PGADMIN_DEFAULT_EMAIL=admin@admin.com
      - PGADMIN_DEFAULT_PASSWORD=admin
    ports:
      - "5050:80"
    depends_on:
      - db

volumes:
  postgres_data:
EOF
    echo "docker-compose.yml created."
}

# Create environment file and Docker Compose file
create_env_file
create_docker_compose

# Build and start the containers
echo "Building and starting the containers..."
docker-compose up -d --build

echo
echo "Service deployment completed."
echo "The FastAPI application is running at: http://localhost:8000"
echo "API documentation is available at: http://localhost:8000/api/docs"
echo "PgAdmin is available at: http://localhost:5050"
echo "  - Email: admin@admin.com"
echo "  - Password: admin"
echo
echo "To view logs: docker-compose logs -f api"
echo "To stop the services: docker-compose down"
