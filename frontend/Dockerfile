# Use Node.js for building the frontend
FROM node:20-alpine as build

WORKDIR /app

# Copy only package.json and package-lock.json (no 'frontend/' prefix, context is already 'frontend')
COPY package.json package-lock.json ./
RUN npm install

# Copy the rest of the frontend source
COPY . .
RUN npm run build

# Serve the build with a lightweight web server
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
