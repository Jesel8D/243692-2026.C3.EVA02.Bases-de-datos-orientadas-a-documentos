-- PROPOSAL ONLY: text extraction, not the timestamptz cast in the official Q2.
-- Requires explicit --accept-text-index-proposal. Does not promise index usage.
CREATE INDEX orders_timestamp_text_idx ON public.orders ((data->>'timestamp'));
