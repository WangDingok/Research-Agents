import json
import os
import time
import statistics
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
from dotenv import load_dotenv

load_dotenv()

# ==================== CẤU HÌNH ====================
API_KEY = os.environ.get('ETSY_API_KEY')
BASE_URL = "https://openapi.etsy.com/v3/application/listings/active"
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_PROJECT_ROOT, "output", "etsy_data")
CHARTS_DIR = os.path.join(_PROJECT_ROOT, "public", "charts")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# Gộp các ID taxonomy của T-shirt lại
T_SHIRT_TAXONOMY_IDS = [449, 482, 559] # Women's, Men's, Unisex Adult's

class EtsyTrendAnalyzer:
    """
    Một lớp để tìm nạp, phân tích và trực quan hóa dữ liệu xu hướng từ Etsy,
    tập trung vào danh mục áo thun.
    """

    def __init__(self, api_key: str, data_dir: str = DATA_DIR):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.data_dir = data_dir
        self.taxonomy_ids = T_SHIRT_TAXONOMY_IDS
        if not self.api_key:
            raise ValueError("ETSY_API_KEY không được thiết lập trong môi trường.")
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_cache_filename(self, keywords: Optional[str], days_back: int) -> str:
        """Tạo tên file cache dựa trên keywords và số ngày."""
        keyword_str = "general"
        if keywords:
            keyword_str = keywords.replace(" ", "_").replace('"', '').lower()
        return os.path.join(self.data_dir, f"listings_tshirts_{keyword_str}_{days_back}days.json")

    def _fetch_listings(
        self,
        keywords: Optional[str] = None,
        days_back: int = 30,
        limit_per_request: int = 100,
        max_items: int = 100,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Lấy danh sách sản phẩm cho tất cả các taxonomy áo thun, gộp và loại bỏ trùng lặp.
        """
        cache_filename = self._get_cache_filename(keywords, days_back)

        if not force_refresh and os.path.exists(cache_filename):
            try:
                with open(cache_filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"Đã tải dữ liệu cache: {len(data.get('listings', []))} sản phẩm từ {cache_filename}")
                return data.get('listings', [])
            except Exception as e:
                print(f"Lỗi khi tải cache: {e}")

        all_listings_map = {}
        start_date = datetime.now() - timedelta(days=days_back)
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(datetime.now().timestamp())
        
        headers = {"x-api-key": self.api_key, "Accept": "application/json"}
        
        search_desc = "T-shirts"
        if keywords:
            search_desc += f" với từ khóa: '{keywords}'"
        
        print(f"\nĐang tìm nạp {search_desc} (trong {days_back} ngày qua)...")

        for tax_id in self.taxonomy_ids:
            offset = 0
            print(f"   - Đang quét taxonomy ID: {tax_id}")
            while True:
                if max_items and len(all_listings_map) >= max_items:
                    break

                params = {
                    "taxonomy_id": tax_id,
                    "limit": min(limit_per_request, 100),
                    "offset": offset,
                    "created_min": start_timestamp,
                    "created_max": end_timestamp,
                }
                if keywords:
                    params["keywords"] = keywords

                try:
                    response = requests.get(self.base_url, headers=headers, params=params)
                    if response.status_code == 429:
                        retry_after = int(response.headers.get('retry-after', 5))
                        print(f"Đã đạt giới hạn request. Đang chờ {retry_after}s...")
                        time.sleep(retry_after)
                        continue
                    
                    response.raise_for_status()
                    data = response.json()
                    results = data.get("results", [])
                    
                    if not results:
                        break
                    
                    for listing in results:
                        all_listings_map[listing['listing_id']] = listing
                    
                    print(f"     Page {offset//limit_per_request + 1}: +{len(results)} sản phẩm (Tổng cộng duy nhất: {len(all_listings_map)})")

                    if len(results) < limit_per_request:
                        break
                    
                    offset += limit_per_request
                    time.sleep(0.5)

                except requests.exceptions.RequestException as e:
                    print(f"Lỗi: {e}")
                    break
        
        all_listings = list(all_listings_map.values())
        print(f"Hoàn tất: {len(all_listings)} sản phẩm duy nhất được tìm thấy.")

        if all_listings:
            cache_data = {
                "cached_date": datetime.now().isoformat(),
                "keywords": keywords,
                "days_back": days_back,
                "listings": all_listings,
            }
            with open(cache_filename, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            print(f"Đã lưu vào cache: {cache_filename}")
        
        return all_listings

    def _get_top_listings(self, listings: List[Dict], keyword: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """Extract top N listings by favorites, then enrich with images/shop via individual API calls."""
        if not listings:
            return []

        # Pre-sort by favorites to find top candidates
        sorted_listings = sorted(listings, key=lambda x: x.get('num_favorers', 0) or 0, reverse=True)
        top_candidates = sorted_listings[:top_n]

        headers = {"x-api-key": self.api_key, "Accept": "application/json"}
        result = []

        for item in top_candidates:
            listing_id = item.get('listing_id')
            price_raw = item.get('price', {})
            price_val = price_raw.get('amount', 0) / 100 if isinstance(price_raw, dict) else 0

            image_url = ""
            shop_name = ""

            # Fetch individual listing with Images + Shop includes
            if listing_id:
                try:
                    resp = requests.get(
                        f"https://openapi.etsy.com/v3/application/listings/{listing_id}",
                        headers=headers,
                        params={"includes": "Images,Shop"},
                    )
                    if resp.status_code == 200:
                        detail = resp.json()
                        images = detail.get("images", [])
                        if images:
                            image_url = images[0].get("url_570xN", images[0].get("url_170x135", ""))
                        shop = detail.get("shop", {})
                        shop_name = shop.get("shop_name", "")
                    time.sleep(0.5)  # rate limiting
                except Exception:
                    pass

            listing_url = item.get('url', f"https://www.etsy.com/listing/{listing_id}")

            result.append({
                'title': (item.get('title') or '')[:80],
                'price': round(price_val, 2),
                'favorites': int(item.get('num_favorers', 0) or 0),
                'views': int(item.get('views', 0) or 0),
                'image_url': image_url,
                'shop_name': shop_name,
                'url': listing_url,
                'listing_id': listing_id,
            })

        return result

    # ── General market discovery dashboard (no keywords) ────────────

    def _generate_general_dashboard(self, listings: List[Dict], analysis: Dict[str, Any], days_back: int) -> List[str]:
        """Create a professional 2-page discovery dashboard for general T-shirt market."""
        if not listings or len(listings) < 10:
            return []

        import numpy as np

        df = pd.DataFrame(listings)
        df['price'] = df['price'].apply(lambda p: p.get('amount', 0) / 100 if isinstance(p, dict) else 0)
        df['favorites'] = pd.to_numeric(df.get('num_favorers', pd.Series(dtype='int')), errors='coerce').fillna(0).astype(int)
        df['views'] = pd.to_numeric(df.get('views', pd.Series(dtype='int')), errors='coerce').fillna(0).astype(int)
        if 'creation_timestamp' in df.columns:
            df['creation_date'] = pd.to_datetime(df['creation_timestamp'], unit='s', errors='coerce')
        else:
            df['creation_date'] = pd.NaT

        sns.set_theme(style="whitegrid")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chart_paths = []

        # ═══════════════ PAGE 1: Market Overview ═══════════════
        fig, axes = plt.subplots(2, 3, figsize=(22, 14))
        fig.suptitle(
            f"Etsy T-Shirt Market Discovery — Tổng quan {days_back} ngày\n"
            f"({len(df)} sản phẩm · Engagement: {analysis.get('engagement_score', 0)} · Fav/View: {analysis.get('fav_view_rate_pct', 0)}%)",
            fontsize=16, fontweight='bold', y=1.01
        )

        # ── 1. Top 20 Tags: Trending niches ──
        ax = axes[0, 0]
        all_tags = [tag for tags_list in df['tags'].dropna() for tag in tags_list]
        top_tags = Counter(all_tags).most_common(20)
        if top_tags:
            tag_names = [t[0] for t in top_tags][::-1]
            tag_counts = [t[1] for t in top_tags][::-1]
            colors = sns.color_palette("viridis", len(tag_names))
            bars = ax.barh(tag_names, tag_counts, color=colors, edgecolor='white')
            ax.bar_label(bars, fmt='%d', padding=3, fontsize=8)
        ax.set_title("Top 20 Tags\n(Niche nào sellers tập trung?)", fontsize=12, fontweight='bold')
        ax.set_xlabel("Số lần xuất hiện")

        # ── 2. Price Distribution ──
        ax = axes[0, 1]
        price_data = df['price'][df['price'] > 0]
        if len(price_data) > 0:
            q99 = price_data.quantile(0.99)
            price_clipped = price_data[price_data <= q99]
            ax.hist(price_clipped, bins=40, color='#4C72B0', edgecolor='white', alpha=0.85)
            median_p = price_data.median()
            mean_p = price_data.mean()
            ax.axvline(median_p, color='#C44E52', linestyle='--', linewidth=2, label=f'Median: ${median_p:.1f}')
            ax.axvline(mean_p, color='#DD8452', linestyle=':', linewidth=2, label=f'Mean: ${mean_p:.1f}')
            ax.legend(fontsize=9)
        ax.set_title("Phân phối giá ($)\n(Vùng giá nào phổ biến?)", fontsize=12, fontweight='bold')
        ax.set_xlabel("Giá ($)")
        ax.set_ylabel("Số sản phẩm")

        # ── 3. Seller Concentration: Cạnh tranh tập trung hay phân tán? ──
        ax = axes[0, 2]
        if 'shop_id' in df.columns:
            shop_counts = df['shop_id'].value_counts()
            total_shops = len(shop_counts)
            top5_shops = shop_counts.head(5)
            top5_pct = top5_shops.sum() / len(df) * 100
            top10_pct = shop_counts.head(10).sum() / len(df) * 100
            rest_pct = 100 - top10_pct

            pie_sizes = [top5_pct, top10_pct - top5_pct, rest_pct]
            pie_labels = [f'Top 5 shops\n({top5_pct:.0f}%)', f'Top 6-10\n({top10_pct - top5_pct:.0f}%)', f'Còn lại ({total_shops - 10}+ shops)\n({rest_pct:.0f}%)']
            pie_colors = ['#C44E52', '#DD8452', '#55A868']
            wedges, texts, autotexts = ax.pie(
                [max(s, 0) for s in pie_sizes], labels=pie_labels, colors=pie_colors,
                autopct='', startangle=90, textprops={'fontsize': 9}
            )
            ax.set_title(f"Phân bố seller ({total_shops} shops)\n(Thị trường tập trung hay phân tán?)", fontsize=12, fontweight='bold')
        else:
            ax.text(0.5, 0.5, 'Không có dữ liệu shop', ha='center', va='center', fontsize=12)
            ax.set_title("Phân bố seller", fontsize=12, fontweight='bold')

        # ── 4. Competition Level: Favorites breakdown ──
        ax = axes[1, 0]
        fav_data = df['favorites']
        if len(fav_data) > 10:
            fav_bins = [0, 1, 5, 20, 50, 100, float('inf')]
            fav_labels = ['0 Fav\n(mới)', '1-5\n(thấp)', '5-20\n(TB)', '20-50\n(tốt)', '50-100\n(hot)', '100+\n(viral)']
            fav_cats = pd.cut(fav_data, bins=fav_bins, labels=fav_labels, right=False)
            fav_dist = fav_cats.value_counts().reindex(fav_labels).fillna(0)
            total = len(fav_data)
            pct = (fav_dist / total * 100).round(1)

            bar_colors = ['#8172B2', '#4C72B0', '#55A868', '#DD8452', '#C44E52', '#D65F5F']
            bars = ax.bar(range(len(fav_dist)), fav_dist.values, color=bar_colors, edgecolor='white')
            for i, (v, p) in enumerate(zip(fav_dist.values, pct.values)):
                ax.text(i, v + total * 0.01, f'{int(v)}\n({p}%)', ha='center', va='bottom', fontsize=8, fontweight='bold')
            ax.set_xticks(range(len(fav_labels)))
            ax.set_xticklabels(fav_labels, fontsize=9)
            ax.set_ylabel("Số sản phẩm")
        ax.set_title("Mức độ cạnh tranh\n(Bao nhiêu SP đã có nhiều Fav?)", fontsize=12, fontweight='bold')

        # ── 5. Price Segments Performance ──
        ax = axes[1, 1]
        price_valid = df[df['price'] > 0].copy()
        if len(price_valid) > 10:
            bins = [0, 10, 20, 30, 50, 100, float('inf')]
            labels = ['<$10', '$10-20', '$20-30', '$30-50', '$50-100', '$100+']
            price_valid['price_segment'] = pd.cut(price_valid['price'], bins=bins, labels=labels)
            seg_stats = price_valid.groupby('price_segment', observed=True).agg(
                count=('price', 'size'),
                avg_fav=('favorites', 'mean'),
                avg_views=('views', 'mean'),
            ).reset_index()

            x = np.arange(len(seg_stats))
            w = 0.35
            bars1 = ax.bar(x - w/2, seg_stats['count'], w, label='Số SP', color='#4C72B0', alpha=0.85)
            ax.bar_label(bars1, fmt='%d', fontsize=8, padding=2)
            ax2 = ax.twinx()
            bars2 = ax2.bar(x + w/2, seg_stats['avg_fav'], w, label='Avg Favorites', color='#DD8452', alpha=0.85)
            ax2.bar_label(bars2, fmt='%.1f', fontsize=8, padding=2)
            ax.set_xticks(x)
            ax.set_xticklabels(seg_stats['price_segment'], rotation=30)
            ax.set_ylabel("Số sản phẩm", color='#4C72B0')
            ax2.set_ylabel("Avg Favorites", color='#DD8452')
            lines1, labels1 = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc='upper right')
        ax.set_title("Phân khúc giá: Lượng SP vs Hiệu suất\n(Vùng giá nào ít cạnh tranh + nhiều Fav?)", fontsize=12, fontweight='bold')

        # ── 6. Tag Co-occurrence: Rising niches ──
        ax = axes[1, 2]
        if len(df) > 20:
            fav_threshold = df['favorites'].quantile(0.8)
            top_df = df[df['favorites'] >= max(fav_threshold, 1)]
            rest_df = df[df['favorites'] < max(fav_threshold, 1)]

            top_tags_set = Counter([tag for tags_list in top_df['tags'].dropna() for tag in tags_list])
            rest_tags_set = Counter([tag for tags_list in rest_df['tags'].dropna() for tag in tags_list])

            tag_success = {}
            for tag, top_count in top_tags_set.items():
                total_count = top_count + rest_tags_set.get(tag, 0)
                if total_count >= 5:
                    tag_success[tag] = (top_count / total_count) * 100

            if tag_success:
                sorted_tags = sorted(tag_success.items(), key=lambda x: x[1], reverse=True)[:15]
                t_names = [t[0] for t in sorted_tags][::-1]
                t_rates = [t[1] for t in sorted_tags][::-1]
                colors = ['#55A868' if r >= 50 else '#DD8452' if r >= 30 else '#8172B2' for r in t_rates]
                bars = ax.barh(t_names, t_rates, color=colors, edgecolor='white')
                ax.bar_label(bars, fmt='%.0f%%', padding=3, fontsize=8)
                ax.axvline(50, color='gray', linestyle='--', alpha=0.5, linewidth=1)
        ax.set_title("Tags \"thành công\" cao\n(% xuất hiện ở SP top 20% Favorites)", fontsize=12, fontweight='bold')
        ax.set_xlabel("Tỷ lệ thành công (%)")

        plt.tight_layout()
        fp = os.path.join(CHARTS_DIR, f"general_market_overview_{timestamp}.png")
        fig.savefig(fp, bbox_inches="tight", dpi=120)
        plt.close(fig)
        chart_paths.append(fp)
        print(f"Đã tạo general market overview: {fp}")

        return chart_paths

    # ── Per-keyword dashboard (single keyword) ────────────

    def _generate_keyword_dashboard(self, listings: List[Dict], keyword: str, analysis: Dict[str, Any]) -> Optional[str]:
        """Create a single-keyword market dashboard (2x2 layout)."""
        if not listings or len(listings) < 5:
            return None

        import numpy as np

        df = pd.DataFrame(listings)
        df['price'] = df['price'].apply(lambda p: p.get('amount', 0) / 100 if isinstance(p, dict) else 0)
        df['favorites'] = pd.to_numeric(df.get('num_favorers', pd.Series(dtype='int')), errors='coerce').fillna(0).astype(int)
        df['views'] = pd.to_numeric(df.get('views', pd.Series(dtype='int')), errors='coerce').fillna(0).astype(int)

        sns.set_theme(style="whitegrid")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_kw = keyword.replace(" ", "_").replace("/", "_")[:30]

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f"Etsy Market Dashboard — \"{keyword}\"\n({analysis.get('total_listings', 0)} sản phẩm · Engagement: {analysis.get('engagement_score', 0)} · Fav/View: {analysis.get('fav_view_rate_pct', 0)}%)",
                     fontsize=15, fontweight='bold', y=1.01)

        palette = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]

        # ── 1. Price Distribution ──
        ax = axes[0, 0]
        price_data = df['price'][df['price'] > 0]
        if len(price_data) > 0:
            q99 = price_data.quantile(0.99)
            price_clipped = price_data[price_data <= q99]
            ax.hist(price_clipped, bins=30, color=palette[0], edgecolor='white', alpha=0.85)
            median_price = price_data.median()
            ax.axvline(median_price, color='#C44E52', linestyle='--', linewidth=2, label=f'Median: ${median_price:.1f}')
            ax.legend(fontsize=10)
        ax.set_title("Phân phối giá ($)", fontsize=13, fontweight='bold')
        ax.set_xlabel("Giá ($)")
        ax.set_ylabel("Số sản phẩm")

        # ── 2. Favorites Distribution ──
        ax = axes[0, 1]
        fav_data = df['favorites']
        if fav_data.sum() > 0:
            q99 = fav_data.quantile(0.99) if fav_data.quantile(0.99) > 0 else fav_data.max()
            fav_clipped = fav_data[fav_data <= q99]
            ax.hist(fav_clipped, bins=30, color=palette[1], edgecolor='white', alpha=0.85)
            median_fav = fav_data.median()
            ax.axvline(median_fav, color='#C44E52', linestyle='--', linewidth=2, label=f'Median: {median_fav:.0f}')
            ax.legend(fontsize=10)
        ax.set_title("Phân phối Favorites", fontsize=13, fontweight='bold')
        ax.set_xlabel("Favorites")
        ax.set_ylabel("Số sản phẩm")

        # ── 3. Views vs Favorites Scatter ──
        ax = axes[1, 0]
        scatter_df = df[(df['views'] > 0) & (df['favorites'] > 0)].copy()
        if len(scatter_df) > 2:
            ax.scatter(scatter_df['views'], scatter_df['favorites'],
                      alpha=0.4, s=20, color=palette[2], edgecolors='white', linewidths=0.3)
            z = np.polyfit(scatter_df['views'], scatter_df['favorites'], 1)
            p = np.poly1d(z)
            x_line = sorted(scatter_df['views'])
            ax.plot(x_line, p(x_line), color='#C44E52', linewidth=2, linestyle='--',
                   label=f'Trend (slope: {z[0]:.3f})')
            ax.legend(fontsize=9)
        ax.set_title("Views vs Favorites (tương quan)", fontsize=13, fontweight='bold')
        ax.set_xlabel("Views")
        ax.set_ylabel("Favorites")

        # ── 4. Top Tags ──
        ax = axes[1, 1]
        all_tags = [tag for tags_list in df['tags'].dropna() for tag in tags_list]
        top_tags = Counter(all_tags).most_common(12)
        if top_tags:
            tag_names = [t[0] for t in top_tags][::-1]
            tag_counts = [t[1] for t in top_tags][::-1]
            colors = sns.color_palette("viridis", len(tag_names))
            bars = ax.barh(tag_names, tag_counts, color=colors, edgecolor='white')
            ax.bar_label(bars, fmt='%d', padding=3, fontsize=9)
        ax.set_title("Top Tags (từ khóa seller dùng)", fontsize=13, fontweight='bold')
        ax.set_xlabel("Số lần xuất hiện")

        plt.tight_layout()
        fp = os.path.join(CHARTS_DIR, f"etsy_dashboard_{safe_kw}_{timestamp}.png")
        fig.savefig(fp, bbox_inches="tight", dpi=120)
        plt.close(fig)
        print(f"Đã tạo dashboard cho '{keyword}': {fp}")
        return fp

    def _generate_comparison_charts(self, keyword_results: Dict[str, Any]) -> Dict[str, str]:
        """Create comparative charts that put ALL keywords side-by-side."""
        valid = {k: v for k, v in keyword_results.items() if "error" not in v}
        if len(valid) < 2:
            return {}

        sns.set_theme(style="whitegrid")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        charts: Dict[str, str] = {}

        # ── 1. Market Overview: price / favorites / views (median) ──
        overview_data = []
        for kw, a in valid.items():
            overview_data.append({
                "Keyword": kw,
                "Giá (median $)": a.get("price_stats", {}).get("50%", 0),
                "Favorites (median)": a.get("favorites_stats", {}).get("50%", 0),
                "Views (median)": a.get("views_stats", {}).get("50%", 0),
            })
        df_ov = pd.DataFrame(overview_data)

        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle("So sánh thị trường giữa các keyword", fontsize=16, y=1.02)
        for ax, col, color in zip(
            axes,
            ["Giá (median $)", "Favorites (median)", "Views (median)"],
            ["#4C72B0", "#DD8452", "#55A868"],
        ):
            bars = ax.barh(df_ov["Keyword"], df_ov[col], color=color)
            ax.set_title(col, fontsize=13)
            ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=9)
            ax.invert_yaxis()
        plt.tight_layout()
        fp = os.path.join(CHARTS_DIR, f"market_overview_{timestamp}.png")
        fig.savefig(fp, bbox_inches="tight", dpi=120)
        plt.close(fig)
        charts["market_overview"] = fp

        # ── 2. User Behavior: Fav/View ratio + engagement score ──
        behavior_data = []
        for kw, a in valid.items():
            med_views = a.get("views_stats", {}).get("50%", 0)
            med_fav = a.get("favorites_stats", {}).get("50%", 0)
            total = a.get("total_listings", 0)
            fav_rate = (med_fav / med_views * 100) if med_views > 0 else 0
            behavior_data.append({
                "Keyword": kw,
                "Fav/View %": round(fav_rate, 2),
                "Engagement Score": a.get("engagement_score", 0),
                "Số sản phẩm": total,
            })
        df_bh = pd.DataFrame(behavior_data)

        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle("Hành vi người dùng — Keyword nào đáng khai thác?", fontsize=16, y=1.02)

        bars = axes[0].barh(df_bh["Keyword"], df_bh["Fav/View %"], color="#C44E52")
        axes[0].set_title("Tỷ lệ Favorite / View (%)\n(cao = hấp dẫn, dễ convert)", fontsize=11)
        axes[0].bar_label(bars, fmt="%.2f%%", padding=3, fontsize=9)
        axes[0].invert_yaxis()

        bars = axes[1].barh(df_bh["Keyword"], df_bh["Engagement Score"], color="#8172B2")
        axes[1].set_title("Engagement Score\n(tổng hợp view + fav)", fontsize=11)
        axes[1].bar_label(bars, fmt="%.1f", padding=3, fontsize=9)
        axes[1].invert_yaxis()

        bars = axes[2].barh(df_bh["Keyword"], df_bh["Số sản phẩm"], color="#937860")
        axes[2].set_title("Số sản phẩm (mức cạnh tranh)\n(thấp = ít cạnh tranh)", fontsize=11)
        axes[2].bar_label(bars, fmt="%d", padding=3, fontsize=9)
        axes[2].invert_yaxis()

        plt.tight_layout()
        fp = os.path.join(CHARTS_DIR, f"user_behavior_{timestamp}.png")
        fig.savefig(fp, bbox_inches="tight", dpi=120)
        plt.close(fig)
        charts["user_behavior"] = fp

        # ── 3. Opportunity Matrix: scatter Fav/View% vs Engagement ──
        import numpy as np
        fig, ax = plt.subplots(figsize=(10, 8))
        sizes = df_bh["Số sản phẩm"].clip(lower=1)
        size_scaled = (sizes / sizes.max() * 500).clip(lower=40)
        scatter = ax.scatter(
            df_bh["Engagement Score"],
            df_bh["Fav/View %"],
            s=size_scaled,
            alpha=0.7,
            c=range(len(df_bh)),
            cmap="tab10",
            edgecolors="black",
            linewidths=0.5,
        )
        for _, row in df_bh.iterrows():
            ax.annotate(
                row["Keyword"],
                (row["Engagement Score"], row["Fav/View %"]),
                fontsize=9,
                ha="center",
                va="bottom",
                xytext=(0, 8),
                textcoords="offset points",
            )
        ax.set_xlabel("Engagement Score (view + fav)", fontsize=12)
        ax.set_ylabel("Tỷ lệ Fav/View % (sức hấp dẫn)", fontsize=12)
        ax.set_title(
            "Ma trận cơ hội\n(Góc trên-phải = tiềm năng cao, bong bóng lớn = cạnh tranh cao)",
            fontsize=14,
        )
        ax.axhline(df_bh["Fav/View %"].median(), ls="--", color="gray", alpha=0.5)
        ax.axvline(df_bh["Engagement Score"].median(), ls="--", color="gray", alpha=0.5)
        plt.tight_layout()
        fp = os.path.join(CHARTS_DIR, f"opportunity_matrix_{timestamp}.png")
        fig.savefig(fp, bbox_inches="tight", dpi=120)
        plt.close(fig)
        charts["opportunity_matrix"] = fp

        print(f"Đã tạo {len(charts)} biểu đồ so sánh trong {CHARTS_DIR}")
        return charts

    def _analyze_data(self, listings: List[Dict], keyword: str) -> Dict[str, Any]:
        """Phân tích chi tiết danh sách sản phẩm."""
        if not listings:
            return {"total": 0, "error": "Không có dữ liệu để phân tích."}

        df = pd.DataFrame(listings)
        
        df['price'] = df['price'].apply(lambda p: p.get('amount', 0) / 100 if isinstance(p, dict) else 0)
        
        if 'num_favorers' in df.columns:
            df['favorites'] = pd.to_numeric(df['num_favorers'], errors='coerce').fillna(0).astype(int)
        else:
            df['favorites'] = 0

        if 'views' in df.columns:
            df['views'] = pd.to_numeric(df['views'], errors='coerce').fillna(0).astype(int)
        else:
            df['views'] = 0

        if 'creation_timestamp' in df.columns:
            df['creation_date'] = pd.to_datetime(df['creation_timestamp'], unit='s', errors='coerce')
        else:
            df['creation_date'] = pd.NaT
        
        price_stats = df['price'].describe().to_dict()
        favorites_stats = df['favorites'].describe().to_dict()
        views_stats = df['views'].describe().to_dict()

        median_views = views_stats.get('50%', 0)
        median_favorites = favorites_stats.get('50%', 0)
        engagement_score = (median_views * 0.4) + (median_favorites * 0.6)

        all_tags = [tag for tags_list in df['tags'].dropna() for tag in tags_list]
        top_tags = Counter(all_tags).most_common(20)

        fav_view_rate = (median_favorites / median_views * 100) if median_views > 0 else 0

        analysis = {
            "keyword": keyword,
            "total_listings": len(df),
            "price_stats": {k: round(v, 2) for k, v in price_stats.items()},
            "favorites_stats": {k: round(v, 2) for k, v in favorites_stats.items()},
            "views_stats": {k: round(v, 2) for k, v in views_stats.items()},
            "engagement_score": round(engagement_score, 2),
            "fav_view_rate_pct": round(fav_view_rate, 2),
            "top_tags": top_tags[:5],
        }
        return analysis

    def run_analysis(self, keywords: List[str], days_back: int = 30) -> Dict[str, Any]:
        """
        Chạy phân tích cho một danh sách từ khóa hoặc phân tích chung.
        Nếu danh sách từ khóa trống, chạy phân tích chung.
        """
        if not keywords:
            print("Chạy phân tích thị trường áo thun chung...")
            listings = self._fetch_listings(keywords=None, days_back=days_back)
            analysis_result = self._analyze_data(listings, "Thị trường chung")
            result = {"general_analysis": analysis_result}

            chart_paths = self._generate_general_dashboard(listings, analysis_result, days_back)
            if chart_paths:
                result["chart_paths"] = chart_paths

            return result
        else:
            print(f"Chạy phân tích so sánh cho các từ khóa: {keywords}")
            keyword_results = {}
            keyword_listings = {}
            for kw in keywords:
                print(f"\n--- Phân tích từ khóa: '{kw}' ---")
                listings = self._fetch_listings(keywords=kw, days_back=days_back)
                keyword_results[kw] = self._analyze_data(listings, kw)
                keyword_listings[kw] = listings
            
            final_result = {"keyword_analysis": keyword_results}
            chart_paths = []

            for kw in keywords:
                analysis = keyword_results.get(kw, {})
                if "error" not in analysis:
                    dashboard_path = self._generate_keyword_dashboard(keyword_listings[kw], kw, analysis)
                    if dashboard_path:
                        chart_paths.append(dashboard_path)

            comparison_charts = self._generate_comparison_charts(keyword_results)
            if comparison_charts:
                final_result["comparison_charts"] = comparison_charts
                chart_paths.extend(comparison_charts.values())

            if chart_paths:
                final_result["chart_paths"] = chart_paths
    
            return final_result
