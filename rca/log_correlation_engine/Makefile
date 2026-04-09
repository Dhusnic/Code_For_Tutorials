.PHONY: build run test clean help

help:
	@echo "Log Correlation Engine - Available targets:"
	@echo "  build       - Build the correlation engine binary"
	@echo "  run         - Run the correlation engine"
	@echo "  test        - Run tests"
	@echo "  clean       - Remove build artifacts"
	@echo "  fmt         - Format code"
	@echo "  lint        - Run linter"
	@echo "  deps        - Download dependencies"

deps:
	go mod download
	go mod tidy

build: deps
	mkdir -p bin
	go build -o bin/correlation-engine ./cmd/main.go

run: build
	./bin/correlation-engine

test:
	go test -v -race -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html

fmt:
	go fmt ./...

lint:
	golangci-lint run ./...

clean:
	rm -rf bin/
	rm -f coverage.out coverage.html
