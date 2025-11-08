ARG BASE_IMAGE=node:20-alpine

FROM ${BASE_IMAGE} AS builder

WORKDIR /app

COPY package.json yarn.lock* package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

# Production image
FROM ${BASE_IMAGE}

WORKDIR /app

RUN npm install -g serve

COPY --from=builder /backend/app/dist ./dist

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]
