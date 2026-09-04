import React, { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "@/App.css";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import ProductDetail from "@/pages/ProductDetail";
import Analytics from "@/pages/Analytics";
import Drivers from "@/pages/Drivers";
import Suppliers from "@/pages/Suppliers";
import Research from "@/pages/Research";
import Watchlist from "@/pages/Watchlist";
import Compare from "@/pages/Compare";
import Fees from "@/pages/Fees";
import { ThemeProvider } from "@/context/ThemeContext";
import { LocationProvider } from "@/context/LocationContext";
import { WatchlistProvider, CompareProvider } from "@/context/AppState";

function App() {
  const [search, setSearch] = useState("");
  return (
    <ThemeProvider>
      <LocationProvider>
        <WatchlistProvider>
          <CompareProvider>
            <BrowserRouter>
              <Layout search={search} onSearch={setSearch}>
                <Routes>
                  <Route path="/" element={<Dashboard search={search} />} />
                  <Route path="/products" element={<Dashboard search={search} />} />
                  <Route path="/products/:id" element={<ProductDetail />} />
                  <Route path="/watchlist" element={<Watchlist />} />
                  <Route path="/compare" element={<Compare />} />
                  <Route path="/drivers" element={<Drivers search={search} />} />
                  <Route path="/suppliers" element={<Suppliers search={search} />} />
                  <Route path="/fees" element={<Fees />} />
                  <Route path="/analytics" element={<Analytics />} />
                  <Route path="/research" element={<Research />} />
                </Routes>
              </Layout>
            </BrowserRouter>
          </CompareProvider>
        </WatchlistProvider>
      </LocationProvider>
    </ThemeProvider>
  );
}

export default App;
