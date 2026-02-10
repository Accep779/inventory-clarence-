# Cephly API Client

Type-safe API client generated from FastAPI OpenAPI schema.

## Architecture

```
lib/api/
├── client.ts      # Typed API client with interceptors
├── schema.ts      # Generated TypeScript types (from OpenAPI)
├── schema.json    # Exported OpenAPI schema (source)
└── README.md      # This file
```

## Generation Workflow

The API client is auto-generated from the FastAPI backend:

1. **Export OpenAPI Schema** (from backend):
   ```bash
   cd backend && python scripts/export_openapi.py
   ```

2. **Generate TypeScript Types** (in frontend):
   ```bash
   cd frontend && npm run generate-api
   ```

3. **Full Pipeline** (both steps):
   ```bash
   npm run generate-api:schema
   ```

## Usage

### Basic Usage

```typescript
import { apiClient, api } from '@/lib/api/client';

// Using convenience methods
const { data: products, error } = await api.getProducts('merchant-id');

// Using the raw client for full control
const { data, error } = await apiClient.GET('/api/products', {
  params: { query: { merchant_id: 'xxx' } }
});
```

### Type Safety

All requests and responses are fully typed:

```typescript
import type { components } from '@/lib/api/client';

type Product = components['schemas']['Product'];
type Campaign = components['schemas']['Campaign'];
```

### Error Handling

```typescript
const { data, error } = await api.getInbox('merchant-id');

if (error) {
  // error is typed based on the endpoint's error responses
  console.error(error.message);
  return;
}

// data is typed based on the endpoint's success response
console.log(data.items);
```

## Regenerating

After backend API changes:

```bash
# From the project root
make generate-api

# Or manually:
cd backend && python scripts/export_openapi.py
cd ../frontend && npm run generate-api
```

## Authentication

The client automatically:
- Adds JWT token from `localStorage` to all requests
- Handles 401 responses by redirecting to auth
- Manages token cleanup on auth failure

## Migration from axios

Old (axios):
```typescript
import api from '@/lib/api';
const response = await api.get('/api/products?merchant_id=xxx');
```

New (openapi-fetch):
```typescript
import { api } from '@/lib/api/client';
const { data } = await api.getProducts('xxx');
```
