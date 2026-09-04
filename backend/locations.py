"""Location-aware intelligence for TrendSell — countries, PPP, local platforms, regulations."""
from typing import List, Dict, Any

# 50+ countries: code, flag, name, region, currency, symbol, ppp_multiplier (relative to USD),
# fx_rate (units of local per USD), platforms (ordered), tariff_pct, shipping_air, shipping_sea (per kg USD).
# PPP multiplier ~ (Big Mac Index / real GDP PPP): 1.0 = US-level, <1 means consumers pay less nominally.
COUNTRIES: List[Dict[str, Any]] = [
    # Americas
    {"code": "US", "flag": "🇺🇸", "name": "United States", "region": "Americas", "currency": "USD", "symbol": "$", "ppp": 1.00, "fx": 1.0,
     "platforms": ["Amazon", "TikTok Shop", "Shopify", "Walmart Marketplace", "eBay", "Etsy"],
     "tariff_pct": 5, "shipping_air": 8.5, "shipping_sea": 1.8, "lead_air": 7, "lead_sea": 32},
    {"code": "CA", "flag": "🇨🇦", "name": "Canada", "region": "Americas", "currency": "CAD", "symbol": "C$", "ppp": 0.96, "fx": 1.36,
     "platforms": ["Amazon.ca", "Shopify", "eBay", "Walmart.ca", "Etsy"],
     "tariff_pct": 6, "shipping_air": 9.2, "shipping_sea": 2.0, "lead_air": 8, "lead_sea": 34},
    {"code": "BR", "flag": "🇧🇷", "name": "Brazil", "region": "Americas", "currency": "BRL", "symbol": "R$", "ppp": 0.48, "fx": 5.05,
     "platforms": ["Mercado Libre", "Shopee Brazil", "Shopify", "Amazon.com.br", "Magalu"],
     "tariff_pct": 30, "shipping_air": 12.0, "shipping_sea": 3.5, "lead_air": 12, "lead_sea": 48},
    {"code": "MX", "flag": "🇲🇽", "name": "Mexico", "region": "Americas", "currency": "MXN", "symbol": "$", "ppp": 0.55, "fx": 17.2,
     "platforms": ["Mercado Libre", "Amazon.com.mx", "Shopify", "Walmart", "Coppel"],
     "tariff_pct": 16, "shipping_air": 10.0, "shipping_sea": 2.8, "lead_air": 10, "lead_sea": 38},
    {"code": "AR", "flag": "🇦🇷", "name": "Argentina", "region": "Americas", "currency": "ARS", "symbol": "$", "ppp": 0.38, "fx": 990.0,
     "platforms": ["Mercado Libre", "Tiendanube", "Shopify"],
     "tariff_pct": 35, "shipping_air": 14.0, "shipping_sea": 4.0, "lead_air": 14, "lead_sea": 55},
    {"code": "CO", "flag": "🇨🇴", "name": "Colombia", "region": "Americas", "currency": "COP", "symbol": "$", "ppp": 0.42, "fx": 3900.0,
     "platforms": ["Mercado Libre", "Falabella", "Éxito", "Shopify"],
     "tariff_pct": 20, "shipping_air": 12.0, "shipping_sea": 3.4, "lead_air": 13, "lead_sea": 42},
    {"code": "CL", "flag": "🇨🇱", "name": "Chile", "region": "Americas", "currency": "CLP", "symbol": "$", "ppp": 0.58, "fx": 920.0,
     "platforms": ["Mercado Libre", "Falabella", "Ripley", "Paris"],
     "tariff_pct": 6, "shipping_air": 11.0, "shipping_sea": 3.0, "lead_air": 13, "lead_sea": 44},

    # Europe
    {"code": "GB", "flag": "🇬🇧", "name": "United Kingdom", "region": "Europe", "currency": "GBP", "symbol": "£", "ppp": 0.85, "fx": 0.79,
     "platforms": ["Amazon.co.uk", "TikTok Shop", "eBay UK", "ASOS Marketplace", "Etsy"],
     "tariff_pct": 8, "shipping_air": 9.5, "shipping_sea": 2.3, "lead_air": 8, "lead_sea": 36},
    {"code": "DE", "flag": "🇩🇪", "name": "Germany", "region": "Europe", "currency": "EUR", "symbol": "€", "ppp": 0.88, "fx": 0.92,
     "platforms": ["Amazon.de", "Otto", "Zalando", "eBay Kleinanzeigen", "Kaufland"],
     "tariff_pct": 8, "shipping_air": 9.0, "shipping_sea": 2.4, "lead_air": 8, "lead_sea": 35},
    {"code": "FR", "flag": "🇫🇷", "name": "France", "region": "Europe", "currency": "EUR", "symbol": "€", "ppp": 0.86, "fx": 0.92,
     "platforms": ["Amazon.fr", "Cdiscount", "Fnac", "Vinted", "Rakuten France"],
     "tariff_pct": 8, "shipping_air": 9.2, "shipping_sea": 2.4, "lead_air": 9, "lead_sea": 36},
    {"code": "IT", "flag": "🇮🇹", "name": "Italy", "region": "Europe", "currency": "EUR", "symbol": "€", "ppp": 0.78, "fx": 0.92,
     "platforms": ["Amazon.it", "eBay", "Subito", "ePrice"],
     "tariff_pct": 8, "shipping_air": 9.4, "shipping_sea": 2.4, "lead_air": 9, "lead_sea": 37},
    {"code": "ES", "flag": "🇪🇸", "name": "Spain", "region": "Europe", "currency": "EUR", "symbol": "€", "ppp": 0.72, "fx": 0.92,
     "platforms": ["Amazon.es", "El Corte Inglés", "PcComponentes", "Vinted"],
     "tariff_pct": 8, "shipping_air": 9.2, "shipping_sea": 2.4, "lead_air": 9, "lead_sea": 36},
    {"code": "NL", "flag": "🇳🇱", "name": "Netherlands", "region": "Europe", "currency": "EUR", "symbol": "€", "ppp": 0.88, "fx": 0.92,
     "platforms": ["Bol.com", "Amazon.nl", "Marktplaats", "Coolblue"],
     "tariff_pct": 8, "shipping_air": 9.0, "shipping_sea": 2.3, "lead_air": 8, "lead_sea": 34},
    {"code": "PL", "flag": "🇵🇱", "name": "Poland", "region": "Europe", "currency": "PLN", "symbol": "zł", "ppp": 0.55, "fx": 4.02,
     "platforms": ["Allegro", "Amazon.pl", "OLX", "Empik"],
     "tariff_pct": 8, "shipping_air": 9.6, "shipping_sea": 2.6, "lead_air": 10, "lead_sea": 38},
    {"code": "SE", "flag": "🇸🇪", "name": "Sweden", "region": "Europe", "currency": "SEK", "symbol": "kr", "ppp": 0.9, "fx": 10.5,
     "platforms": ["Amazon.se", "Blocket", "Tradera", "CDON"],
     "tariff_pct": 8, "shipping_air": 9.5, "shipping_sea": 2.4, "lead_air": 9, "lead_sea": 36},
    {"code": "NO", "flag": "🇳🇴", "name": "Norway", "region": "Europe", "currency": "NOK", "symbol": "kr", "ppp": 1.05, "fx": 10.8,
     "platforms": ["Finn.no", "Elkjøp", "Komplett"],
     "tariff_pct": 6, "shipping_air": 10.0, "shipping_sea": 2.6, "lead_air": 10, "lead_sea": 38},
    {"code": "CH", "flag": "🇨🇭", "name": "Switzerland", "region": "Europe", "currency": "CHF", "symbol": "CHF", "ppp": 1.15, "fx": 0.88,
     "platforms": ["Digitec Galaxus", "Ricardo", "Amazon.de (ship-to)"],
     "tariff_pct": 4, "shipping_air": 10.5, "shipping_sea": 2.6, "lead_air": 9, "lead_sea": 36},
    {"code": "IE", "flag": "🇮🇪", "name": "Ireland", "region": "Europe", "currency": "EUR", "symbol": "€", "ppp": 0.82, "fx": 0.92,
     "platforms": ["Amazon.co.uk", "DoneDeal", "Adverts"],
     "tariff_pct": 8, "shipping_air": 9.5, "shipping_sea": 2.4, "lead_air": 9, "lead_sea": 37},
    {"code": "PT", "flag": "🇵🇹", "name": "Portugal", "region": "Europe", "currency": "EUR", "symbol": "€", "ppp": 0.68, "fx": 0.92,
     "platforms": ["Amazon.es", "Worten", "OLX Portugal"],
     "tariff_pct": 8, "shipping_air": 9.4, "shipping_sea": 2.4, "lead_air": 9, "lead_sea": 37},
    {"code": "TR", "flag": "🇹🇷", "name": "Turkey", "region": "Europe", "currency": "TRY", "symbol": "₺", "ppp": 0.35, "fx": 32.0,
     "platforms": ["Trendyol", "Hepsiburada", "N11", "Amazon.com.tr"],
     "tariff_pct": 18, "shipping_air": 10.5, "shipping_sea": 2.8, "lead_air": 10, "lead_sea": 38},

    # Africa
    {"code": "NG", "flag": "🇳🇬", "name": "Nigeria", "region": "Africa", "currency": "NGN", "symbol": "₦", "ppp": 0.30, "fx": 1550.0,
     "platforms": ["Jumia", "Konga", "Instagram Shops", "WhatsApp Commerce", "Flutterwave Stores"],
     "tariff_pct": 25, "shipping_air": 14.0, "shipping_sea": 3.6, "lead_air": 14, "lead_sea": 55},
    {"code": "KE", "flag": "🇰🇪", "name": "Kenya", "region": "Africa", "currency": "KES", "symbol": "KSh", "ppp": 0.34, "fx": 129.0,
     "platforms": ["Jumia", "Kilimall", "Instagram Shops", "Sky.Garden"],
     "tariff_pct": 25, "shipping_air": 13.5, "shipping_sea": 3.5, "lead_air": 15, "lead_sea": 58},
    {"code": "ZA", "flag": "🇿🇦", "name": "South Africa", "region": "Africa", "currency": "ZAR", "symbol": "R", "ppp": 0.46, "fx": 18.4,
     "platforms": ["Takealot", "Superbalist", "Makro", "Bidorbuy"],
     "tariff_pct": 20, "shipping_air": 12.5, "shipping_sea": 3.2, "lead_air": 13, "lead_sea": 48},
    {"code": "EG", "flag": "🇪🇬", "name": "Egypt", "region": "Africa", "currency": "EGP", "symbol": "E£", "ppp": 0.28, "fx": 48.5,
     "platforms": ["Jumia", "Souq (Amazon.eg)", "Noon Egypt", "Instagram Shops"],
     "tariff_pct": 30, "shipping_air": 13.5, "shipping_sea": 3.6, "lead_air": 15, "lead_sea": 56},
    {"code": "MA", "flag": "🇲🇦", "name": "Morocco", "region": "Africa", "currency": "MAD", "symbol": "DH", "ppp": 0.42, "fx": 9.9,
     "platforms": ["Jumia", "Avito", "MarocAnnonces"],
     "tariff_pct": 22, "shipping_air": 12.0, "shipping_sea": 3.2, "lead_air": 12, "lead_sea": 46},
    {"code": "GH", "flag": "🇬🇭", "name": "Ghana", "region": "Africa", "currency": "GHS", "symbol": "GH₵", "ppp": 0.36, "fx": 15.2,
     "platforms": ["Jumia", "Tonaton", "Instagram Shops"],
     "tariff_pct": 25, "shipping_air": 14.5, "shipping_sea": 3.7, "lead_air": 16, "lead_sea": 58},

    # Middle East
    {"code": "AE", "flag": "🇦🇪", "name": "UAE", "region": "Middle East", "currency": "AED", "symbol": "د.إ", "ppp": 0.72, "fx": 3.67,
     "platforms": ["Noon", "Amazon.ae", "Namshi", "Carrefour", "Sharaf DG"],
     "tariff_pct": 5, "shipping_air": 10.5, "shipping_sea": 2.6, "lead_air": 8, "lead_sea": 34},
    {"code": "SA", "flag": "🇸🇦", "name": "Saudi Arabia", "region": "Middle East", "currency": "SAR", "symbol": "ر.س", "ppp": 0.68, "fx": 3.75,
     "platforms": ["Noon", "Amazon.sa", "Jarir", "Namshi"],
     "tariff_pct": 5, "shipping_air": 10.5, "shipping_sea": 2.6, "lead_air": 9, "lead_sea": 35},
    {"code": "IL", "flag": "🇮🇱", "name": "Israel", "region": "Middle East", "currency": "ILS", "symbol": "₪", "ppp": 0.92, "fx": 3.72,
     "platforms": ["Amazon (Prime IL)", "Shufersal", "AliExpress", "Yad2"],
     "tariff_pct": 12, "shipping_air": 11.0, "shipping_sea": 2.8, "lead_air": 10, "lead_sea": 38},
    {"code": "QA", "flag": "🇶🇦", "name": "Qatar", "region": "Middle East", "currency": "QAR", "symbol": "ر.ق", "ppp": 0.85, "fx": 3.64,
     "platforms": ["Noon", "Snoonu", "Rafeeq", "Carrefour Qatar"],
     "tariff_pct": 5, "shipping_air": 11.0, "shipping_sea": 2.7, "lead_air": 10, "lead_sea": 36},

    # Asia
    {"code": "IN", "flag": "🇮🇳", "name": "India", "region": "Asia", "currency": "INR", "symbol": "₹", "ppp": 0.28, "fx": 83.2,
     "platforms": ["Flipkart", "Amazon.in", "Meesho", "JioMart", "Myntra", "Ajio"],
     "tariff_pct": 20, "shipping_air": 11.0, "shipping_sea": 2.5, "lead_air": 9, "lead_sea": 30},
    {"code": "ID", "flag": "🇮🇩", "name": "Indonesia", "region": "Asia", "currency": "IDR", "symbol": "Rp", "ppp": 0.34, "fx": 15800.0,
     "platforms": ["Shopee", "Tokopedia", "Lazada", "TikTok Shop", "Blibli"],
     "tariff_pct": 15, "shipping_air": 8.5, "shipping_sea": 1.6, "lead_air": 6, "lead_sea": 20},
    {"code": "TH", "flag": "🇹🇭", "name": "Thailand", "region": "Asia", "currency": "THB", "symbol": "฿", "ppp": 0.42, "fx": 35.5,
     "platforms": ["Shopee", "Lazada", "TikTok Shop", "JD Central"],
     "tariff_pct": 12, "shipping_air": 8.5, "shipping_sea": 1.6, "lead_air": 6, "lead_sea": 20},
    {"code": "VN", "flag": "🇻🇳", "name": "Vietnam", "region": "Asia", "currency": "VND", "symbol": "₫", "ppp": 0.32, "fx": 24500.0,
     "platforms": ["Shopee", "Lazada", "Tiki", "TikTok Shop", "Sendo"],
     "tariff_pct": 15, "shipping_air": 8.0, "shipping_sea": 1.5, "lead_air": 5, "lead_sea": 18},
    {"code": "PH", "flag": "🇵🇭", "name": "Philippines", "region": "Asia", "currency": "PHP", "symbol": "₱", "ppp": 0.36, "fx": 57.5,
     "platforms": ["Shopee", "Lazada", "TikTok Shop", "Zalora"],
     "tariff_pct": 15, "shipping_air": 8.5, "shipping_sea": 1.7, "lead_air": 6, "lead_sea": 22},
    {"code": "MY", "flag": "🇲🇾", "name": "Malaysia", "region": "Asia", "currency": "MYR", "symbol": "RM", "ppp": 0.48, "fx": 4.7,
     "platforms": ["Shopee", "Lazada", "TikTok Shop", "PGMall"],
     "tariff_pct": 10, "shipping_air": 8.5, "shipping_sea": 1.6, "lead_air": 6, "lead_sea": 20},
    {"code": "SG", "flag": "🇸🇬", "name": "Singapore", "region": "Asia", "currency": "SGD", "symbol": "S$", "ppp": 0.92, "fx": 1.35,
     "platforms": ["Shopee", "Lazada", "Amazon.sg", "Qoo10", "Carousell"],
     "tariff_pct": 8, "shipping_air": 9.0, "shipping_sea": 1.8, "lead_air": 6, "lead_sea": 20},
    {"code": "CN", "flag": "🇨🇳", "name": "China", "region": "Asia", "currency": "CNY", "symbol": "¥", "ppp": 0.55, "fx": 7.24,
     "platforms": ["Taobao", "Tmall", "JD.com", "Pinduoduo", "Douyin"],
     "tariff_pct": 8, "shipping_air": 4.5, "shipping_sea": 0.6, "lead_air": 3, "lead_sea": 12},
    {"code": "JP", "flag": "🇯🇵", "name": "Japan", "region": "Asia", "currency": "JPY", "symbol": "¥", "ppp": 0.78, "fx": 152.0,
     "platforms": ["Amazon.co.jp", "Rakuten", "Yahoo Shopping", "Mercari", "Zozotown"],
     "tariff_pct": 8, "shipping_air": 9.5, "shipping_sea": 2.0, "lead_air": 7, "lead_sea": 22},
    {"code": "KR", "flag": "🇰🇷", "name": "South Korea", "region": "Asia", "currency": "KRW", "symbol": "₩", "ppp": 0.76, "fx": 1340.0,
     "platforms": ["Coupang", "Gmarket", "11st", "Naver Shopping"],
     "tariff_pct": 8, "shipping_air": 9.0, "shipping_sea": 1.9, "lead_air": 6, "lead_sea": 22},
    {"code": "HK", "flag": "🇭🇰", "name": "Hong Kong", "region": "Asia", "currency": "HKD", "symbol": "HK$", "ppp": 0.82, "fx": 7.82,
     "platforms": ["HKTVmall", "Carousell", "Yahoo HK Auctions"],
     "tariff_pct": 0, "shipping_air": 4.8, "shipping_sea": 0.7, "lead_air": 3, "lead_sea": 10},
    {"code": "TW", "flag": "🇹🇼", "name": "Taiwan", "region": "Asia", "currency": "TWD", "symbol": "NT$", "ppp": 0.72, "fx": 32.0,
     "platforms": ["Shopee", "PChome 24h", "Momoshop", "Ruten"],
     "tariff_pct": 8, "shipping_air": 5.5, "shipping_sea": 0.9, "lead_air": 4, "lead_sea": 14},
    {"code": "PK", "flag": "🇵🇰", "name": "Pakistan", "region": "Asia", "currency": "PKR", "symbol": "₨", "ppp": 0.26, "fx": 278.0,
     "platforms": ["Daraz", "OLX", "Instagram Shops"],
     "tariff_pct": 30, "shipping_air": 11.5, "shipping_sea": 2.7, "lead_air": 12, "lead_sea": 38},
    {"code": "BD", "flag": "🇧🇩", "name": "Bangladesh", "region": "Asia", "currency": "BDT", "symbol": "৳", "ppp": 0.28, "fx": 118.0,
     "platforms": ["Daraz", "Chaldal", "AjkerDeal"],
     "tariff_pct": 30, "shipping_air": 11.5, "shipping_sea": 2.7, "lead_air": 12, "lead_sea": 38},

    # Oceania
    {"code": "AU", "flag": "🇦🇺", "name": "Australia", "region": "Oceania", "currency": "AUD", "symbol": "A$", "ppp": 0.88, "fx": 1.52,
     "platforms": ["Amazon.com.au", "eBay AU", "Kogan", "Catch", "The Iconic"],
     "tariff_pct": 5, "shipping_air": 10.0, "shipping_sea": 2.2, "lead_air": 9, "lead_sea": 28},
    {"code": "NZ", "flag": "🇳🇿", "name": "New Zealand", "region": "Oceania", "currency": "NZD", "symbol": "NZ$", "ppp": 0.84, "fx": 1.65,
     "platforms": ["Trade Me", "Amazon (Prime NZ)", "The Warehouse", "Mighty Ape"],
     "tariff_pct": 5, "shipping_air": 10.5, "shipping_sea": 2.4, "lead_air": 10, "lead_sea": 32},
]


