"""
Add audit indexes and IntegrationCredential table

Revision ID: add_audit_indexes_and_integration_credential
Revises: cb9b9614736a
Create Date: 2025-02-08

This migration:
1. Adds comprehensive indexes to audit_logs table
2. Creates integration_credentials table
3. Removes deprecated JSON columns from merchants
4. Adds missing indexes to existing tables
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = 'add_audit_indexes_and_integration_credential'
down_revision = 'cb9b9614736a'
branch_labels = None
depends_on = None


def upgrade():
    # =========================================================================
    # 1. Add indexes to audit_logs table
    # =========================================================================
    op.create_index(
        'idx_audit_merchant_created',
        'audit_logs',
        ['merchant_id', 'created_at']
    )
    op.create_index(
        'idx_audit_entity',
        'audit_logs',
        ['entity_type', 'entity_id']
    )
    op.create_index(
        'idx_audit_action_type',
        'audit_logs',
        ['action', 'entity_type']
    )
    op.create_index(
        'idx_audit_actor',
        'audit_logs',
        ['actor_type', 'actor_agent_type']
    )
    op.create_index(
        'idx_audit_created',
        'audit_logs',
        ['created_at']
    )

    # =========================================================================
    # 2. Create integration_credentials table
    # =========================================================================
    op.create_table(
        'integration_credentials',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('merchant_id', sa.String(36), sa.ForeignKey('merchants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('channel_type', sa.String(50), nullable=False),
        sa.Column('channel_name', sa.String(100)),
        sa.Column('environment', sa.String(20), default='production'),
        sa.Column('api_key_encrypted', sa.Text()),
        sa.Column('api_secret_encrypted', sa.Text()),
        sa.Column('access_token_encrypted', sa.Text()),
        sa.Column('refresh_token_encrypted', sa.Text()),
        sa.Column('token_expires_at', sa.DateTime()),
        sa.Column('scopes', postgresql.JSONB()),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('last_error', sa.Text()),
        sa.Column('last_used_at', sa.DateTime()),
        sa.Column('config', postgresql.JSONB(), default={}),
        sa.Column('excluded_categories', postgresql.JSONB(), default=[]),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Add indexes for integration_credentials
    op.create_index(
        'idx_integration_cred_merchant_channel',
        'integration_credentials',
        ['merchant_id', 'channel_type']
    )
    op.create_index(
        'idx_integration_cred_status',
        'integration_credentials',
        ['status']
    )

    # =========================================================================
    # 3. Add missing indexes to existing tables
    # =========================================================================

    # Add index on orders for merchant + created_at (common time-series query)
    op.create_index(
        'idx_order_merchant_date',
        'orders',
        ['merchant_id', 'created_at']
    )

    # Add index on products for dead stock queries
    op.create_index(
        'idx_product_merchant_status',
        'products',
        ['merchant_id', 'status']
    )

    # Add index on campaigns for status filtering
    op.create_index(
        'idx_campaign_merchant_status',
        'campaigns',
        ['merchant_id', 'status']
    )

    # Add index on inbox_items for status filtering
    op.create_index(
        'idx_inbox_merchant_status',
        'inbox_items',
        ['merchant_id', 'status']
    )

    # Add index on agent_thoughts for execution tracing
    op.create_index(
        'idx_thought_execution',
        'agent_thoughts',
        ['execution_id']
    )

    # Add index on campaigns for execution tracing
    op.create_index(
        'idx_campaign_execution',
        'campaigns',
        ['origin_execution_id']
    )

    # =========================================================================
    # 4. Add platform_shop_id to merchants (replaces platform_context JSON)
    # =========================================================================
    op.add_column(
        'merchants',
        sa.Column('platform_shop_id', sa.String(100))
    )

    # =========================================================================
    # 5. Mark deprecated columns (we keep them for backward compatibility)
    # =========================================================================
    # Note: We don't drop the JSON columns immediately to allow for data migration
    # They will be removed in a future migration after data is migrated


def downgrade():
    # Remove integration_credentials table
    op.drop_table('integration_credentials')

    # Remove audit indexes
    op.drop_index('idx_audit_merchant_created', 'audit_logs')
    op.drop_index('idx_audit_entity', 'audit_logs')
    op.drop_index('idx_audit_action_type', 'audit_logs')
    op.drop_index('idx_audit_actor', 'audit_logs')
    op.drop_index('idx_audit_created', 'audit_logs')

    # Remove added indexes
    op.drop_index('idx_order_merchant_date', 'orders')
    op.drop_index('idx_product_merchant_status', 'products')
    op.drop_index('idx_campaign_merchant_status', 'campaigns')
    op.drop_index('idx_inbox_merchant_status', 'inbox_items')
    op.drop_index('idx_thought_execution', 'agent_thoughts')
    op.drop_index('idx_campaign_execution', 'campaigns')

    # Remove platform_shop_id column
    op.drop_column('merchants', 'platform_shop_id')
