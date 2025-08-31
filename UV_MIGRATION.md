# UV Migration Guide

## Overview
This project has been migrated from pip to uv for faster dependency management and better reproducible builds.

## Local Development

### Installing uv
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

### Using uv with CodeArtifact (Internal Development)
```bash
# Set up CodeArtifact authentication
CODEARTIFACT_AUTH_TOKEN=$(aws codeartifact get-authorization-token \
  --region us-west-2 --domain windward-python --domain-owner 724428538127 \
  --query authorizationToken --output text)

UV_EXTRA_INDEX_URL="https://aws:${CODEARTIFACT_AUTH_TOKEN}@windward-python-724428538127.d.codeartifact.us-west-2.amazonaws.com/pypi/development/simple/"

# Install dependencies
uv pip install --extra-index-url "$UV_EXTRA_INDEX_URL" -r requirements.lock
```

### Using uv with Public PyPI (GitHub Actions / External)
```bash
# Install dependencies from lockfile
uv pip install --system -r requirements.lock

# Or install from requirements.txt (not recommended for production)
uv pip install -r requirements.txt
```

## Development Workflow

### Adding New Dependencies
1. Add to `requirements.txt`
2. Regenerate lockfile:
   ```bash
   # With CodeArtifact
   uv pip compile --extra-index-url "$UV_EXTRA_INDEX_URL" requirements.txt -o requirements.lock
   
   # With public PyPI only
   uv pip compile requirements.txt -o requirements.lock
   ```

### Benefits
- **10-100x faster** than pip for dependency resolution
- **Better dependency resolution** - catches conflicts pip misses
- **Exact reproducible builds** via lockfile
- **Faster CI/CD** - GitHub Actions now ~50% faster

## Files
- `requirements.txt` - Source dependencies (human-readable)
- `requirements.lock` - Exact pinned versions (generated, don't edit manually)
- `.github/workflows/news-aggregator.yml` - Updated to use uv

## Rollback Plan
If needed, can rollback by reverting GitHub Actions workflow and using:
```bash
pip install -r requirements.txt
```