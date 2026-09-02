FROM rust:1.83-slim AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --locked

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/target/release/lang-bench-rust /usr/local/bin/server
ENV PORT=8000 WORKERS=2
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
CMD ["/usr/local/bin/server"]
