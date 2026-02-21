# 📊 Crypto & Stock Technical Analysis Scanner + Dashboard

Automatický skener technických vzorů pro kryptoměny a akcie s Telegram notifikacemi
a interaktivním webovým dashboardem.

**100% zdarma:** GitHub Actions + Supabase free tier + Telegram Bot API + Streamlit Community Cloud.

---

## 1. Popis projektu

Aplikace má dvě nezávislé části:

**SCANNER** – běží jako GitHub Actions cron job každých 30 minut:
- Stahuje OHLCV data pro kryptoměny (BTC, ETH, SOL via Binance public API) a akcie (AAPL, NVDA via yfinance)
- Detekuje 8 technických vzorů na timeframech 1h / 4h / 1d
- Ukládá alerty do Supabase (PostgreSQL) včetně pattern_data pro vykreslení v dashboardu
- Odesílá Telegram notifikace s odkazem na dashboard

**DASHBOARD** – Streamlit webová aplikace na Streamlit Community Cloud:
- Interaktivní svíčkový graf (Plotly) s overlay EMA, Bollinger Bands, Volume, RSI
- Vizualizace detekovaného patternu přímo v grafu (čáry, anotace, zvýraznění)
- Popis patternu + konkrétní TP/SL doporučení s Risk/Reward výpočtem
- Historie alertů ze Supabase s filtry a kliknutím pro zobrazení v grafu

### Architektura komunikace

```
GitHub Actions (každých 30 min)
       │
       ├─── yfinance / ccxt/Binance ──▶ OHLCV data
       │
       ├─── Pattern detektory ──▶ Nalezené vzory
       │
       ├─── Supabase (PostgreSQL) ──▶ Uložení alertů
       │        │                     (pattern_data JSONB)
       │        │
       │        └────────────────────▶ Streamlit Dashboard
       │                               (čte data z DB)
       │
       └─── Telegram Bot API ──▶ Notifikace uživateli
                                  (s odkazem na dashboard)
```

---

## 2. Detekované vzory

| Vzor | Timeframe | Signál |
|------|-----------|--------|
| Double Top/Bottom | 1h, 4h, 1d | Bearish/Bullish reversal |
| Head & Shoulders | 4h, 1d | Bearish/Bullish reversal |
| Bull/Bear Flag | 1h, 4h, 1d | Continuation pattern |
| Ascending/Descending Triangle | 4h, 1d | Bullish/Bearish breakout |
| Golden/Death Cross | 1d | Long-term trend change |
| RSI Divergence | 1h, 4h, 1d | Hidden strength/weakness |
| Engulfing Candle | 4h, 1d | Short-term reversal |
| S/R Breakout | 1h, 4h, 1d | Momentum breakout |

---

## 3. Telegram bot – vytvoření a nastavení

### Vytvoření bota
1. Otevři Telegram a vyhledej **@BotFather**
2. Pošli `/newbot`, zadej název bota (např. `Market Scanner`)
3. Zadej username bota (musí končit `bot`, např. `my_scanner_bot`)
4. BotFather pošle **TOKEN** ve formátu `123456789:ABCdefGHI...`
5. Ulož token – budeš ho potřebovat jako `TELEGRAM_TOKEN`

### Zjištění chat_id
1. Vyhledej v Telegramu **@userinfobot**
2. Pošli libovolnou zprávu
3. Bot odpoví číslem **Id** – to je tvoje `TELEGRAM_CHAT_ID`
4. Pro skupinový chat: přidej bota do skupiny, pošli zprávu – vrátí ID začínající `-`

### Spuštění příkazů bota
Pošli botu `/start`, pak používej:
- `/status` – sledovaná aktiva, počet alertů dnes, čas posledního
- `/scan` – okamžitý scan (i pod 65 % confidence)
- `/alerts` – posledních 10 alertů
- `/help` – seznam příkazů

---

## 4. Supabase – databáze

