# Market Check

Quick market conditions assessment for trading decisions.

## Checks

### 1. Market Regime
- Fetch SPY and ^RUT (Russell 2000) data
- Calculate 50-day and 200-day SMAs for each
- Determine regime: BULL / BEAR / SIDEWAYS
- Show current price vs both moving averages

### 2. Volatility Assessment
- Fetch VIX current level
- Compare to historical average (~20)
- Flag if elevated (>25) or extreme (>30)

### 3. Sector Rotation (optional)
- Quick check on sector ETFs: XLK, XLF, XLE, XLV, XLI
- Show 5-day momentum for each
- Identify leading/lagging sectors

### 4. Trading Day Status
- Is market currently open?
- Time until next open/close
- Any upcoming holidays

### 5. Implications for Strategy
Based on findings, state:
- Should we be buying today? (regime check)
- Position size modifier (based on volatility)
- Sectors to favor/avoid

## Output

Concise terminal summary with:
- Regime indicator with emoji (bull/bear/flat)
- VIX level with alert if elevated
- Clear recommendation for today's trading
