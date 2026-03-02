console.log("Lotto Navi engine initializing...");
/**
 * 로또 Navi by Kinov Ai - Core Logic Engine (UX High-End v2)
 * 6단계 테마 내비게이션 및 정밀 필터링 알고리즘
 */

class LottoNaviEngine {
    constructor(historyData) {
        // Normalize keys to String to ensure consistent access (JSON keys are always strings)
        this.history = {};
        for (const key of Object.keys(historyData)) {
            this.history[String(key)] = historyData[key];
        }
        this.latestRound = String(Math.max(...Object.keys(this.history).map(Number)));
    }

    /**
     * AC(Arithmetic Complexity) 값 계산
     * 6개 번호의 모든 조합 간의 차이(difference) 중 고유한 값의 개수 - 5
     */
    calculateAC(numbers) {
        if (numbers.length !== 6) return 0;
        const sorted = [...numbers].sort((a, b) => a - b);
        const diffs = new Set();
        for (let i = 0; i < sorted.length; i++) {
            for (let j = i + 1; j < sorted.length; j++) {
                diffs.add(sorted[j] - sorted[i]);
            }
        }
        return diffs.size - 5;
    }

    /**
     * 번호 합계 계산
     */
    calculateSum(numbers) {
        return numbers.reduce((a, b) => Number(a) + Number(b), 0);
    }

    /**
     * 홀짝 비율 계산 (홀수의 개수 반환)
     */
    calculateOddCount(numbers) {
        return numbers.filter(n => n % 2 !== 0).length;
    }

    /**
     * 이월수 개수 확인 (직전 회차와 겹치는 번호 수)
     */
    getCarryOverCount(numbers, round = this.latestRound) {
        const prevNumbers = this.history[round]?.slice(0, 6) || [];
        return numbers.filter(n => prevNumbers.includes(n)).length;
    }

    /**
     * 번호별 미출현 기간(weeks) 계산
     */
    getMissingDurations() {
        const durations = {};
        for (let i = 1; i <= 45; i++) {
            let weeks = 0;
            let found = false;
            while (!found && this.latestRound - weeks > 0) {
                const roundData = this.history[this.latestRound - weeks];
                if (roundData && roundData.slice(0, 6).map(Number).includes(i)) {
                    found = true;
                } else {
                    weeks++;
                }
            }
            durations[i] = weeks;
        }
        return durations;
    }

    /**
     * AI 추천 미출현 번호 3인(캡슐) 선정
     * @param {number[]} exclude 제외할 번호 목록 (예: 1단계 선택 번호)
     */
    getAIRecommendedMissingCapsules(exclude = []) {
        const durations = this.getMissingDurations();
        const excludeNums = exclude.map(Number);
        const pool = Object.keys(durations)
            .filter(n => durations[n] >= 5)
            .map(Number)
            .filter(n => !excludeNums.includes(n)); // 제외 번호 필터링

        const weighted = pool.map(n => ({
            num: n,
            weeks: durations[n],
            weight: this.calculateWeight(n)
        })).sort((a, b) => b.weight - a.weight);

        const selected = weighted.slice(0, 3);
        if (selected.length > 0) {
            selected[0].isHighest = true; // 가중치 1등에게 Highest Probability 부여
        }
        return selected;
    }

    /**
     * 이웃수 계산 (특정 회차 번호들의 ±1 번호)
     */
    getNeighborNumbers(round = this.latestRound) {
        const baseNumbers = this.history[round]?.slice(0, 6) || [];
        const neighbors = new Set();
        baseNumbers.forEach(n => {
            if (n > 1) neighbors.add(n - 1);
            if (n < 45) neighbors.add(n + 1);
        });
        return Array.from(neighbors).sort((a, b) => a - b);
    }

    /**
     * 회귀 주기별 번호 가져오기 (예: 7회귀면 7회 전 번호)
     */
    getRegressionNumbers(cycle) {
        const targetRound = this.latestRound - cycle;
        return this.history[targetRound]?.slice(0, 6) || [];
    }