### Vytvoření projektu
1. Jdi na [supabase.com](https://supabase.com) a registruj se (zdarma)
2. **New Project** → zvol název, nastav heslo DB, vyber region
3. Počkej ~2 minuty na inicializaci

### SQL pro vytvoření tabulky
V levém menu klikni na **SQL Editor → New Query**, vlož a spusť:

```sql
CREATE TABLE alerts (
    id           BIGSERIAL PRIMARY KEY,
    asset        TEXT NOT NULL,
    timeframe    TEXT NOT NULL,
    pattern      TEXT NOT NULL,
    type         TEXT NOT NULL,
    confidence   NUMERIC(5,2) NOT NULL,
    price        NUMERIC(20,8) NOT NULL,
    detected_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message_sent BOOLEAN NOT NULL DEFAULT FALSE,
    key_levels   JSONB,
    pattern_data JSONB
);

CREATE INDEX idx_alerts_lookup
    ON alerts (asset, timeframe, pattern, detected_at DESC);
CREATE INDEX idx_alerts_asset_time
    ON alerts (asset, detected_at DESC);
```

### Získání přihlašovacích údajů
1. **Settings → API**
2. **Project URL** → `SUPABASE_URL`
3. **anon / public** klíč → `SUPABASE_KEY`

---

## 5. GitHub – nastavení repozitáře

### Fork a upload
1. Vytvoř nový **public** repozitář na GitHubu (Actions jsou zdarma pouze pro public repo)
2. Nahraj všechny soubory projektu (nebo použij `git push`)
3. V záložce **Actions** ověř, že jsou GitHub Actions povoleny

### GitHub Secrets
**Settings → Secrets and variables → Actions → New repository secret:**

| Secret | Hodnota |
|--------|---------|
| `TELEGRAM_TOKEN` | Token od @BotFather |
| `TELEGRAM_CHAT_ID` | Tvoje chat ID |
| `SUPABASE_URL` | URL ze Supabase Settings |
| `SUPABASE_KEY` | anon klíč ze Supabase |
| `DASHBOARD_URL` | URL dashboardu po nasazení na Streamlit (volitelné) |

> Nikdy nevkládej tokeny přímo do kódu nebo config.yaml!

---

## 6. Streamlit Community Cloud – nasazení dashboardu

### Krok 1: Registrace
1. Jdi na [streamlit.io/cloud](https://streamlit.io/cloud) a registruj se (zdarma, přes GitHub)

### Krok 2: Napojení na repozitář
1. Klikni **New app**
2. Vyber svůj GitHub repozitář
3. **Main file path:** `dashboard/app.py`
4. Klikni **Deploy**

### Krok 3: Nastavení secrets ve Streamlit Cloud
1. Po deployi klikni na **trojúhelník → Settings → Secrets**
2. Vlož secrets ve formátu TOML:

```toml
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

3. Klikni **Save** – app se automaticky restartuje

### Krok 4: Dashboard URL do Telegramu
1. Po deployi zkopíruj URL dashboardu (např. `https://muj-app.streamlit.app`)
2. Přidej do GitHub Secrets jako `DASHBOARD_URL`
3. Od teď bude každá Telegram notifikace obsahovat odkaz na dashboard

---

## 7. config.yaml – přidání vlastních aktiv

```yaml
assets:
  crypto:
    - symbol: "BTC/USDT"      # Binance trading pair (přesný formát)
      exchange: "binance"
      timeframes: ["1h", "4h", "1d"]
    - symbol: "ADA/USDT"      # Přidat nový token
      exchange: "binance"
      timeframes: ["4h", "1d"]
  stocks:
    - symbol: "MSFT"          # Yahoo Finance ticker
      timeframes: ["1d"]
    - symbol: "SPY"           # ETF
      timeframes: ["1h", "1d"]

scanner:
  min_confidence: 65          # Snizit pro vice alertu, zvysit pro mene sumu
  alert_cooldown_hours: 24    # Doba mezi opakovani stejneho alertu
```

---

## 8. Ruční testování

### Scanner (GitHub Actions)
1. Záložka **Actions** v repozitáři
2. Levé menu: **Market Scanner**
3. **Run workflow** → **Run workflow** (zelené tlačítko)
4. Klikni na spuštěný job → zobrazí se logy v reálném čase

### Dashboard (lokálně)
```bash
pip install -r requirements.txt

# Vytvoř soubor .streamlit/secrets.toml:
# SUPABASE_URL = "..."
# SUPABASE_KEY = "..."

streamlit run dashboard/app.py
```

---

## 9. Čtení logů v GitHub Actions

**Klíčové log zprávy:**
```
Scanning BTC/USDT (crypto) on 4h          # Zacina scan aktiva
  Current price: 67420.00 | Candles: 200  # Stazeno dat
  [bull_bear_flag] BTC/USDT – bullish 78  # Detekovan vzor
  Alert sent! id=42                        # Notifikace odeslana
  Duplicate within 24h – skipping         # Cooldown aktivni
No data for AAPL 1h – skipping            # Chyba dat (pokracuje)
Scan complete in 45.2s | 3 detected       # Souhrn
```

---

## 10. Troubleshooting

### Telegram notifikace neprichazejí
- Posli botu `/start` v Telegramu (musi byt aktivovan)
- Overeni `TELEGRAM_TOKEN` a `TELEGRAM_CHAT_ID` v GitHub Secrets
- Pro skupinový chat: pridej bota jako admina nebo mu posli zpravu ve skupine

### Dashboard zobrazuje "Zadna data"
- Zkontroluj Streamlit Secrets (Settings → Secrets)
- Overeni formatu TOML – klice bez uvozovek, hodnoty v uvozovkach
- Zkontroluj, zda scanner jiz ulozil nejake alerty do Supabase

### "SUPABASE_URL or SUPABASE_KEY not set"
- Overeni presne nazvy secrets – case-sensitive
- Scanner pokracuje i bez DB (alerty jsou logovany do stdout)

### Zadne alerty, confidence pod 65 %
- Trh muze byt v konsolidaci – vzory se netvoří
- Snizuj `min_confidence` na 50 pro testovani
- Zkontroluj logy pro detailni prehled vsech detekovanych vzoru

### GitHub Actions se nespoustejí
- Repozitar musi byt **public** pro free Actions
- Zalozka Actions → Settings – overeni, ze jsou Actions povoleny
- Cron joby maji zpozdeni 5-30 min na pretezenem GitHub (normalni chovani)

### Streamlit app pada pri startu
- Zkontroluj zalosku **Logs** v Streamlit Cloud
- Nejcastejsi pricina: chybi secrets nebo nekompatibilni verze knihovny
- Overeni, ze `requirements.txt` je v root adresari repozitare

---

## Stack

| Komponenta | Technologie | Cena |
|-----------|-------------|------|
| Scanner CI/CD | GitHub Actions | Zdarma (public repo) |
| Krypto data | ccxt + Binance public API | Zdarma |
| Akciova data | yfinance | Zdarma |
| Databaze | Supabase (PostgreSQL) | Zdarma (500MB) |
| Notifikace | Telegram Bot API | Zdarma |
| Dashboard | Streamlit Community Cloud | Zdarma |
| Analyza | pandas, pandas-ta, scipy, numpy | Open source |
| Grafy | Plotly | Open source |
