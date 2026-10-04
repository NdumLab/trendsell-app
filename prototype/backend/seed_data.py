"""Rich, realistic seed data for TrendSell dashboard."""
from datetime import datetime, timezone, timedelta
import uuid


CATEGORIES = [
    "Electronics",
    "Beauty",
    "Fitness",
    "Home",
    "Fashion",
    "Gadgets",
    "Pet",
    "Kitchen",
]


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


SEED_PRODUCTS = [
    {
        "id": str(uuid.uuid4()),
        "name": "Stanley Quencher H2.0 Tumbler",
        "category": "Home",
        "description": "40oz insulated stainless-steel tumbler with straw, viral hydration essential.",
        "trend_score": 96,
        "demand_level": "very_high",
        "image_url": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["TikTok Shop", "Amazon", "Target"],
        "price_range": "$35 - $50",
        "estimated_monthly_revenue": "$18.4M",
        "growth_rate": 142,
        "sales_drivers": [
            {"name": "TikTok Shop", "type": "marketplace", "description": "Explosive #WaterTok trend drove 8B+ hashtag views, fueling flash sellouts.", "impact_score": 95},
            {"name": "Meta Ads Advantage+", "type": "ads", "description": "AI-optimized creative testing on Instagram Reels for lookalike moms 25-44.", "impact_score": 78},
            {"name": "Kalodata", "type": "analytics", "description": "TikTok Shop analytics identify winning color drops before restocks.", "impact_score": 65},
            {"name": "Loox Reviews", "type": "shopify_app", "description": "Photo review widget triples conversion on hero product pages.", "impact_score": 60},
        ],
        "market_opportunity_score": 92,
        "why_trending": "Combination of celebrity endorsements, limited color drops, and Gen-Z 'emotional support water bottle' meme created sustained hype loop.",
        "date_added": _iso_days_ago(2),
        "trend_history": [62, 71, 78, 82, 88, 92, 96],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "COSRX Advanced Snail 96 Mucin Essence",
        "category": "Beauty",
        "description": "Korean skincare hero product with 96% snail mucin filtrate for hydration & repair.",
        "trend_score": 94,
        "demand_level": "very_high",
        "image_url": "https://images.unsplash.com/photo-1576426863848-c21f53c60b19?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["TikTok Shop", "Amazon", "Sephora"],
        "price_range": "$18 - $28",
        "estimated_monthly_revenue": "$12.1M",
        "growth_rate": 118,
        "sales_drivers": [
            {"name": "TikTok Shop", "type": "marketplace", "description": "SkinTok creators drove #snailmucin to 2.3B views with before/after content.", "impact_score": 94},
            {"name": "Influencer Affiliate (LTK)", "type": "influencer", "description": "Micro-influencer affiliate stack with 8-15% commissions drives repeat sales.", "impact_score": 82},
            {"name": "Amazon PPC (Helium10)", "type": "ads", "description": "Sponsored Products on 'K-beauty essence' cluster; 4.2x ROAS sustained.", "impact_score": 71},
            {"name": "Klaviyo Email Flows", "type": "email", "description": "Replenishment flows retain 34% of first-time buyers within 60 days.", "impact_score": 58},
        ],
        "market_opportunity_score": 88,
        "why_trending": "Long-term K-beauty adoption meets Gen-Z 'glass skin' obsession; TikTok tutorials made this a gateway product.",
        "date_added": _iso_days_ago(4),
        "trend_history": [58, 66, 72, 79, 85, 90, 94],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Owala FreeSip 24oz Water Bottle",
        "category": "Fitness",
        "description": "Dual-purpose sip/straw insulated bottle in bright collector-style colors.",
        "trend_score": 91,
        "demand_level": "very_high",
        "image_url": "https://images.unsplash.com/photo-1523362628745-0c100150b504?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["TikTok Shop", "Amazon", "Target"],
        "price_range": "$28 - $38",
        "estimated_monthly_revenue": "$9.8M",
        "growth_rate": 128,
        "sales_drivers": [
            {"name": "TikTok Shop", "type": "marketplace", "description": "Riding Stanley wake with cleaner design and better sip mechanism.", "impact_score": 90},
            {"name": "Motion Ads", "type": "ads", "description": "Programmatic UGC-style creative rotation on TikTok Spark Ads.", "impact_score": 72},
            {"name": "Triple Whale", "type": "analytics", "description": "Attribution stitching across TikTok → email → checkout, unlocking scale.", "impact_score": 68},
        ],
        "market_opportunity_score": 85,
        "why_trending": "Perceived as 'the smart Stanley' — collectors mix-and-match FreeSip with tumblers for daily hydration.",
        "date_added": _iso_days_ago(6),
        "trend_history": [50, 58, 66, 74, 82, 87, 91],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "8Sheep Organics Nursing Bath Kit",
        "category": "Beauty",
        "description": "Postpartum bath salts and body butter, viral among new mom communities.",
        "trend_score": 87,
        "demand_level": "high",
        "image_url": "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["TikTok Shop", "Instagram Shop"],
        "price_range": "$45 - $70",
        "estimated_monthly_revenue": "$3.6M",
        "growth_rate": 96,
        "sales_drivers": [
            {"name": "TikTok Shop Affiliate", "type": "influencer", "description": "Momfluencer network with authentic postpartum recovery content.", "impact_score": 91},
            {"name": "Meta Advantage+ Shopping", "type": "ads", "description": "Broad audience creative testing on Instagram Reels + Facebook Feeds.", "impact_score": 74},
            {"name": "Yotpo Reviews", "type": "shopify_app", "description": "SMS-triggered review requests build social proof for pregnancy market.", "impact_score": 62},
        ],
        "market_opportunity_score": 81,
        "why_trending": "Niche community trust + emotional postpartum content converts at extremely high engagement rates.",
        "date_added": _iso_days_ago(9),
        "trend_history": [40, 48, 56, 64, 72, 80, 87],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Ridge Wallet Titanium Edition",
        "category": "Fashion",
        "description": "Minimalist RFID-blocking metal wallet, dominant DTC brand in the space.",
        "trend_score": 84,
        "demand_level": "high",
        "image_url": "https://images.unsplash.com/photo-1627123424574-724758594e93?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["Amazon", "Ridge DTC", "Meta Shops"],
        "price_range": "$95 - $165",
        "estimated_monthly_revenue": "$7.2M",
        "growth_rate": 42,
        "sales_drivers": [
            {"name": "YouTube Sponsorships", "type": "influencer", "description": "Legendary 8-figure creator sponsorship program across tech + finance channels.", "impact_score": 92},
            {"name": "Meta Ads", "type": "ads", "description": "Retargeting stacked with UGC unboxing videos across Facebook/Instagram.", "impact_score": 78},
            {"name": "Klaviyo", "type": "email", "description": "Post-purchase upsell to accessories yields 22% cross-sell rate.", "impact_score": 65},
            {"name": "Recharge", "type": "shopify_app", "description": "Subscription cards & accessories drive predictable MRR.", "impact_score": 51},
        ],
        "market_opportunity_score": 79,
        "why_trending": "Mature DTC playbook with heavy YouTube presence continues to expand internationally.",
        "date_added": _iso_days_ago(12),
        "trend_history": [70, 72, 74, 76, 79, 82, 84],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Apple AirTag 4-Pack",
        "category": "Electronics",
        "description": "Coin-sized item trackers with UWB precision finding.",
        "trend_score": 82,
        "demand_level": "high",
        "image_url": "https://images.unsplash.com/photo-1617997455403-41f333d44d5b?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["Amazon", "Apple Store", "Best Buy"],
        "price_range": "$79 - $99",
        "estimated_monthly_revenue": "$28.5M",
        "growth_rate": 34,
        "sales_drivers": [
            {"name": "Amazon PPC", "type": "ads", "description": "Sponsored Brands + Sponsored Products dominate travel + luggage categories.", "impact_score": 88},
            {"name": "Google Shopping", "type": "ads", "description": "High-intent search on 'luggage tracker' and 'wallet finder' keywords.", "impact_score": 74},
            {"name": "Travel Influencers", "type": "influencer", "description": "Solo-travel creators demo AirTag setups in luggage/wallets pre-trip.", "impact_score": 66},
        ],
        "market_opportunity_score": 76,
        "why_trending": "Revenge travel boom + rising luggage theft coverage keeps demand structurally elevated.",
        "date_added": _iso_days_ago(15),
        "trend_history": [65, 68, 71, 74, 77, 80, 82],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Bala Bangles Weighted Wrist Set",
        "category": "Fitness",
        "description": "Aesthetic 1lb/2lb wrist & ankle weights in matte pastel colors.",
        "trend_score": 80,
        "demand_level": "high",
        "image_url": "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["TikTok Shop", "Amazon", "Nordstrom"],
        "price_range": "$55 - $75",
        "estimated_monthly_revenue": "$4.1M",
        "growth_rate": 88,
        "sales_drivers": [
            {"name": "TikTok Pilates Creators", "type": "influencer", "description": "Wall Pilates + hot girl walk creators showcase Bala in every routine.", "impact_score": 89},
            {"name": "Meta Ads", "type": "ads", "description": "Instagram Reels ads targeting Pilates + Alo Yoga audience overlaps.", "impact_score": 71},
            {"name": "Gorgias Support", "type": "shopify_app", "description": "Concierge chat drives incremental gift bundle sales during peaks.", "impact_score": 55},
        ],
        "market_opportunity_score": 74,
        "why_trending": "Pilates girl aesthetic + low-impact workout wave positions Bala as lifestyle jewelry, not just fitness gear.",
        "date_added": _iso_days_ago(18),
        "trend_history": [45, 52, 60, 66, 72, 76, 80],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Ninja CREAMi Deluxe Ice Cream Maker",
        "category": "Kitchen",
        "description": "Countertop protein ice cream & sorbet machine, viral high-protein dessert essential.",
        "trend_score": 89,
        "demand_level": "very_high",
        "image_url": "https://images.unsplash.com/photo-1516685018646-549198525c1b?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["Amazon", "TikTok Shop", "Costco"],
        "price_range": "$199 - $279",
        "estimated_monthly_revenue": "$15.3M",
        "growth_rate": 156,
        "sales_drivers": [
            {"name": "TikTok Creators", "type": "influencer", "description": "#creamitiktok recipe videos hit 900M views with cottage-cheese protein ice cream.", "impact_score": 94},
            {"name": "Amazon PPC (Helium10)", "type": "ads", "description": "Top-of-search dominance on 'protein ice cream maker' cluster.", "impact_score": 82},
            {"name": "Meta Advantage+ Catalog", "type": "ads", "description": "Product-feed ads with recipe UGC drive strong ROAS.", "impact_score": 70},
        ],
        "market_opportunity_score": 90,
        "why_trending": "Protein-obsessed fitness culture + easy recipe formats made Ninja CREAMi the kitchen appliance of the year.",
        "date_added": _iso_days_ago(3),
        "trend_history": [42, 55, 65, 74, 82, 86, 89],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Rare Beauty Soft Pinch Liquid Blush",
        "category": "Beauty",
        "description": "Selena Gomez-founded liquid blush that dominates TikTok beauty rotations.",
        "trend_score": 93,
        "demand_level": "very_high",
        "image_url": "https://images.unsplash.com/photo-1631730359585-38a4935cbec4?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["Sephora", "TikTok Shop", "Amazon"],
        "price_range": "$23 - $32",
        "estimated_monthly_revenue": "$22.7M",
        "growth_rate": 74,
        "sales_drivers": [
            {"name": "TikTok Shop", "type": "marketplace", "description": "BeautyTok GRWM videos feature Rare Beauty in 68% of makeup routines.", "impact_score": 96},
            {"name": "Sephora Rouge Loyalty", "type": "loyalty", "description": "Rare Beauty is #1 requested SKU for Rouge tier gift redemptions.", "impact_score": 78},
            {"name": "Celebrity Halo (Selena)", "type": "influencer", "description": "Founder authenticity + mental health mission drives sustained brand affinity.", "impact_score": 90},
        ],
        "market_opportunity_score": 87,
        "why_trending": "Founder-driven brand with the strongest emotional storytelling in beauty; blush shades sell out weekly.",
        "date_added": _iso_days_ago(5),
        "trend_history": [70, 74, 79, 84, 88, 91, 93],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Anker Nano II 65W GaN Charger",
        "category": "Electronics",
        "description": "Ultra-compact GaN travel charger for MacBook + iPhone + iPad.",
        "trend_score": 78,
        "demand_level": "high",
        "image_url": "https://images.unsplash.com/photo-1587037288437-8bf3f61a4f00?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["Amazon", "Anker DTC", "Best Buy"],
        "price_range": "$39 - $59",
        "estimated_monthly_revenue": "$6.4M",
        "growth_rate": 38,
        "sales_drivers": [
            {"name": "Amazon PPC (Helium10)", "type": "ads", "description": "Aggressive Sponsored Brands for 'MacBook charger' + 'travel charger'.", "impact_score": 85},
            {"name": "Tech YouTube (MKBHD tier)", "type": "influencer", "description": "Product-review videos drive Google Search demand → Amazon closure.", "impact_score": 74},
            {"name": "Google Shopping", "type": "ads", "description": "High-intent SEM captures upgrade cycles around new iPhone launches.", "impact_score": 68},
        ],
        "market_opportunity_score": 72,
        "why_trending": "USB-C mandate + travel rebound normalized single-brick charging for tech professionals.",
        "date_added": _iso_days_ago(20),
        "trend_history": [60, 62, 65, 69, 72, 76, 78],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Halara Everyday Flare Dress",
        "category": "Fashion",
        "description": "Built-in shorts activewear dress viral on TikTok as versatile go-to summer piece.",
        "trend_score": 86,
        "demand_level": "high",
        "image_url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["TikTok Shop", "Halara DTC", "Instagram"],
        "price_range": "$45 - $65",
        "estimated_monthly_revenue": "$11.9M",
        "growth_rate": 108,
        "sales_drivers": [
            {"name": "TikTok Shop", "type": "marketplace", "description": "Try-on hauls with #halaradupe drive massive comparison-shopping traffic.", "impact_score": 93},
            {"name": "Meta Advantage+", "type": "ads", "description": "Dynamic product ads with catalog feed personalize by size + color.", "impact_score": 77},
            {"name": "Klaviyo SMS", "type": "email", "description": "SMS drops for restock announcements drive 12x ROAS on new colors.", "impact_score": 68},
        ],
        "market_opportunity_score": 82,
        "why_trending": "Tennis-core + wellness-athletic aesthetic overlap made Halara the fast-fashion favorite for Pilates + errands.",
        "date_added": _iso_days_ago(7),
        "trend_history": [52, 60, 68, 74, 80, 84, 86],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "PetLibro Automatic Cat Feeder",
        "category": "Pet",
        "description": "Wi-Fi enabled automatic pet feeder with app scheduling & voice recording.",
        "trend_score": 77,
        "demand_level": "high",
        "image_url": "https://images.unsplash.com/photo-1585499193448-30836a54c1e6?w=800&auto=format&fit=crop&q=80",
        "trending_platforms": ["Amazon", "Chewy", "TikTok Shop"],
        "price_range": "$85 - $145",
        "estimated_monthly_revenue": "$5.7M",
        "growth_rate": 82,
        "sales_drivers": [
            {"name": "TikTok Cat Creators", "type": "influencer", "description": "Cat-owner creator network (#catsoftiktok) drives high-affinity purchase intent.", "impact_score": 84},
            {"name": "Amazon PPC", "type": "ads", "description": "Category-leading share of voice on 'automatic cat feeder' terms.", "impact_score": 79},
            {"name": "Chewy Autoship", "type": "loyalty", "description": "Subscription-based accessory bundles (batteries, replacement lids) retain buyers.", "impact_score": 60},
        ],
        "market_opportunity_score": 75,
        "why_trending": "Pet humanization spending + return-to-office lifestyle drives smart pet-care category growth.",
        "date_added": _iso_days_ago(11),
        "trend_history": [48, 55, 62, 68, 72, 75, 77],
    },
]


