---
name: restaurant-booking
description: 订餐厅：查真实空位、比较、预订（Google 地图 / Reserve with Google、Chope、TableCheck、餐厅官网）Find restaurants, check real availability, compare and book a table.
---
# Restaurant booking / 订餐厅

## 0. What you need
- Date, time (and how flexible, e.g. ±30 min), party size, area, cuisine / budget — or a specific restaurant.
- For the booking itself: the name, phone and email to book under. Look in memory first (memory_search "phone", "email", "booking name").
  If they are missing, ask the user once **before the booking step** (searching doesn't need them).
- Occasion, dietary needs, seating wishes (memory_search "diet", "allergy" only if the user mentioned it).
- If Google Calendar is connected, check calendar_list_events around that time for conflicts.

## 1. Find candidates — Google Maps first
- Search: `https://www.google.com/maps/search/<cuisine>+restaurant+<area>+<city>?hl=en` (use + for spaces).
  Each result shows name, rating (number of reviews), price, category, address, open/closed, and often a **"Reserve a table"** link.
- A specific restaurant: `https://www.google.com/maps/search/<restaurant name>+<city>?hl=en`, then open the place.
- Pick 5–8 that fit: rating ≥ 4.3 with a decent number of reviews (unless the user says otherwise), open at that time, price fits.
  Skip "Sponsored" results unless they clearly fit.
- If Google shows a SITE BLOCKED / "unusual traffic" page, use browser_search and the platforms in step 2.

## 2. Check REAL availability
For each candidate, in this order:
a) **Reserve with Google** — the "Reserve a table" link (google.com/maps/reserve/...). The page has *Party*, *Date* and *Time*
   controls: click each one and pick from the list / calendar. It then shows the bookable times and the providers
   (e.g. Chope, Quandoo, TableCheck).
b) The booking provider's page for that restaurant: Chope (chope.co), TableCheck (tablecheck.com), Quandoo, SevenRooms,
   Inline, Eatigo, OpenTable, or the restaurant's own "Reservations / Book" page.
c) No online booking → give the phone number and say the user has to call (OMuse can't make phone calls).

Rules:
- Report a time as available **only** after you set that restaurant's date and party size on its booking page and saw the
  time offered. Times on search/listing pages are often generic — mark them "未核实 unverified".
- If several restaurants show exactly the same list of times, be suspicious and verify on one booking page.
- Checking is not booking: the offered times are in the time list / slot buttons once date and party are set (Chope:
  the *Time* dropdown on the restaurant page lists only bookable times). Do NOT press "Book Now" / "Reserve" / "Find a
  table → Book" while only checking — that starts a booking, needs the user's approval and stops the check.
- Note deposits / prepayment, minimum spend, seating time limits (e.g. 90 min) and cancellation rules.
- Verify each shortlisted restaurant (usually 3–5) with **delegate — one sub-agent per restaurant**. Their steps don't use
  your budget, so every candidate gets checked instead of only the first one. Give each sub-agent everything it needs:
  "Check real availability at <restaurant> (<address>) on <date> around <time> for <n> people. Open <Reserve with Google
  link or booking page URL>, set party size and date, read the offered times (the time list shows them). Do NOT press Book Now / Reserve /
  Continue / Confirm.
  Report: verified times (or 'none near <time>'), booking provider, deposit/min spend, link."
- If a sub-agent can't verify, keep that restaurant as "未核实 unverified" — never fill in times yourself.

## 3. Present the options
Markdown table: restaurant · rating (reviews) · price · area · available times (✓ verified / unverified) · book via · notes.
Recommend 1–2 with a short reason. If the user already said "just book the best one", continue; otherwise ask which one
(one short question) and stop.

## 4. Book
- Open the chosen booking page, set date / time / party, fill name, phone, email (profile_get) and special requests.
- Click the final Confirm / Book / Reserve button yourself — Sentinel shows the user an approval dialog with the details.
  Don't ask for confirmation in chat.
- Login needed (Google account, Chope account…) → browser_request_takeover("请登录 … 以完成订位"). Never type passwords.
- Credit card guarantee, deposit or prepayment → say the amount and the cancellation terms first. If a card is in the vault
  (vault_list), fill it with browser_fill_secret (the user approves each field); otherwise browser_request_takeover so the
  user enters it. Never type card numbers yourself.
- Read the confirmation page: reference number, date, time, party size, address. "Request received / pending" means NOT
  confirmed yet — say so.

## 5. After booking
- Google Calendar connected → calendar_create_event: title "🍽 <restaurant>", start = booking time, end = +2 h,
  location = address, description = reference number, party size, booking link, cancellation rules; reminder_minutes 120.
- Final answer: the confirmed details, reference number, how to change/cancel, anything still pending.

## Blocked sites
Some sites (e.g. OpenTable, Tabelog) block automated browsers ("Access Denied", 403, Cloudflare "Just a moment…").
Don't retry other URLs on that site: switch at once to Reserve with Google or another provider for the same restaurant.
Japan: TableCheck (`https://www.tablecheck.com/en/japan`), Omakase (`https://omakase.in/en`), the restaurant's own site,
or Google Maps "Reserve a table". Singapore: Chope, TableCheck, SevenRooms. Say in the answer which site blocked and what
you used instead. Only if the user insists on that exact site,
request a takeover so they can pass the check themselves.

## Showing the shortlist
- When you have 2–6 verified candidates, call present_choices(kind="comparison"): label = the restaurant name as written on
  its page, details = exact snippets you read (available times, price range, rating, address). Put your recommendation
  in note. The user's pick comes back as their next message; then book it (approval).
