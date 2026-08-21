FROM node:24-bookworm-slim AS build

WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY docs/openapi.json /workspace/docs/openapi.json
COPY frontend ./
RUN npm run build

FROM nginx:1.29-alpine

COPY --from=build /workspace/frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY frontend/entrypoint.sh /usr/local/bin/link-hoarder-frontend-entrypoint
RUN chmod +x /usr/local/bin/link-hoarder-frontend-entrypoint

EXPOSE 80
ENTRYPOINT ["/usr/local/bin/link-hoarder-frontend-entrypoint"]
CMD ["nginx", "-g", "daemon off;"]
