export type MarketAssetClass = "CRYPTO" | "METAL" | "FOREX" | "INDEX" | "COMMODITY";

export type MarketAssetGroup =
  | "CRYPTO"
  | "METALS"
  | "FOREX_MAJORS"
  | "FOREX_CROSSES"
  | "INDICES"
  | "COMMODITIES";

export interface MarketPreset {
  symbol: string;
  name: string;
  asset_class: MarketAssetClass;
  asset_group: MarketAssetGroup;
  quote?: string;
  default_timeframe: string;
  description: string;
  aliases: string[];
  tags: string[];
}

export interface MarketSelectionPayload {
  symbol: string;
  asset_class: MarketAssetClass;
  timeframe: string;
}

export interface MarketAssetTab {
  id: MarketAssetGroup | "ALL";
  label: string;
  asset_class?: MarketAssetClass;
}

export const MARKET_UNAVAILABLE_MESSAGE = "This market is not available from the current data source.";
export const DEFAULT_MARKET_TIMEFRAME = "15m";

export const MARKET_ASSET_TABS: MarketAssetTab[] = [
  { id: "ALL", label: "All Markets" },
  { id: "CRYPTO", label: "Crypto", asset_class: "CRYPTO" },
  { id: "METALS", label: "Metals", asset_class: "METAL" },
  { id: "FOREX_MAJORS", label: "Forex Majors", asset_class: "FOREX" },
  { id: "FOREX_CROSSES", label: "Forex Crosses", asset_class: "FOREX" },
  { id: "INDICES", label: "Indices", asset_class: "INDEX" },
  { id: "COMMODITIES", label: "Commodities", asset_class: "COMMODITY" },
];

export const MARKET_PRESETS: MarketPreset[] = [
  {
    symbol: "BTCUSDT",
    name: "Bitcoin",
    asset_class: "CRYPTO",
    asset_group: "CRYPTO",
    quote: "USDT",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "High-liquidity crypto benchmark with strong macro and risk-on sensitivity.",
    aliases: ["BTC", "BTC/USDT", "Bitcoin"],
    tags: ["crypto", "large-cap", "perpetual"],
  },
  {
    symbol: "ETHUSDT",
    name: "Ethereum",
    asset_class: "CRYPTO",
    asset_group: "CRYPTO",
    quote: "USDT",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Smart-contract beta with strong correlation to crypto liquidity cycles.",
    aliases: ["ETH", "ETH/USDT", "Ether"],
    tags: ["crypto", "large-cap", "perpetual"],
  },
  {
    symbol: "SOLUSDT",
    name: "Solana",
    asset_class: "CRYPTO",
    asset_group: "CRYPTO",
    quote: "USDT",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "High-beta crypto market with faster impulse and liquidity shifts.",
    aliases: ["SOL", "SOL/USDT", "Solana"],
    tags: ["crypto", "high-beta", "perpetual"],
  },
  {
    symbol: "XAUUSD",
    name: "Gold",
    asset_class: "METAL",
    asset_group: "METALS",
    quote: "USD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Gold spot proxy, sensitive to real yields, USD strength, and risk stress.",
    aliases: ["XAU", "Gold", "XAU/USD"],
    tags: ["metal", "safe-haven", "macro"],
  },
  {
    symbol: "XAGUSD",
    name: "Silver",
    asset_class: "METAL",
    asset_group: "METALS",
    quote: "USD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Silver spot proxy with mixed precious-metal and industrial demand behavior.",
    aliases: ["XAG", "Silver", "XAG/USD"],
    tags: ["metal", "industrial", "macro"],
  },
  {
    symbol: "EURUSD",
    name: "Euro / US Dollar",
    asset_class: "FOREX",
    asset_group: "FOREX_MAJORS",
    quote: "USD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Most liquid FX major, driven by ECB/Fed rate expectations and USD flows.",
    aliases: ["EUR/USD", "Euro", "Euro Dollar"],
    tags: ["forex", "major", "euro"],
  },
  {
    symbol: "GBPUSD",
    name: "British Pound / US Dollar",
    asset_class: "FOREX",
    asset_group: "FOREX_MAJORS",
    quote: "USD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Sterling major with strong sensitivity to UK rates and risk appetite.",
    aliases: ["GBP/USD", "Cable", "Pound"],
    tags: ["forex", "major", "pound"],
  },
  {
    symbol: "USDJPY",
    name: "US Dollar / Japanese Yen",
    asset_class: "FOREX",
    asset_group: "FOREX_MAJORS",
    quote: "JPY",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Rate-differential FX major with frequent trend persistence and intervention risk.",
    aliases: ["USD/JPY", "Dollar Yen", "Yen"],
    tags: ["forex", "major", "yen"],
  },
  {
    symbol: "AUDUSD",
    name: "Australian Dollar / US Dollar",
    asset_class: "FOREX",
    asset_group: "FOREX_MAJORS",
    quote: "USD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Commodity-linked FX major sensitive to China growth and risk appetite.",
    aliases: ["AUD/USD", "Aussie"],
    tags: ["forex", "major", "commodity-fx"],
  },
  {
    symbol: "USDCAD",
    name: "US Dollar / Canadian Dollar",
    asset_class: "FOREX",
    asset_group: "FOREX_MAJORS",
    quote: "CAD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "North American FX major with oil sensitivity and USD rate exposure.",
    aliases: ["USD/CAD", "Loonie"],
    tags: ["forex", "major", "oil-linked"],
  },
  {
    symbol: "USDCHF",
    name: "US Dollar / Swiss Franc",
    asset_class: "FOREX",
    asset_group: "FOREX_MAJORS",
    quote: "CHF",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Safe-haven FX major sensitive to USD strength and risk stress.",
    aliases: ["USD/CHF", "Swiss Franc", "Swissy"],
    tags: ["forex", "major", "safe-haven"],
  },
  {
    symbol: "EURJPY",
    name: "Euro / Japanese Yen",
    asset_class: "FOREX",
    asset_group: "FOREX_CROSSES",
    quote: "JPY",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Liquid FX cross combining euro flows with yen carry dynamics.",
    aliases: ["EUR/JPY", "Euro Yen"],
    tags: ["forex", "cross", "yen"],
  },
  {
    symbol: "GBPJPY",
    name: "British Pound / Japanese Yen",
    asset_class: "FOREX",
    asset_group: "FOREX_CROSSES",
    quote: "JPY",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Volatile FX cross often used for momentum and carry-sensitive setups.",
    aliases: ["GBP/JPY", "Pound Yen", "Geppy"],
    tags: ["forex", "cross", "high-volatility"],
  },
  {
    symbol: "NAS100",
    name: "Nasdaq 100",
    asset_class: "INDEX",
    asset_group: "INDICES",
    quote: "USD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "US tech-heavy index proxy with growth, rates, and volatility sensitivity.",
    aliases: ["NASDAQ", "NDX", "US100"],
    tags: ["index", "tech", "us"],
  },
  {
    symbol: "US30",
    name: "Dow Jones",
    asset_class: "INDEX",
    asset_group: "INDICES",
    quote: "USD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "US blue-chip index proxy with cyclical and industrial exposure.",
    aliases: ["Dow", "DJI", "Dow Jones"],
    tags: ["index", "blue-chip", "us"],
  },
  {
    symbol: "SPX500",
    name: "S&P 500",
    asset_class: "INDEX",
    asset_group: "INDICES",
    quote: "USD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Broad US equity benchmark used for risk sentiment and macro trend analysis.",
    aliases: ["SPX", "US500", "S&P500", "S&P 500"],
    tags: ["index", "broad-market", "us"],
  },
  {
    symbol: "WTI",
    name: "WTI Crude Oil",
    asset_class: "COMMODITY",
    asset_group: "COMMODITIES",
    quote: "USD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "US crude oil proxy driven by inventory, supply, demand, and USD conditions.",
    aliases: ["Crude", "USOIL", "West Texas Intermediate"],
    tags: ["commodity", "energy", "oil"],
  },
  {
    symbol: "BRENT",
    name: "Brent Crude Oil",
    asset_class: "COMMODITY",
    asset_group: "COMMODITIES",
    quote: "USD",
    default_timeframe: DEFAULT_MARKET_TIMEFRAME,
    description: "Global crude benchmark with geopolitical and supply-demand sensitivity.",
    aliases: ["UKOIL", "Brent Oil", "Brent"],
    tags: ["commodity", "energy", "oil"],
  },
];

