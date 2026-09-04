"""Enrichment templates + logic for TrendSell — deterministic, category-driven."""
from typing import List, Dict, Any


# ---------- Category-driven templates ----------

PLATFORM_FEES = [
    {
        "platform": "Amazon FBA",
        "referral_fee_pct": 15.0,
        "fulfillment_fee": "$3.22 - $6.30 per unit",
        "monthly_subscription": "$39.99 (Professional)",
        "payment_processing_pct": 0.0,
        "notes": "FBA fulfillment fees vary by size/weight; referral is category-based (8-15%).",
    },
    {
        "platform": "TikTok Shop",
        "referral_fee_pct": 6.0,
        "fulfillment_fee": "Self-ship or Fulfilled by TikTok (2-4%)",
        "monthly_subscription": "Free",
        "payment_processing_pct": 2.9,
        "notes": "First 90 days often 1-2% promotional referral for new sellers.",
    },
    {
        "platform": "Shopify",
        "referral_fee_pct": 0.0,
        "fulfillment_fee": "Self-managed or Shopify Fulfillment Network",
        "monthly_subscription": "$29 - $299",
        "payment_processing_pct": 2.9,
        "notes": "No referral fee; you own the storefront but pay for traffic yourself.",
    },
    {
        "platform": "Etsy",
        "referral_fee_pct": 6.5,
        "fulfillment_fee": "Self-ship",
        "monthly_subscription": "Free (listing $0.20/item)",
        "payment_processing_pct": 3.0,
        "notes": "Best for handmade, vintage, and craft supplies with strong margins.",
    },
    {
        "platform": "eBay",
        "referral_fee_pct": 13.25,
        "fulfillment_fee": "Self-ship",
        "monthly_subscription": "$4.95 - $299.95",
        "payment_processing_pct": 0.0,
        "notes": "Final value fee includes payment processing; auction + Buy-It-Now formats.",
    },
    {
        "platform": "Walmart Marketplace",
        "referral_fee_pct": 12.0,
        "fulfillment_fee": "$3.45 - $7.50 (WFS)",
        "monthly_subscription": "Free",
        "payment_processing_pct": 0.0,
        "notes": "Category referral fees range 6-15%; requires approval to sell.",
    },
]


_CATEGORY_SEASONALITY: Dict[str, List[int]] = {
    "Home": [70, 68, 72, 75, 82, 78, 74, 76, 88, 92, 96, 94],
    "Beauty": [82, 84, 88, 78, 82, 76, 74, 80, 86, 92, 98, 94],
    "Fitness": [98, 92, 88, 80, 74, 68, 66, 72, 78, 80, 76, 74],
    "Fashion": [72, 68, 78, 84, 90, 92, 86, 82, 88, 84, 80, 76],
    "Electronics": [76, 68, 72, 74, 78, 82, 76, 78, 82, 88, 96, 98],
    "Kitchen": [92, 78, 74, 72, 76, 70, 68, 72, 78, 84, 96, 98],
    "Pet": [74, 76, 80, 82, 84, 86, 82, 80, 78, 82, 88, 92],
    "Gadgets": [80, 72, 74, 76, 78, 80, 78, 80, 84, 88, 94, 98],
}


