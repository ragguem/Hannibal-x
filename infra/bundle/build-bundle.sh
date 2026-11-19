#!/usr/bin/env bash
# Paquet d'installation hors ligne, construit sur une machine reliée à Internet (Docker, syft, zstd).
#   infra/bundle/build-bundle.sh 1.0.0
# Produit dist/hannibal-<version>/ : images (docker save), modèles Ollama, Whisper et reclassement,
# SBOM CycloneDX par image, fichiers d'exploitation, SHA256SUMS. dist/ n'est jamais suivi par git.
set -euo pipefail

version=${1:?usage : build-bundle.sh <version>}
root=$(cd "$(dirname "$0")/../.." && pwd)
out="$root/dist/hannibal-$version"
drafting_model=${HX_BUNDLE_DRAFTING_MODEL:-gemma3:12b}
embedding_model=${HX_BUNDLE_EMBEDDING_MODEL:-bge-m3}
whisper_models=${HX_BUNDLE_WHISPER_MODELS:-"large-v3-turbo small"}
rerank_model=${HX_BUNDLE_RERANK_MODEL:-BAAI/bge-reranker-v2-m3}

for tool in docker syft zstd sha256sum; do
  command -v "$tool" >/dev/null || { echo "outil manquant : $tool" >&2; exit 1; }
done
rm -rf "$out" && mkdir -p "$out"/{images,models,sbom,opt}

build() {  # build <tag> <dockerfile> [target]
  local args=(--build-arg "VERSION=$version" -t "$1" -f "$root/$2")
  [[ -n "${3:-}" ]] && args+=(--target "$3")
  docker build "${args[@]}" "$root"
}

build "hannibal/proxy:$version" infra/bord/Dockerfile
build "hannibal/api:$version" apps/api/Dockerfile
build "hannibal/backoffice:$version" apps/backoffice/Dockerfile
build "hannibal/doctrine:$version" services/doctrine/Dockerfile
build "hannibal/asr:$version-gpu" services/asr/Dockerfile gpu
build "hannibal/rerank:$version-gpu" services/rerank/Dockerfile gpu
build "hannibal/sim-bridge:$version-ros" services/sim_bridge/Dockerfile ros

third_party=$(awk '$1 == "image:" { print $2 }' "$root/infra/compose/compose.yml" | grep -v '^hannibal/' | sort -u)
for image in $third_party; do docker pull "$image"; done

images=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E "^hannibal/.*:$version(-gpu|-ros)?$")
for image in $images $third_party; do
  file=$(echo "$image" | tr '/:' '__')
  docker save "$image" | zstd -T0 -19 -q -o "$out/images/$file.tar.zst"
  syft "$image" -q -o cyclonedx-json > "$out/sbom/$file.cdx.json"
done

# Modèles chargés dans des volumes temporaires, puis archivés tels quels.
volume() { docker volume create "hx-bundle-$1-$$" >/dev/null && echo "hx-bundle-$1-$$"; }
archive() {  # archive <volume> <fichier>
  docker run --rm --user 0 -v "$1:/src:ro" -v "$out/models:/dst" --entrypoint tar "hannibal/api:$version" \
    -C /src -cf "/dst/$2" .
  docker volume rm "$1" >/dev/null
}

ollama_volume=$(volume ollama)
ollama_image=$(echo "$third_party" | grep '^ollama/')
docker run -d --name "hx-bundle-ollama-$$" -v "$ollama_volume:/root/.ollama" "$ollama_image" >/dev/null
sleep 3
for model in $drafting_model $embedding_model; do docker exec "hx-bundle-ollama-$$" ollama pull "$model"; done
docker rm -f "hx-bundle-ollama-$$" >/dev/null
archive "$ollama_volume" ollama.tar

asr_volume=$(volume asr)
for model in $whisper_models; do
  docker run --rm --user 0 -v "$asr_volume:/models" --entrypoint python3.12 "hannibal/asr:$version-gpu" \
    -c "from faster_whisper import download_model; download_model('$model')"
done
archive "$asr_volume" asr-models.tar

rerank_volume=$(volume rerank)
docker run --rm --user 0 -v "$rerank_volume:/models" --entrypoint python3.12 "hannibal/rerank:$version-gpu" \
  -c "from huggingface_hub import snapshot_download; snapshot_download('$rerank_model')"
archive "$rerank_volume" rerank-models.tar

cp -r "$root/infra/compose" "$root/infra/observability" "$root/infra/systemd" "$root/infra/backup" "$out/opt/"
rm -f "$out/opt/compose/compose.dev.yml" "$out/opt/compose/dev.env.example"
cp "$root/infra/bundle/install.sh" "$out/"
echo "$version" > "$out/VERSION"
(cd "$out" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
echo "paquet prêt : $out ($(du -sh "$out" | cut -f1))"