    /**
     * 특정 끝수를 가진 번호들 추출 (예: 끝수 3 -> 3, 13, 23, 33, 43)
     */
    getNumbersByEndingDigit(digit) {
        const results = [];
        for (let i = 1; i <= 45; i++) {
            if (i % 10 === digit) results.push(i);
        }
        return results;
    }

    /**
     * 특정 번호 n의 가중치 P(n) 계산
     * P(n) = (역대 출현 빈도) * (최근 회귀 일치도) * (이월 성능 가중치) * (사용자 선호도)
     */
    calculateWeight(n, userPreference = 1.0, isCarryOverContext = false) {
        const num = Number(n);
        // 역대 출현 빈도
        let appearanceCount = 0;
        let totalRounds = Object.keys(this.history).length;
        for (const round in this.history) {
            if (this.history[round].slice(0, 6).map(Number).includes(num)) appearanceCount++;
        }
        const frequencyFactor = appearanceCount / totalRounds;

        // 최근 회귀 일치도 (최근 10회차 가중치)
        let recentFactor = 1.0;
        for (let i = 0; i < 10; i++) {
            const r = this.latestRound - i;
            if (this.history[r]?.slice(0, 6).map(Number).includes(num)) {
                recentFactor += (10 - i) * 0.1;
            }
        }

        // 이월 성능 가중치 (Carry-over Ratio)
        // 역대 이월 횟수 / 역대 출현 횟수
        let carryOverCount = 0;
        const rounds = Object.keys(this.history).map(Number).sort((a, b) => a - b);
        for (let i = 1; i < rounds.length; i++) {
            const prev = this.history[rounds[i - 1]].slice(0, 6).map(Number);
            const curr = this.history[rounds[i]].slice(0, 6).map(Number);
            if (prev.includes(num) && curr.includes(num)) carryOverCount++;
        }
        const carryOverRatio = appearanceCount > 0 ? (carryOverCount / appearanceCount) : 0;

        // 이월수 추천 상황(Step 1)일 경우 이월 확률 가중치를 더 강하게 적용
        const carryOverFactor = isCarryOverContext ? (1.0 + carryOverRatio * 2) : (1.0 + carryOverRatio);

        return frequencyFactor * recentFactor * carryOverFactor * userPreference;
    }

    /**
     * 특정 번호의 이월 확률(%) 반환
     */
    getCarryOverProbability(n) {
        const num = Number(n);
        let appearanceCount = 0;
        let carryOverCount = 0;
        const rounds = Object.keys(this.history).map(Number).sort((a, b) => a - b);
        for (let i = 0; i < rounds.length; i++) {
            const curr = this.history[rounds[i]].slice(0, 6).map(Number);
            if (curr.includes(num)) {
                appearanceCount++;
                if (i > 0) {
                    const prev = this.history[rounds[i - 1]].slice(0, 6).map(Number);
                    if (prev.includes(num)) carryOverCount++;
                }
            }
        }
        return appearanceCount > 0 ? (carryOverCount / appearanceCount * 100).toFixed(1) : "0.0";
    }

    /**
     * AI 추천 이월수 2개 선정 (가중치 기반)
     */
    getAIRecommendedCarryover(round = this.latestRound) {
        const baseNumbers = this.history[round]?.slice(0, 6) || [];
        const weighted = baseNumbers.map(n => ({
            num: n,
            weight: this.calculateWeight(n, 1.0, true)
        })).sort((a, b) => b.weight - a.weight);
        return weighted.slice(0, 2).map(x => x.num);
    }

    /**
     * AI 추천 이웃수 2개 선정 (가중치 기반)
     */
    getAIRecommendedNeighbors(round = this.latestRound) {
        const baseNumbers = this.history[round]?.slice(0, 6) || [];
        const neighbors = this.getNeighborNumbers(round).filter(n => !baseNumbers.includes(n));
        const weighted = neighbors.map(n => ({
            num: n,
            weight: this.calculateWeight(n)
        })).sort((a, b) => b.weight - a.weight);
        return weighted.slice(0, 2).map(x => x.num);
    }

