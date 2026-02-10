-- =============================================================================
-- Cephly Multi-Agents Database Migrations
-- =============================================================================
-- 
-- This file contains all SQL migrations for setting up the database schema.
-- Compatible with PostgreSQL / Supabase.
--
-- Run these in order when setting up a new database.
--
-- Last updated: 2026-01-20
-- =============================================================================


-- =============================================================================
-- MIGRATION 001: Core Tables
-- =============================================================================

-- Merchants Table
CREATE TABLE merchants (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    shopify_domain VARCHAR(255) UNIQUE NOT NULL,
    shopify_shop_id VARCHAR(255) UNIQUE NOT NULL,
    access_token TEXT NOT NULL,
    store_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    
    -- Subscription
    plan VARCHAR(50) DEFAULT 'trial',
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Agent Settings
    max_auto_discount NUMERIC(5, 2) DEFAULT 0.40,
    max_auto_ad_spend NUMERIC(10, 2) DEFAULT 500.00,
    
    -- Governor Settings
    governor_aggressive_mode BOOLEAN DEFAULT FALSE,
    governor_calibration_threshold INTEGER DEFAULT 50,
    governor_trust_threshold NUMERIC(5, 2) DEFAULT 0.95,
    
    -- DNA Status
    dna_status VARCHAR(20) DEFAULT 'pending',
    
    -- Integration Credentials (per-tenant)
    klaviyo_api_key TEXT,
    twilio_account_sid VARCHAR(255),
    twilio_auth_token TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_merchant_domain ON merchants(shopify_domain);


-- Products Table
CREATE TABLE products (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    shopify_product_id BIGINT NOT NULL,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    -- Basic Info
    title TEXT NOT NULL,
    handle VARCHAR(255) NOT NULL,
    product_type VARCHAR(255),
    vendor VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    
    -- Inventory
    total_inventory INTEGER DEFAULT 0,
    variant_count INTEGER DEFAULT 0,
    
    -- Sales Velocity
    units_sold_30d INTEGER DEFAULT 0,
    units_sold_60d INTEGER DEFAULT 0,
    units_sold_90d INTEGER DEFAULT 0,
    revenue_30d NUMERIC(10, 2) DEFAULT 0.00,
    last_sale_date TIMESTAMP,
    
    -- Dead Stock Classification
    velocity_score NUMERIC(5, 2),
    is_dead_stock BOOLEAN DEFAULT FALSE,
    dead_stock_severity VARCHAR(20),
    days_since_last_sale INTEGER,
    
    -- Cost Tracking
    cost_per_unit NUMERIC(10, 2),
    holding_cost_per_day NUMERIC(10, 2),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    published_at TIMESTAMP
);

CREATE INDEX idx_product_merchant_dead ON products(merchant_id, is_dead_stock);
CREATE INDEX idx_product_velocity ON products(velocity_score);
CREATE INDEX idx_product_last_sale ON products(last_sale_date);


-- Product Variants Table
CREATE TABLE product_variants (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    shopify_variant_id BIGINT UNIQUE NOT NULL,
    product_id VARCHAR(36) NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    
    title VARCHAR(255) NOT NULL,
    sku VARCHAR(255),
    price NUMERIC(10, 2) NOT NULL,
    compare_at_price NUMERIC(10, 2),
    inventory_quantity INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_variant_product ON product_variants(product_id);


-- Customers Table
CREATE TABLE customers (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    shopify_customer_id BIGINT NOT NULL,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    -- Contact Info
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    phone VARCHAR(50),
    
    -- RFM Scoring
    recency_score INTEGER,
    frequency_score INTEGER,
    monetary_score INTEGER,
    rfm_segment VARCHAR(50),
    
    -- Purchase Behavior
    total_orders INTEGER DEFAULT 0,
    total_spent NUMERIC(10, 2) DEFAULT 0.00,
    last_order_date TIMESTAMP,
    avg_order_value NUMERIC(10, 2),
    
    -- Engagement Preferences
    email_optin BOOLEAN DEFAULT FALSE,
    sms_optin BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_customer_merchant_segment ON customers(merchant_id, rfm_segment);
CREATE INDEX idx_customer_last_order ON customers(last_order_date);


-- Orders Table
CREATE TABLE orders (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    shopify_order_id BIGINT UNIQUE NOT NULL,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    customer_id VARCHAR(36) REFERENCES customers(id),
    
    order_number VARCHAR(50) NOT NULL,
    total_price NUMERIC(10, 2) NOT NULL,
    subtotal_price NUMERIC(10, 2) NOT NULL,
    total_tax NUMERIC(10, 2) DEFAULT 0.00,
    
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_order_merchant_date ON orders(merchant_id, created_at);
CREATE INDEX idx_order_customer ON orders(customer_id);


-- Order Items Table
CREATE TABLE order_items (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    order_id VARCHAR(36) NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id VARCHAR(36) REFERENCES products(id),
    
    quantity INTEGER NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_orderitem_order ON order_items(order_id);
CREATE INDEX idx_orderitem_product ON order_items(product_id);


-- Inbox Items Table (Agent Proposals)
CREATE TABLE inbox_items (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    proposal_data JSONB NOT NULL,
    
    risk_level VARCHAR(20) DEFAULT 'low',
    agent_type VARCHAR(50) NOT NULL,
    confidence NUMERIC(5, 2),
    
    viewed_at TIMESTAMP,
    decided_at TIMESTAMP,
    executed_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_inbox_merchant_status ON inbox_items(merchant_id, status);
CREATE INDEX idx_inbox_created ON inbox_items(created_at);


-- Audit Logs Table
CREATE TABLE audit_logs (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    user_id VARCHAR(255),
    
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(36) NOT NULL,
    
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);


-- Campaigns Table
CREATE TABLE campaigns (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    
    target_segments JSONB,
    product_ids JSONB,
    
    emails_sent INTEGER DEFAULT 0,
    emails_opened INTEGER DEFAULT 0,
    emails_clicked INTEGER DEFAULT 0,
    sms_sent INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    revenue NUMERIC(10, 2) DEFAULT 0.00,
    
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_campaign_merchant_status ON campaigns(merchant_id, status);


-- LLM Usage Logs Table
CREATE TABLE llm_usage_logs (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) REFERENCES merchants(id),
    
    provider VARCHAR(50),
    model VARCHAR(100),
    task_type VARCHAR(100),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10, 6),
    latency NUMERIC(10, 3),
    used_fallback BOOLEAN DEFAULT FALSE,
    metadata_json JSONB,
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- Ledger Entries Table (Financial Attribution)
CREATE TABLE ledger_entries (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    order_id VARCHAR(255) UNIQUE NOT NULL,
    gross_amount NUMERIC(10, 2) NOT NULL,
    net_amount NUMERIC(10, 2) NOT NULL,
    agent_stake NUMERIC(10, 2) NOT NULL,
    attribution_source VARCHAR(255),
    currency VARCHAR(10) DEFAULT 'USD',
    raw_data JSONB,
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- Store DNA Table
CREATE TABLE store_dna (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    -- Financial DNA
    aov_p50 NUMERIC(10, 2) DEFAULT 0.00,
    aov_p90 NUMERIC(10, 2) DEFAULT 0.00,
    total_revenue_30d NUMERIC(12, 2) DEFAULT 0.00,
    
    -- Creative DNA
    brand_tone VARCHAR(50) DEFAULT 'Modern',
    industry_type VARCHAR(50) DEFAULT 'Retail',
    brand_values JSONB DEFAULT '[]',
    
    -- Brand Guide
    brand_guide_raw TEXT,
    brand_guide_parsed JSONB,
    
    -- URL Scraping
    scraped_homepage_meta JSONB,
    scraped_about_content TEXT,
    scraped_at TIMESTAMP,
    
    -- Identity
    identity_description TEXT,
    
    -- Metadata
    last_analyzed_at TIMESTAMP DEFAULT NOW(),
    raw_discovery_snapshot JSONB
);


-- Floor Pricing Table
CREATE TABLE floor_pricing (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    sku VARCHAR(255),
    shopify_product_id BIGINT,
    product_id VARCHAR(36) REFERENCES products(id),
    
    cost_price NUMERIC(10, 2) NOT NULL,
    min_margin_pct NUMERIC(5, 2),
    floor_price NUMERIC(10, 2),
    liquidation_mode BOOLEAN DEFAULT FALSE,
    
    notes TEXT,
    source VARCHAR(50) DEFAULT 'csv_upload',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_floor_pricing_merchant ON floor_pricing(merchant_id);
CREATE INDEX idx_floor_pricing_sku ON floor_pricing(sku);


-- Commercial Journeys Table (Reactivation)
CREATE TABLE commercial_journeys (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    
    journey_type VARCHAR(50) DEFAULT 'reactivation',
    status VARCHAR(20) DEFAULT 'active',
    current_touch INTEGER DEFAULT 1,
    
    next_touch_due_at TIMESTAMP DEFAULT NOW(),
    last_touch_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);


-- Audit trail for every communication dispatched.
CREATE TABLE IF NOT EXISTS touch_logs (
    id VARCHAR(36) PRIMARY KEY,
    journey_id VARCHAR(36) REFERENCES commercial_journeys(id) ON DELETE CASCADE,
    campaign_id VARCHAR(36) REFERENCES campaigns(id) ON DELETE CASCADE,
    customer_id VARCHAR(36) REFERENCES customers(id) ON DELETE CASCADE,
    external_id VARCHAR(100),
    
    touch_stage INTEGER DEFAULT 1,
    channel VARCHAR(20) NOT NULL,
    sent_content TEXT,
    status VARCHAR(20) DEFAULT 'sent',
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_touch_log_external ON touch_logs(external_id);
CREATE INDEX IF NOT EXISTS idx_touch_log_campaign ON touch_logs(campaign_id);


-- Global Strategy Patterns Table
CREATE TABLE global_strategy_patterns (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    
    industry_type VARCHAR(50) NOT NULL,
    skill_name VARCHAR(50) NOT NULL,
    strategy_type VARCHAR(50) DEFAULT 'conservative',
    
    avg_discount_p50 NUMERIC(10, 2) DEFAULT 0.00,
    avg_lift_p50 NUMERIC(10, 2) DEFAULT 0.00,
    avg_roi_p50 NUMERIC(10, 2) DEFAULT 0.00,
    
    sample_size INTEGER DEFAULT 0,
    confidence_score NUMERIC(5, 2) DEFAULT 0.00,
    last_updated TIMESTAMP DEFAULT NOW()
);


-- Global Strategy Templates Table
CREATE TABLE global_strategy_templates (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    
    name VARCHAR(255) NOT NULL,
    description TEXT,
    industry_type VARCHAR(50),
    skill_name VARCHAR(50),
    
    recommended_discount NUMERIC(5, 2),
    expected_lift NUMERIC(5, 2)
);


-- Agent Thoughts Table
CREATE TABLE agent_thoughts (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    agent_type VARCHAR(50) NOT NULL,
    execution_id VARCHAR(36),
    
    thought_type VARCHAR(50),
    summary TEXT NOT NULL,
    detailed_reasoning JSONB,
    
    confidence_score NUMERIC(5, 2) DEFAULT 1.00,
    step_number INTEGER DEFAULT 1,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_thought_merchant_agent ON agent_thoughts(merchant_id, agent_type);
CREATE INDEX idx_thought_execution ON agent_thoughts(execution_id);
CREATE INDEX idx_thought_created ON agent_thoughts(created_at);


-- =============================================================================
-- MIGRATION 002: Security Updates (2026-01-20)
-- =============================================================================
-- Run this if upgrading from an earlier schema version

-- Add per-tenant integration credentials
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS klaviyo_api_key TEXT;
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS twilio_account_sid VARCHAR(255);
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS twilio_auth_token TEXT;



-- =============================================================================
-- MIGRATION 003: Auth0 Identity Patterns (2026-01-20)
-- =============================================================================

-- Token Vault Table (Encrypted Credential Storage)
CREATE TABLE token_vault (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    provider VARCHAR(50) NOT NULL,
    connection_name VARCHAR(100),
    
    -- Encrypted Storage
    access_token_encrypted TEXT NOT NULL,
    refresh_token_encrypted TEXT,
    token_type VARCHAR(50) DEFAULT 'bearer',
    
    -- Lifecycle
    expires_at TIMESTAMP,
    refresh_expires_at TIMESTAMP,
    last_refreshed_at TIMESTAMP,
    
    -- Scopes
    scopes_granted JSONB,
    scopes_requested JSONB,
    
    -- Status & Retry Logic
    status VARCHAR(20) DEFAULT 'active',
    last_error TEXT,
    retry_attempts INTEGER DEFAULT 0,
    max_retry_attempts INTEGER DEFAULT 3,
    retry_backoff_seconds INTEGER DEFAULT 60,
    next_retry_at TIMESTAMP,
    permanent_failure_at TIMESTAMP,
    merchant_notified_of_failure BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_token_vault_merchant_provider ON token_vault(merchant_id, provider);
CREATE INDEX idx_token_vault_status ON token_vault(status);


-- Async Authorization Requests (CIBA - Push Auth)
CREATE TABLE async_auth_requests (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    auth_req_id VARCHAR(100) UNIQUE NOT NULL,
    inbox_item_id VARCHAR(36) REFERENCES inbox_items(id),
    
    -- Context
    agent_type VARCHAR(50) NOT NULL,
    operation_type VARCHAR(100) NOT NULL,
    authorization_details JSONB NOT NULL,
    
    -- Lifecycle
    status VARCHAR(20) DEFAULT 'pending',
    expires_at TIMESTAMP NOT NULL,
    decided_at TIMESTAMP,
    decision_channel VARCHAR(50),
    
    -- Notifications
    push_sent_at TIMESTAMP,
    sms_sent_at TIMESTAMP,
    email_sent_at TIMESTAMP,
    reminder_sent_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_async_auth_merchant ON async_auth_requests(merchant_id);
CREATE INDEX idx_async_auth_status ON async_auth_requests(status);
CREATE INDEX idx_async_auth_inbox ON async_auth_requests(inbox_item_id);


-- Merchant Scope Grants (Fine-Grained Authorization)
CREATE TABLE merchant_scope_grants (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    agent_type VARCHAR(50) NOT NULL,
    scope VARCHAR(100) NOT NULL,
    
    granted_at TIMESTAMP DEFAULT NOW(),
    granted_by VARCHAR(36),
    
    conditions JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    revoked_at TIMESTAMP,
    revoked_by VARCHAR(36),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scope_grant_merchant_agent ON merchant_scope_grants(merchant_id, agent_type);
CREATE INDEX idx_scope_grant_scope ON merchant_scope_grants(scope);


-- Agent Clients (Machine-to-Machine Identity)
CREATE TABLE agent_clients (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    client_id VARCHAR(100) UNIQUE NOT NULL,
    client_secret_hash VARCHAR(255) NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    
    allowed_scopes JSONB,
    
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_client_merchant ON agent_clients(merchant_id);
CREATE INDEX idx_agent_client_client_id ON agent_clients(client_id);


-- Audit Log Enhancements (Actor & Context)
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS actor_type VARCHAR(20) DEFAULT 'system';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS actor_agent_type VARCHAR(50);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS delegated_by VARCHAR(36);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS client_id VARCHAR(100);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS authorization_id VARCHAR(100);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS scopes_used JSONB;



-- ============================================================================
-- MIGRATION 005: Onboarding Reliability (Day 0 Fixes)
-- ============================================================================

-- Add sync_status to track initial data synchronization state
-- Values: 'pending', 'syncing', 'completed', 'failed'
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS sync_status VARCHAR(20) DEFAULT 'pending';

-- Add phone number capture for SMS CIBA fallback
-- Captured from Shopify Shop Resource during OAuth
ALTER TABLE merchants ADD COLUMN IF NOT EXISTS phone VARCHAR(20);

-- Ensure we can index by status for performance
CREATE INDEX IF NOT EXISTS idx_merchant_sync_status ON merchants(sync_status);

-- ============================================================================
-- MIGRATION 006: Campaign Content Snapshot (World Class Learning)
-- ============================================================================

-- Add content_snapshot to store the actual email/SMS copy sent
-- Enables the AI to "read" past successful campaigns and match tone.
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS content_snapshot JSONB;

-- ============================================================================
-- MIGRATION 007: Tier 1 Intelligence Engines (2026-01-20)
-- ============================================================================

-- Governor Risk Policies (#1)
CREATE TABLE governor_risk_policies (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    agent_type VARCHAR(50) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    risk_level VARCHAR(20) NOT NULL, -- low, moderate, high, critical
    
    requires_approval BOOLEAN DEFAULT TRUE,
    min_confidence NUMERIC(5, 4) DEFAULT 0.95,
    min_trust_score NUMERIC(5, 4) DEFAULT 0.90,
    
    last_updated TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_risk_policy_agent ON governor_risk_policies(agent_type, risk_level);

-- Merchant Journeys & SMART Goals (#3)
CREATE TABLE merchant_journeys (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merchant_id VARCHAR(36) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    
    title VARCHAR(255) NOT NULL,
    journey_type VARCHAR(50) NOT NULL,
    
    target_metric VARCHAR(50) NOT NULL,
    target_value NUMERIC(12, 2) NOT NULL,
    current_value NUMERIC(12, 2) DEFAULT 0.00,
    
    deadline_at TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_merchant_journey_merchant ON merchant_journeys(merchant_id, status);

-- Global Brain Strategy Patterns (#2)
-- Upgrading the draft table to match implementation
DROP TABLE IF EXISTS global_strategy_patterns;
CREATE TABLE global_strategy_patterns (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    
    pattern_key VARCHAR(255) NOT NULL,
    industry_type VARCHAR(50),
    strategy_key VARCHAR(50) NOT NULL,
    
    p50_conversion NUMERIC(10, 4) DEFAULT 0.0000,
    p90_conversion NUMERIC(10, 4) DEFAULT 0.0000,
    avg_roi_p50 NUMERIC(10, 2) DEFAULT 0.00,
    recommendation_score FLOAT DEFAULT 0.0,
    
    context_criteria JSONB, 
    last_updated TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_global_pattern_key ON global_strategy_patterns(pattern_key);


-- =============================================================================
-- MIGRATION 008: Security - Touch Log Tenant Isolation (2026-01-21)
-- =============================================================================
-- Adds merchant_id to touch_logs for proper tenant isolation
-- Required for multi-tenant security

ALTER TABLE touch_logs ADD COLUMN IF NOT EXISTS merchant_id VARCHAR(36) REFERENCES merchants(id) ON DELETE CASCADE;

-- For existing data, backfill merchant_id from the linked campaign
UPDATE touch_logs tl
SET merchant_id = c.merchant_id
FROM campaigns c
WHERE tl.campaign_id = c.id AND tl.merchant_id IS NULL;

-- Make it required after backfill (new installs will have it from the start)
-- ALTER TABLE touch_logs ALTER COLUMN merchant_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_touch_log_merchant ON touch_logs(merchant_id);


-- =============================================================================
-- MIGRATION 009: Data Integrity Improvements (2026-01-21)
-- =============================================================================

-- Fix OrderItem->Product FK to preserve order history on product deletion
ALTER TABLE order_items 
DROP CONSTRAINT IF EXISTS order_items_product_id_fkey;

ALTER TABLE order_items 
ADD CONSTRAINT order_items_product_id_fkey 
FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL;

-- Add unique constraint to prevent duplicate pending proposals for same product
CREATE UNIQUE INDEX IF NOT EXISTS idx_inbox_pending_product 
ON inbox_items(merchant_id, (proposal_data->>'product_id'))
WHERE status = 'pending';


-- =============================================================================
-- MIGRATION 010: Optimistic Locking & Soft Delete (2026-01-21)
-- =============================================================================

-- Products: version for optimistic locking, deleted_at for soft delete
ALTER TABLE products ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE products ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

-- Index for soft delete filtering
CREATE INDEX IF NOT EXISTS idx_product_deleted ON products(deleted_at) WHERE deleted_at IS NULL;

-- InboxItems: version for optimistic locking
ALTER TABLE inbox_items ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
