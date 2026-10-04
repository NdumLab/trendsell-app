import React, { createContext, useContext, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Country } from "@/types";

interface LocationCtx {
  country: Country;
  setCountry: (code: string) => void;
  countries: Country[];
  loading: boolean;
}

const DEFAULT_COUNTRY: Country = {
  code: "US",
  flag: "🇺🇸",
  name: "United States",
  region: "Americas",
  currency: "USD",
  symbol: "$",
  ppp: 1.0,
  fx: 1.0,
  platforms: ["Amazon", "TikTok Shop", "Shopify", "Walmart Marketplace", "eBay", "Etsy"],
  tariff_pct: 5,
  shipping_air: 8.5,
  shipping_sea: 1.8,
  lead_air: 7,
  lead_sea: 32,
};

const LocationContext = createContext<LocationCtx>({
  country: DEFAULT_COUNTRY,
  setCountry: () => {},
  countries: [],
  loading: true,
});

const STORAGE_KEY = "trendsell-country-v1";

const guessLocale = (): string => {
  if (typeof window === "undefined") return "US";
  // navigator.language typically like 'en-GB', 'pt-BR', 'ja-JP'
  const raw = navigator.language || (navigator as any).userLanguage || "";
  const parts = raw.split("-");
  if (parts.length >= 2) return parts[1].toUpperCase();
  // Fallback: map language → country
  const langMap: Record<string, string> = {
    en: "US", ja: "JP", ko: "KR", zh: "CN", hi: "IN", pt: "BR", es: "ES", fr: "FR",
    de: "DE", it: "IT", nl: "NL", pl: "PL", tr: "TR", ar: "AE", th: "TH", vi: "VN", id: "ID",
  };
  return langMap[parts[0]] || "US";
};

export const LocationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data: countries = [], isLoading } = useQuery<Country[]>({
    queryKey: ["countries"],
    queryFn: async () => {
      const { data } = await api.get<{ countries: Country[] }>("/countries");
      return data.countries;
    },
    staleTime: Infinity,
  });

  const [code, setCode] = useState<string>(() => {
    if (typeof window === "undefined") return "US";
    return localStorage.getItem(STORAGE_KEY) || guessLocale();
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, code);
  }, [code]);

  const country =
    countries.find((c) => c.code === code) ||
    countries.find((c) => c.code === "US") ||
    DEFAULT_COUNTRY;

  return (
    <LocationContext.Provider value={{ country, setCountry: setCode, countries, loading: isLoading }}>
      {children}
    </LocationContext.Provider>
  );
};

export const useLocation = () => useContext(LocationContext);
