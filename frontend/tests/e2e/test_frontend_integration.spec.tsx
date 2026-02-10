import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '@/lib/api';
// Import Pages
import ScanPage from '../../pages/scan';
import InboxPage from '../../pages/inbox';
import ProductsPage from '../../pages/inventory';
import CustomersPage from '../../pages/customers';
import CampaignsPage from '../../pages/campaigns';
import SettingsPage from '../../pages/settings';

// Mocks for Next.js router
const mockPush = jest.fn();
jest.mock('next/router', () => ({
  useRouter() {
    return {
      push: mockPush,
      pathname: '/',
      route: '/',
      asPath: '/',
      query: {},
    };
  },
}));

// Mock components to avoid deep rendering issues if necessary,
// but for integration we prefer real components.
// However, we might need to mock API calls.
// Since we don't have a real backend during these tests, we mock fetch/axios/react-query.

// Mock React Query
jest.mock('@tanstack/react-query', () => ({
  useQuery: jest.fn(),
  useMutation: jest.fn(),
  useQueryClient: jest.fn(() => ({
    invalidateQueries: jest.fn(),
    setQueryData: jest.fn(),
  })),
}));

// Mock API
jest.mock('@/lib/api', () => ({
  defaults: { baseURL: 'http://localhost:8000/api' },
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
}));

// Mock API declaration
jest.mock('@/lib/api', () => ({
  defaults: { baseURL: 'http://localhost:8000/api' },
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
}));

// Mock Contexts
jest.mock('@/lib/context/MerchantContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    merchantId: 'test-merchant',
    token: 'test-token',
    logout: jest.fn(),
  }),
  useMerchant: () => ({
    merchantId: 'test-merchant',
    isLoading: false,
    setMerchantId: jest.fn(),
  })
}));

jest.mock('@/lib/context/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'glass',
    setTheme: jest.fn(),
    toggleTheme: jest.fn(),
  })
}));

jest.mock('@/lib/context/LayoutContext', () => ({
  useLayout: () => ({
    isAgentStreamOpen: false,
    toggleAgentStream: jest.fn(),
    setAgentStreamOpen: jest.fn(),
  })
}));

// Mock Contexts
// ... mocks ...

// Mocks start here
// ...

// --- Part 1: API Integration Completeness Check ---