_CATEGORY_COMPETITORS: Dict[str, List[Dict[str, Any]]] = {
    "Home": [
        {"name": "Stanley 1913", "platform": "DTC + Amazon", "monthly_revenue": "$42M", "strength": 92},
        {"name": "YETI", "platform": "DTC + Amazon", "monthly_revenue": "$68M", "strength": 88},
        {"name": "Simple Modern", "platform": "Amazon + TikTok Shop", "monthly_revenue": "$8.4M", "strength": 74},
        {"name": "Owala Life", "platform": "DTC + Amazon", "monthly_revenue": "$12M", "strength": 78},
    ],
    "Beauty": [
        {"name": "The Ordinary", "platform": "DTC + Sephora", "monthly_revenue": "$38M", "strength": 90},
        {"name": "COSRX Official", "platform": "TikTok Shop + Amazon", "monthly_revenue": "$14M", "strength": 84},
        {"name": "Beauty of Joseon", "platform": "TikTok Shop + Amazon", "monthly_revenue": "$9.2M", "strength": 76},
        {"name": "Anua Global", "platform": "TikTok Shop", "monthly_revenue": "$6.8M", "strength": 68},
    ],
    "Fitness": [
        {"name": "Alo Yoga", "platform": "DTC + Amazon", "monthly_revenue": "$54M", "strength": 92},
        {"name": "Bala", "platform": "DTC + Nordstrom", "monthly_revenue": "$4.2M", "strength": 78},
        {"name": "Lululemon", "platform": "DTC", "monthly_revenue": "$120M", "strength": 95},
        {"name": "Gymshark", "platform": "DTC + Amazon", "monthly_revenue": "$48M", "strength": 88},
    ],
    "Fashion": [
        {"name": "Halara", "platform": "DTC + TikTok Shop", "monthly_revenue": "$18M", "strength": 82},
        {"name": "Skims", "platform": "DTC", "monthly_revenue": "$68M", "strength": 92},
        {"name": "Ridge", "platform": "DTC + Amazon", "monthly_revenue": "$8.4M", "strength": 80},
        {"name": "Bombas", "platform": "DTC + Amazon", "monthly_revenue": "$22M", "strength": 78},
    ],
    "Electronics": [
        {"name": "Anker Official", "platform": "Amazon + DTC", "monthly_revenue": "$92M", "strength": 96},
        {"name": "Apple", "platform": "DTC + Apple Store", "monthly_revenue": "$4.2B", "strength": 100},
        {"name": "UGREEN", "platform": "Amazon", "monthly_revenue": "$28M", "strength": 84},
        {"name": "Belkin", "platform": "Amazon + Best Buy", "monthly_revenue": "$18M", "strength": 76},
    ],
    "Kitchen": [
        {"name": "Ninja Kitchen", "platform": "Amazon + DTC", "monthly_revenue": "$62M", "strength": 92},
        {"name": "Cuisinart", "platform": "Amazon + Costco", "monthly_revenue": "$44M", "strength": 88},
        {"name": "Vitamix", "platform": "DTC + Amazon", "monthly_revenue": "$32M", "strength": 84},
    ],
    "Pet": [
        {"name": "PetLibro", "platform": "Amazon + Chewy", "monthly_revenue": "$8.6M", "strength": 82},
        {"name": "PETKIT", "platform": "Amazon + DTC", "monthly_revenue": "$14M", "strength": 84},
        {"name": "Whisker (Litter-Robot)", "platform": "DTC + Amazon", "monthly_revenue": "$28M", "strength": 88},
    ],
    "Gadgets": [
        {"name": "Anker Nebula", "platform": "Amazon + DTC", "monthly_revenue": "$18M", "strength": 82},
        {"name": "Baseus Official", "platform": "Amazon + AliExpress", "monthly_revenue": "$12M", "strength": 76},
        {"name": "Ugreen Group", "platform": "Amazon + DTC", "monthly_revenue": "$24M", "strength": 84},
    ],
}


