

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE EXTENSION IF NOT EXISTS "pgsodium";






COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "postgis" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "vector" WITH SCHEMA "extensions";






CREATE TYPE "public"."sex_type" AS ENUM (
    'male',
    'female'
);


ALTER TYPE "public"."sex_type" OWNER TO "postgres";


CREATE TYPE "public"."unit_preference_type" AS ENUM (
    'metric',
    'imperial'
);


ALTER TYPE "public"."unit_preference_type" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."find_restaurants_within_radius"("lat" double precision, "lng" double precision, "radius_meters" double precision, "result_limit" integer DEFAULT 5) RETURNS TABLE("id" "uuid", "name" character varying, "address" character varying, "latitude" double precision, "longitude" double precision, "rating" character varying, "phone" character varying, "website" character varying, "menu_url" character varying, "menu_items" "jsonb", "source" character varying, "created_at" timestamp with time zone, "updated_at" timestamp with time zone, "distance" double precision)
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.id, 
        r.name,
        r.address,
        r.latitude,
        r.longitude,
        r.rating,
        r.phone,
        r.website,
        r.menu_url,
        r.menu_items,
        r.source,
        r.created_at,
        r.updated_at,
        ST_Distance(
            r.geom, 
            ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
        ) as distance
    FROM restaurants r
    WHERE ST_DWithin(
        r.geom,
        ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
        radius_meters
    )
    ORDER BY distance
    LIMIT result_limit;
END;
$$;


ALTER FUNCTION "public"."find_restaurants_within_radius"("lat" double precision, "lng" double precision, "radius_meters" double precision, "result_limit" integer) OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."meal_logs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "name" "text" NOT NULL,
    "protein" numeric NOT NULL,
    "carbs" numeric NOT NULL,
    "fat" numeric NOT NULL,
    "calories" numeric NOT NULL,
    "meal_time" timestamp with time zone NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "notes" "text",
    "meal_type" character varying,
    "description" "text",
    "photo_url" "text",
    "serving_unit" character varying(20) DEFAULT 'grams'::character varying NOT NULL,
    "amount" numeric(10,2) DEFAULT 1.0 NOT NULL,
    "favorite" boolean DEFAULT false NOT NULL,
    "logging_mode" character varying NOT NULL
);


ALTER TABLE "public"."meal_logs" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."query_meals_by_date_range"("user_id_param" "text", "start_date_param" "date", "end_date_param" "date") RETURNS SETOF "public"."meal_logs"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  RETURN QUERY
  SELECT *
  FROM meal_logs
  WHERE user_id = user_id_param
    AND created_at::date >= start_date_param
    AND created_at::date <= end_date_param
  ORDER BY created_at DESC;
END;
$$;


ALTER FUNCTION "public"."query_meals_by_date_range"("user_id_param" "text", "start_date_param" "date", "end_date_param" "date") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."query_todays_meals"("user_id_param" "uuid") RETURNS SETOF "public"."meal_logs"
    LANGUAGE "sql" SECURITY DEFINER
    AS $$
    SELECT *
    FROM meal_logs
    WHERE 
        user_id = user_id_param
        AND DATE(created_at) = CURRENT_DATE
    ORDER BY meal_time DESC;
$$;


