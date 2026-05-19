CREATE TABLE "products" (
	"id" serial PRIMARY KEY NOT NULL,
	"code" varchar(32) NOT NULL,
	"name" varchar(64) NOT NULL,
	"max_brands_per_group" smallint NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "categories" (
	"id" serial PRIMARY KEY NOT NULL,
	"parent_id" integer,
	"name" varchar(128) NOT NULL,
	"level" smallint NOT NULL
);
--> statement-breakpoint
CREATE TABLE "keyword_groups" (
	"id" serial PRIMARY KEY NOT NULL,
	"product_id" integer NOT NULL,
	"category_id" integer NOT NULL,
	"name" varchar(128) NOT NULL
);
--> statement-breakpoint
CREATE TABLE "rounds" (
	"id" serial PRIMARY KEY NOT NULL,
	"product_id" integer NOT NULL,
	"round_no" integer NOT NULL,
	"period_start" date NOT NULL,
	"period_end" date NOT NULL,
	"regular_bid_start" date,
	"regular_bid_end" date,
	"regular_announce_date" date,
	"rebid_start" date,
	"rebid_end" date,
	"rebid_announce_date" date
);
--> statement-breakpoint
CREATE TABLE "round_keyword_groups" (
	"id" serial PRIMARY KEY NOT NULL,
	"round_id" integer NOT NULL,
	"keyword_group_id" integer NOT NULL,
	"reference_query_volume" integer,
	"min_bid_price" bigint,
	"bid_status" varchar(32),
	"empty_slots" smallint,
	"keyword_count" smallint,
	"regular_winning_bid" bigint,
	"captured_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "round_keywords" (
	"id" serial PRIMARY KEY NOT NULL,
	"round_keyword_group_id" integer NOT NULL,
	"keyword" varchar(128) NOT NULL
);
--> statement-breakpoint
CREATE TABLE "brands" (
	"id" serial PRIMARY KEY NOT NULL,
	"business_name" varchar(256) NOT NULL,
	"display_name" varchar(128) NOT NULL,
	"aliases" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "round_brands" (
	"id" serial PRIMARY KEY NOT NULL,
	"round_keyword_group_id" integer NOT NULL,
	"brand_id" integer,
	"slot_no" smallint NOT NULL,
	"source" varchar(32) NOT NULL,
	"confidence" double precision,
	"captured_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "clients" (
	"id" serial PRIMARY KEY NOT NULL,
	"slug" varchar(64) NOT NULL,
	"display_name" varchar(128) NOT NULL,
	"brand_ids" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"sheet_id" varchar(128),
	"report_config" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "ingest_runs" (
	"id" serial PRIMARY KEY NOT NULL,
	"run_type" varchar(32) NOT NULL,
	"product_id" integer,
	"file_path" text,
	"status" varchar(16) NOT NULL,
	"error_message" text,
	"rows_total" integer,
	"rows_inserted" integer,
	"rows_updated" integer,
	"run_at" timestamp with time zone DEFAULT now() NOT NULL,
	"completed_at" timestamp with time zone
);
--> statement-breakpoint
ALTER TABLE "keyword_groups" ADD CONSTRAINT "keyword_groups_product_id_products_id_fk" FOREIGN KEY ("product_id") REFERENCES "public"."products"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "keyword_groups" ADD CONSTRAINT "keyword_groups_category_id_categories_id_fk" FOREIGN KEY ("category_id") REFERENCES "public"."categories"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "rounds" ADD CONSTRAINT "rounds_product_id_products_id_fk" FOREIGN KEY ("product_id") REFERENCES "public"."products"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "round_keyword_groups" ADD CONSTRAINT "round_keyword_groups_round_id_rounds_id_fk" FOREIGN KEY ("round_id") REFERENCES "public"."rounds"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "round_keyword_groups" ADD CONSTRAINT "round_keyword_groups_keyword_group_id_keyword_groups_id_fk" FOREIGN KEY ("keyword_group_id") REFERENCES "public"."keyword_groups"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "round_keywords" ADD CONSTRAINT "round_keywords_round_keyword_group_id_round_keyword_groups_id_fk" FOREIGN KEY ("round_keyword_group_id") REFERENCES "public"."round_keyword_groups"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "round_brands" ADD CONSTRAINT "round_brands_round_keyword_group_id_round_keyword_groups_id_fk" FOREIGN KEY ("round_keyword_group_id") REFERENCES "public"."round_keyword_groups"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "round_brands" ADD CONSTRAINT "round_brands_brand_id_brands_id_fk" FOREIGN KEY ("brand_id") REFERENCES "public"."brands"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ingest_runs" ADD CONSTRAINT "ingest_runs_product_id_products_id_fk" FOREIGN KEY ("product_id") REFERENCES "public"."products"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE UNIQUE INDEX "products_code_uq" ON "products" USING btree ("code");--> statement-breakpoint
CREATE UNIQUE INDEX "categories_parent_name_uq" ON "categories" USING btree ("parent_id","name");--> statement-breakpoint
CREATE UNIQUE INDEX "keyword_groups_product_name_uq" ON "keyword_groups" USING btree ("product_id","name");--> statement-breakpoint
CREATE UNIQUE INDEX "rounds_product_round_uq" ON "rounds" USING btree ("product_id","round_no");--> statement-breakpoint
CREATE UNIQUE INDEX "round_keyword_groups_round_kg_uq" ON "round_keyword_groups" USING btree ("round_id","keyword_group_id");--> statement-breakpoint
CREATE UNIQUE INDEX "round_keywords_rkg_keyword_uq" ON "round_keywords" USING btree ("round_keyword_group_id","keyword");--> statement-breakpoint
CREATE UNIQUE INDEX "brands_business_uq" ON "brands" USING btree ("business_name");--> statement-breakpoint
CREATE UNIQUE INDEX "round_brands_rkg_slot_uq" ON "round_brands" USING btree ("round_keyword_group_id","slot_no");--> statement-breakpoint
CREATE UNIQUE INDEX "clients_slug_uq" ON "clients" USING btree ("slug");