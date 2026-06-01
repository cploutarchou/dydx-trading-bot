job "dydx-trading-bot" {
  datacenters = ["dc1"]
  type        = "service"

  constraint {
    attribute = "${node.unique.name}"
    operator  = "="
    value     = "${var.nomad_node_name}"
  }

  update {
    max_parallel     = 1
    min_healthy_time = "15s"
    healthy_deadline = "10m"
    progress_deadline = "15m"
    auto_revert      = true
    canary           = 1
  }

  group "app" {
    count = 1

    network {
      mode = "host"

      port "frontend" {
        static = 5173
        to     = 80
      }

      port "backend" {
        static = 8888
        to     = 8888
      }

      port "botapi" {
        static = 8889
        to = 8889
      }

      port "postgres" {
        static = 5432
        to = 5432
      }

      port "redis" {
        static = 6379
        to = 6379
      }
    }

    restart {
      attempts = 10
      interval = "30m"
      delay    = "15s"
      mode     = "delay"
    }

    task "postgres" {
      driver = "docker"

      config {
        image = "postgres:16"
        ports = ["postgres"]

        mount {
          type   = "volume"
          source = "dydx-postgres-data"
          target = "/var/lib/postgresql/data"
        }
      }

      env {
        POSTGRES_DB       = "${var.app_db_name}"
        POSTGRES_USER     = "${var.app_db_user}"
        POSTGRES_PASSWORD = "${var.app_db_password}"
      }

      resources {
        cpu    = 600
        memory = 768
      }

      service {
        name = "dydx-postgres"
        port = "postgres"

        check {
          name     = "postgres-tcp"
          type     = "tcp"
          interval = "20s"
          timeout  = "3s"
        }
      }
    }

    task "redis" {
      driver = "docker"

      config {
        image   = "redis:7-alpine"
        command = "redis-server"
        args    = ["--appendonly", "yes"]
        ports   = ["redis"]

        mount {
          type   = "volume"
          source = "dydx-redis-data"
          target = "/data"
        }
      }

      resources {
        cpu    = 300
        memory = 384
      }

      service {
        name = "dydx-redis"
        port = "redis"

        check {
          name     = "redis-tcp"
          type     = "tcp"
          interval = "20s"
          timeout  = "3s"
        }
      }
    }

    task "bot" {
      driver = "docker"

      config {
        image = "${var.bot_image}"
        ports = ["botapi"]
      }

      env {
        ENVIRONMENT        = "${var.environment}"
        APP_CONFIG_ENV     = "${var.app_config_env}"
        LOG_LEVEL          = "${var.log_level}"
        SECRET_KEY         = "${var.secret_key}"
        JWT_SECRET_KEY     = "${var.jwt_secret_key}"
        ENCRYPTION_KEY     = "${var.encryption_key}"
        BOT_API_TOKEN      = "${var.bot_api_token}"
        BOT_DB_CUTOVER_MODE = "shared"

        DB_HOST     = "127.0.0.1"
        DB_PORT     = "${NOMAD_PORT_postgres}"
        DB_NAME     = "${var.app_db_name}"
        DB_USER     = "${var.app_db_user}"
        DB_PASSWORD = "${var.app_db_password}"

        REDIS_HOST = "127.0.0.1"
        REDIS_PORT = "${NOMAD_PORT_redis}"

        BOT_API_HOST = "0.0.0.0"
        BOT_API_PORT = "8889"
      }

      resources {
        cpu    = 1000
        memory = 1536
      }

      service {
        name = "dydx-bot"
        port = "botapi"

        check {
          name     = "bot-ready"
          type     = "http"
          path     = "/ready"
          interval = "20s"
          timeout  = "5s"
        }
      }
    }

    task "backend" {
      driver = "docker"

      config {
        image = "${var.backend_image}"
        ports = ["backend"]
      }

      env {
        ENVIRONMENT    = "${var.environment}"
        APP_CONFIG_ENV = "${var.app_config_env}"
        LOG_LEVEL      = "${var.log_level}"

        API_PORT       = "8888"
        SECRET_KEY     = "${var.secret_key}"
        JWT_SECRET_KEY = "${var.jwt_secret_key}"
        ENCRYPTION_KEY = "${var.encryption_key}"

        DB_HOST     = "127.0.0.1"
        DB_PORT     = "${NOMAD_PORT_postgres}"
        DB_NAME     = "${var.app_db_name}"
        DB_USER     = "${var.app_db_user}"
        DB_PASSWORD = "${var.app_db_password}"

        REDIS_HOST = "127.0.0.1"
        REDIS_PORT = "${NOMAD_PORT_redis}"

        BOT_API_URL               = "http://127.0.0.1:${NOMAD_PORT_botapi}"
        BOT_API_USE_SERVICE_TOKEN = "true"
        BOT_API_TOKEN             = "${var.bot_api_token}"
        BOT_DB_CUTOVER_MODE       = "shared"

        FRONTEND_URL         = "https://${var.app_domain}"
        CORS_ALLOWED_ORIGINS = "https://${var.app_domain}"
      }

      resources {
        cpu    = 1200
        memory = 1536
      }

      service {
        name = "dydx-backend"
        port = "backend"
        tags = [
          "traefik.enable=true",
          "traefik.http.routers.dydx-backend.rule=Host(`${var.api_domain}`)",
          "traefik.http.routers.dydx-backend.entrypoints=websecure",
          "traefik.http.routers.dydx-backend.tls=true",
          "traefik.http.services.dydx-backend.loadbalancer.server.port=8888"
        ]

        check {
          name     = "backend-ready"
          type     = "http"
          path     = "/ready"
          interval = "15s"
          timeout  = "5s"
        }
      }
    }

    task "frontend" {
      driver = "docker"

      config {
        image = "${var.frontend_image}"
        ports = ["frontend"]
      }

      resources {
        cpu    = 600
        memory = 768
      }

      service {
        name = "dydx-frontend"
        port = "frontend"
        tags = [
          "traefik.enable=true",
          "traefik.http.routers.dydx-frontend.rule=Host(`${var.app_domain}`)",
          "traefik.http.routers.dydx-frontend.entrypoints=websecure",
          "traefik.http.routers.dydx-frontend.tls=true",
          "traefik.http.services.dydx-frontend.loadbalancer.server.port=80"
        ]

        check {
          name     = "frontend-root"
          type     = "http"
          path     = "/"
          interval = "20s"
          timeout  = "5s"
        }
      }
    }
  }
}