COUNTRIES_BY_CODE: Dict[str, Dict[str, Any]] = {c["code"]: c for c in COUNTRIES}


def get_country(code: str) -> Dict[str, Any]:
    return COUNTRIES_BY_CODE.get((code or "US").upper(), COUNTRIES_BY_CODE["US"])


# ---- Regulation matrix (category, country_code_or_region) -> flag + note ----
# flag values: 'clear' | 'certification' | 'restricted'
_CATEGORY_REGULATION: Dict[str, Dict[str, Dict[str, str]]] = {
    "Electronics": {
        "US": {"flag": "certification", "note": "FCC Part 15 required for wireless/electronics; UL for power adapters."},
        "EU": {"flag": "certification", "note": "CE marking + RoHS required; UK requires UKCA post-Brexit."},
        "IN": {"flag": "certification", "note": "BIS registration required under Compulsory Registration Scheme (CRS)."},
        "BR": {"flag": "certification", "note": "Anatel homologation required for RF devices; INMETRO for power products."},
        "SA": {"flag": "certification", "note": "SASO Saber certification + CITC for wireless devices."},
        "AE": {"flag": "certification", "note": "TDRA / TRA type approval required for wireless & telecom products."},
        "CN": {"flag": "certification", "note": "CCC (China Compulsory Certification) required for most electronics."},
        "JP": {"flag": "certification", "note": "PSE mark required; Giteki certification for wireless."},
        "NG": {"flag": "certification", "note": "SON MANCAP + NCC type approval for wireless devices."},
        "ZA": {"flag": "certification", "note": "ICASA approval required for radio-frequency equipment."},
    },
    "Beauty": {
        "US": {"flag": "certification", "note": "FDA cosmetic labeling; MoCRA (2023) requires facility registration."},
        "EU": {"flag": "certification", "note": "CPNP notification + Responsible Person required (EC 1223/2009)."},
        "GB": {"flag": "certification", "note": "SCPN notification + UK Responsible Person required."},
        "IN": {"flag": "certification", "note": "CDSCO cosmetic import registration required."},
        "SA": {"flag": "certification", "note": "SFDA registration required for imported cosmetics."},
        "AE": {"flag": "certification", "note": "Dubai Municipality / MoH product registration required."},
        "CN": {"flag": "restricted", "note": "General cosmetics NMPA filing; special cosmetics need pre-market approval (animal testing may be required for some)."},
        "NG": {"flag": "certification", "note": "NAFDAC registration required for cosmetics import & sale."},
        "BR": {"flag": "certification", "note": "ANVISA registration required."},
    },
    "Fitness": {
        "US": {"flag": "clear", "note": "General consumer goods regs apply — CPSIA labeling for kids' products."},
        "EU": {"flag": "clear", "note": "General consumer product safety; CE if electronics inside."},
        "IN": {"flag": "clear", "note": "BIS voluntary; general consumer product laws apply."},
    },
    "Home": {
        "US": {"flag": "clear", "note": "FDA food-contact rules if used with beverages; drop-testing recommended."},
        "EU": {"flag": "certification", "note": "REACH compliance for materials; food-contact regulation 1935/2004."},
        "CN": {"flag": "clear", "note": "GB standards apply for food-contact & thermal products."},
    },
    "Kitchen": {
        "US": {"flag": "certification", "note": "FDA food-contact + UL for electrical appliances."},
        "EU": {"flag": "certification", "note": "CE + REACH + food-contact regulation."},
        "IN": {"flag": "certification", "note": "BIS mark for kitchen appliances (CRS)."},
        "JP": {"flag": "certification", "note": "PSE mark required."},
    },
    "Pet": {
        "US": {"flag": "certification", "note": "FCC for smart devices; USDA import restrictions for animal-food products."},
        "EU": {"flag": "certification", "note": "CE + RoHS for electronic pet-tech; DEFRA equivalent for feed."},
        "AU": {"flag": "restricted", "note": "Biosecurity Australia has strict rules on pet-food imports."},
    },
    "Fashion": {
        "US": {"flag": "clear", "note": "General labeling: fiber content, country of origin, care instructions."},
        "EU": {"flag": "clear", "note": "REACH compliance for chemicals; textile labeling regulation."},
    },
    "Gadgets": {
        "US": {"flag": "certification", "note": "FCC Part 15 for RF-emitting gadgets; UL for battery-powered."},
        "EU": {"flag": "certification", "note": "CE + RoHS + WEEE for e-waste; RED for radio equipment."},
        "IN": {"flag": "certification", "note": "BIS registration required."},
    },
}


