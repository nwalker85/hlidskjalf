#!/usr/bin/env python3
"""
Add Traefik labels to docker-compose.yml services for autodiscovery
"""

import yaml
import sys

# Service mappings for Traefik routes
service_mappings = {
    'grafana': 'grafana.observe.ravenhelm.test',
    'langfuse': 'langfuse.observe.ravenhelm.test',
    'phoenix': 'phoenix.observe.ravenhelm.test',
    'redpanda-console': 'events.ravenhelm.test',
    'openbao': 'vault.ravenhelm.test',
    'n8n': 'n8n.ravenhelm.test',
    'hlidskjalf-ui': 'hlidskjalf.ravenhelm.test'
}

# Service port mappings
service_ports = {
    'grafana': 3000,
    'langfuse': 3000,
    'phoenix': 6006,
    'redpanda-console': 8080,
    'openbao': 8200,
    'n8n': 5678,
    'hlidskjalf-ui': 3900
}

def add_traefik_labels(service_name, host, port):
    """Generate Traefik labels for a service"""
    labels = [
        "traefik.enable=true",
        f"traefik.http.routers.{service_name}.rule=Host(`{host}`)",
        f"traefik.http.routers.{service_name}.tls=true",
        f"traefik.http.routers.{service_name}.entrypoints=websecure",
        f"traefik.http.services.{service_name}.loadbalancer.server.port={port}",
        f"traefik.http.routers.{service_name}.middlewares=secure-headers@file",
        "traefik.docker.network=edge"
    ]
    return labels

def update_compose_file():
    """Update docker-compose.yml with Traefik labels"""
    
    # Read the current compose file
    with open('docker-compose.yml', 'r') as f:
        content = f.read()
    
    # Process each service
    lines = content.split('\n')
    updated_lines = []
    in_service = None
    service_indent = None
    
    for line in lines:
        updated_lines.append(line)
        
        # Check if we're starting a service definition
        if line.strip().endswith(':') and not line.startswith(' ') and not line.startswith('#'):
            potential_service = line.strip().rstrip(':')
            if potential_service in service_mappings:
                in_service = potential_service
                service_indent = len(line) - len(line.lstrip())
                print(f"Found service: {in_service}")
        
        # Add labels after ports section for targeted services
        if in_service and 'ports:' in line and service_indent is not None:
            # Find the end of the ports section
            continue
        
        # Add labels before networks section
        if in_service and line.strip().startswith('networks:') and service_indent is not None:
            # Add labels before networks
            labels_indent = ' ' * (service_indent + 2)
            updated_lines.insert(-1, f"{labels_indent}labels:")
            
            for label in add_traefik_labels(in_service, service_mappings[in_service], service_ports[in_service]):
                updated_lines.insert(-1, f"{labels_indent}  - \"{label}\"")
            
            print(f"Added labels for {in_service}")
            
            # Also add edge network
            updated_lines.append(line)  # Add the networks: line
            updated_lines.append(f"{labels_indent}  - platform_net")
            updated_lines.append(f"{labels_indent}  - edge")
            in_service = None
            continue
    
    # Write the updated content
    with open('docker-compose.yml', 'w') as f:
        f.write('\n'.join(updated_lines))
    
    print("Updated docker-compose.yml with Traefik labels")

if __name__ == "__main__":
    update_compose_file()