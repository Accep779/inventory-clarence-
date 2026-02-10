#!/bin/bash
#
# Generate TypeScript API Client from FastAPI OpenAPI Schema
#
# Usage:
#   ./scripts/generate-api-client.sh
#   ./scripts/generate-api-client.sh --watch
#

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Generating Cephly API Client...${NC}"

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Step 1: Export OpenAPI schema from backend
echo -e "${BLUE}📦 Step 1: Exporting OpenAPI schema...${NC}"
cd backend

# Check if we have a running backend or need to generate statically
if curl -s http://localhost:8000/openapi.json > /dev/null; then
    echo -e "${GREEN}✓ Backend running, fetching schema from API${NC}"
    curl -s http://localhost:8000/openapi.json > ../frontend/lib/api/schema.json
else
    echo -e "${YELLOW}⚠ Backend not running, generating schema statically${NC}"
    python scripts/export_openapi.py --output ../frontend/lib/api/schema.json
fi

cd ..

# Step 2: Generate TypeScript types
echo -e "${BLUE}📝 Step 2: Generating TypeScript types...${NC}"
cd frontend

# Check if openapi-typescript is installed
if ! npx openapi-typescript --version > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ openapi-typescript not found, installing...${NC}"
    npm install --save-dev openapi-typescript
fi

# Generate types
npx openapi-typescript lib/api/schema.json --output lib/api/schema.ts

echo -e "${GREEN}✅ API client generated successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Generated files:${NC}"
echo "  - frontend/lib/api/schema.json (OpenAPI schema)"
echo "  - frontend/lib/api/schema.ts (TypeScript types)"
echo "  - frontend/lib/api/client.ts (API client)"
echo ""
echo -e "${BLUE}🚀 Usage:${NC}"
echo "  import { api, apiClient } from '@/lib/api/client';"
