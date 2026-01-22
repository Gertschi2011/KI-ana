FROM node:20-alpine
WORKDIR /app

ARG NEXT_PUBLIC_BUILD_SHA=unknown
ENV NEXT_PUBLIC_BUILD_SHA=$NEXT_PUBLIC_BUILD_SHA

COPY package.json .
# Install deps (no lockfile present in repo)
RUN npm install --no-audit --no-fund
# Ensure Tailwind toolchain is present in the container
RUN npm install --no-audit --no-fund tailwindcss postcss autoprefixer
COPY . .
ENV PORT=3000 HOST=0.0.0.0
RUN npm run build
EXPOSE 3000
CMD ["npm","start"]
