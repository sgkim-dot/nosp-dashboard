export type ProductCode = "SEARCHING_VIEW" | "NEW_PRODUCT";

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
  minBidPrice: number | null;
  regularWinningBid: number | null;
  emptySlots: number | null;
  bidStatus: string | null;
  ratio: number | null;
};

export type KeywordGroupSummary = {
  keywordGroupId: number;
  keywordGroupName: string;
  product: ProductCode;
  categoryLvl1: string;
  categoryLvl2: string;
  latestWinning: number | null;
  latestEmptySlots: number | null;
  rounds: RoundRow[];
};

export type Insights = {
  meanRatio: number | null;
  vacancyRate: number | null;
  recommendedLow: number | null;
  recommendedHigh: number | null;
};