_EU_CODES = {"DE", "FR", "IT", "ES", "NL", "PL", "SE", "IE", "PT", "SE", "NO", "CH", "AT", "BE", "DK", "FI"}


def regulation_for(category: str, country_code: str) -> Dict[str, str]:
    """Return regulation flag + note for a category in a country."""
    reg_map = _CATEGORY_REGULATION.get(category, {})
    if country_code in reg_map:
        return reg_map[country_code]
    if country_code in _EU_CODES and "EU" in reg_map:
        return reg_map["EU"]
    # Default: clear
    return {"flag": "clear", "note": "No known specific restrictions — standard consumer-goods rules apply."}


# ---- Local competitors overrides per country ----
_LOCAL_COMPETITORS: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "IN": {
        "Home": [
            {"name": "Milton", "platform": "Amazon.in + Flipkart", "monthly_revenue": "₹22 Cr", "strength": 84},
            {"name": "Cello World", "platform": "Amazon.in + Flipkart", "monthly_revenue": "₹18 Cr", "strength": 78},
            {"name": "Borosil", "platform": "DTC + Amazon.in", "monthly_revenue": "₹32 Cr", "strength": 82},
        ],
        "Beauty": [
            {"name": "Mamaearth", "platform": "DTC + Nykaa + Amazon.in", "monthly_revenue": "₹120 Cr", "strength": 92},
            {"name": "Plum Goodness", "platform": "Nykaa + DTC", "monthly_revenue": "₹28 Cr", "strength": 78},
            {"name": "The Derma Co.", "platform": "DTC + Nykaa", "monthly_revenue": "₹48 Cr", "strength": 82},
        ],
        "Fashion": [
            {"name": "Myntra Fashion", "platform": "Myntra", "monthly_revenue": "₹340 Cr", "strength": 94},
            {"name": "Meesho Reselling", "platform": "Meesho", "monthly_revenue": "₹180 Cr", "strength": 82},
            {"name": "Bewakoof", "platform": "DTC + Myntra", "monthly_revenue": "₹42 Cr", "strength": 76},
        ],
        "Electronics": [
            {"name": "boAt", "platform": "Amazon.in + Flipkart + DTC", "monthly_revenue": "₹280 Cr", "strength": 94},
            {"name": "Noise", "platform": "Amazon.in + DTC", "monthly_revenue": "₹120 Cr", "strength": 86},
            {"name": "Portronics", "platform": "Amazon.in + Flipkart", "monthly_revenue": "₹42 Cr", "strength": 78},
        ],
    },
    "NG": {
        "Fashion": [
            {"name": "Zaron Cosmetics", "platform": "Instagram + Jumia", "monthly_revenue": "₦18M", "strength": 76},
            {"name": "Alara Lagos", "platform": "DTC + Instagram", "monthly_revenue": "₦42M", "strength": 84},
        ],
        "Beauty": [
            {"name": "Zaron Cosmetics", "platform": "Instagram + Jumia + DTC", "monthly_revenue": "₦34M", "strength": 84},
            {"name": "House of Tara", "platform": "Instagram + DTC", "monthly_revenue": "₦22M", "strength": 76},
            {"name": "R&R Luxury", "platform": "Instagram Shops", "monthly_revenue": "₦16M", "strength": 68},
        ],
    },
    "BR": {
        "Beauty": [
            {"name": "Natura", "platform": "DTC + Mercado Libre", "monthly_revenue": "R$180M", "strength": 96},
            {"name": "O Boticário", "platform": "DTC", "monthly_revenue": "R$120M", "strength": 92},
            {"name": "Vult", "platform": "Amazon.com.br + Farmácias", "monthly_revenue": "R$28M", "strength": 78},
        ],
    },
    "ID": {
        "Beauty": [
            {"name": "Somethinc", "platform": "Shopee + Tokopedia + TikTok Shop", "monthly_revenue": "Rp18B", "strength": 88},
            {"name": "Wardah", "platform": "Retail + Shopee + Tokopedia", "monthly_revenue": "Rp42B", "strength": 92},
            {"name": "Emina", "platform": "Shopee + Tokopedia", "monthly_revenue": "Rp14B", "strength": 78},
        ],
        "Fashion": [
            {"name": "Erigo", "platform": "TikTok Shop + Shopee", "monthly_revenue": "Rp28B", "strength": 88},
            {"name": "3Second", "platform": "Tokopedia + Shopee", "monthly_revenue": "Rp12B", "strength": 76},
        ],
    },
    "AE": {
        "Beauty": [
            {"name": "Huda Beauty", "platform": "DTC + Sephora + Namshi", "monthly_revenue": "AED 8.4M", "strength": 96},
            {"name": "Kayali", "platform": "Sephora + DTC", "monthly_revenue": "AED 4.2M", "strength": 82},
        ],
    },
}


