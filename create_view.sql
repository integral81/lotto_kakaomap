-- Create a view to get all stores with their total win count and all winning rounds
CREATE OR REPLACE VIEW public.vw_lotto_store_stats AS
SELECT
    s.id,
    s.name,
    s.address,
    s.lat,
    s.lng,
    s.is_online,
    s.verified,
    COUNT(w.id) AS total_wins,
    jsonb_agg(
        jsonb_build_object(
            'r', w.round,
            'm', w.method
        ) ORDER BY w.round DESC
    ) AS rounds
FROM public.lotto_stores s
LEFT JOIN public.lotto_winners w ON s.id = w.store_id
GROUP BY s.id, s.name, s.address, s.lat, s.lng, s.is_online, s.verified;

-- Make it accessible to anon
GRANT SELECT ON public.vw_lotto_store_stats TO anon, authenticated;
