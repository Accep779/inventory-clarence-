---
name: event_clearance_deployment
description: >-
  Framework for deploying automated clearance events through merchant-owned tools and platforms. Use when the user needs to: execute clearance campaigns, deploy event-driven sales, integrate with email/SMS platforms, build event landing pages, coordinate multi-channel clearance promotions, or automate clearance event workflows for e-commerce merchants.
---

# Event-Driven Clearance Deployment Framework

## Overview

Event-based clearance campaigns require coordinated asset generation across multiple merchant platforms. This framework defines how to generate deployable assets that merchants can execute using their existing tool stack.

## Merchant Tool Integration Categories

### Category 1: Email/SMS Platforms (Klaviyo, Postscript, etc.)
**Required Outputs:**
1. **Email Package**: Subject variants, body copy, segmentation logic (dormancy, legacy purchase), and CTA tracking.
2. **SMS Package**: 160-char text, UTM links, and frequency caps.

### Category 2: Landing Page Builders (Shopify, PageFly, etc.)
**Asset Generation**: Provide a JSON Schema structure for the builder (Hero section with countdown, UGC social proof, clearance product grid, tiered offer stack).

### Category 3: Paid Advertising Platforms (Meta, TikTok)
**Creative Asset Package:**
1. **UGC Scripts**: Hooks, problem/solution arcs, and shot lists.
2. **Ad Alpha**: Primary text, headlines, and interest categories for targeting.

### Category 4: Social Posting Tools (Buffer, Hootsuite)
**Post Package**: Platform-specific captions (IG/TikTok), story sequences, and scheduling logic (Teaser, Launch, Urgency, Recap).

## Multi-Agent Coordination Flow

### Agent Interaction Sequence
1. **Inventory Clearance Agent** -> Identifies SKUs/Waves.
2. **DB Reactivation Agent** -> Segments by propensity to convert.
3. **Event Generator Agent** -> Designs assets/timing.

## Implementation Checklist

**Pre-Event**: confirmed inventory sync, landing page schema, UGC scripts sent.
**Launch Day**: publish page, activate discounts, launch email 1, enable ads.
**Post-Event**: deactivate discounts, redirect page, analyze performance.

## Success Benchmarks

- **Email conversion**: 2-5%
- **Landing page conversion**: 3-8%
- **Ad ROAS**: 3x minimum
- **Inventory clearance**: 60-80% of targeted SKUs