_CATEGORY_CHANNELS: Dict[str, List[Dict[str, Any]]] = {
    "Home": [
        {"platform": "TikTok Shop", "score": 92, "reason": "Virality driver for tumblers/home hydration; #WaterTok content compounds organic sales.", "est_margin_pct": 38},
        {"platform": "Amazon FBA", "score": 88, "reason": "High-intent search on 'insulated tumbler' clusters + Prime shipping expectation.", "est_margin_pct": 32},
        {"platform": "Shopify", "score": 74, "reason": "Best for brand storytelling and repeat buyers; drives higher AOV bundles.", "est_margin_pct": 48},
        {"platform": "Walmart Marketplace", "score": 62, "reason": "Growing category, less competition than Amazon for mid-tier price points.", "est_margin_pct": 34},
    ],
    "Beauty": [
        {"platform": "TikTok Shop", "score": 96, "reason": "SkinTok + BeautyTok drive 60%+ of category discovery; affiliate programs compound.", "est_margin_pct": 55},
        {"platform": "Sephora / DTC", "score": 88, "reason": "Premium beauty buyers concentrate here; Rouge loyalty drives repeat.", "est_margin_pct": 52},
        {"platform": "Amazon FBA", "score": 76, "reason": "Category leader for essentials but competitive; PPC costs elevated.", "est_margin_pct": 38},
        {"platform": "Shopify", "score": 82, "reason": "DTC-first strategy allows premium pricing + subscription/replenishment flows.", "est_margin_pct": 62},
    ],
    "Fitness": [
        {"platform": "TikTok Shop", "score": 88, "reason": "Pilates + wellness creators drive massive demand; #wallpilates 2B+ views.", "est_margin_pct": 48},
        {"platform": "Amazon FBA", "score": 84, "reason": "High-intent buyers searching gear; Prime shipping matters for gifts.", "est_margin_pct": 36},
        {"platform": "Shopify", "score": 78, "reason": "Perfect for building lifestyle brand with community + subscription.", "est_margin_pct": 54},
        {"platform": "Etsy", "score": 42, "reason": "Limited fit unless handmade or custom fitness gear.", "est_margin_pct": 46},
    ],
    "Fashion": [
        {"platform": "TikTok Shop", "score": 94, "reason": "Try-on hauls + #dupe content drive impulse purchases at 3-6x industry avg.", "est_margin_pct": 52},
        {"platform": "Shopify", "score": 88, "reason": "Brand-owned experience critical for fashion; enables drops + loyalty.", "est_margin_pct": 58},
        {"platform": "Amazon FBA", "score": 68, "reason": "Fashion buyers less loyal on Amazon; sizing returns hurt margin.", "est_margin_pct": 28},
        {"platform": "Instagram Shop", "score": 76, "reason": "Great for visual brands; Advantage+ ads drive strong ROAS.", "est_margin_pct": 46},
    ],
    "Electronics": [
        {"platform": "Amazon FBA", "score": 94, "reason": "Highest-intent tech buyers; Prime + reviews decide the sale.", "est_margin_pct": 32},
        {"platform": "Shopify", "score": 78, "reason": "Direct sales enable warranty/support upsells and brand equity.", "est_margin_pct": 42},
        {"platform": "Best Buy Marketplace", "score": 72, "reason": "Trust signal for tech; higher AOV but harder to onboard.", "est_margin_pct": 28},
        {"platform": "TikTok Shop", "score": 64, "reason": "Growing for gadgets but tech buyers still prefer specs on Amazon.", "est_margin_pct": 36},
    ],
    "Kitchen": [
        {"platform": "Amazon FBA", "score": 92, "reason": "Countertop appliances dominate 'kitchen gadget' search; Prime critical.", "est_margin_pct": 34},
        {"platform": "TikTok Shop", "score": 88, "reason": "Recipe creators drive appliance sales; #creamitiktok 900M+ views.", "est_margin_pct": 42},
        {"platform": "Costco / Walmart", "score": 78, "reason": "Bulk buyers and value-conscious families; big-box distribution.", "est_margin_pct": 26},
        {"platform": "Shopify", "score": 66, "reason": "DTC works with strong brand + accessory subscription.", "est_margin_pct": 48},
    ],
    "Pet": [
        {"platform": "Amazon FBA", "score": 88, "reason": "Highest-intent pet parents search here; Subscribe & Save is huge.", "est_margin_pct": 36},
        {"platform": "Chewy Marketplace", "score": 84, "reason": "Category-specific trust + auto-ship drives 3x LTV.", "est_margin_pct": 32},
        {"platform": "TikTok Shop", "score": 78, "reason": "#catsoftiktok + #dogsoftiktok are massive; smart tech products win.", "est_margin_pct": 46},
        {"platform": "Shopify", "score": 68, "reason": "Best for niche brands with strong educational content.", "est_margin_pct": 52},
    ],
    "Gadgets": [
        {"platform": "Amazon FBA", "score": 90, "reason": "Tech gadgets thrive on Amazon with strong PPC + reviews.", "est_margin_pct": 34},
        {"platform": "TikTok Shop", "score": 82, "reason": "'Tech I use daily' creator content drives impulse.", "est_margin_pct": 42},
        {"platform": "Shopify", "score": 72, "reason": "Great for hero product brands with bundle upsells.", "est_margin_pct": 48},
    ],
}


