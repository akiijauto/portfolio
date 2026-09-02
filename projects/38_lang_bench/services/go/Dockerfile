FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY main.go score.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/server .

FROM alpine:3.20
RUN apk add --no-cache curl ca-certificates
COPY --from=build /out/server /usr/local/bin/server
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
CMD ["/usr/local/bin/server"]
