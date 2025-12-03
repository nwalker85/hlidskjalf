ui = true

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true  # TLS handled by nginx proxy
}

storage "file" {
  path = "/openbao/data"
}

api_addr = "http://0.0.0.0:8200"
cluster_addr = "http://0.0.0.0:8201"

# Dev-friendly settings
disable_mlock = true
log_level = "info"