_CATEGORY_ADSPEND: Dict[str, List[Dict[str, Any]]] = {
    "Home": [
        {"platform": "TikTok Ads", "monthly_budget": "$8,000 - $15,000", "expected_roas": "3.2x - 5.4x", "difficulty": "Medium"},
        {"platform": "Meta Ads", "monthly_budget": "$10,000 - $22,000", "expected_roas": "2.4x - 3.8x", "difficulty": "High"},
        {"platform": "Amazon PPC", "monthly_budget": "$6,000 - $14,000", "expected_roas": "3.8x - 5.6x", "difficulty": "Medium"},
        {"platform": "Google Shopping", "monthly_budget": "$4,000 - $9,000", "expected_roas": "3.6x - 5.2x", "difficulty": "Low"},
    ],
    "Beauty": [
        {"platform": "TikTok Ads", "monthly_budget": "$6,000 - $12,000", "expected_roas": "4.2x - 6.8x", "difficulty": "Low"},
        {"platform": "Meta Ads", "monthly_budget": "$12,000 - $28,000", "expected_roas": "2.8x - 4.4x", "difficulty": "High"},
        {"platform": "Amazon PPC", "monthly_budget": "$10,000 - $22,000", "expected_roas": "2.6x - 4.2x", "difficulty": "High"},
        {"platform": "Google Shopping", "monthly_budget": "$3,000 - $7,000", "expected_roas": "3.2x - 4.8x", "difficulty": "Medium"},
    ],
    "Fitness": [
        {"platform": "TikTok Ads", "monthly_budget": "$7,000 - $14,000", "expected_roas": "3.8x - 5.6x", "difficulty": "Medium"},
        {"platform": "Meta Ads", "monthly_budget": "$9,000 - $18,000", "expected_roas": "3.0x - 4.6x", "difficulty": "Medium"},
        {"platform": "Amazon PPC", "monthly_budget": "$5,000 - $11,000", "expected_roas": "3.4x - 5.0x", "difficulty": "Medium"},
        {"platform": "Google Shopping", "monthly_budget": "$3,500 - $8,000", "expected_roas": "3.4x - 4.8x", "difficulty": "Low"},
    ],
    "Fashion": [
        {"platform": "TikTok Ads", "monthly_budget": "$9,000 - $18,000", "expected_roas": "3.6x - 5.2x", "difficulty": "Medium"},
        {"platform": "Meta Ads", "monthly_budget": "$14,000 - $30,000", "expected_roas": "2.4x - 3.8x", "difficulty": "High"},
        {"platform": "Amazon PPC", "monthly_budget": "$6,000 - $13,000", "expected_roas": "2.0x - 3.2x", "difficulty": "High"},
        {"platform": "Google Shopping", "monthly_budget": "$4,000 - $10,000", "expected_roas": "3.2x - 4.6x", "difficulty": "Medium"},
    ],
    "Electronics": [
        {"platform": "Amazon PPC", "monthly_budget": "$14,000 - $32,000", "expected_roas": "3.6x - 5.4x", "difficulty": "High"},
        {"platform": "Google Shopping", "monthly_budget": "$8,000 - $16,000", "expected_roas": "4.2x - 6.4x", "difficulty": "Medium"},
        {"platform": "Meta Ads", "monthly_budget": "$8,000 - $18,000", "expected_roas": "2.8x - 4.2x", "difficulty": "Medium"},
        {"platform": "TikTok Ads", "monthly_budget": "$5,000 - $11,000", "expected_roas": "3.2x - 4.8x", "difficulty": "Medium"},
    ],
    "Kitchen": [
        {"platform": "Amazon PPC", "monthly_budget": "$12,000 - $26,000", "expected_roas": "3.4x - 5.2x", "difficulty": "High"},
        {"platform": "TikTok Ads", "monthly_budget": "$7,000 - $14,000", "expected_roas": "3.6x - 5.4x", "difficulty": "Medium"},
        {"platform": "Meta Ads", "monthly_budget": "$9,000 - $18,000", "expected_roas": "2.8x - 4.2x", "difficulty": "Medium"},
        {"platform": "Google Shopping", "monthly_budget": "$5,000 - $10,000", "expected_roas": "3.8x - 5.2x", "difficulty": "Low"},
    ],
    "Pet": [
        {"platform": "Amazon PPC", "monthly_budget": "$8,000 - $16,000", "expected_roas": "3.8x - 5.6x", "difficulty": "Medium"},
        {"platform": "Meta Ads", "monthly_budget": "$7,000 - $14,000", "expected_roas": "3.4x - 5.0x", "difficulty": "Medium"},
        {"platform": "TikTok Ads", "monthly_budget": "$5,000 - $10,000", "expected_roas": "3.8x - 5.4x", "difficulty": "Low"},
        {"platform": "Google Shopping", "monthly_budget": "$3,500 - $7,500", "expected_roas": "3.6x - 5.0x", "difficulty": "Low"},
    ],
    "Gadgets": [
        {"platform": "Amazon PPC", "monthly_budget": "$10,000 - $22,000", "expected_roas": "3.4x - 5.2x", "difficulty": "High"},
        {"platform": "TikTok Ads", "monthly_budget": "$6,000 - $12,000", "expected_roas": "3.6x - 5.2x", "difficulty": "Medium"},
        {"platform": "Meta Ads", "monthly_budget": "$7,000 - $15,000", "expected_roas": "2.8x - 4.4x", "difficulty": "Medium"},
    ],
}


