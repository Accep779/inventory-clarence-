# app/services/clustering.py
import logging
import json
import hashlib
from datetime import datetime
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sentence_transformers import SentenceTransformer

from app.redis import get_redis_client

logger = logging.getLogger(__name__)

class InventoryClusteringService:
    """
    Groups high-volume inventory into manageable clusters.
    Uses K-Means for statistical clustering and SentenceTransformers for semantic grouping.
    
    [HARDENED]: Implements Redis Caching (24h TTL) to prevent expensive re-calculation.
    """
    
    CACHE_TTL = 86400  # 24 hours
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.redis = get_redis_client()
        # Lazy load model to save memory if not needed
        self._embedding_model = None

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            logger.info("loading sentence-transformer model...")
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._embedding_model

    async def cluster_inventory(self, products: List[Dict[str, Any]], n_clusters: int = 5) -> List[Dict[str, Any]]:
        """
        Groups products into clusters based on:
        1. Numerical: Price, Inventory, Velocity Score, Days Since Last Sale
        2. Semantic: Product Title, Category
        """
        if not products or len(products) < n_clusters:
            logger.warning(f"Not enough products ({len(products)}) to form {n_clusters} clusters.")
            return []

        # 0. CACHE CHECK
        # Create a stable cache key based on merchant + date + product count
        # (This avoids re-clustering the same inventory on the same day)
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        cache_key = f"merch:{self.merchant_id}:clustering:{date_str}:{len(products)}"
        
        cached_data = self.redis.get(cache_key)
        if cached_data:
            try:
                logger.info(f"⚡ [Observer] Cache Hit for Clustering ({len(products)} items)")
                return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Cache decode failed: {e}")

        logger.info(f"🐢 [Observer] Cache Miss. Running Clustering on {len(products)} items...")

        df = pd.DataFrame(products)
        
        # 1. Statistical Features
        numerical_features = ['price', 'inventory', 'velocity_score', 'days_since_last_sale']
        # Handle potential missing keys from dicts
        for feat in numerical_features:
            if feat not in df.columns:
                df[feat] = 0.0
        
        X_num = df[numerical_features].fillna(0).values
        scaler = StandardScaler()
        X_num_scaled = scaler.fit_transform(X_num)

        # 2. Semantic Features (LSI)
        titles = df['title'].fillna('').astype(str).tolist()
        categories = df['product_type'].fillna('').astype(str).tolist()
        text_data = [f"{t} {c}" for t, c in zip(titles, categories)]
        
        embeddings = self.embedding_model.encode(text_data)
        
        # Combine numerical and semantic
        # Weighting: 40% Numerical, 60% Semantic for better "meaningful" clusters
        X_combined = np.hstack([X_num_scaled * 0.4, embeddings * 0.6])

        # 3. K-Means
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
        df['cluster'] = kmeans.fit_predict(X_combined)

        # 4. Summarize Clusters
        summaries = []
        for i in range(n_clusters):
            cluster_data = df[df['cluster'] == i]
            
            # Identify "Thematic Label" via top keywords or most common category
            top_category = cluster_data['product_type'].mode().iloc[0] if not cluster_data['product_type'].mode().empty else "General"
            
            summary = {
                "cluster_id": i,
                "label": f"Cluster {i}: {top_category}",
                "item_count": len(cluster_data),
                "avg_price": round(cluster_data['price'].mean(), 2),
                "total_inventory": int(cluster_data['inventory'].sum()),
                "avg_velocity": round(cluster_data['velocity_score'].mean(), 1),
                "avg_days_since_sale": int(cluster_data['days_since_last_sale'].mean()),
                # "total_stuck_value": round((cluster_data['price'] * cluster_data['inventory']).sum(), 2), # Avoid float issues
                "sample_titles": cluster_data['title'].head(3).tolist(),
                # "top_categories": cluster_data['product_type'].value_counts().head(2).to_dict() # Serialize dict issues
            }
            # Float serialization safety
            summary["avg_price"] = float(summary["avg_price"])
            summaries.append(summary)

        # 5. CACHE WRITE
        try:
            self.redis.setex(cache_key, self.CACHE_TTL, json.dumps(summaries))
            logger.info(f"💾 [Observer] Clustering results cached (TTL: 24h)")
        except Exception as e:
            logger.error(f"Failed to write cache: {e}")

        return summaries

    def generate_llm_prompt_fragment(self, summaries: List[Dict[str, Any]]) -> str:
        """
        Converts cluster summaries into a concise string for LLM prompts.
        This is the "DNA Compression" for the inventory body.
        """
        parts = ["## Inventory Cluster Summaries"]
        for s in summaries:
            parts.append(
                f"- **{s['label']}** ({s['item_count']} items)\n"
                f"  - Financials: Avg Price ${s['avg_price']}\n"
                f"  - Risk: Avg Velocity {s['avg_velocity']}/100, {s['avg_days_since_sale']} days since sale\n"
                f"  - Themes: {', '.join(s['sample_titles'])}..."
            )
        return "\n".join(parts)
