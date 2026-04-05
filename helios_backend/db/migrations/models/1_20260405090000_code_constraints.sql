-- upgrade --
ALTER TABLE "codes"
    ADD CONSTRAINT "ck_codes_discount_percent_range"
    CHECK ("discount_percent" IS NULL OR ("discount_percent" >= 0 AND "discount_percent" <= 100));

ALTER TABLE "codes"
    ADD CONSTRAINT "ck_codes_reward_days_percent_range"
    CHECK ("reward_days_percent" IS NULL OR ("reward_days_percent" >= 0 AND "reward_days_percent" <= 100));

ALTER TABLE "codes"
    ADD CONSTRAINT "ck_codes_type_owner_consistency"
    CHECK (
        ("type" = 'PROMO' AND "owner_id" IS NULL)
        OR ("type" = 'REFERRAL' AND "owner_id" IS NOT NULL)
    );

-- downgrade --
ALTER TABLE "codes" DROP CONSTRAINT IF EXISTS "ck_codes_type_owner_consistency";
ALTER TABLE "codes" DROP CONSTRAINT IF EXISTS "ck_codes_reward_days_percent_range";
ALTER TABLE "codes" DROP CONSTRAINT IF EXISTS "ck_codes_discount_percent_range";