_CATEGORY_BUNDLES: Dict[str, List[Dict[str, Any]]] = {
    "Home": [
        {"items": ["Insulated Tumbler", "Silicone Boot", "Straw Set"], "bundle_price": "$54", "margin_uplift_pct": 28, "reason": "Accessory bundles lift AOV by 40%+ and reduce single-SKU returns."},
        {"items": ["Tumbler", "Cleaning Brush", "Ice Tray"], "bundle_price": "$48", "margin_uplift_pct": 22, "reason": "Care-kit positioning increases perceived value and repeat buys."},
    ],
    "Beauty": [
        {"items": ["Snail Mucin Essence", "Hydrating Toner", "Ceramide Cream"], "bundle_price": "$62", "margin_uplift_pct": 34, "reason": "Complete K-beauty routine bundle — highest converting SKU stack on TikTok Shop."},
        {"items": ["Serum", "Cotton Rounds", "Mini Facial Roller"], "bundle_price": "$44", "margin_uplift_pct": 26, "reason": "'Full routine' bundles convert first-time buyers into replenishment loops."},
    ],
    "Fitness": [
        {"items": ["Yoga Mat", "Resistance Bands", "Insulated Bottle"], "bundle_price": "$78", "margin_uplift_pct": 32, "reason": "Home workout starter kit — cross-category bundle used by 60% of Pilates creators."},
        {"items": ["Weighted Bangles", "Mat", "Grip Socks"], "bundle_price": "$92", "margin_uplift_pct": 30, "reason": "Wall Pilates essentials — proven bundle for lifestyle creators."},
    ],
    "Fashion": [
        {"items": ["Activewear Dress", "Sports Bra", "Bike Shorts"], "bundle_price": "$118", "margin_uplift_pct": 26, "reason": "'Outfit-in-one' pitches convert on TikTok live shopping streams."},
        {"items": ["Wallet", "AirTag Holder", "Money Clip"], "bundle_price": "$135", "margin_uplift_pct": 32, "reason": "EDC-stack bundle drives 3x higher AOV vs single wallet."},
    ],
    "Electronics": [
        {"items": ["GaN Charger", "USB-C Cable", "Travel Pouch"], "bundle_price": "$68", "margin_uplift_pct": 36, "reason": "'Travel-ready' bundle sells 4.5x more units during holiday travel window."},
        {"items": ["AirTag 4-Pack", "Silicone Cases", "Keyring Loops"], "bundle_price": "$115", "margin_uplift_pct": 28, "reason": "Accessory upsell locks in ecosystem loyalty and boosts margin."},
    ],
    "Kitchen": [
        {"items": ["Ice Cream Maker", "Protein Powder Sample", "Pint Containers"], "bundle_price": "$249", "margin_uplift_pct": 30, "reason": "'Starter kit' bundle removes friction for TikTok recipe creators."},
    ],
    "Pet": [
        {"items": ["Smart Feeder", "Extra Battery Pack", "Silicone Placemat"], "bundle_price": "$142", "margin_uplift_pct": 32, "reason": "Complete cat-parent setup — reduces support tickets and boosts reviews."},
    ],
    "Gadgets": [
        {"items": ["Wireless Charger", "Cable Set", "Desk Mat"], "bundle_price": "$88", "margin_uplift_pct": 28, "reason": "'Desk-setup' bundle appeals to WFH audience via #deskmakeover content."},
    ],
}