def local_competitors(category: str, country_code: str) -> List[Dict[str, Any]]:
    country_map = _LOCAL_COMPETITORS.get(country_code, {})
    return country_map.get(category, [])


def convert_price_range(price_range: str, country: Dict[str, Any]) -> str:
    """Convert USD price range string like '$35 - $50' to local PPP-adjusted display."""
    import re
    nums = re.findall(r"\$?([\d,.]+)", price_range)
    if not nums:
        return price_range
    ppp = country["ppp"]
    fx = country["fx"]
    symbol = country["symbol"]
    parts = []
    for n in nums[:2]:
        usd = float(n.replace(",", ""))
        local = usd * ppp * fx
        if local >= 1000:
            parts.append(f"{symbol}{local:,.0f}")
        elif local >= 10:
            parts.append(f"{symbol}{local:.0f}")
        else:
            parts.append(f"{symbol}{local:.2f}")
    return " - ".join(parts) if len(parts) > 1 else parts[0]


def convert_revenue(revenue: str, country: Dict[str, Any]) -> str:
    """Convert '$18.4M' to local. Preserves suffix."""
    import re
    m = re.match(r"\$?([\d.]+)\s*([MBK]?)", revenue.strip())
    if not m:
        return revenue
    val = float(m.group(1))
    suffix = m.group(2)
    ppp = country["ppp"]
    fx = country["fx"]
    symbol = country["symbol"]
    local = val * ppp * fx
    return f"{symbol}{local:,.1f}{suffix}/mo".replace(",", ",")


