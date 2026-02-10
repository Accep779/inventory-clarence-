/**
 * Cephly API Client
 * =================
 *
 * Type-safe API client generated from FastAPI OpenAPI schema.
 *
 * This client is generated using openapi-typescript and openapi-fetch
 * for full type safety and auto-completion.
 *
 * Usage:
 *   import { apiClient } from '@/lib/api/client';
 *
 *   // GET request with typed response
 *   const { data, error } = await apiClient.GET('/api/products', {
 *     params: { query: { merchant_id: 'xxx' } }
 *   });
 *
 *   // POST request with typed body and response
 *   const { data, error } = await apiClient.POST('/api/inbox/{id}/approve', {
 *     params: { path: { id: 'xxx' } }
 *   });
 */

import createClient from 'openapi-fetch';
import type { paths, components } from './schema';

// Create the typed API client
const apiClient = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add JWT auth interceptor
apiClient.use({
  onRequest({ request }) {
    // Get token from localStorage (client-side only)
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('cephly_token');
      if (token) {
        request.headers.set('Authorization', `Bearer ${token}`);
      }
    }
    return request;
  },
  onResponse({ response }) {
    // Handle 401 unauthorized
    if (response.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('cephly_token');
        localStorage.removeItem('cephly_merchant_id');

        // Redirect to auth
        const shopDomain = localStorage.getItem('cephly_shop_domain') || 'demo.myshopify.com';
        window.location.href = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/auth/install?shop=${shopDomain}`;
      }
    }
    return response;
  },
});

// Export types for use in components
export type { paths, components };

// Export common types
export type Schema = components['schemas'];
export type Merchant = components['schemas']['Merchant'];
export type Product = components['schemas']['Product'];
export type Campaign = components['schemas']['Campaign'];
export type InboxItem = components['schemas']['InboxItem'];
export type AgentThought = components['schemas']['AgentThought'];

// Export the client
export { apiClient };

// Convenience wrapper for common operations
export const api = {
  // Health check
  async health() {
    return apiClient.GET('/health');
  },

  // Products
  async getProducts(merchantId: string) {
    return apiClient.GET('/api/products', {
      params: { query: { merchant_id: merchantId } },
    });
  },

  async getDeadStock(merchantId: string) {
    return apiClient.GET('/api/products/dead-stock-summary', {
      params: { query: { merchant_id: merchantId } },
    });
  },

  // Inbox
  async getInbox(merchantId: string) {
    return apiClient.GET('/api/inbox', {
      params: { query: { merchant_id: merchantId } },
    });
  },

  async approveInboxItem(id: string) {
    return apiClient.POST('/api/inbox/{id}/approve', {
      params: { path: { id } },
    });
  },

  async rejectInboxItem(id: string) {
    return apiClient.POST('/api/inbox/{id}/reject', {
      params: { path: { id } },
    });
  },

  // Campaigns
  async getCampaigns(merchantId: string) {
    return apiClient.GET('/api/campaigns', {
      params: { query: { merchant_id: merchantId } },
    });
  },

  // Strategy
  async generateStrategy(merchantId: string, productIds: string[]) {
    return apiClient.POST('/api/strategy/generate', {
      body: { merchant_id: merchantId, product_ids: productIds },
    });
  },

  // Agent Thoughts
  async getThoughts(merchantId: string) {
    return apiClient.GET('/api/thoughts', {
      params: { query: { merchant_id: merchantId } },
    });
  },

  // DNA
  async getStoreDNA(merchantId: string) {
    return apiClient.GET('/api/dna', {
      params: { query: { merchant_id: merchantId } },
    });
  },

  // Scan
  async quickScan(merchantId: string) {
    return apiClient.POST('/api/scan/quick', {
      body: { merchant_id: merchantId },
    });
  },
};