# Category → representative supplier archetypes (curated, realistic)
_SUPPLIER_TEMPLATES = {
    "Home": [
        {"name": "Yongkang Kingda Industry", "platform": "Alibaba", "moq": 500, "unit_price": "$4.20 - $6.80", "lead_time_days": 25, "rating": 4.7},
        {"name": "Zhejiang Haers Vacuum Containers", "platform": "Alibaba", "moq": 1000, "unit_price": "$5.50 - $8.10", "lead_time_days": 30, "rating": 4.9},
        {"name": "CJ Dropshipping — Insulated Tumbler", "platform": "CJ Dropshipping", "moq": 1, "unit_price": "$7.80 - $12.40", "lead_time_days": 7, "rating": 4.5},
    ],
    "Beauty": [
        {"name": "Guangzhou Beauty Wave Cosmetics", "platform": "Alibaba", "moq": 200, "unit_price": "$1.80 - $3.40", "lead_time_days": 20, "rating": 4.6},
        {"name": "Faire Wholesale — Indie Skincare", "platform": "Faire", "moq": 12, "unit_price": "$8.00 - $14.00", "lead_time_days": 5, "rating": 4.8},
        {"name": "Spocket — US Skincare Suppliers", "platform": "Spocket", "moq": 1, "unit_price": "$6.50 - $11.20", "lead_time_days": 4, "rating": 4.4},
    ],
    "Fitness": [
        {"name": "Ningbo Kingcheer Bottle Co.", "platform": "Alibaba", "moq": 500, "unit_price": "$3.60 - $5.90", "lead_time_days": 22, "rating": 4.7},
        {"name": "AliExpress — Weighted Bangles Vendor", "platform": "AliExpress", "moq": 1, "unit_price": "$4.80 - $9.20", "lead_time_days": 12, "rating": 4.5},
        {"name": "Zendrop Plus — Fitness Category", "platform": "Zendrop", "moq": 1, "unit_price": "$5.20 - $10.80", "lead_time_days": 6, "rating": 4.6},
    ],
    "Fashion": [
        {"name": "Yiwu Ruile Import & Export", "platform": "Alibaba", "moq": 300, "unit_price": "$3.20 - $6.10", "lead_time_days": 18, "rating": 4.5},
        {"name": "DHgate — Activewear Dress Vendor", "platform": "DHgate", "moq": 10, "unit_price": "$5.40 - $9.80", "lead_time_days": 14, "rating": 4.3},
        {"name": "AliExpress — Ridge-style Wallets", "platform": "AliExpress", "moq": 1, "unit_price": "$3.90 - $8.50", "lead_time_days": 15, "rating": 4.4},
    ],
    "Electronics": [
        {"name": "Shenzhen Beloong Electronics", "platform": "Alibaba", "moq": 200, "unit_price": "$8.20 - $14.60", "lead_time_days": 25, "rating": 4.8},
        {"name": "AliExpress — GaN Charger Wholesale", "platform": "AliExpress", "moq": 1, "unit_price": "$9.10 - $16.80", "lead_time_days": 12, "rating": 4.6},
        {"name": "Global Sources — Certified Tech OEM", "platform": "Global Sources", "moq": 500, "unit_price": "$7.40 - $12.90", "lead_time_days": 28, "rating": 4.7},
    ],
    "Kitchen": [
        {"name": "Foshan Shunde Homelinks Electric", "platform": "Alibaba", "moq": 100, "unit_price": "$42.00 - $68.00", "lead_time_days": 35, "rating": 4.8},
        {"name": "Global Sources — Small Appliance OEM", "platform": "Global Sources", "moq": 200, "unit_price": "$38.50 - $59.20", "lead_time_days": 30, "rating": 4.7},
        {"name": "DHgate — Countertop Machine Vendor", "platform": "DHgate", "moq": 20, "unit_price": "$52.00 - $79.00", "lead_time_days": 18, "rating": 4.4},
    ],
    "Pet": [
        {"name": "Shenzhen Petwant Products", "platform": "Alibaba", "moq": 300, "unit_price": "$18.40 - $32.80", "lead_time_days": 25, "rating": 4.7},
        {"name": "CJ Dropshipping — Smart Pet Feeders", "platform": "CJ Dropshipping", "moq": 1, "unit_price": "$26.00 - $42.00", "lead_time_days": 8, "rating": 4.5},
        {"name": "Zendrop — Pet Tech Category", "platform": "Zendrop", "moq": 1, "unit_price": "$28.50 - $45.00", "lead_time_days": 7, "rating": 4.6},
    ],
    "Gadgets": [
        {"name": "Shenzhen Longkuan Technology", "platform": "Alibaba", "moq": 200, "unit_price": "$6.20 - $11.40", "lead_time_days": 24, "rating": 4.6},
        {"name": "AliExpress — Wireless Gadget OEM", "platform": "AliExpress", "moq": 1, "unit_price": "$7.80 - $13.60", "lead_time_days": 14, "rating": 4.5},
    ],
}


def _attach_suppliers(product: dict) -> dict:
    cat = product.get("category", "Home")
    templates = _SUPPLIER_TEMPLATES.get(cat, _SUPPLIER_TEMPLATES["Home"])
    product["suppliers"] = [
        {
            "name": t["name"],
            "platform": t["platform"],
            "moq": t["moq"],
            "unit_price": t["unit_price"],
            "lead_time_days": t["lead_time_days"],
            "rating": t["rating"],
            "url": f"https://www.google.com/search?q={t['platform'].replace(' ', '+')}+{product['name'].replace(' ', '+')}",
        }
        for t in templates
    ]
    return product


def get_seed_products():
    """Return a fresh copy of seed products, each enriched with supplier options."""
    import copy
    return [_attach_suppliers(copy.deepcopy(p)) for p in SEED_PRODUCTS]


def get_categories():
    """Return unique category list derived from seed data."""
    return sorted({p["category"] for p in SEED_PRODUCTS})
