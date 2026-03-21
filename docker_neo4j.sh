#!/bin/zsh 
# Start Neo4j using docker-compose
docker compose up -d
echo "Waiting for Neo4j to be healthy..."
docker compose ps
