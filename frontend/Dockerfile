# Frontend image — multi-stage, pinned base, non-root runtime.
#   docker build -f frontend/Dockerfile -t masterminds-frontend frontend
FROM node:22.14.0-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22.14.0-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# Next.js standalone output: minimal server + static assets.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
