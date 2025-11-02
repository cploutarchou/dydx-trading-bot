FROM golang:1.23-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git make gcc musl-dev sqlite-dev

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=1 GOOS=linux go build -a -installsuffix cgo -o /app/bin/server ./cmd/server

# Final stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates sqlite-libs

WORKDIR /root/

# Copy binary from builder
COPY --from=builder /app/bin/server .
COPY --from=builder /app/migrations ./migrations

# Copy .env file (optional - better to use environment variables)
# COPY .env .

EXPOSE 8888

CMD ["./server"]