variable "nomad_node_name" {
  type        = string
  description = "Nomad node name that should host this allocation (e.g. nomad-cp-01)"
  default     = "nomad-cp-01"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "app_config_env" {
  type    = string
  default = "production"
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "app_domain" {
  type        = string
  description = "Public frontend domain"
  default     = "app.example.com"
}

variable "api_domain" {
  type        = string
  description = "Public backend API domain"
  default     = "api.example.com"
}

variable "frontend_image" {
  type        = string
  description = "Frontend image already pushed to a registry reachable by Nomad clients"
  default     = "ghcr.io/example/dydx-trading-bot-frontend:latest"
}

variable "backend_image" {
  type        = string
  description = "Backend image already pushed to a registry reachable by Nomad clients"
  default     = "ghcr.io/example/dydx-trading-bot-backend:latest"
}

variable "bot_image" {
  type        = string
  description = "Bot API image already pushed to a registry reachable by Nomad clients"
  default     = "ghcr.io/example/dydx-trading-bot-bot:latest"
}

variable "app_db_name" {
  type    = string
  default = "app"
}

variable "app_db_user" {
  type    = string
  default = "app"
}

variable "app_db_password" {
  type    = string
  default = "REPLACE_ME"
}

variable "secret_key" {
  type    = string
  default = "REPLACE_ME"
}

variable "jwt_secret_key" {
  type    = string
  default = "REPLACE_ME"
}

variable "encryption_key" {
  type    = string
  default = "REPLACE_ME"
}

variable "bot_api_token" {
  type    = string
  default = "REPLACE_ME"
}