def local_score_for(global_score: int, country_code: str, category: str, seed_id: str) -> int:
    """Deterministic per-country local score derived from global score."""
    # Hash to keep stable per (country, product)
    h = (hash(seed_id + country_code) % 41) - 20  # -20..+20
    # Category × country affinity biases
    bias = 0
    beauty_asia = {"KR", "JP", "SG", "HK", "TW", "TH", "ID"}
    if category == "Beauty" and country_code in beauty_asia:
        bias += 12
    if category == "Fitness" and country_code in {"AU", "US", "NZ", "GB"}:
        bias += 8
    if category == "Electronics" and country_code in {"JP", "KR", "DE", "US"}:
        bias += 6
    if category == "Fashion" and country_code in {"FR", "IT", "JP", "KR", "GB"}:
        bias += 8
    if category == "Home" and country_code in {"US", "CA", "AU"}:
        bias += 6
    if category == "Pet" and country_code in {"US", "GB", "JP", "AU"}:
        bias += 4
    return max(15, min(100, global_score + h + bias))


def landed_cost(country: Dict[str, Any], unit_cost_usd: float, unit_weight_kg: float = 0.5, mode: str = "air") -> Dict[str, Any]:
    """Compute landed cost breakdown for one unit shipped from China to target country."""
    shipping_rate = country["shipping_air"] if mode == "air" else country["shipping_sea"]
    shipping = shipping_rate * unit_weight_kg
    tariff = unit_cost_usd * (country["tariff_pct"] / 100)
    customs = 0.85  # flat processing
    total_usd = unit_cost_usd + shipping + tariff + customs
    lead = country["lead_air"] if mode == "air" else country["lead_sea"]
    symbol = country["symbol"]
    fx = country["fx"]
    ppp = country["ppp"]

    def fmt(v_usd: float) -> str:
        v_local = v_usd * ppp * fx
        if v_local >= 1000:
            return f"{symbol}{v_local:,.0f}"
        elif v_local >= 10:
            return f"{symbol}{v_local:.0f}"
        return f"{symbol}{v_local:.2f}"

    return {
        "mode": mode,
        "unit_cost_usd": round(unit_cost_usd, 2),
        "unit_cost_local": fmt(unit_cost_usd),
        "shipping_usd": round(shipping, 2),
        "shipping_local": fmt(shipping),
        "tariff_pct": country["tariff_pct"],
        "tariff_usd": round(tariff, 2),
        "tariff_local": fmt(tariff),
        "customs_fee_usd": round(customs, 2),
        "customs_fee_local": fmt(customs),
        "total_usd": round(total_usd, 2),
        "total_local": fmt(total_usd),
        "lead_time_days": lead,
    }


