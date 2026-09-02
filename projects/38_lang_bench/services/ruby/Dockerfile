FROM ruby:3.3-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*
COPY Gemfile ./
RUN bundle config set --local without 'development test' && bundle install
COPY app.rb core.rb config.ru ./
ENV PORT=8000 WORKERS=2 THREADS=8 RUBY_YJIT_ENABLE=1
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
CMD ["sh", "-c", "bundle exec puma -b tcp://0.0.0.0:${PORT} -w ${WORKERS} -t ${THREADS}:${THREADS} --no-log-requests config.ru"]
