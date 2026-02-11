/**
 * Generated TypeScript Types from OpenAPI Schema
 * ==============================================
 *
 * This file is AUTO-GENERATED from the FastAPI OpenAPI schema.
 * DO NOT EDIT MANUALLY - Run `npm run generate-api` to regenerate.
 *
 * Generated from: schema.json
 * Generation tool: openapi-typescript
 *
 * Usage:
 *   import type { components, paths } from '@/lib/api/schema';
 *   type Product = components['schemas']['Product'];
 */

// Re-export from schema.types
export type { paths, components } from './schema.types';

// Common type exports for convenience  
export type Schema = import('./schema.types').components['schemas'];
