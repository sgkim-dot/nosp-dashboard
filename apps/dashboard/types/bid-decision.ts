export type ProductCode = "SEARCHING_VIEW" | "NEW_PRODUCT";

export type RoundBrand = {
  slotNo: number;
  displayName: string;
  /** Main ad headline (renamed from "광고 카피" → "타이틀") */
  title: string;
  /** NP only — small sub-title above the main title */
  subTitle: string | null;
  /** NP only — body description below the title */
  description: string | null;
  businessName: string;
  source: "dom" | "landing" | "manual" | "scrape_failed";
  confidence: number | null;
};

export type FilterState = {
  product: ProductCode;
  categoryLvl1: string | null;
  categoryLvl2: string | null;
  keywordGroupId: number | null;
  lastNRounds: number;
};

export type RoundRow = {
  roundId: number;
  roundNo: number;
  periodStart: string;
  periodEnd: string;
  referenceQueryVolume: number | null;
  minBidPrice: number | null;
  regularWinningBid: number | null;
  emptySlots: number | null;
  bidStatus: string | null;
  ratio: number | null;
  brands: RoundBrand[];
  brandsScrapedAt: string | null;
  regularAnnounceDate: string | null;
};

export type KeywordGroupSummary = {
  keywordGroupId: number;
  keywordGroupName: string;
  product: ProductCode;
  categoryLvl1: string;
  categoryLvl2: string;
  latestWinning: number | null;
  latestEmptySlots: number | null;
  latestBrands: RoundBrand[];
  latestBrandsScrapedAt: string | null;
  rounds: RoundRow[];
};

export type Insights = {
  meanRatio: number | null;
  vacancyRate: number | null;
  recommendedLow: number | null;
  recommendedHigh: number | null;
  /** Strategy name shown in UI (e.g. "1슬롯 방어 전략"). */
  strategyLabel: string | null;
  /** Short explanation of how the recommendation was derived. */
  strategyHint: string | null;
  /**
   * NP only — second-price auctions hide the winner's bid; the published
   * winning_bid reflects #2's price. When we aim for #1, this is the
   * approximate amount we'll actually pay.
   */
  expectedActualCost: number | null;
  /**
   * Per-KG backtest hit rate: of past rounds where we know the winning_bid,
   * what fraction would have been captured by `recommendedHigh` (computed
   * using only data available BEFORE each round). null if too few sims.
   */
  hitRate: number | null;
  hitRateSims: number;
};