    /**
     * 6단계 필터링 및 추천 엔진
     */
    generateRecommendedNumbers(filters = {}) {
        const fixedNumbers = (filters.fixedNumbers || []).map(Number);
        const fixedCount = fixedNumbers.length;

        // 1~45개 번호 풀 생성 (이미 고정된 번호는 제외)
        let pool = Array.from({ length: 45 }, (_, i) => i + 1).filter(n => !fixedNumbers.includes(n));

        // 가중치 적용하여 정렬
        const weightedPool = pool.map(n => ({
            num: n,
            weight: this.calculateWeight(n, filters.userPref?.[n] || 1.0)
        })).sort((a, b) => b.weight - a.weight);

        // 시뮬레이션: 필터 조건에 맞는 조합이 나올 때까지 반복
        let attempts = 0;
        while (attempts < 5000) {
            attempts++;
            // 고정수 포함
            const candidate = [...fixedNumbers];
            const tempPool = [...weightedPool];

            // 부족한 만큼만 풀에서 채움 (상위 가중치 위주)
            for (let i = 0; i < (6 - fixedCount); i++) {
                if (tempPool.length === 0) break;
                // 상위 20개 중 랜덤 (또는 풀이 작으면 풀 전체)
                const pickLimit = Math.min(tempPool.length, 20);
                const idx = Math.floor(Math.random() * pickLimit);
                candidate.push(tempPool.splice(idx, 1)[0].num);
            }

            if (candidate.length < 6) continue;
            candidate.sort((a, b) => a - b);

            // 필터 검증
            if (filters.minSum && this.calculateSum(candidate) < filters.minSum) continue;
            if (filters.maxSum && this.calculateSum(candidate) > filters.maxSum) continue;
            if (filters.minAC && this.calculateAC(candidate) < filters.minAC) continue;
            if (filters.exactOdd !== undefined && this.calculateOddCount(candidate) !== filters.exactOdd) continue;

            // 이월수 필터 (고정수 포함 결과로 체크)
            if (filters.exactCarry !== undefined && this.getCarryOverCount(candidate) !== filters.exactCarry) continue;

            if (filters.exactMissing !== undefined) {
                const missingNums = this.getMissingNumbers(filters.missingLookback || 10);
                const count = candidate.filter(n => missingNums.includes(n)).length;
                if (count !== filters.exactMissing) continue;
            }

            if (filters.regressionCycle && filters.regressionMatchCount) {
                const regNums = this.getRegressionNumbers(filters.regressionCycle);
                const matchCount = candidate.filter(n => regNums.includes(n)).length;
                if (matchCount < filters.regressionMatchCount) continue;
            }

            if (filters.preferredEndingDigits && filters.preferredEndingDigits.length > 0) {
                const matches = candidate.filter(n => filters.preferredEndingDigits.includes(n % 10));
                if (matches.length < 1) continue; // 최소 1개는 포함되어야 함
            }

            return candidate; // 조건 만족 시 반환
        }

        return weightedPool.slice(0, 6).map(n => n.num); // 실패 시 가중치 상위 6개
    }

