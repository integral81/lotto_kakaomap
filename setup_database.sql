-- ==========================================
-- KINOV Lotto Map: Supabase Database Schema
-- ==========================================

-- 1. 역대 당첨 번호 테이블 (lotto_rounds)
CREATE TABLE IF NOT EXISTS public.lotto_rounds (
    round INT PRIMARY KEY,        -- 회차 번호 (예: 1213)
    num1 INT NOT NULL,            -- 당첨번호 1
    num2 INT NOT NULL,            -- 당첨번호 2
    num3 INT NOT NULL,            -- 당첨번호 3
    num4 INT NOT NULL,            -- 당첨번호 4
    num5 INT NOT NULL,            -- 당첨번호 5
    num6 INT NOT NULL,            -- 당첨번호 6
    bonus INT NOT NULL            -- 보너스 번호
);

-- 2. 상점 고유 정보 테이블 (lotto_stores)
-- 한 상점이 여러 번 1등을 배출할 수 있으므로 상점 정보는 고유하게 저장
CREATE TABLE IF NOT EXISTS public.lotto_stores (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,           -- 상점명
    address TEXT NOT NULL,        -- 주소
    lat FLOAT8,                   -- 위도
    lng FLOAT8,                   -- 경도
    is_online BOOLEAN DEFAULT FALSE, -- 동행복권 온라인 여부
    verified BOOLEAN DEFAULT FALSE,  -- 구글맵 좌푯값 검증 여부
    UNIQUE(name, address)         -- 이름과 주소 조합으로 중복 방지
);

-- 테이블 컬럼 인덱스 생성 (위치 기반 검색 속도 향상)
CREATE INDEX IF NOT EXISTS idx_store_location ON public.lotto_stores(lat, lng);

-- 3. 당첨 매칭 테이블 (lotto_winners)
-- 어느 방에서 몇 회차에 수동/자동으로 당첨되었는지 기록
CREATE TABLE IF NOT EXISTS public.lotto_winners (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    store_id UUID NOT NULL REFERENCES public.lotto_stores(id) ON DELETE CASCADE,
    round INT NOT NULL REFERENCES public.lotto_rounds(round) ON DELETE CASCADE,
    method TEXT NOT NULL          -- 자동, 수동, 반자동, 사이트 등
);

-- 조회 성능을 위한 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_winner_round ON public.lotto_winners(round);
CREATE INDEX IF NOT EXISTS idx_winner_store ON public.lotto_winners(store_id);

-- API 익명 읽기 권한 설정 (프론트엔드에서 데이터를 읽을 수 있게 허용)
ALTER TABLE public.lotto_rounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lotto_stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lotto_winners ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read-only access to lotto_rounds"
ON public.lotto_rounds FOR SELECT USING (true);

CREATE POLICY "Allow public read-only access to lotto_stores"
ON public.lotto_stores FOR SELECT USING (true);

CREATE POLICY "Allow public read-only access to lotto_winners"
ON public.lotto_winners FOR SELECT USING (true);