describe('Frontend Integration Tests', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        mockPush.mockClear();
    });

    // 1. Authentication & Onboarding
    describe('Authentication & Onboarding', () => {
        test('Onboarding scan real-time updates (SSE)', async () => {
            // Mock fetch for session check and scan start
            global.fetch = jest.fn((url) => {
                if (url.toString().includes('auth/me')) {
                     return Promise.resolve({
                         ok: true,
                         json: () => Promise.resolve({ id: 'test-merchant' })
                     } as Response);
                }
                if (url.toString().includes('scan/quick-start')) {
                     return Promise.resolve({
                         ok: true,
                         json: () => Promise.resolve({ session_id: 'test-session' })
                     } as Response);
                }
                return Promise.resolve({ ok: false } as Response);
            });

            await act(async () => {
                render(<ScanPage />);
            });
            
            // Allow effects to run
            await waitFor(() => {
                 expect(screen.getByText(/Scanning Your Inventory/i)).toBeInTheDocument();
            });
        });
    });

    // 2. Inbox & Proposals
    describe('Inbox & Proposals', () => {
        test('Inbox renders proposals correctly', async () => {
             const mockProposalsResponse = {
                data: {
                    items: [
                        { 
                            id: '1', 
                            type: 'clearance_proposal', 
                            status: 'pending', 
                            agent_type: 'Observer',
                            proposal_data: {
                                title: 'Flash Sale Proposal', 
                                risk_level: 'moderate', 
                                reasoning: 'ObserverAgent detected excess stock',
                                description: 'Test description'
                            },
                            created_at: new Date().toISOString() 
                        },
                        { 
                            id: '2', 
                            type: 'reactivation', 
                            status: 'pending', 
                            agent_type: 'Strategy', 
                            proposal_data: {
                                title: 'Reactivation Campaign', 
                                risk_level: 'high', 
                                reasoning: 'High churn risk',
                                description: 'Test description'
                            },
                            created_at: new Date().toISOString() 
                        }
                    ],
                    pending_count: 2
                }
             };

             (api.get as jest.Mock).mockResolvedValue(mockProposalsResponse);

             await act(async () => {
                 render(<InboxPage />);
             });
             
             // Check if proposals are rendered
             await waitFor(() => {
                 expect(screen.getByText('Flash Sale Proposal')).toBeInTheDocument();
                 expect(screen.getByText('Reactivation Campaign')).toBeInTheDocument();
             });
        });
    });

    // 3. Products & Dead Stock
    describe('Products & Dead Stock', () => {
        test('Product list shows dead stock indicators', async () => {
            const mockProductsResponse = {
                data: {
                    products: [
                        { id: '1', title: 'Product A', sku: 'SKU-A', is_dead_stock: true, dead_stock_severity: 'critical', velocity_score: 0.1, total_inventory: 100, inventory_value: 1000 },
                        { id: '2', title: 'Product B', sku: 'SKU-B', is_dead_stock: false, velocity_score: 0.9, total_inventory: 50, inventory_value: 500 }
                    ],
                    total: 2,
                    dead_stock_count: 1
                }
            };

            (api.get as jest.Mock).mockResolvedValue(mockProductsResponse);

            await act(async () => {
                render(<ProductsPage />);
            });
            
            await waitFor(() => {
                expect(screen.getByText('Product A')).toBeInTheDocument();
                // Check for potential dead stock visual indicators
                expect(screen.getByText('critical Priority')).toBeInTheDocument();
            });
        });
    });
    
    // 4. Customers & RFM Segmentation
    describe('Customers & RFM Segmentation', () => {
        test('RFM segments render', async () => {
             const mockStatsResponse = {
                data: {
                   total_reachable: 1000,
                   at_risk_count: 50,
                   recovered_count: 20,
                   neural_lift: '5%'
                }
             };
             // Mock needs to handle sequential calls if page makes multiple
             // or check the URL
             (api.get as jest.Mock).mockImplementation((url) => {
                 if (url.includes('stats')) return Promise.resolve(mockStatsResponse);
                 if (url.includes('journeys')) return Promise.resolve({ data: [] });
                 return Promise.resolve({ data: {} });
             });

             await act(async () => {
                 render(<CustomersPage />);
             });
             
             await waitFor(() => {
                 expect(screen.getByText('Customer Relations')).toBeInTheDocument();
                 expect(screen.getByText('1,000')).toBeInTheDocument(); // Formatted number
             });
        });
    });

    // 5. Campaigns
    describe('Campaigns', () => {
         test('Campaign list shows status', async () => {
             const mockCampaignsResponse = {
                 data: {
                     campaigns: [
                         { 
                             id: 1, 
                             name: 'Winter Sale', 
                             status: 'active', 
                             type: 'Email',
                             revenue: 5000,
                             emails_sent: 1000,
                             sms_sent: 0
                         }
                     ],
                     total_revenue: 5000,
                     active_count: 1,
                     total_spend: 100
                 }
             };
             
             (api.get as jest.Mock).mockResolvedValue(mockCampaignsResponse);
             
             await act(async () => {
                render(<CampaignsPage />);
             });
             
             await waitFor(() => {
                 expect(screen.getByText('Winter Sale')).toBeInTheDocument();
             });
         });
    });

    // 6. Store DNA & Settings
    describe('Store DNA & Settings', () => {
        test('Settings page renders DNA and Safety components', async () => {
             await act(async () => {
                render(<SettingsPage />);
             });
             
             // Use getAllByText because it might appear in the nav and the header/content
             const dnaElements = screen.getAllByText(/Store DNA/i);
             expect(dnaElements.length).toBeGreaterThan(0);
             
             // Click on Security tab
             const securityTab = screen.getByText(/Security & Access/i);
             await act(async () => {
                 fireEvent.click(securityTab);
             });
             
             expect(screen.getByText('System Control')).toBeInTheDocument();
        });
    });

    // 7. Safety & Kill Switch
    describe('Safety & Kill Switch', () => {
         test('Kill switch interaction', async () => {
             render(<SettingsPage />);
             
             const securityTab = screen.getByText('Security & Access');
             fireEvent.click(securityTab);
             
             // Assuming there's a kill switch button or toggle
             // We might need to look for specific text or aria-label
             // expect(screen.getByText(/Emergency Stop/i)).toBeInTheDocument();
         });
    });
});
