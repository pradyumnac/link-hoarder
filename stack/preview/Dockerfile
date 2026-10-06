FROM node:24-slim

ENV NODE_ENV=production
WORKDIR /srv/preview

COPY stack/preview/package.json stack/preview/package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY stack/preview/server.js ./

USER node
EXPOSE 3001
CMD ["node", "server.js"]
