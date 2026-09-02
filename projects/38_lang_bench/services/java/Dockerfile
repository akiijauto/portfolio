FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY pom.xml ./
# 依存解決だけを先に済ませ、ソース変更時の再ビルドを速くする
RUN mvn -B -q dependency:go-offline
COPY src ./src
RUN mvn -B -q -DskipTests package

FROM eclipse-temurin:21-jre-jammy
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/target/lang-bench-java-1.0.0.jar ./app.jar
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=40 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
# コンテナのCPU/メモリ上限をJVMに認識させる（-XX:MaxRAMPercentage）。
# 既定では上限を無視してヒープを取りに行き、他言語と条件が揃わない。
CMD ["sh", "-c", "java -XX:MaxRAMPercentage=75 -jar app.jar"]