    /**
     * AI 패턴 궁합 점수 계산
     * 역대 당첨 조합들과의 유사도(AC, 합계, 홀짝)를 비교하여 점수화
     */
    /**
     * Step 3: 홀짝 비율 및 총합 골든존 최적화 추천
     * @param {number[]} fixedNums Step 1, 2에서 선택된 고정수
     * @param {number} targetOddCount 목표 홀수 개수 (0~6)
     * @returns {number[]} 최적의 추가 번호 4개 (총 6개 중 고정수 2개를 뺀 나머지)
     */
    getAIRecommendedBalanceNumbers(fixedNums, targetOddCount) {
        // 타입 정합성을 위해 입력값을 숫자로 강제 변환
        const fNums = (fixedNums || []).map(Number);
        const currentOddCount = fNums.filter(n => n % 2 !== 0).length;
        const remainingToFill = 6 - fNums.length;

        // 목표 홀수 개수를 맞추기 위해 추가로 필요한 홀수 개수 계산
        let neededOdd = Math.max(0, targetOddCount - currentOddCount);
        neededOdd = Math.min(remainingToFill, neededOdd);

        const neededEven = Math.max(0, remainingToFill - neededOdd);

        const pool = Array.from({ length: 45 }, (_, i) => i + 1).filter(n => !fNums.includes(n));
        const odds = pool.filter(n => n % 2 !== 0);
        const evens = pool.filter(n => n % 2 === 0);

        let bestCandidate = null;
        let bestScore = -1;

        // 3000번 시뮬레이션하여 가장 가중치 합이 높고 Golden Zone(100~170)에 근접한 조합 탐색
        for (let i = 0; i < 3000; i++) {
            const selectedOdds = this.sampleFromPool(odds, neededOdd);
            const selectedEvens = this.sampleFromPool(evens, neededEven);
            const candidate = [...selectedOdds, ...selectedEvens];
            const fullSet = [...fNums, ...candidate];
            const sum = this.calculateSum(fullSet);

            // Golden Zone (100~170) 우선순위 부여
            if (sum >= 100 && sum <= 170) {
                const totalWeight = candidate.reduce((acc, n) => acc + this.calculateWeight(n), 0);
                if (totalWeight > bestScore) {
                    bestScore = totalWeight;
                    bestCandidate = candidate;
                }
            }
        }

        // Golden Zone 실패 시 가장 근접한 조합이라도 반환 (안전장치)
        if (!bestCandidate) {
            let minDiff = 1000;
            for (let i = 0; i < 500; i++) {
                const sOdds = this.sampleFromPool(odds, Math.max(0, neededOdd));
                const sEvens = this.sampleFromPool(evens, Math.max(0, neededEven));
                const cand = [...sOdds, ...sEvens];
                const sum = this.calculateSum([...fNums, ...cand]);
                const actualDiff = Math.min(Math.abs(sum - 100), Math.abs(sum - 170));
                if (actualDiff < minDiff) {
                    minDiff = actualDiff;
                    bestCandidate = cand;
                }
            }
        }

        const result = bestCandidate ? bestCandidate.sort((a, b) => a - b) : [];
        console.log("getAIRecommendedBalanceNumbers result:", result);
        return result;
    }

    sampleFromPool(pool, count) {
        const result = [];
        const temp = [...pool];
        for (let i = 0; i < count; i++) {
            if (temp.length === 0) break;
            const idx = Math.floor(Math.random() * temp.length);
            result.push(temp.splice(idx, 1)[0]);
        }
        return result;
    }

    /**
     * Step 5: AI 추천 끝수 분석
     * 현재까지의 고정수와 역대 데이터 분석을 통해 궁합이 좋은 끝수 2~3개 추천
     */
    getAIRecommendedEndings(fixedNums = []) {
        const endingCounts = {};
        for (let i = 0; i < 10; i++) endingCounts[i] = 0;

        // 최근 10회차 출현 끝수 빈도 분석
        const rounds = Object.keys(this.history).map(Number).sort((a, b) => b - a).slice(0, 10);
        rounds.forEach(r => {
            this.history[r].slice(0, 6).forEach(n => {
                endingCounts[n % 10]++;
            });
        });

        // 현재 고정수들의 끝수 가중치 부여 (중복 끝수 피하거나 선호 패턴 유도)
        fixedNums.forEach(n => {
            endingCounts[n % 10] += 5; // 이미 나온 끝수는 다음에도 나올 확률이 높다는 로또계의 가설 반영(Hot digits)
        });

        const sorted = Object.keys(endingCounts).map(Number).sort((a, b) => {
            return (endingCounts[b] + this.calculateWeight(b + 10)) - (endingCounts[a] + this.calculateWeight(a + 10));
        });

        return sorted.slice(0, 3); // 상위 3개 추천
    }
}

// 브라우저 환경에서 사용 가능하도록 내보내기
if (typeof window !== 'undefined') {
    window.LottoNaviEngine = LottoNaviEngine;
}