_CATEGORY_REGIONS: Dict[str, List[Dict[str, Any]]] = {
    "Home": [
        {"code": "US", "flag": "🇺🇸", "name": "United States", "intensity": 96},
        {"code": "CA", "flag": "🇨🇦", "name": "Canada", "intensity": 82},
        {"code": "GB", "flag": "🇬🇧", "name": "United Kingdom", "intensity": 74},
        {"code": "AU", "flag": "🇦🇺", "name": "Australia", "intensity": 68},
    ],
    "Beauty": [
        {"code": "US", "flag": "🇺🇸", "name": "United States", "intensity": 94},
        {"code": "KR", "flag": "🇰🇷", "name": "South Korea", "intensity": 98},
        {"code": "JP", "flag": "🇯🇵", "name": "Japan", "intensity": 88},
        {"code": "GB", "flag": "🇬🇧", "name": "United Kingdom", "intensity": 76},
        {"code": "SG", "flag": "🇸🇬", "name": "Singapore", "intensity": 72},
    ],
    "Fitness": [
        {"code": "US", "flag": "🇺🇸", "name": "United States", "intensity": 94},
        {"code": "AU", "flag": "🇦🇺", "name": "Australia", "intensity": 88},
        {"code": "GB", "flag": "🇬🇧", "name": "United Kingdom", "intensity": 78},
        {"code": "CA", "flag": "🇨🇦", "name": "Canada", "intensity": 74},
    ],
    "Fashion": [
        {"code": "US", "flag": "🇺🇸", "name": "United States", "intensity": 92},
        {"code": "GB", "flag": "🇬🇧", "name": "United Kingdom", "intensity": 82},
        {"code": "DE", "flag": "🇩🇪", "name": "Germany", "intensity": 74},
        {"code": "FR", "flag": "🇫🇷", "name": "France", "intensity": 78},
        {"code": "IT", "flag": "🇮🇹", "name": "Italy", "intensity": 68},
    ],
    "Electronics": [
        {"code": "US", "flag": "🇺🇸", "name": "United States", "intensity": 94},
        {"code": "DE", "flag": "🇩🇪", "name": "Germany", "intensity": 84},
        {"code": "JP", "flag": "🇯🇵", "name": "Japan", "intensity": 82},
        {"code": "GB", "flag": "🇬🇧", "name": "United Kingdom", "intensity": 78},
        {"code": "CA", "flag": "🇨🇦", "name": "Canada", "intensity": 72},
    ],
    "Kitchen": [
        {"code": "US", "flag": "🇺🇸", "name": "United States", "intensity": 96},
        {"code": "CA", "flag": "🇨🇦", "name": "Canada", "intensity": 84},
        {"code": "AU", "flag": "🇦🇺", "name": "Australia", "intensity": 76},
        {"code": "GB", "flag": "🇬🇧", "name": "United Kingdom", "intensity": 72},
    ],
    "Pet": [
        {"code": "US", "flag": "🇺🇸", "name": "United States", "intensity": 92},
        {"code": "GB", "flag": "🇬🇧", "name": "United Kingdom", "intensity": 78},
        {"code": "JP", "flag": "🇯🇵", "name": "Japan", "intensity": 74},
        {"code": "AU", "flag": "🇦🇺", "name": "Australia", "intensity": 72},
    ],
    "Gadgets": [
        {"code": "US", "flag": "🇺🇸", "name": "United States", "intensity": 90},
        {"code": "JP", "flag": "🇯🇵", "name": "Japan", "intensity": 86},
        {"code": "DE", "flag": "🇩🇪", "name": "Germany", "intensity": 78},
        {"code": "GB", "flag": "🇬🇧", "name": "United Kingdom", "intensity": 72},
    ],
}


_CATEGORY_NICHES: Dict[str, List[Dict[str, Any]]] = {
    "Home": [
        {"name": "Insulated tumblers for nurses (12-hour shift)", "competition": "Low"},
        {"name": "Personalized tumblers for teachers", "competition": "Medium"},
        {"name": "Kids' spill-proof colored tumblers", "competition": "Low"},
        {"name": "Car-cup-holder compatible tumblers", "competition": "Medium"},
    ],
    "Beauty": [
        {"name": "Snail mucin for sensitive/rosacea skin", "competition": "Low"},
        {"name": "Fragrance-free K-beauty essence for men", "competition": "Very Low"},
        {"name": "Travel-size hydrating essence duos", "competition": "Medium"},
        {"name": "Pregnancy-safe K-beauty routines", "competition": "Low"},
    ],
    "Fitness": [
        {"name": "Weighted bangles for seniors (0.5 lb)", "competition": "Very Low"},
        {"name": "Travel-friendly Pilates rings + bands", "competition": "Low"},
        {"name": "Pregnancy-safe Pilates accessories", "competition": "Low"},
        {"name": "Kids' Pilates & yoga mats", "competition": "Medium"},
    ],
    "Fashion": [
        {"name": "Activewear dresses for tall women (5'10+)", "competition": "Low"},
        {"name": "Modest activewear dresses (elbow + knee coverage)", "competition": "Low"},
        {"name": "Post-partum activewear dresses", "competition": "Very Low"},
        {"name": "Petite ridge-style wallets with ID window", "competition": "Medium"},
    ],
    "Electronics": [
        {"name": "GaN chargers for RV / van-life", "competition": "Low"},
        {"name": "AirTag-compatible pet collars", "competition": "Medium"},
        {"name": "Chargers with international plug swap-outs", "competition": "Medium"},
    ],
    "Kitchen": [
        {"name": "Protein ice cream mixes (single-serve)", "competition": "Low"},
        {"name": "CREAMi accessory kits for keto/paleo", "competition": "Low"},
        {"name": "Dairy-free CREAMi cookbook + pint kit", "competition": "Very Low"},
    ],
    "Pet": [
        {"name": "Smart feeders for multi-cat households", "competition": "Low"},
        {"name": "Feeders with medication compartments", "competition": "Very Low"},
        {"name": "Travel-portable feeders for pet parents", "competition": "Medium"},
    ],
    "Gadgets": [
        {"name": "Desk-setup bundles for streamers", "competition": "Medium"},
        {"name": "Ergonomic gear for tall users (6'2+)", "competition": "Low"},
    ],
}


