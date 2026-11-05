// Docker Bake file for building and pushing the OpenSAMPL server images
// (backend + migrations) as multi-arch images tagged with both `latest`
// and the current opensampl package version.
//
// Usage:
//   docker buildx bake -f docker-bake.hcl --push
//
// Override the registry or version if needed:
//   REGISTRY=myregistry.example.com/opensampl OPENSAMPL_VERSION=1.2.1 \
//     docker buildx bake -f docker-bake.hcl --push

variable "REGISTRY" {
  default = "savannah.ornl.gov/opensampl"
}

// Read the version straight out of the repo's pyproject.toml so the bake
// file never drifts from the package version.
variable "OPENSAMPL_VERSION" {
  default = "1.2.4"
}

variable "PLATFORMS" {
  default = ["linux/amd64", "linux/arm64"]
}

// Directory containing a locally built opensampl wheel (`uv build --wheel`).
// If it holds no wheel the images install OPENSAMPL_VERSION from PyPI.
variable "WHEEL_DIR" {
  default = "../../dist"
}

group "default" {
  targets = ["db", "backend", "grafana", "migrations"]
}

target "db" {
  context   = "./db"
  platforms = PLATFORMS
  tags = [
    "${REGISTRY}/db:latest",
    "${REGISTRY}/db:${OPENSAMPL_VERSION}",
  ]
}

target "grafana" {
  context   = "./grafana"
  platforms = PLATFORMS
  tags = [
    "${REGISTRY}/grafana:latest",
    "${REGISTRY}/grafana:${OPENSAMPL_VERSION}",
  ]
}

target "backend" {
  context    = "./backend"
  dockerfile = "Dockerfile"
  target     = "prod"
  contexts   = { wheel = WHEEL_DIR }
  platforms  = PLATFORMS
  args = {
    OPENSAMPL_VERSION = OPENSAMPL_VERSION
  }
  tags = [
    "${REGISTRY}/backend:latest",
    "${REGISTRY}/backend:${OPENSAMPL_VERSION}",
  ]
}

target "migrations" {
  context    = "./migrations"
  dockerfile = "Dockerfile"
  contexts   = { wheel = WHEEL_DIR }
  platforms  = PLATFORMS
  args = {
    OPENSAMPL_VERSION = OPENSAMPL_VERSION
  }
  tags = [
    "${REGISTRY}/migrations:latest",
    "${REGISTRY}/migrations:${OPENSAMPL_VERSION}",
  ]
}
