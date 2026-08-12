FROM node:20-alpine AS h5-builder

WORKDIR /build
COPY 003.UI/uniapp/package.json 003.UI/uniapp/package-lock.json ./
RUN npm ci

COPY 003.UI/uniapp/ ./
RUN npm run build:h5

FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY --from=h5-builder /build/dist/build/h5/ /usr/share/nginx/h5/
