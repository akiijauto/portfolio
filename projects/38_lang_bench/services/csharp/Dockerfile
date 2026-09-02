FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src
COPY lang-bench-csharp.csproj ./
RUN dotnet restore
COPY Score.cs Program.cs ./
RUN dotnet publish -c Release -o /out --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:9.0
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /out ./
ENV PORT=8000 ASPNETCORE_ENVIRONMENT=Production DOTNET_gcServer=1
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=30 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
CMD ["dotnet", "lang-bench-csharp.dll"]
