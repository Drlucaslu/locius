---
name: travel-planning
description: 旅行：机票/酒店比价、行程规划、签证入境、天气与行李、当地交通（Google Flights、Booking.com、Google 地图、官方来源）Flights, hotels, itineraries, visas, weather and packing, local transport.
---
# Travel planning / 旅行规划

## 0. Ground rules
- Research only: never book, pay or hold anything. Stop at the page that asks for passenger or card details and say so.
- Every price, time and policy needs a source link and the time you checked it ("查询于 10/12 14:05 SGT"). Prices with currency.
- Do NOT open gmail / calendar / memory tools for general travel questions. Use them only when the request is about the
  user's *own* booked trip ("my flight", "我订的酒店", "从邮件里找行程").
- Do not assume group size, companions or a business purpose. Use what the request says; otherwise plan for the
  number of people stated, or say "按 1 人计".
- The user lives in Singapore unless told otherwise: currency SGD, plugs Type G (UK 3-pin) → Japan uses Type A/B
  (100 V), so an adapter is needed; Singapore passport holders' rules, not China's.
- Never repeat passport numbers, expiry dates or birth dates in an answer unless a form needs them.

## 1. Flights
- Google Flights: `https://www.google.com/travel/flights?hl=en&curr=SGD&q=Flights%20from%20SIN%20to%20NRT%20on%202026-11-20%20one%20way%20nonstop`
  If the form is not prefilled, fill it: click the "Where from?" box, then type into the **inner text input** of the
  dialog that opens (not the dialog itself), wait for the suggestion list and click the airport; same for "Where to?";
  pick the date in the calendar and press "Done", then "Search". Turn on "Nonstop only" under Stops.
- Use IATA codes (SIN, NRT, HND, KIX, ICN, HKG, YVR). "Tokyo" = NRT + HND → search `TYO` or check both.
- Fallback when Google Flights fails twice: the airline sites (singaporeair.com, jal.co.jp, ana.co.jp, flyscoot.com)
  or Skyscanner `https://www.skyscanner.com.sg/transport/flights/sin/tyoa/261120/?adultsv2=1&cabinclass=economy&preferdirects=true`.
- Do not spend more than ~6 steps on one site; switch source instead.

## 2. Hotels
- Booking.com search URL (fills everything at once):
  `https://www.booking.com/searchresults.html?ss=Ginza%2C+Tokyo&checkin=2026-11-20&checkout=2026-11-23&group_adults=2&no_rooms=1&selected_currency=SGD&nflt=review_score%3D80`
  (`review_score=80` = 8.0+, `90` = 9.0+; add `%3Bprice%3DSGD-min-400-1` for a nightly cap).
- After the search page opens, read the hotel cards with **browser_read on the same search URL** (full text: names,
  scores, prices) or browser_find "per night" / "Show prices" — do not re-open the search with small URL changes; after
  two loads that show no hotel cards, change source (Agoda `https://www.agoda.com/search?city=5085&checkIn=2026-11-20&los=3&adults=2&currency=SGD`,
  Google Hotels `https://www.google.com/travel/hotels/Ginza?hl=en&curr=SGD`). Hotels.com and Trip.com often show robot checks.
- Report per hotel: total and per-night price (taxes in or out), review score, nearest station + walk minutes,
  free cancellation yes/no and until when, link.
- If nothing fits the budget, widen before giving up: nearby areas (Ginza → Tsukiji, Higashi-Ginza, Kyobashi,
  Nihonbashi, Shimbashi), a lower score threshold, or one less night — and say what you widened.

## 3. Itineraries and travel times
- Check every "X minutes from Y" with Google Maps directions, transit mode:
  `https://www.google.com/maps/dir/?api=1&origin=Kyoto+Station&destination=Nishiki+Market&travelmode=transit`
  Never guess distances or which area a place is in — look it up (e.g. the Nintendo Museum is in Uji, not near Kyoto Station).
- Group sights by area, at most the number per day the user asked for, with travel mode and time between them,
  opening hours / closed days, and whether a reservation is needed (Ghibli Museum, teamLab, Nintendo Museum …).