ALTER FUNCTION "public"."query_todays_meals"("user_id_param" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_dishes_by_nutrition_and_country"("min_protein" double precision DEFAULT 0, "max_calories" double precision DEFAULT 10000, "max_carbs" double precision DEFAULT 10000, "max_fats" double precision DEFAULT 10000, "target_country" "text" DEFAULT NULL::"text", "match_count" integer DEFAULT 10) RETURNS TABLE("id" integer, "dish_name" "text", "country" "text", "nutritional_info" "jsonb")
    LANGUAGE "sql"
    AS $$
    SELECT
        dishes.id,
        dishes.dish_name,
        dishes.country,
        dishes.nutritional_info
    FROM dishes
    WHERE 
        (nutritional_info->>'protein')::float >= min_protein
        AND (nutritional_info->>'calories')::float <= max_calories
        AND (nutritional_info->>'carbs')::float <= max_carbs
        AND (nutritional_info->>'fats')::float <= max_fats
        AND (target_country IS NULL OR LOWER(dishes.country) = LOWER(target_country))
    ORDER BY dishes.id
    LIMIT match_count;
$$;


ALTER FUNCTION "public"."search_dishes_by_nutrition_and_country"("min_protein" double precision, "max_calories" double precision, "max_carbs" double precision, "max_fats" double precision, "target_country" "text", "match_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_similar_dishes"("query_embedding" "extensions"."vector", "match_threshold" double precision DEFAULT 0.7, "match_count" integer DEFAULT 3) RETURNS TABLE("id" integer, "dish_name" "text", "similarity" double precision, "original_index" integer, "country" "text", "nutritional_info" "jsonb")
    LANGUAGE "sql"
    AS $$
    SELECT
        dishes.id,
        dishes.dish_name,
        1 - (dishes.embedding <=> query_embedding) as similarity,
        dishes.original_index,
        dishes.country,
        dishes.nutritional_info
    FROM dishes
    WHERE 1 - (dishes.embedding <=> query_embedding) > match_threshold
    ORDER BY dishes.embedding <=> query_embedding
    LIMIT match_count;
$$;


ALTER FUNCTION "public"."search_similar_dishes"("query_embedding" "extensions"."vector", "match_threshold" double precision, "match_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_similar_dishes_by_country"("query_embedding" "extensions"."vector", "target_country" "text", "match_threshold" double precision DEFAULT 0.7, "match_count" integer DEFAULT 3) RETURNS TABLE("id" integer, "dish_name" "text", "similarity" double precision, "original_index" integer, "country" "text", "nutritional_info" "jsonb")
    LANGUAGE "sql"
    AS $$
    SELECT
        dishes.id,
        dishes.dish_name,
        1 - (dishes.embedding <=> query_embedding) as similarity,
        dishes.original_index,
        dishes.country,
        dishes.nutritional_info
    FROM dishes
    WHERE 
        1 - (dishes.embedding <=> query_embedding) > match_threshold
        AND LOWER(dishes.country) = LOWER(target_country)
    ORDER BY dishes.embedding <=> query_embedding
    LIMIT match_count;
$$;


ALTER FUNCTION "public"."search_similar_dishes_by_country"("query_embedding" "extensions"."vector", "target_country" "text", "match_threshold" double precision, "match_count" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_contact_submissions_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_contact_submissions_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_modified_column"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_modified_column"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_updated_at_column"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_updated_at_column"() OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."contact_submissions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "reference_id" character varying(20) NOT NULL,
    "client_name" character varying(100) NOT NULL,
    "client_email" character varying(255) NOT NULL,
    "subject" character varying(200),
    "message" "text" NOT NULL,
    "submitted_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "ip_address" "inet",
    "user_agent" "text",
    "support_email_sent" boolean DEFAULT false,
    "confirmation_email_sent" boolean DEFAULT false,
    "status" character varying(20) DEFAULT 'open'::character varying,
    "priority" character varying(10) DEFAULT 'normal'::character varying,
    "assigned_to" character varying(100),
    "first_response_at" timestamp with time zone,
    "resolved_at" timestamp with time zone,
    "response_time_hours" integer GENERATED ALWAYS AS (
CASE
    WHEN ("first_response_at" IS NOT NULL) THEN (EXTRACT(epoch FROM ("first_response_at" - "submitted_at")) / (3600)::numeric)
    ELSE NULL::numeric
END) STORED,
    "internal_notes" "text",
    "tags" "text"[],
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "contact_submissions_priority_check" CHECK ((("priority")::"text" = ANY ((ARRAY['low'::character varying, 'normal'::character varying, 'high'::character varying, 'urgent'::character varying])::"text"[]))),
    CONSTRAINT "contact_submissions_status_check" CHECK ((("status")::"text" = ANY ((ARRAY['open'::character varying, 'in_progress'::character varying, 'resolved'::character varying, 'closed'::character varying])::"text"[])))
);


ALTER TABLE "public"."contact_submissions" OWNER TO "postgres";


COMMENT ON TABLE "public"."contact_submissions" IS 'Stores all contact form submissions from the MacroMeals website';



COMMENT ON COLUMN "public"."contact_submissions"."reference_id" IS 'Unique reference ID shown to users (e.g., REF-A1B2C3D4)';



COMMENT ON COLUMN "public"."contact_submissions"."status" IS 'Current status of the inquiry (open, in_progress, resolved, closed)';



COMMENT ON COLUMN "public"."contact_submissions"."priority" IS 'Priority level assigned by support team';



COMMENT ON COLUMN "public"."contact_submissions"."response_time_hours" IS 'Calculated hours between submission and first response';



COMMENT ON COLUMN "public"."contact_submissions"."tags" IS 'Array of tags for categorizing inquiries (e.g., billing, technical, feature-request)';



CREATE TABLE IF NOT EXISTS "public"."dishes" (
    "id" integer NOT NULL,
    "dish_name" "text" NOT NULL,
    "embedding" "extensions"."vector"(768),
    "original_index" integer,
    "country" "text",
    "nutritional_info" "jsonb",
    "created_at" timestamp without time zone DEFAULT "now"(),
    "updated_at" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."dishes" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."dishes_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."dishes_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."dishes_id_seq" OWNED BY "public"."dishes"."id";



CREATE TABLE IF NOT EXISTS "public"."meal_feedback" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "meal_name" "text",
    "feedback" "text",
    "user_id" "uuid" DEFAULT "auth"."uid"(),
    "metadata" "jsonb" DEFAULT '{}'::"jsonb",
    "meal_image" "text"
);


ALTER TABLE "public"."meal_feedback" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."notifications" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "user_id" "uuid" DEFAULT "auth"."uid"() NOT NULL,
    "type" character varying NOT NULL,
    "subtype" "text",
    "title" character varying NOT NULL,
    "body" character varying NOT NULL,
    "status" "text" DEFAULT 'unread'::"text" NOT NULL,
    "delivered_at" timestamp with time zone DEFAULT ("now"() AT TIME ZONE 'utc'::"text") NOT NULL,
    "read_at" timestamp with time zone
);


ALTER TABLE "public"."notifications" OWNER TO "postgres";


COMMENT ON TABLE "public"."notifications" IS 'This will house all scheduled, system and miscellaneous notifications sent to our users.';



CREATE TABLE IF NOT EXISTS "public"."otp" (
    "email" "text" NOT NULL,
    "otp_hash" "text" NOT NULL,
    "expires_at" timestamp without time zone NOT NULL,
    "created_at" timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE "public"."otp" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."product_feedback" (
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "product_name" "text",
    "feedback" "text",
    "user_id" "uuid" DEFAULT "auth"."uid"(),
    "metadata" "jsonb" DEFAULT '{}'::"jsonb",
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "barcode" "text"
);


ALTER TABLE "public"."product_feedback" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."products" (
    "barcode" character varying NOT NULL,
    "product_name" character varying NOT NULL,
    "brand_name" character varying,
    "nutrition_facts" "jsonb",
    "gpt_nutrition_facts" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp without time zone DEFAULT "now"(),
    "ingredients" "text"
);


ALTER TABLE "public"."products" OWNER TO "postgres";


COMMENT ON TABLE "public"."products" IS 'Stores information about food and beverage products, including unique barcodes and associated nutrition facts.';



COMMENT ON COLUMN "public"."products"."ingredients" IS 'ingredients that make up the product';



CREATE TABLE IF NOT EXISTS "public"."referral_codes" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "referral_code" "text",
    "generated_by" "uuid" DEFAULT "auth"."uid"(),
    "expires_at" timestamp with time zone,
    "metadata" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."referral_codes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."referral_tracking" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "referral_code" "text",
    "influencer_id" "uuid" DEFAULT "auth"."uid"(),
    "referred_user_id" "uuid" DEFAULT "auth"."uid"(),
    "date_used" "date"
);


ALTER TABLE "public"."referral_tracking" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."restaurants" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "name" character varying(255) NOT NULL,
    "address" character varying(500),
    "latitude" double precision,
    "longitude" double precision,
    "rating" character varying(10),
    "phone" character varying(50),
    "website" character varying(500),
    "menu_url" character varying(500),
    "menu_items" "jsonb" DEFAULT '[]'::"jsonb",
    "source" character varying(50) NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "geom" "extensions"."geography"(Point,4326) GENERATED ALWAYS AS (("extensions"."st_setsrid"("extensions"."st_makepoint"("longitude", "latitude"), 4326))::"extensions"."geography") STORED
);


ALTER TABLE "public"."restaurants" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."session_tokens" (
    "email" "text" NOT NULL,
    "token" "text" NOT NULL,
    "created_at" timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE "public"."session_tokens" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."user_preferences" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "dietary_restrictions" "text"[] DEFAULT '{}'::"text"[],
    "favorite_cuisines" "text"[] DEFAULT '{}'::"text"[],
    "disliked_ingredients" "text"[] DEFAULT '{}'::"text"[],
    "calorie_target" double precision DEFAULT '0'::double precision,
    "protein_target" double precision DEFAULT '0'::double precision,
    "carbs_target" double precision DEFAULT '0'::double precision,
    "fat_target" double precision DEFAULT '0'::double precision,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "target_weight" double precision DEFAULT '0'::double precision NOT NULL,
    "dietary_preference" character varying,
    "goal_type" character varying DEFAULT 'maintain'::character varying
);


ALTER TABLE "public"."user_preferences" OWNER TO "postgres";


COMMENT ON TABLE "public"."user_preferences" IS 'Dietary preferences for meal recommendation app users';



CREATE TABLE IF NOT EXISTS "public"."user_profiles" (
    "id" "uuid" NOT NULL,
    "email" "text" NOT NULL,
    "display_name" "text",
    "is_active" boolean DEFAULT true,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "is_pro" boolean,
    "stripe_customer_id" "text",
    "stripe_subscription_id" "text",
    "subscription_start" timestamp without time zone,
    "subscription_end" timestamp without time zone,
    "plan_tier" "text",
    "first_name" character varying,
    "last_name" character varying,
    "avatar_url" "text",
    "fcm_token" "text",
    "age" integer,
    "meal_reminder_preferences_set" boolean DEFAULT false,
    "has_macros" boolean DEFAULT false NOT NULL,
    "trial_end_date" "date",
    "sex" "public"."sex_type",
    "height" double precision,
    "dob" "date",
    "email_verified" boolean DEFAULT false,
    "plan" character varying,
    "has_used_trial" boolean DEFAULT false,
    "height_unit_preference" character varying(10) DEFAULT 'metric'::character varying NOT NULL,
    "weight_unit_preference" character varying(10) DEFAULT 'metric'::character varying NOT NULL,
    "weight" double precision,
    CONSTRAINT "user_profiles_height_unit_preference_check" CHECK ((("height_unit_preference")::"text" = ANY ((ARRAY['metric'::character varying, 'imperial'::character varying])::"text"[]))),
    CONSTRAINT "user_profiles_weight_unit_preference_check" CHECK ((("weight_unit_preference")::"text" = ANY ((ARRAY['metric'::character varying, 'imperial'::character varying])::"text"[])))
);


ALTER TABLE "public"."user_profiles" OWNER TO "postgres";


COMMENT ON TABLE "public"."user_profiles" IS 'User profile information for meal recommendation app users';



COMMENT ON COLUMN "public"."user_profiles"."is_pro" IS 'user''s subscriptions status';



COMMENT ON COLUMN "public"."user_profiles"."height" IS 'height in cm';



COMMENT ON COLUMN "public"."user_profiles"."weight" IS 'weight in kg';



CREATE TABLE IF NOT EXISTS "public"."webhook_events" (
    "id" integer NOT NULL,
    "event_id" character varying(255) NOT NULL,
    "processed_at" timestamp with time zone NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."webhook_events" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."webhook_events_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."webhook_events_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."webhook_events_id_seq" OWNED BY "public"."webhook_events"."id";



ALTER TABLE ONLY "public"."dishes" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."dishes_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."webhook_events" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."webhook_events_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."contact_submissions"
    ADD CONSTRAINT "contact_submissions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."contact_submissions"
    ADD CONSTRAINT "contact_submissions_reference_id_key" UNIQUE ("reference_id");



ALTER TABLE ONLY "public"."dishes"
    ADD CONSTRAINT "dishes_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."meal_feedback"
    ADD CONSTRAINT "meal_feedback_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."meal_logs"
    ADD CONSTRAINT "meal_logs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."notifications"
    ADD CONSTRAINT "notifications_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."otp"
    ADD CONSTRAINT "otp_pkey" PRIMARY KEY ("email");



ALTER TABLE ONLY "public"."product_feedback"
    ADD CONSTRAINT "product_feedback_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."products"
    ADD CONSTRAINT "products_barcode_key" UNIQUE ("barcode");



ALTER TABLE ONLY "public"."products"
    ADD CONSTRAINT "products_pkey" PRIMARY KEY ("barcode");



ALTER TABLE ONLY "public"."referral_codes"
    ADD CONSTRAINT "referral_codes_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."referral_tracking"
    ADD CONSTRAINT "referral_tracking_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."restaurants"
    ADD CONSTRAINT "restaurants_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."session_tokens"
    ADD CONSTRAINT "session_tokens_pkey" PRIMARY KEY ("email");



ALTER TABLE ONLY "public"."user_preferences"
    ADD CONSTRAINT "unique_user_preferences" UNIQUE ("user_id");



ALTER TABLE ONLY "public"."user_preferences"
    ADD CONSTRAINT "user_preferences_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_profiles"
    ADD CONSTRAINT "user_profiles_email_key" UNIQUE ("email");



ALTER TABLE ONLY "public"."user_profiles"
    ADD CONSTRAINT "user_profiles_fcm_token_key" UNIQUE ("fcm_token");



ALTER TABLE ONLY "public"."user_profiles"
    ADD CONSTRAINT "user_profiles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."webhook_events"
    ADD CONSTRAINT "webhook_events_event_id_key" UNIQUE ("event_id");



ALTER TABLE ONLY "public"."webhook_events"
    ADD CONSTRAINT "webhook_events_pkey" PRIMARY KEY ("id");



CREATE INDEX "dishes_country_idx" ON "public"."dishes" USING "btree" ("country");



CREATE INDEX "dishes_embedding_idx" ON "public"."dishes" USING "ivfflat" ("embedding" "extensions"."vector_cosine_ops") WITH ("lists"='100');



CREATE INDEX "dishes_nutritional_info_idx" ON "public"."dishes" USING "gin" ("nutritional_info");



CREATE INDEX "idx_contact_submissions_client_email" ON "public"."contact_submissions" USING "btree" ("client_email");



CREATE INDEX "idx_contact_submissions_priority_status" ON "public"."contact_submissions" USING "btree" ("priority", "status");



CREATE INDEX "idx_contact_submissions_reference_id" ON "public"."contact_submissions" USING "btree" ("reference_id");



CREATE INDEX "idx_contact_submissions_status" ON "public"."contact_submissions" USING "btree" ("status");



CREATE INDEX "idx_contact_submissions_submitted_at" ON "public"."contact_submissions" USING "btree" ("submitted_at" DESC);



CREATE INDEX "idx_restaurants_geom" ON "public"."restaurants" USING "gist" ("geom");



CREATE INDEX "idx_user_preferences_user_id" ON "public"."user_preferences" USING "btree" ("user_id");



CREATE INDEX "idx_user_profiles_email" ON "public"."user_profiles" USING "btree" ("email");



CREATE INDEX "idx_webhook_events_event_id" ON "public"."webhook_events" USING "btree" ("event_id");



CREATE INDEX "meal_logs_created_at_idx" ON "public"."meal_logs" USING "btree" ("created_at");



CREATE INDEX "meal_logs_meal_time_idx" ON "public"."meal_logs" USING "btree" ("meal_time");



CREATE INDEX "meal_logs_user_id_idx" ON "public"."meal_logs" USING "btree" ("user_id");



CREATE OR REPLACE TRIGGER "trigger_update_contact_submissions_updated_at" BEFORE UPDATE ON "public"."contact_submissions" FOR EACH ROW EXECUTE FUNCTION "public"."update_contact_submissions_updated_at"();



CREATE OR REPLACE TRIGGER "update_restaurants_updated_at" BEFORE UPDATE ON "public"."restaurants" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at_column"();



CREATE OR REPLACE TRIGGER "update_user_preferences_updated_at" BEFORE UPDATE ON "public"."user_preferences" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at_column"();



CREATE OR REPLACE TRIGGER "update_user_profiles_updated_at" BEFORE UPDATE ON "public"."user_profiles" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at_column"();



ALTER TABLE ONLY "public"."meal_feedback"
    ADD CONSTRAINT "meal_feedback_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."user_profiles"("id");



ALTER TABLE ONLY "public"."meal_logs"
    ADD CONSTRAINT "meal_logs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."user_profiles"("id");



ALTER TABLE ONLY "public"."notifications"
    ADD CONSTRAINT "notifications_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."user_profiles"("id");



ALTER TABLE ONLY "public"."product_feedback"
    ADD CONSTRAINT "product_feedback_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."user_profiles"("id");



ALTER TABLE ONLY "public"."referral_codes"
    ADD CONSTRAINT "referral_codes_generated_by_fkey" FOREIGN KEY ("generated_by") REFERENCES "public"."user_profiles"("id");



ALTER TABLE ONLY "public"."referral_tracking"
    ADD CONSTRAINT "referral_tracking_influencer_id_fkey" FOREIGN KEY ("influencer_id") REFERENCES "public"."user_profiles"("id");



ALTER TABLE ONLY "public"."referral_tracking"
    ADD CONSTRAINT "referral_tracking_referred_user_id_fkey" FOREIGN KEY ("referred_user_id") REFERENCES "public"."user_profiles"("id");



ALTER TABLE ONLY "public"."user_preferences"
    ADD CONSTRAINT "user_preferences_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."user_profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_profiles"
    ADD CONSTRAINT "user_profiles_id_fkey" FOREIGN KEY ("id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



CREATE POLICY "Service role can access all preferences" ON "public"."user_preferences" USING (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role can access all profiles" ON "public"."user_profiles" USING (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Service role can manage contact submissions" ON "public"."contact_submissions" USING (("auth"."role"() = 'service_role'::"text"));



CREATE POLICY "Users can only access their own preferences" ON "public"."user_preferences" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can update their own preferences" ON "public"."user_preferences" FOR UPDATE USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can update their own profile" ON "public"."user_profiles" FOR UPDATE USING (("auth"."uid"() = "id"));



CREATE POLICY "Users can view their own preferences" ON "public"."user_preferences" FOR SELECT USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view their own profile" ON "public"."user_profiles" FOR SELECT USING (("auth"."uid"() = "id"));



ALTER TABLE "public"."contact_submissions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."meal_feedback" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."meal_logs" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "meal_logs_delete_policy" ON "public"."meal_logs" FOR DELETE USING (("auth"."uid"() = "user_id"));



CREATE POLICY "meal_logs_insert_policy" ON "public"."meal_logs" FOR INSERT WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "meal_logs_select_policy" ON "public"."meal_logs" FOR SELECT USING (("auth"."uid"() = "user_id"));



CREATE POLICY "meal_logs_update_policy" ON "public"."meal_logs" FOR UPDATE USING (("auth"."uid"() = "user_id"));



ALTER TABLE "public"."notifications" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."otp" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."product_feedback" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."products" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."referral_codes" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."referral_tracking" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."restaurants" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."session_tokens" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_preferences" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_profiles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."webhook_events" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































GRANT ALL ON FUNCTION "public"."find_restaurants_within_radius"("lat" double precision, "lng" double precision, "radius_meters" double precision, "result_limit" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."find_restaurants_within_radius"("lat" double precision, "lng" double precision, "radius_meters" double precision, "result_limit" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."find_restaurants_within_radius"("lat" double precision, "lng" double precision, "radius_meters" double precision, "result_limit" integer) TO "service_role";



GRANT ALL ON TABLE "public"."meal_logs" TO "anon";
GRANT ALL ON TABLE "public"."meal_logs" TO "authenticated";
GRANT ALL ON TABLE "public"."meal_logs" TO "service_role";



GRANT ALL ON FUNCTION "public"."query_meals_by_date_range"("user_id_param" "text", "start_date_param" "date", "end_date_param" "date") TO "anon";
GRANT ALL ON FUNCTION "public"."query_meals_by_date_range"("user_id_param" "text", "start_date_param" "date", "end_date_param" "date") TO "authenticated";
GRANT ALL ON FUNCTION "public"."query_meals_by_date_range"("user_id_param" "text", "start_date_param" "date", "end_date_param" "date") TO "service_role";



GRANT ALL ON FUNCTION "public"."query_todays_meals"("user_id_param" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."query_todays_meals"("user_id_param" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."query_todays_meals"("user_id_param" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."search_dishes_by_nutrition_and_country"("min_protein" double precision, "max_calories" double precision, "max_carbs" double precision, "max_fats" double precision, "target_country" "text", "match_count" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."search_dishes_by_nutrition_and_country"("min_protein" double precision, "max_calories" double precision, "max_carbs" double precision, "max_fats" double precision, "target_country" "text", "match_count" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."search_dishes_by_nutrition_and_country"("min_protein" double precision, "max_calories" double precision, "max_carbs" double precision, "max_fats" double precision, "target_country" "text", "match_count" integer) TO "service_role";









GRANT ALL ON FUNCTION "public"."update_contact_submissions_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_contact_submissions_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_contact_submissions_updated_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_modified_column"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_modified_column"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_modified_column"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "service_role";





























































































GRANT ALL ON TABLE "public"."contact_submissions" TO "anon";
GRANT ALL ON TABLE "public"."contact_submissions" TO "authenticated";
GRANT ALL ON TABLE "public"."contact_submissions" TO "service_role";



GRANT ALL ON TABLE "public"."dishes" TO "anon";
GRANT ALL ON TABLE "public"."dishes" TO "authenticated";
GRANT ALL ON TABLE "public"."dishes" TO "service_role";



GRANT ALL ON SEQUENCE "public"."dishes_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."dishes_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."dishes_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."meal_feedback" TO "anon";
GRANT ALL ON TABLE "public"."meal_feedback" TO "authenticated";
GRANT ALL ON TABLE "public"."meal_feedback" TO "service_role";



GRANT ALL ON TABLE "public"."notifications" TO "anon";
GRANT ALL ON TABLE "public"."notifications" TO "authenticated";
GRANT ALL ON TABLE "public"."notifications" TO "service_role";



GRANT ALL ON TABLE "public"."otp" TO "anon";
GRANT ALL ON TABLE "public"."otp" TO "authenticated";
GRANT ALL ON TABLE "public"."otp" TO "service_role";



GRANT ALL ON TABLE "public"."product_feedback" TO "anon";
GRANT ALL ON TABLE "public"."product_feedback" TO "authenticated";
GRANT ALL ON TABLE "public"."product_feedback" TO "service_role";



GRANT ALL ON TABLE "public"."products" TO "anon";
GRANT ALL ON TABLE "public"."products" TO "authenticated";
GRANT ALL ON TABLE "public"."products" TO "service_role";



GRANT ALL ON TABLE "public"."referral_codes" TO "anon";
GRANT ALL ON TABLE "public"."referral_codes" TO "authenticated";
GRANT ALL ON TABLE "public"."referral_codes" TO "service_role";



GRANT ALL ON TABLE "public"."referral_tracking" TO "anon";
GRANT ALL ON TABLE "public"."referral_tracking" TO "authenticated";
GRANT ALL ON TABLE "public"."referral_tracking" TO "service_role";



GRANT ALL ON TABLE "public"."restaurants" TO "anon";
GRANT ALL ON TABLE "public"."restaurants" TO "authenticated";
GRANT ALL ON TABLE "public"."restaurants" TO "service_role";



GRANT ALL ON TABLE "public"."session_tokens" TO "anon";
GRANT ALL ON TABLE "public"."session_tokens" TO "authenticated";
GRANT ALL ON TABLE "public"."session_tokens" TO "service_role";



GRANT ALL ON TABLE "public"."user_preferences" TO "anon";
GRANT ALL ON TABLE "public"."user_preferences" TO "authenticated";
GRANT ALL ON TABLE "public"."user_preferences" TO "service_role";



GRANT ALL ON TABLE "public"."user_profiles" TO "anon";
GRANT ALL ON TABLE "public"."user_profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."user_profiles" TO "service_role";



GRANT ALL ON TABLE "public"."webhook_events" TO "anon";
GRANT ALL ON TABLE "public"."webhook_events" TO "authenticated";
GRANT ALL ON TABLE "public"."webhook_events" TO "service_role";



GRANT ALL ON SEQUENCE "public"."webhook_events_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."webhook_events_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."webhook_events_id_seq" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";






























RESET ALL;
