FROM php:8.4-fpm-alpine
WORKDIR /app
RUN apk add --no-cache nginx curl gettext \
    && docker-php-ext-install opcache
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/opcache.ini /usr/local/etc/php/conf.d/zz-opcache.ini
COPY docker/zz-bench.conf /usr/local/etc/php-fpm.d/zz-bench.conf.tpl
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
COPY src ./src
COPY public ./public
ENV PHP_FPM_CHILDREN=8
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
CMD ["/usr/local/bin/entrypoint.sh"]
