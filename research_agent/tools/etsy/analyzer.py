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
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(_PROJECT_ROOT, "output", "etsy_data")
CHARTS_DIR = os.path.join(_PROJECT_ROOT, "public", "charts")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# Gộp các ID taxonomy của T-shirt lại
T_SHIRT_TAXONOMY_IDS = [449, 482, 559] 

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
        limit_per_request: int = 500,
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

    def _get_top_listings(self, listings: List[Dict], keyword: str, top_n: int = 10) -> List[Dict[str, Any]]:
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
        fig.patch.set_facecolor("#f5faff")
        for _ax in axes.flat:
            _ax.set_facecolor("#f5faff")
        fig.suptitle(
            f"Etsy T-Shirt Market Discovery - Tổng quan {days_back} ngày\n"
            f"{len(df)} sản phẩm  *  Mức tương tác: {analysis.get('engagement_score', 0)}  *  Yêu thích/Xem: {analysis.get('fav_view_rate_pct', 0)}%",
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
        ax.set_title("Top 20 Tags — Niche đang tập trung\n[Đây là những từ khóa bạn nên biết]", fontsize=12, fontweight='bold')
        ax.set_xlabel("Số lần xuất hiện")

        # ── 2. Price Distribution ──
        ax = axes[0, 1]
        price_data = df['price'][df['price'] > 0]
        if len(price_data) > 0:
            p95 = price_data.quantile(0.95)  # clip at p95 to avoid sparse long tail
            price_clipped = price_data[price_data <= p95]
            ax.hist(price_clipped, bins=30, color='#4C72B0', edgecolor='white', alpha=0.85)
            median_p = price_data.median()
            mean_p = price_data.mean()
            ax.axvline(median_p, color='#C44E52', linestyle='--', linewidth=2, label=f'Median: ${median_p:.1f}')
            ax.axvline(mean_p, color='#DD8452', linestyle=':', linewidth=2, label=f'Mean: ${mean_p:.1f}')
            ax.legend(fontsize=9)
        ax.set_title("Phân phối giá ($) — bỏ top 5% đuôi\n[Vùng giá bạn nên bán là $20–$35]", fontsize=12, fontweight='bold')
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
            pie_labels = [f'Top 5 shops\n({top5_pct:.0f}%)', f'Top 6–10\n({top10_pct - top5_pct:.0f}%)', f'Còn lại ({total_shops - 10}+ shops)\n({rest_pct:.0f}%)']
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
            fav_labels = ['0 Fav\n(mới)', '1–5\n(thấp)', '5–20\n(TB)', '20–50\n(tốt)', '50–100\n(hot)', '100+\n(viral)']
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
        ax.set_title("Mức độ cạnh tranh\n[Nhiều SP ở cột 0 Fav = thị trường non, bạn có cơ hội chen vào]", fontsize=12, fontweight='bold')

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
            bars2 = ax2.bar(x + w/2, seg_stats['avg_fav'], w, label='Avg Yêu thích', color='#DD8452', alpha=0.85)
            ax2.bar_label(bars2, fmt='%.1f', fontsize=8, padding=2)
            ax.set_xticks(x)
            ax.set_xticklabels(seg_stats['price_segment'], rotation=30)
            ax.set_ylabel("Số sản phẩm", color='#4C72B0')
            ax2.set_ylabel("Avg Yêu thích", color='#DD8452')
            lines1, labels1 = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc='upper right')
        ax.set_title("Phân khúc giá: Số SP vs Hiệu suất\n[Vùng giá ít SP + Fav cao = dễ thâm nhập nhất]", fontsize=12, fontweight='bold')

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
        ax.set_title("Tags thành công cao\n[Nên dùng các tag này trong listing — xanh ≥ 50% rất tốt]", fontsize=12, fontweight='bold')
        ax.set_xlabel("Tỷ lệ thành công (%)")

        plt.tight_layout()
        fp = os.path.join(CHARTS_DIR, f"general_market_overview_{timestamp}.png")
        fig.savefig(fp, bbox_inches="tight", dpi=130)
        plt.close(fig)
        chart_paths.append(fp)
        print(f"Đã tạo general market overview: {fp}")

        return chart_paths

    # ── Per-keyword dashboard (single keyword) ────────────

    def _generate_keyword_dashboard(self, listings: List[Dict], keyword: str, analysis: Dict[str, Any]) -> Optional[str]:
        """Create an insightful single-keyword market dashboard (2x2 layout).

        Charts:
          1. Price Segment: count vs avg-favorites (dual axis)
          2. Favorites breakdown by competitive tier (categorical bins)
          3. Shop concentration (top-10 shops by listing count)
          4. Tag success rate (% appearing in top-20% favorites products)
        """
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

        # Choose background tint by market health (Fav/View > 3% = hot, < 1% = cold)
        fav_view_rate = analysis.get('fav_view_rate_pct', 0)
        if fav_view_rate >= 3:
            bg_color = "#f0fdf4"        # light green — hot niche
            health_label = "[NICHE NÓNG — Nên đầu tư]"
        elif fav_view_rate >= 1:
            bg_color = "#fffbf0"        # light yellow — moderate
            health_label = "[TRUNG BÌNH — Cần theo dõi]"
        else:
            bg_color = "#fff5f5"        # light red — cold niche
            health_label = "[LẠNH — Ít người mua]"

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.patch.set_facecolor(bg_color)
        for _ax in axes.flat:
            _ax.set_facecolor(bg_color)
        fig.suptitle(
            f"Etsy Market Dashboard — \"{keyword}\" {health_label}\n"
            f"{analysis.get('total_listings', 0)} sản phẩm  *  "
            f"Mức tương tác: {analysis.get('engagement_score', 0)}  *  "
            f"Yêu thích/Xem: {analysis.get('fav_view_rate_pct', 0)}%",
            fontsize=15, fontweight='bold', y=1.01,
        )

        # ── 1. Price Segment: count vs avg-favorites ──
        ax = axes[0, 0]
        price_valid = df[df['price'] > 0].copy()
        if len(price_valid) > 5:
            bins = [0, 10, 20, 30, 50, 100, float('inf')]
            seg_labels = ['<$10', '$10-20', '$20-30', '$30-50', '$50-100', '$100+']
            price_valid['seg'] = pd.cut(price_valid['price'], bins=bins, labels=seg_labels)
            seg_stats = price_valid.groupby('seg', observed=True).agg(
                count=('price', 'size'),
                avg_fav=('favorites', 'mean'),
            ).reset_index()
            x = np.arange(len(seg_stats))
            w = 0.38
            bars1 = ax.bar(x - w / 2, seg_stats['count'], w,
                           label='Số sản phẩm', color='#4C72B0', alpha=0.85, edgecolor='white')
            ax.bar_label(bars1, fmt='%d', fontsize=8, padding=2)
            ax2_r = ax.twinx()
            bars2 = ax2_r.bar(x + w / 2, seg_stats['avg_fav'], w,
                              label='Avg Yêu thích', color='#DD8452', alpha=0.85, edgecolor='white')
            ax2_r.bar_label(bars2, fmt='%.1f', fontsize=8, padding=2)
            ax.set_xticks(x)
            ax.set_xticklabels(seg_stats['seg'], rotation=30, fontsize=9)
            ax.set_ylabel("Số sản phẩm", color='#4C72B0', fontsize=9)
            ax2_r.set_ylabel("Avg Yêu thích", color='#DD8452', fontsize=9)
            lines1, labs1 = ax.get_legend_handles_labels()
            lines2, labs2 = ax2_r.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labs1 + labs2, fontsize=8, loc='upper right')
        ax.set_title("Phân khúc giá: Số SP vs Avg Yêu thích\n[Ít SP + Fav cao = giá tốt để thử nghiệm]", fontsize=11, fontweight='bold')

        # ── 2. Favorites Breakdown — competitive maturity ──
        ax = axes[0, 1]
        fav_data = df['favorites']
        if len(fav_data) > 5:
            fav_bins = [0, 1, 5, 20, 50, 100, float('inf')]
            fav_cat_labels = ['0\n(mới)', '1–5\n(thấp)', '5–20\n(TB)', '20–50\n(tốt)', '50–100\n(hot)', '100+\n(viral)']
            fav_cats = pd.cut(fav_data, bins=fav_bins, labels=fav_cat_labels, right=False)
            fav_dist = fav_cats.value_counts().reindex(fav_cat_labels).fillna(0)
            total = len(fav_data)
            pct = (fav_dist / total * 100).round(1)
            # Vivid gradient: grey (new) → blue → green → orange → red → dark red
            bar_colors = ['#9e9e9e', '#5c85d6', '#43a863', '#f0a030', '#e05050', '#b71c1c']
            bars = ax.bar(range(len(fav_dist)), fav_dist.values, color=bar_colors,
                          edgecolor='white', linewidth=1.2)
            for i, (v, p) in enumerate(zip(fav_dist.values, pct.values)):
                ax.text(i, v + total * 0.012, f'{int(v)}\n({p}%)',
                        ha='center', va='bottom', fontsize=9, fontweight='bold')
            ax.set_xticks(range(len(fav_cat_labels)))
            ax.set_xticklabels(fav_cat_labels, fontsize=9)
            ax.set_ylabel("Số sản phẩm")
        ax.set_title("Mức độ cạnh tranh theo Yêu thích\n[Nhiều SP ở cột 0 = thị trường non, dễ vào]", fontsize=11, fontweight='bold')

        # ── 3. Shop Concentration ──
        ax = axes[1, 0]
        if 'shop_id' in df.columns and df['shop_id'].notna().sum() > 0:
            shop_counts = df.groupby('shop_id').size().sort_values(ascending=False)
            total_shops = len(shop_counts)
            top10 = shop_counts.head(10)
            top10_share = top10.sum() / len(df) * 100
            top5_share = shop_counts.head(5).sum() / len(df) * 100
            shop_labels_bar = [f"#{i + 1}" for i in range(len(top10))][::-1]
            cmap_colors = plt.cm.RdYlGn_r(np.linspace(0.1, 0.7, len(top10)))[::-1]
            bars = ax.barh(shop_labels_bar, top10.values[::-1], color=cmap_colors, edgecolor='white')
            ax.bar_label(bars, fmt='%d', padding=3, fontsize=8)
            ax.set_title(
                f"Top 10 shops chiếm {top10_share:.0f}% thị trường (top 5: {top5_share:.0f}%)\n"
                f"({total_shops} shops — càng tập trung, càng khó cạnh tranh)",
                fontsize=11, fontweight='bold',
            )
            ax.set_xlabel("Số listings")
        else:
            # Fallback: price histogram clipped to p95
            price_data = df['price'][df['price'] > 0]
            if len(price_data) > 0:
                p95 = price_data.quantile(0.95)
                ax.hist(price_data[price_data <= p95], bins=20, color='#4C72B0', edgecolor='white', alpha=0.85)
                ax.axvline(price_data.median(), color='#C44E52', linestyle='--', linewidth=2,
                           label=f'Median: ${price_data.median():.1f}')
                ax.legend(fontsize=9)
                ax.set_xlabel("Giá ($) — cắt p95")
                ax.set_ylabel("Số sản phẩm")
            ax.set_title("Phân phối giá ($)", fontsize=11, fontweight='bold')

        # ── 4. Tag Success Rate ──
        ax = axes[1, 1]
        if len(df) > 10:
            fav_thresh = df['favorites'].quantile(0.8)
            top_df_tags = df[df['favorites'] >= max(fav_thresh, 1)]
            rest_df_tags = df[df['favorites'] < max(fav_thresh, 1)]
            top_tag_ct = Counter([t for tags in top_df_tags['tags'].dropna() for t in tags])
            rest_tag_ct = Counter([t for tags in rest_df_tags['tags'].dropna() for t in tags])
            min_presence = max(3, int(len(df) * 0.03))
            tag_success = {
                tag: (cnt / (cnt + rest_tag_ct.get(tag, 0))) * 100
                for tag, cnt in top_tag_ct.items()
                if (cnt + rest_tag_ct.get(tag, 0)) >= min_presence
            }
            if tag_success:
                sorted_tags = sorted(tag_success.items(), key=lambda x: x[1], reverse=True)[:15]
                t_names = [t[0] for t in sorted_tags][::-1]
                t_rates = [t[1] for t in sorted_tags][::-1]
                colors_tag = ['#55A868' if r >= 50 else '#DD8452' if r >= 30 else '#8172B2' for r in t_rates]
                bars = ax.barh(t_names, t_rates, color=colors_tag, edgecolor='white')
                ax.bar_label(bars, fmt='%.0f%%', padding=3, fontsize=8)
                ax.axvline(50, color='gray', linestyle='--', alpha=0.5, linewidth=1)
                ax.set_xlabel("% xuất hiện ở SP top 20% Yêu thích")
            else:
                # Fallback: plain tag frequency
                all_tags_flat = [t for tags in df['tags'].dropna() for t in tags]
                top_tags_list = Counter(all_tags_flat).most_common(15)
                if top_tags_list:
                    t_names = [t[0] for t in top_tags_list][::-1]
                    t_counts = [t[1] for t in top_tags_list][::-1]
                    tag_colors = sns.color_palette("viridis", len(t_names))
                    bars = ax.barh(t_names, t_counts, color=tag_colors, edgecolor='white')
                    ax.bar_label(bars, fmt='%d', padding=3, fontsize=9)
                ax.set_xlabel("Số lần xuất hiện")
        ax.set_title("Tags xuất hiện nhiều ở SP top 20% Yêu thích\n[Xanh ≥ 50% = nên dùng tag này cho listing của bạn]", fontsize=11, fontweight='bold')

        plt.tight_layout()
        fp = os.path.join(CHARTS_DIR, f"etsy_dashboard_{safe_kw}_{timestamp}.png")
        fig.savefig(fp, bbox_inches="tight", dpi=130)
        plt.close(fig)
        print(f"Đã tạo dashboard cho '{keyword}': {fp}")
        return fp

    def _generate_comparison_charts(self, keyword_results: Dict[str, Any]) -> Dict[str, str]:
        """Create comparative charts that put ALL keywords side-by-side.

        Produces:
          - comparison_dashboard: 2x3 grid with color-coded bars (green=best, red=worst)
          - opportunity_matrix:   scatter with quadrant shading and winner annotation
        """
        valid = {k: v for k, v in keyword_results.items() if "error" not in v}
        if len(valid) < 2:
            return {}

        import numpy as np

        sns.set_theme(style="whitegrid")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        charts: Dict[str, str] = {}

        # ── Build unified data table ──
        rows = []
        for kw, a in valid.items():
            med_views = a.get("views_stats", {}).get("50%", 0)
            med_fav   = a.get("favorites_stats", {}).get("50%", 0)
            med_price = a.get("price_stats", {}).get("50%", 0)
            total     = a.get("total_listings", 0)
            fav_rate  = (med_fav / med_views * 100) if med_views > 0 else 0
            rows.append({
                "Keyword":      kw,
                "fav_view_pct": round(fav_rate, 2),
                "engagement":   a.get("engagement_score", 0),
                "med_fav":      round(med_fav, 1),
                "med_price":    round(med_price, 1),
                "med_views":    round(med_views, 0),
                "n_products":   total,
            })
        df = pd.DataFrame(rows)
        n = len(df)

        # Helper: map values to green→yellow→red based on rank
        def rank_palette(series: pd.Series, high_is_good: bool = True) -> list:
            ranks = series.rank(ascending=not high_is_good, method='min')
            colors = []
            for rv in ranks:
                t = (rv - 1) / max(n - 1, 1)   # 0=best (green) … 1=worst (red)
                if t < 0.5:
                    t2 = t * 2
                    rc = int(44  + (255 - 44)  * t2)
                    gc = int(160 + (127 - 160) * t2)
                    bc = int(44  * (1 - t2))
                else:
                    t2 = (t - 0.5) * 2
                    rc = int(255 + (214 - 255) * t2)
                    gc = int(127 + (39  - 127) * t2)
                    bc = int(14  + (24  - 14)  * t2)
                colors.append(f"#{rc:02x}{gc:02x}{bc:02x}")
            return colors

        # Sort rows by fav_view_pct ascending so best keyword is at bottom of horizontal bar charts
        df_sorted = df.sort_values("fav_view_pct", ascending=True).reset_index(drop=True)

        # 6-panel metric config: (column, title, high_is_good, format_str)
        metrics_cfg = [
            ("fav_view_pct", "Tỷ lệ Yêu thích / Lượt xem (%)\n[Cao = khách hàng thích, dễ bán hàng]",  True,  "%.2f%%"),
            ("engagement",   "Điểm Tương tác (Traffic)\n[Cao = thị trường sôi động, nhiều khách]",      True,  "%.1f"),
            ("med_fav",      "Yêu thích trung vị\n[Cao = sản phẩm bán chạy trong niche]",               True,  "%.1f"),
            ("med_price",    "Giá trung vị ($)\n[Tham khảo để định giá sản phẩm của bạn]",             None,  "$%.1f"),
            ("med_views",    "Lượt xem trung vị\n[Traffic tiềm năng của niche]",                        True,  "%.0f"),
            ("n_products",   "Số sản phẩm (cạnh tranh)\n[Thấp = ít đối thủ, dễ thâm nhập]",            False, "%d"),
        ]

        # ── 1. Comparison Dashboard (2x3) ──
        fig, axes = plt.subplots(2, 3, figsize=(22, 12))
        fig.patch.set_facecolor("#f5f9ff")
        fig.suptitle(
            "So sánh Cơ hội giữa các Keyword\n"
            "Màu XANH = cơ hội tốt nhất  |  Màu ĐỎ = nên xem xét lại  |  Xám = trung tính (giá)",
            fontsize=16, fontweight="bold", y=1.03,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#daeeff", alpha=0.7),
        )

        for (col, title, high_is_good, fmt), ax in zip(metrics_cfg, axes.flat):
            vals = df_sorted[col].values
            kws  = df_sorted["Keyword"].values
            if high_is_good is not None:
                colors = rank_palette(df_sorted[col], high_is_good=high_is_good)
            else:
                colors = ["#4C72B0"] * n   # neutral blue for price (no good/bad)

            bars = ax.barh(kws, vals, color=colors, edgecolor="white", linewidth=0.8, height=0.55)
            bar_labels = [fmt % v for v in vals]
            ax.bar_label(bars, labels=bar_labels, padding=6, fontsize=10, fontweight="bold")
            ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
            max_val = max(vals) if max(vals) > 0 else 1
            ax.set_xlim(0, max_val * 1.35)
            ax.tick_params(axis="y", labelsize=10)
            ax.xaxis.set_visible(False)
            for spine in ("top", "right", "bottom"):
                ax.spines[spine].set_visible(False)
            ax.set_facecolor("#f5f9ff")

        plt.tight_layout(rect=[0, 0, 1, 0.97])
        fp = os.path.join(CHARTS_DIR, f"comparison_dashboard_{timestamp}.png")
        fig.savefig(fp, bbox_inches="tight", dpi=130)
        plt.close(fig)
        charts["comparison_dashboard"] = fp
        print(f"Đã tạo Comparison Dashboard: {fp}")

        # ── 2. Opportunity Matrix (scatter) ──
        fig, ax = plt.subplots(figsize=(12, 9))
        fig.patch.set_facecolor("#fefefe")

        x_vals = df["engagement"].values.astype(float)
        y_vals = df["fav_view_pct"].values.astype(float)
        x_med  = float(np.median(x_vals))
        y_med  = float(np.median(y_vals))

        # Plot limits with generous padding
        x_rng = max(x_vals.max() - x_vals.min(), 1.0)
        y_rng = max(y_vals.max() - y_vals.min(), 0.1)
        x_lo  = max(0.0, x_vals.min() - x_rng * 0.35)
        x_hi  = x_vals.max() + x_rng * 0.35
        y_lo  = max(0.0, y_vals.min() - y_rng * 0.35)
        y_hi  = y_vals.max() + y_rng * 0.35
        ax.set_xlim(x_lo, x_hi)
        ax.set_ylim(y_lo, y_hi)

        # Quadrant background shading
        ax.axhspan(y_med, y_hi * 1.1, alpha=0.07, color="#2ca02c", zorder=0)
        ax.axhspan(y_lo * 0.9, y_med, alpha=0.05, color="#d62728", zorder=0)
        ax.axvline(x_med, ls="--", color="#888888", alpha=0.6, linewidth=1.5, zorder=1)
        ax.axhline(y_med, ls="--", color="#888888", alpha=0.6, linewidth=1.5, zorder=1)

        # Bubble size = competition (inverted: small bubble = less competition)
        sizes     = df["n_products"].clip(lower=1)
        size_max  = float(sizes.max())
        size_scaled = (sizes / size_max * 700).clip(lower=80)

        # Color by quadrant
        pt_colors = []
        for _, row in df.iterrows():
            if row["engagement"] >= x_med and row["fav_view_pct"] >= y_med:
                pt_colors.append("#2ca02c")   # green  — sweet spot
            elif row["engagement"] < x_med and row["fav_view_pct"] < y_med:
                pt_colors.append("#d62728")   # red    — avoid
            else:
                pt_colors.append("#ff7f0e")   # orange — mixed signal

        ax.scatter(x_vals, y_vals, s=size_scaled, c=pt_colors,
                   alpha=0.85, edgecolors="white", linewidths=2, zorder=5)

        # Keyword labels
        for _, row in df.iterrows():
            ax.annotate(
                row["Keyword"],
                (row["engagement"], row["fav_view_pct"]),
                fontsize=12, fontweight="bold",
                ha="center", va="bottom",
                xytext=(0, 13), textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          alpha=0.75, edgecolor="none"),
                zorder=6,
            )

        # Mark the best keyword
        best_idx = (df["engagement"].rank() + df["fav_view_pct"].rank()).idxmax()
        best_row = df.loc[best_idx]
        ax.annotate(
            ">> CHỌN NICHE NÀY <<",
            (best_row["engagement"], best_row["fav_view_pct"]),
            fontsize=11, fontweight="bold", color="#1a7a1a",
            ha="center", va="top",
            xytext=(0, -30), textcoords="offset points",
            arrowprops=dict(arrowstyle="->", color="#1a7a1a", lw=2.5),
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#e8f5e9",
                      edgecolor="#2ca02c", linewidth=1.5),
            zorder=7,
        )

        ax.set_xlabel("Điểm Tương tác — Traffic tiềm năng (càng cao càng tốt)", fontsize=13, labelpad=10)
        ax.set_ylabel("Tỷ lệ Yêu thích/Xem % — Khả năng chuyển đổi (càng cao càng tốt)", fontsize=13, labelpad=10)
        ax.set_title(
            "Ma trận Cơ hội — Keyword nào đáng đầu tư nhất?\n"
            "Góc trên-phải = sweet spot  |  Bong bóng NHỎ = ít cạnh tranh  |  Góc dưới-trái = tránh",
            fontsize=14, fontweight="bold", pad=15,
        )

        # Quadrant corner labels
        ax.text(x_hi - (x_hi - x_lo) * 0.03, y_hi - (y_hi - y_lo) * 0.04,
                "Cơ hội tốt nhất\nTraffic cao + Chuyển đổi cao",
                ha="right", va="top", fontsize=10, color="#1a7a1a",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#e8f5e9",
                          alpha=0.85, edgecolor="#2ca02c"))
        ax.text(x_lo + (x_hi - x_lo) * 0.03, y_lo + (y_hi - y_lo) * 0.04,
                "Rủi ro cao\nTraffic thấp + Chuyển đổi kém",
                ha="left", va="bottom", fontsize=10, color="#b71c1c",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#ffebee",
                          alpha=0.85, edgecolor="#d62728"))

        # Size legend
        ref_sizes = sorted(set([int(sizes.min()), int(sizes.median()), int(sizes.max())]))
        for sp in ref_sizes:
            sc_s = max(sp / size_max * 700, 20)
            ax.scatter([], [], s=sc_s, c="#888888", alpha=0.5, edgecolors="white",
                       label=f"{sp:,} sản phẩm")
        ax.legend(title="Mức cạnh tranh (kích thước bong bóng)",
                  fontsize=10, title_fontsize=11, loc="lower right",
                  framealpha=0.85, edgecolor="#cccccc")

        plt.tight_layout()
        fp = os.path.join(CHARTS_DIR, f"opportunity_matrix_{timestamp}.png")
        fig.savefig(fp, bbox_inches="tight", dpi=130)
        plt.close(fig)
        charts["opportunity_matrix"] = fp
        print(f"Đã tạo Opportunity Matrix: {fp}")

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