export function normalizeMarketSymbol(value: string): string {
  return value.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();
}

export function findMarketPreset(symbol: string | null | undefined): MarketPreset | null {
  if (!symbol) return null;
  const normalized = normalizeMarketSymbol(symbol);
  return (
    MARKET_PRESETS.find((preset) => {
      if (normalizeMarketSymbol(preset.symbol) === normalized) return true;
      return preset.aliases.some((alias) => normalizeMarketSymbol(alias) === normalized);
    }) ?? null
  );
}

export function searchMarketPresets(
  query: string,
  assetGroup: MarketAssetGroup | "ALL" = "ALL",
): MarketPreset[] {
  const normalizedQuery = normalizeMarketSymbol(query);
  const textQuery = query.trim().toLowerCase();
  return MARKET_PRESETS.filter((preset) => {
    if (assetGroup !== "ALL" && preset.asset_group !== assetGroup) return false;
    if (!normalizedQuery && !textQuery) return true;
    const searchable = [
      preset.symbol,
      preset.name,
      preset.asset_class,
      preset.asset_group,
      preset.description,
      ...preset.aliases,
      ...preset.tags,
    ];
    return searchable.some((value) => {
      const text = value.toLowerCase();
      return text.includes(textQuery) || normalizeMarketSymbol(value).includes(normalizedQuery);
    });
  });
}

export function createMarketSelectionPayload(
  preset: MarketPreset,
  timeframe = DEFAULT_MARKET_TIMEFRAME,
): MarketSelectionPayload {
  return {
    symbol: preset.symbol,
    asset_class: preset.asset_class,
    timeframe,
  };
}

export function isSupportedMarket(symbol: string | null | undefined): boolean {
  return findMarketPreset(symbol) !== null;
}
