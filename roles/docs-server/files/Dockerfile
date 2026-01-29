FROM python:3.11-slim

# Install MkDocs and Material theme
RUN pip install --no-cache-dir \
    mkdocs==1.5.3 \
    mkdocs-material==9.5.3 \
    pymdown-extensions==10.7

# Create app directory
WORKDIR /docs

# Copy documentation files (they're already in the build context)
COPY docs /docs/docs
COPY mkdocs.yml /docs/

# Build the static site
RUN mkdocs build

# Use nginx to serve the built site
FROM nginx:alpine
COPY --from=0 /docs/site /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
