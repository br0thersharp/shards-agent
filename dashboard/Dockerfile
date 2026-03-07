FROM node:22-slim

WORKDIR /app

COPY package.json ./
RUN npm install --production

COPY server.js ./
COPY public/ ./public/

USER node
EXPOSE 3000

CMD ["node", "server.js"]
