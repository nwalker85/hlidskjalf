#!/bin/bash
# Created by the Norns' guidance
networks=(
  "edge:10.0.10.0/24"
  "platform_net:10.10.0.0/24"
  "gitlab_net:10.20.0.0/24"
  "saaa_net:10.30.0.0/24"
  "m2c_net:10.40.0.0/24"
  "tinycrm_net:10.50.0.0/24"
)

for net in "${networks[@]}"; do
  name="${net%%:*}"
  subnet="${net##*:}"
  
  if ! docker network inspect "$name" >/dev/null 2>&1; then
    echo "✓ Creating network $name ($subnet)..."
    docker network create --driver bridge --subnet "$subnet" "$name"
  else
    echo "  Network $name already exists"
  fi
done

echo ""
echo "✅ All networks ready!"
