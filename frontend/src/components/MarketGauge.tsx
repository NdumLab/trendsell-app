import React from "react";

interface Props {
  score: number;
}

// Semi-circular gauge (0-100)
const MarketGauge: React.FC<Props> = ({ score }) => {
  const radius = 90;
  const circumference = Math.PI * radius; // half-circle
  const dash = (score / 100) * circumference;

  const rating =
    score >= 85 ? "Exceptional" : score >= 70 ? "Strong" : score >= 55 ? "Moderate" : "Watchlist";

  const ratingColor =
    score >= 85 ? "text-emerald-400" : score >= 70 ? "text-indigo-400" : score >= 55 ? "text-amber-400" : "text-rose-400";

  return (
    <div className="flex flex-col items-center" data-testid="market-opportunity-gauge">
      <svg viewBox="0 0 220 130" className="w-full max-w-[280px]">
        <defs>
          <linearGradient id="gaugeGradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#f43f5e" />
            <stop offset="40%" stopColor="#f59e0b" />
            <stop offset="75%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#10b981" />
          </linearGradient>
        </defs>
        <path
          d="M 20 110 A 90 90 0 0 1 200 110"
          stroke="rgb(30 41 59)"
          strokeWidth="18"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M 20 110 A 90 90 0 0 1 200 110"
          stroke="url(#gaugeGradient)"
          strokeWidth="18"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          style={{ transition: "stroke-dasharray 800ms ease-out" }}
        />
        <text
          x="110"
          y="95"
          textAnchor="middle"
          className="fill-slate-50"
          fontSize="42"
          fontWeight="800"
          fontFamily="'JetBrains Mono', monospace"
        >
          {score}
        </text>
        <text
          x="110"
          y="118"
          textAnchor="middle"
          className="fill-slate-500"
          fontSize="10"
          letterSpacing="2"
          fontWeight="600"
        >
          OPPORTUNITY
        </text>
      </svg>
      <div className={`text-sm font-bold tracking-wider uppercase ${ratingColor}`}>{rating}</div>
    </div>
  );
};

export default MarketGauge;