def apply_country(product: Dict[str, Any], country_code: str) -> Dict[str, Any]:
    """Attach country-aware fields to an already-enriched product doc."""
    country = get_country(country_code)
    cat = product.get("category", "Home")

    product["country_code"] = country["code"]
    product["country_name"] = country["name"]
    product["country_flag"] = country["flag"]
    product["local_currency"] = country["currency"]
    product["local_symbol"] = country["symbol"]

    # Local vs Global scores
    global_score = product.get("trend_score", 50)
    product["global_score"] = global_score
    local_score = local_score_for(global_score, country["code"], cat, product.get("id", ""))
    product["local_score"] = local_score

    diff = local_score - global_score
    product["is_local_hidden_gem"] = diff >= 20
    product["is_untapped_local"] = diff <= -20

    # Local platforms
    product["local_platforms"] = country["platforms"]

    # PPP pricing
    product["local_price_range"] = convert_price_range(product.get("price_range", ""), country)
    product["local_estimated_monthly_revenue"] = convert_revenue(product.get("estimated_monthly_revenue", ""), country)
    product["usd_price_range"] = product.get("price_range", "")

    # Local competitors override
    lc = local_competitors(cat, country["code"])
    product["local_competitors"] = lc if lc else product.get("competitors", [])

    # Regulation
    reg = regulation_for(cat, country["code"])
    product["regulation_flag"] = reg["flag"]
    product["regulation_note"] = reg["note"]

    # Landed cost — use first supplier's low unit price as reference
    unit_low = 8.0
    if product.get("suppliers"):
        import re
        m = re.match(r"\$?([\d.]+)", product["suppliers"][0].get("unit_price", "$8"))
        if m:
            unit_low = float(m.group(1))
    product["landed_cost_air"] = landed_cost(country, unit_low, mode="air")
    product["landed_cost_sea"] = landed_cost(country, unit_low, mode="sea")

    return product
