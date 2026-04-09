#!/bin/bash
set -e

echo "Building log correlation engine..."
go mod download
go mod tidy
mkdir -p bin
go build -o bin/correlation-engine ./cmd/main.go

echo "Build complete!"
echo "Run with: ./bin/correlation-engine"