- With children or older people: shorter walks, rest breaks, earlier evenings.

## 4. Visas, entry, health
- Use official sources only: Japan MOFA (mofa.go.jp/j_info/visit/visa), the embassy site, Visit Japan Web
  (vjw-lp.digital.go.jp), ICA for Singapore, the destination's immigration site. Quote what they say; do not add
  rules they don't state (e.g. a passport-validity rule) — if unsure, say "以官方为准" and link it.

## 5. Weather and packing
- Use climate normals from the national weather service (Japan: JMA `https://www.data.jma.go.jp/obd/stats/etrn/`) or
  a named forecast site for dates within ~10 days. Give average high/low and rain days for the actual period asked;
  label forecast vs. historical average.
- Packing list by category (clothes for the stated temperatures, documents, electronics incl. the plug adapter,
  health, money/IC card), matched to the trip length.

## 6. Rail, local transport, money
- Japan rail fares: JR Central / JR West official fare pages, SmartEX; JR Pass price at japanrailpass.net. Show the sum.
- Airport transfers: compare 3 options with time, price and source (e.g. Keikyu, monorail, limousine bus, taxi).
- Exchange rates: name the source and time (e.g. MAS, xe.com, Google Finance).
- Budgets: every line needs a basis — a looked-up price (hotel search, fare table) or a named estimate source
  (e.g. JNTO / Japan Guide typical costs). Say "1 人" or the stated group size, and keep totals consistent with the rows.
- Check rule changes with a current official page before stating them (e.g. Nozomi non-reserved seats are suspended
  only in peak periods — check JR Central's notice for the dates in question).

## 7. Car rental (Japan)
- Compare on one aggregator plus one company site: ToCoo! (`https://www2.tocoo.jp/en/`), Tabirai (`https://www.tabirai.net/car/`),
  Rakuten Travel rent-a-car, or the companies directly — Toyota Rent a Car (`https://rent.toyota.co.jp/en/`), Times Car
  Rental, Nippon Rent-A-Car, Orix. Set pick-up/return place, dates and car class, then read the quote page (stop there).
- For winter (Dec–Mar, Hokkaido/Tohoku) report: studless winter tyres included or extra (and the fee), 4WD option,
  CDW (免責補償) price, NOC (Non-Operation Charge, 营业损失赔偿) amount and the cover that waives it, ETC card, and
  whether an International Driving Permit (1949 Geneva) is accepted for a Singapore licence.
- If a quote needs a login or a date picker that will not take input after two tries, use the other site.

## 8. Insurance and other plan tables
- Read the insurer's official plan / benefits table or policy wording (PDF). Quote numbers with plan names exactly as
  written; give premiums only from an actual quote page.
- Sanity-check tables you extract: higher tiers normally have equal or higher limits. If a number breaks the pattern
  (e.g. a top plan with a lower cancellation limit than a middle plan), re-read that row or mark it "需核实".

## 8b. Attraction tickets (teamLab, museums, theme parks)
- Prices: read the official price page with browser_read. Availability: open the official ticket calendar for the date
  (it usually shows sold-out / few left per time slot) — navigate to its URL rather than clicking "Buy" buttons.
- A click on "Buy / Reserve / Book" asks the user for approval. When the user said "stop before payment", it is fine to
  ask once to reach the date/time selection, but report prices and slots you already found in the same answer.

## 9. Multi-city trips
- Fix concrete dates first (e.g. day 1 = a date the user gave, or the next suitable date ≥ 2 weeks out, and say so),
  then search every leg on its own date in that same trip: SIN→ICN day 1, ICN→NRT day N, NRT→SIN last day. Never mix
  prices from unrelated dates. Also check a multi-city search (Google Flights "Multi-city") against the sum of one-ways.
- Cabin: what the request says; if it says nothing and memory has a cabin preference, use it and say so in one line.

## 10. Answer format
- A table first (option / price / time / key condition / link), then a 2–3 line recommendation with the reason.
- Before sending, check every summary sentence against the table: if an option misses a criterion (budget, rating,
  dates), say which ones meet it and which don't — never write "all meet …" when a row does not.
- Say what was not verified.
