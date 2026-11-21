FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --omit=dev

COPY server.js rabbitmq.js ./

EXPOSE 8001

CMD ["npm", "start"]