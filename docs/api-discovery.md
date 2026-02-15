# BPSB API Discovery — February 15, 2026

> All flows confirmed working with plain `requests.Session()` (no browser needed).
> Total time for full discovery: ~2-3 seconds per flow.

## Session Management

- **Cookie**: `PHPSESSID` — set on first GET, maintained for all subsequent requests
- **No CSRF** on booking flow (steps 1-4, register)
- **CSRF required** on login only: `_csrf_token` from login form

---

## Booking Flow (Public — No Auth)

### Step 1: Load page (establish session)
```
GET /client-interface/appointment-subscription/step1
→ Sets PHPSESSID cookie
```

### Step 2: Submit subscription code
```
POST /client-interface/appointment-subscription/step2
Body: clientInput=<subscription_code>
→ Returns hidden inputs: subscription=<id>, resource=<id>
→ Also contains subscription metadata:
  - <h4>Resource name</h4> (e.g., "Sauna")
  - Subscription type (e.g., "ABONAMENT SAUNA 10 SEDINTE")
  - "Valabilitate: DD.MM.YYYY - DD.MM.YYYY"
  - "Sedinte disponibile: N"
```

### Step 3: Select resource (sauna)
```
POST /client-interface/appointment-subscription/step3
Body: resource=<resource_id>&subscription=<subscription_id>
→ Returns datepicker config with:
  - valabilityStart / valabilityEnd (moment dates)
  - daysOfWeekDisabled: "0,1" (Sunday, Monday)
  - Holiday blackout dates (hardcoded in changeDate handler)
```

### Step 4: Get slots for a date
```
POST /client-interface/appointment-subscription/step4
Body: date=<YYYY-MM-DD>
→ Returns HTML with slot cards, each containing (in this order):
  - <form> with <input type="hidden" name="interval" value="<interval_id>">
  - <h5> with "Grupa HH:MM - HH:MM" (e.g., "Grupa 07:00 - 10:30")
  - <p> with "Locuri disponibile: N"
  - <button> "Selecteaza"
```

**Can call step4 repeatedly** for different dates within the same session (no need to redo steps 1-3).

### Step 5: Add slot to cart
```
POST /client-interface/appointment-subscription/register
Body: interval=<interval_id>
→ Adds slot to server-side cart
→ Redirects (302) back to step4
→ Cart visible in "Rezumatul comenzii tale" side panel
→ Temporarily holds the spot (decreases visible availability)
```

**Cart management:**
```
GET /client-interface/appointment-subscription/remove/<index>
→ Removes item at index from cart (0-based)
```

Can add multiple slots to cart before finalizing.

### Step 6: Finalize booking
```
GET /client-interface/appointment-subscription/final
→ Commits all cart items as real appointments
→ Returns HTML with: "Programarea a fost adaugata cu succes"
→ Appointments now visible in authenticated /client-user/appointments
```

**TESTED AND CONFIRMED** — full flow verified: register → final → appears in status → deletable.

**Important:** Without calling /final, slots are held temporarily but no appointment is created. Cart is scoped to the PHP session.

---

## Auth Flow (Login)

### Load login page
```
GET /client-user/appointments
→ Redirects to /login
→ Returns form with _csrf_token hidden input
```

### Submit login
```
POST /login_check
Body: _csrf_token=<token>&_username=<email>&_password=<password>&_submit=Autentificare
→ Redirects to /client-user/appointments on success
→ Stays on /login on failure
```

---

## Appointments (Authenticated)

### View appointments
```
GET /client-user/appointments
→ HTML table with rows:
  - cells[1]: Resource (e.g., "Sauna")
  - cells[2]: DateTime (e.g., "17.02.2026 17:30 - 21:00")
  - cells[3]: Places count
  - cells[4]: Price
  - button.deleteAppButton[data-id="<base64_id>"]
```

### Delete an appointment
```
GET /appointment/delete/<base64_id>
→ Returns JSON (success/failure)
```

**Note**: This is a GET, not a POST. The SweetAlert2 confirmation dialog is purely client-side.

### Reschedule endpoint (discovered, not tested)
```
/client-user/moveAppointment/<base64_id>/<YYYY-MM-DD>
```

---

## Datepicker Config (from Step 3 JS)

```javascript
var valabilityStart = moment("2026-01-08");
var valabilityEnd = moment("2026-03-21");
// maxDate = min(valabilityEnd, today + 30 days)

$('#rg_datepicker').datepicker({
    daysOfWeekDisabled: "0,1",  // Sunday=0, Monday=1
    language: "ro",
});

// Holiday blackout dates (checked on changeDate):
// 2025-12-25, 2025-12-26, 2026-01-01, 2026-01-02,
// 2026-01-06, 2026-01-07, 2026-01-24, 2026-04-10,
// 2026-04-11, 2026-04-12, 2026-04-13, 2026-05-01,
// 2026-05-31, 2026-06-01, 2026-08-15, 2026-11-30,
// 2026-12-01, 2026-12-25, 2026-12-26
```

---

## Performance Comparison

| Operation | Selenium | HTTP requests |
|-----------|----------|--------------|
| Check 7 dates | ~30-60s | **2.6s** |
| Check 30 dates | ~2-3 min | **10s** |
| Login + list appointments | ~8-10s | **1.5s** |
| Delete appointment | ~5-8s | **0.3s** |
| Memory usage | ~200MB (Chrome) | ~5MB |
