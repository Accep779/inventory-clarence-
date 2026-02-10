# Observer Agent: Clustering Algorithm & Caching Specification

**Version**: 1.0 **Status**: Implemented / Needs Hardening with Cache
**Implementation**: `app.services.clustering.InventoryClusteringService`

---

## 1. Algorithm Design

The Observer agent uses a **Hybrid Clustering** approach to reduce token costs
by ~100x (O(10,000) products → O(50) clusters).

### Feature Vectors

We combine two types of features:

1. **Numerical Features (40% Weight)**: Normalized via `StandardScaler`.
   - `price`: Unit price.
   - `inventory`: Quantity on hand.
   - `velocity_score`: Proprietary 0-100 score.
   - `days_since_last_sale`: Recency metric.

2. **Semantic Features (60% Weight)**: Embedded via `all-MiniLM-L6-v2`.
   - Input: `"{product_title} {product_type}"` (e.g., "Vintage Blue Denim Jacket
     Outerwear").
   - Output: 384-dimensional dense vector.

### Clustering Method

- **Method**: K-Means Clustering (`sklearn.cluster.KMeans`).
- **Cluster Count**: Dynamic, defaulting to `sqrt(n_products / 2)` or capped at
  50 to fit LLM context window.
- **Initialization**: `k-means++` for efficiency.

---

## 2. Caching Strategy (The Token Saver)

**CRITICAL IMPLEMENTATION DETAIL**: The current implementation lacks this layer,
making it expensive.

### Cache Key Construction

```python
cache_key = f"merch:{merchant_id}:clustering:{date_str}"
# e.g., "merch:123:clustering:2026-01-25"
```

### Flow

1. **Check Redis**: `GET {cache_key}`
   - If Hit: Return JSON summary immediately (0 tokens, 0 compute).
2. **On Miss**:
   - Run K-Means (CPU intensive).
   - Generate Summaries (Aggregations).
   - `SETEX {cache_key} 86400 {json_summary}` (24 hour TTL).

---

## 3. Fallback Logic

If `sklearn` or `SentenceTransformer` fails (e.g., memory OOM on small worker):

1. **Metric-Only Grouping**: Fallback to simple bucketing by `Velocity Score`
   (High/Med/Low).
2. **No-Ops**: If < 10 products, skip clustering and analyze individually.
