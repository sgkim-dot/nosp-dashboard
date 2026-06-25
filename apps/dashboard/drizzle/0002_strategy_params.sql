CREATE TABLE "strategy_params" (
	"id" serial PRIMARY KEY NOT NULL,
	"product_code" varchar(32) NOT NULL,
	"status" varchar(16) NOT NULL,
	"weights" jsonb NOT NULL,
	"low_percentile_bps" integer NOT NULL,
	"high_percentile_bps" integer NOT NULL,
	"low_premium_bps" integer NOT NULL,
	"high_premium_bps" integer NOT NULL,
	"expected_cost_percentile_bps" integer,
	"backtest_score_bps" integer,
	"sample_size" integer,
	"avg_overpay" integer,
	"avg_underbid" integer,
	"delta_max_bps" integer,
	"source" varchar(64) NOT NULL,
	"note" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"activated_at" timestamp with time zone,
	"activated_by" varchar(128)
);
--> statement-breakpoint
ALTER TABLE "keyword_groups" ADD COLUMN IF NOT EXISTS "search_keyword" varchar(128);--> statement-breakpoint
ALTER TABLE "round_keyword_groups" ADD COLUMN IF NOT EXISTS "total_slots" smallint;--> statement-breakpoint
ALTER TABLE "round_keyword_groups" ADD COLUMN IF NOT EXISTS "brands_scraped_at" timestamp with time zone;--> statement-breakpoint
ALTER TABLE "round_keyword_groups" ADD COLUMN IF NOT EXISTS "detected_slot_count" smallint;--> statement-breakpoint
ALTER TABLE "round_brands" ADD COLUMN IF NOT EXISTS "display_name" varchar(200);--> statement-breakpoint
ALTER TABLE "round_brands" ADD COLUMN IF NOT EXISTS "sub_title" text;--> statement-breakpoint
ALTER TABLE "round_brands" ADD COLUMN IF NOT EXISTS "description" text;--> statement-breakpoint
CREATE UNIQUE INDEX "strategy_params_active_unique" ON "strategy_params" USING btree ("product_code") WHERE status = 'active';