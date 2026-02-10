import React, { createContext, useContext, useState, useEffect } from 'react';
import { useRouter } from 'next/router';

interface AuthContextType {
  merchantId: string | null;
  token: string | null;
  setAuth: (merchantId: string, token: string) => void;
  logout: () => void;
  isLoading: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType>({
  merchantId: null,
  token: null,
  setAuth: () => {},
  logout: () => {},
  isLoading: true,
  isAuthenticated: false,
});

export function MerchantProvider({ children }: { children: React.ReactNode }) {
  const [merchantId, setMerchantId] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    // Check URL params first (from OAuth redirect)
    const urlMerchantId = router.query.merchant_id as string;
    const urlToken = router.query.token as string;
    
    if (urlToken && urlMerchantId) {
      // Store auth from OAuth callback
      setMerchantId(urlMerchantId);
      setToken(urlToken);
      localStorage.setItem('cephly_merchant_id', urlMerchantId);
      localStorage.setItem('cephly_token', urlToken);
      
      // Clean URL by removing sensitive query params
      const { merchant_id, token, ...cleanQuery } = router.query;
      router.replace({ pathname: router.pathname, query: cleanQuery }, undefined, { shallow: true });
      
      setIsLoading(false);
      return;
    }

    // Check localStorage for existing session
    const storedId = localStorage.getItem('cephly_merchant_id');
    const storedToken = localStorage.getItem('cephly_token');
    
    if (storedId && storedToken) {
      setMerchantId(storedId);
      setToken(storedToken);
    }
    setIsLoading(false);
  }, [router.query.merchant_id, router.query.token]);

  const setAuth = (id: string, authToken: string) => {
    setMerchantId(id);
    setToken(authToken);
    localStorage.setItem('cephly_merchant_id', id);
    localStorage.setItem('cephly_token', authToken);
  };

  const logout = () => {
    setMerchantId(null);
    setToken(null);
    localStorage.removeItem('cephly_merchant_id');
    localStorage.removeItem('cephly_token');
  };

  return (
    <AuthContext.Provider value={{ 
      merchantId, 
      token, 
      setAuth, 
      logout, 
      isLoading,
      isAuthenticated: !!token 
    }}>
      {children}
    </AuthContext.Provider>
  );
}

// Backward compatible export
export function useMerchant() {
  const { merchantId, isLoading, setAuth } = useContext(AuthContext);
  
  // Provide backward compatible setMerchantId that stores with empty token
  const setMerchantId = (id: string) => {
    // For backward compat - just set merchant ID without token (won't work for auth)
    // This should be replaced with proper auth flow
    localStorage.setItem('cephly_merchant_id', id);
  };
  
  return { merchantId, isLoading, setMerchantId };
}

// New auth hook
export function useAuth() {
  return useContext(AuthContext);
}
