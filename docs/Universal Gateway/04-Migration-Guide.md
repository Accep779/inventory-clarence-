# Universal Gateway: Migration Guide

How to move your existing Cephly Agents from "Hardcoded APIs" to the "Universal Gateway".

## 1. Updating the Agent Logic

**Before (Hardcoded Service Calls):**

```python
# app/agents/strategy.py

from app.services.email import EmailService

class StrategyAgent:
    async def execute(self, user):
        # ❌ Hard dependency on Email
        await EmailService.send(user.email, "Here is your plan")
```

**After (Gateway Pattern):**

```python
# app/agents/strategy.py

from app.services.gateway import GatewayService

class StrategyAgent:
    async def execute(self, user):
        # ✅ Channel Agnostic - just needs a "Session Key"
        # User object now has a primary_session_key property
        await GatewayService.send(user.primary_session_key, "Here is your plan")
```

## 2. Converting Existing Services

You currently have `EmailService` and `SMSService`. You will NOT delete them immediately. Instead, wrap them.

1.  **Create Wrapper:** Create `backend/app/channels/email_wrapper.py`.
2.  **Implement Protocol:** Make it implement `ChannelPlugin`.
3.  **Delegate:** inside `send_message()`, call the old `EmailService.send()`.

This allows a gradual migration.

## 3. Database Updates

You need to store `SessionKeys`.

**Migration SQL:**
```sql
ALTER TABLE customers ADD COLUMN primary_session_key VARCHAR(255);
-- Backfill existing data
UPDATE customers SET primary_session_key = 'email:' || email WHERE email IS NOT NULL;
```
