# Servidor de desarrollo de Vite para docker compose (con recarga en caliente).
# Debian slim (glibc): los binarios nativos de Vite 8, Tailwind 4 y Rolldown tienen el mismo build que en el equipo.
FROM node:22-slim

WORKDIR /app

ENV VITE_API_PROXY_TARGET=http://api:8000 \
    TZ=America/Bogota

# Dependencias primero: esta capa solo se reconstruye si cambian package.json / package-lock.json.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

# --host: escucha en todas las interfaces para que el puerto publicado sea alcanzable desde fuera del contenedor.
CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "3000", "--strictPort"]
