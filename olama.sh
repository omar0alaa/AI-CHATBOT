

docker network create ollama-net;

docker-compose -f olama.yml up -d;

docker exec -d ollama ollama run gemma3:1b