# ---------- Enrichment logic ----------

def compute_velocity(hist: List[int]) -> Dict[str, Any]:
    if len(hist) >= 2 and hist[0] > 0:
        pct = int(round(((hist[-1] - hist[0]) / hist[0]) * 100))
    else:
        pct = 0
    if pct >= 30:
        label = "surging"
    elif pct >= 10:
        label = "climbing"
    elif pct >= -5:
        label = "flat"
    else:
        label = "declining"
    return {"velocity_pct": pct, "velocity_label": label}


def saturation_label(score: int) -> str:
    if score >= 80:
        return "Oversaturated"
    if score >= 60:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def compute_opportunity_score(product: Dict[str, Any]) -> Dict[str, Any]:
    trend = product.get("trend_score", 50)
    velocity = product.get("velocity_pct", 0)
    saturation = product.get("saturation_score", 50)
    market_op = product.get("market_opportunity_score", 50)

    # Sub-scores 0-100
    velocity_sub = max(0, min(100, 50 + velocity))  # velocity of +50% → 100; -50% → 0
    saturation_inv = max(0, 100 - saturation)
    margin_sub = market_op
    first_mover_sub = 90 if product.get("is_early_opportunity") else max(30, saturation_inv - 10)

    composite = round(
        trend * 0.30 +
        velocity_sub * 0.25 +
        saturation_inv * 0.20 +
        margin_sub * 0.15 +
        first_mover_sub * 0.10
    )
    return {
        "opportunity_score": composite,
        "opportunity_breakdown": {
            "trend": trend,
            "velocity": velocity_sub,
            "saturation_inverse": saturation_inv,
            "margin_potential": margin_sub,
            "first_mover": first_mover_sub,
        },
    }


def enrich(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Attach all computed & category-templated fields to a product doc (mutates + returns)."""
    hist = doc.get("trend_history") or []
    doc.update(compute_velocity(hist))

    sat = doc.get("saturation_score", 50)
    doc["saturation_label"] = saturation_label(sat)

    platforms = doc.get("trending_platforms") or []
    tiktok_led = any("TikTok" in p or "Instagram" in p for p in platforms)
    amazon_heavy = any(p == "Amazon" for p in platforms)
    doc["is_early_opportunity"] = bool(tiktok_led and sat < 55 and not amazon_heavy)

    doc.update(compute_opportunity_score(doc))

    cat = doc.get("category", "Home")
    doc["seasonal_demand"] = _CATEGORY_SEASONALITY.get(cat, _CATEGORY_SEASONALITY["Home"])
    doc["competitors"] = _CATEGORY_COMPETITORS.get(cat, [])
    doc["channel_recommendations"] = _CATEGORY_CHANNELS.get(cat, [])
    doc["ad_spend_estimates"] = _CATEGORY_ADSPEND.get(cat, [])
    doc["bundle_suggestions"] = _CATEGORY_BUNDLES.get(cat, [])
    doc["regions"] = _CATEGORY_REGIONS.get(cat, [])
    # Niches: use stored (LLM-generated) if present, else fallback template
    if not doc.get("niches"):
        doc["niches"] = _CATEGORY_NICHES.get(cat, [])
    return doc
