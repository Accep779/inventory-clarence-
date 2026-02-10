"""
Cephly Scopes
=============

Fine-grained authorization scopes for Cephly operations.
Implements Auth0 pattern for scope-based access control.

Features:
- Scope taxonomy following OAuth2 naming conventions
- Per-agent default scope sets
- Dynamic scope resolution for discount tiers
- Scope validation utilities
"""

from typing import List, Set


class CephlyScopes:
    """
    Scope definitions for Cephly agent operations.
    Follows OAuth2 scope naming conventions (resource:action).
    """
    
    # =========================================================================
    # INVENTORY OPERATIONS
    # =========================================================================
    INVENTORY_READ = "inventory:read"
    INVENTORY_WRITE = "inventory:write"
    INVENTORY_PRICE_SUGGEST = "inventory:price:suggest"
    INVENTORY_PRICE_APPLY = "inventory:price:apply"
    
    # =========================================================================
    # CAMPAIGN OPERATIONS
    # =========================================================================
    CAMPAIGNS_READ = "campaigns:read"
    CAMPAIGNS_CREATE = "campaigns:create"
    CAMPAIGNS_EXECUTE = "campaigns:execute"
    CAMPAIGNS_DELETE = "campaigns:delete"
    
    # =========================================================================
    # CUSTOMER OPERATIONS
    # =========================================================================
    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_SEGMENT = "customers:segment"
    CUSTOMERS_MESSAGE = "customers:message"
    
    # =========================================================================
    # COMMUNICATION OPERATIONS
    # =========================================================================
    MESSAGING_EMAIL = "messaging:email"
    MESSAGING_SMS = "messaging:sms"
    
    # =========================================================================
    # FINANCIAL OPERATIONS
    # =========================================================================
    PRICING_READ = "pricing:read"
    PRICING_SUGGEST = "pricing:suggest"
    PRICING_APPLY = "pricing:apply"
    DISCOUNTS_LOW = "discounts:low"           # Up to 20%
    DISCOUNTS_MODERATE = "discounts:moderate" # 20-40%
    DISCOUNTS_HIGH = "discounts:high"         # 40%+
    
    # =========================================================================
    # ALL SCOPES (for reference)
    # =========================================================================
    ALL_SCOPES = {
        INVENTORY_READ, INVENTORY_WRITE, INVENTORY_PRICE_SUGGEST, INVENTORY_PRICE_APPLY,
        CAMPAIGNS_READ, CAMPAIGNS_CREATE, CAMPAIGNS_EXECUTE, CAMPAIGNS_DELETE,
        CUSTOMERS_READ, CUSTOMERS_SEGMENT, CUSTOMERS_MESSAGE,
        MESSAGING_EMAIL, MESSAGING_SMS,
        PRICING_READ, PRICING_SUGGEST, PRICING_APPLY,
        DISCOUNTS_LOW, DISCOUNTS_MODERATE, DISCOUNTS_HIGH
    }
    
    # =========================================================================
    # DEFAULT SCOPE SETS PER AGENT TYPE
    # =========================================================================
    AGENT_SCOPES = {
        "observer": {
            INVENTORY_READ,
            CUSTOMERS_READ,
        },
        "strategy": {
            INVENTORY_READ,
            CUSTOMERS_READ,
            CAMPAIGNS_CREATE,
            PRICING_SUGGEST,
            DISCOUNTS_LOW,
            DISCOUNTS_MODERATE,
        },
        "execution": {
            CAMPAIGNS_READ,
            CAMPAIGNS_EXECUTE,
            MESSAGING_EMAIL,
            MESSAGING_SMS,
            PRICING_APPLY,
        },
        "reactivation": {
            CUSTOMERS_READ,
            CUSTOMERS_SEGMENT,
            CUSTOMERS_MESSAGE,
            MESSAGING_EMAIL,
            MESSAGING_SMS,
        },
    }
    
    # =========================================================================
    # SCOPE RESOLUTION HELPERS
    # =========================================================================
    
    @staticmethod
    def get_required_discount_scope(discount_pct: float) -> str:
        """
        Determine which discount scope is required for a given discount percentage.
        
        Args:
            discount_pct: Discount as a decimal (e.g., 0.35 for 35%)
            
        Returns:
            The required scope string
        """
        if discount_pct <= 0.20:
            return CephlyScopes.DISCOUNTS_LOW
        elif discount_pct <= 0.40:
            return CephlyScopes.DISCOUNTS_MODERATE
        else:
            return CephlyScopes.DISCOUNTS_HIGH
    
    @staticmethod
    def get_required_scopes_for_campaign(
        discount_pct: float, 
        has_sms: bool = False,
        has_email: bool = True
    ) -> List[str]:
        """
        Get all scopes required to execute a campaign.
        
        Args:
            discount_pct: Discount percentage as decimal
            has_sms: Whether campaign includes SMS
            has_email: Whether campaign includes email
            
        Returns:
            List of required scopes
        """
        scopes = [
            CephlyScopes.CAMPAIGNS_EXECUTE,
            CephlyScopes.PRICING_APPLY,
            CephlyScopes.get_required_discount_scope(discount_pct)
        ]
        
        if has_email:
            scopes.append(CephlyScopes.MESSAGING_EMAIL)
        
        if has_sms:
            scopes.append(CephlyScopes.MESSAGING_SMS)
        
        return scopes
    
    @staticmethod
    def get_default_scopes_for_agent(agent_type: str) -> Set[str]:
        """Get default scope set for an agent type."""
        return CephlyScopes.AGENT_SCOPES.get(agent_type, set())
    
    @staticmethod
    def validate_scopes(scopes: List[str]) -> tuple[bool, List[str]]:
        """
        Validate that all scopes are recognized.
        
        Returns:
            Tuple of (is_valid, invalid_scopes)
        """
        invalid = [s for s in scopes if s not in CephlyScopes.ALL_SCOPES]
        return len(invalid) == 0, invalid


# =============================================================================
# SCOPE UTILITIES
# =============================================================================

def check_scopes(
    required: List[str], 
    granted: List[str]
) -> tuple[bool, List[str]]:
    """
    Check if all required scopes are present in granted scopes.
    
    Args:
        required: List of required scopes
        granted: List of granted scopes
        
    Returns:
        Tuple of (is_authorized, missing_scopes)
    """
    required_set = set(required)
    granted_set = set(granted)
    
    missing = required_set - granted_set
    return len(missing) == 0, list(missing)


def scope_implies(parent_scope: str, child_scope: str) -> bool:
    """
    Check if a parent scope implies a child scope.
    
    E.g., discounts:high implies discounts:moderate implies discounts:low
    """
    # Discount hierarchy
    discount_hierarchy = [
        CephlyScopes.DISCOUNTS_LOW,
        CephlyScopes.DISCOUNTS_MODERATE,
        CephlyScopes.DISCOUNTS_HIGH
    ]
    
    if parent_scope in discount_hierarchy and child_scope in discount_hierarchy:
        return discount_hierarchy.index(parent_scope) >= discount_hierarchy.index(child_scope)
    
    return False
