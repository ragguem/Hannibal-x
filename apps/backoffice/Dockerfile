# syntax=docker/dockerfile:1.7
# Construit depuis la racine du dépôt : docker build -f apps/backoffice/Dockerfile -t hannibal/backoffice:dev .
ARG SDK_IMAGE=mcr.microsoft.com/dotnet/sdk:11.0
ARG RUNTIME_IMAGE=mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled

FROM ${SDK_IMAGE} AS build
WORKDIR /src
COPY global.json ./
COPY apps/backoffice/Directory.Build.props apps/backoffice/Directory.Packages.props apps/backoffice/nuget.config apps/backoffice/
COPY apps/backoffice/src/Hannibal.Backoffice.Domain/*.csproj apps/backoffice/src/Hannibal.Backoffice.Domain/packages.lock.json apps/backoffice/src/Hannibal.Backoffice.Domain/
COPY apps/backoffice/src/Hannibal.Backoffice.Application/*.csproj apps/backoffice/src/Hannibal.Backoffice.Application/packages.lock.json apps/backoffice/src/Hannibal.Backoffice.Application/
COPY apps/backoffice/src/Hannibal.Backoffice.Infrastructure/*.csproj apps/backoffice/src/Hannibal.Backoffice.Infrastructure/packages.lock.json apps/backoffice/src/Hannibal.Backoffice.Infrastructure/
COPY apps/backoffice/src/Hannibal.Backoffice.Api/*.csproj apps/backoffice/src/Hannibal.Backoffice.Api/packages.lock.json apps/backoffice/src/Hannibal.Backoffice.Api/
RUN --mount=type=cache,target=/root/.nuget/packages \
    dotnet restore apps/backoffice/src/Hannibal.Backoffice.Api --locked-mode
COPY apps/backoffice apps/backoffice
COPY packages/contracts/schemas/ScenarioDocument.json packages/contracts/schemas/
COPY apps/api/scenarios apps/api/scenarios
RUN --mount=type=cache,target=/root/.nuget/packages \
    dotnet publish apps/backoffice/src/Hannibal.Backoffice.Api -c Release --no-restore -o /out /p:UseAppHost=false

FROM ${RUNTIME_IMAGE} AS runtime
ARG VERSION=0.2.0
LABEL org.opencontainers.image.title="hannibal-backoffice" org.opencontainers.image.version="${VERSION}"
WORKDIR /app
COPY --from=build /out ./
ENV ASPNETCORE_URLS=http://+:8080 DOTNET_gcServer=0
USER app
EXPOSE 8080
ENTRYPOINT ["dotnet", "Hannibal.Backoffice.Api.dll"]
