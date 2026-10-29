# DOCUMENT 03: APPLICATION FLOW DOCUMENT (APP FLOW)
## Application Name: QuotePulse GMC (AI-Driven Quote Preparation & Demography Workbench)

| Document Attribute | Specification |
| :--- | :--- |
| **Document Version** | 4.0 (Master Engineering Baseline) |
| **Document Type** | Application Flow & User Journey Specification |
| **Date** | 29 October 2026 |
| **Parent Documents** | `BRD v3.0`, `PRD v2.0`, `TRD v4.0` |
| **Core Architecture** | Next.js 15 (App Router, Bun 1.x) + FastAPI (Python 3.11+) + Neon PostgreSQL + Drizzle ORM + Clerk Auth + OpenAI `gpt-5.4-mini` + AWS EC2 Docker Deployment |

---

## 1. Complete Route Inventory (All Routes)

Every route in the application is enumerated below with its strict path and single-sentence functional purpose:

1. `/` — **Landing Page**: Public hero page showcasing enterprise value propositions, zero-data-retention compliance badges, and a single "Sign In with Corporate SSO" button.
2. `/login` — **Authentication Screen**: Corporate login portal governed by Clerk supporting Enterprise SAML/OIDC and email authentication; self-registration is explicitly disabled.
3. `/invite/accept` — **Invitation Acceptance Screen**: Secure token-gated landing page where an invited underwriter or sales RM sets credentials after being provisioned by an administrator.
4. `/onboarding` — **Profile Setup**: Single-step configuration screen where newly invited users confirm their display name, assigned underwriting branch, default brokerage tag, and telephone extension.
5. `/dashboard` — **Quotation Cases Dashboard**: The primary operational workbench showing all active, pending review, and completed GMC quotation cases in a virtualized, filterable table.
6. `/cases/new` — **New Case Ingestion Screen**: Modal/dedicated dropzone for uploading multi-format RFQ packages and demographic censuses, with inline password prompts for locked files.
7. `/cases/[id]` — **Pipeline Ingestion Hub**: Real-time progress screen visualizing the 4-stage ingestion pipeline (`Docling` layout parsing, `gpt-5.4-mini` 400k extraction, Polars census standardization, and Option 1–4 sub-limit matching) via Server-Sent Events (SSE).
8. `/cases/[id]/quote` — **Quotation Details Workbench**: The central 5-column review grid (`Quote Fields`, `Coverage Details`, `Proposed Details`, `Source Status`, `Confidence`) with inline editable inputs for `Rater Type`, `Brokerage %`, `PINCODE`, `State`, and `District`.
9. `/cases/[id]/treatments` — **Hospitalization & Treatments Matrix**: Categorized accordion grid displaying the 20 Modern Treatments, 11 Medical Coverages, 5 Maternity Clauses, 5 Hospital Expenses, 4 Wellness Offerings, and 6 Policy Conditions.
10. `/cases/[id]/sublimits` — **Procedure Sub-Limits Matcher**: Surgical procedure comparison table matching raw amounts against Options 1–4 and highlighting unmapped sub-limits.
11. `/cases/[id]/demography` — **Demography Workbench**: High-performance virtualized grid rendering the standardized 7-column member roster (`Age`, `Date of Birth`, `Sum Insured`, `Relationship`, `Name`, `EmpCode`, `Gender`) with dynamic age-basis recalculation.
12. `/cases/[id]/exceptions` — **Exceptions & Conflicts Queue**: Triage workspace highlighting unmapped sub-limits, under-18 workers, orphan dependants, and conflicting clauses requiring underwriter sign-off.
13. `/cases/[id]/audit` — **Audit Trail & Changelog**: Chronological, immutable audit log displaying original values, user overrides, timestamps, and reviewer email addresses.
14. `/settings` — **User Preferences & Security**: User profile view displaying role permissions, active session details, and outbound proxy/storage configuration diagnostics.
15. `/admin/users` — **User Management & Invites (Admin Only)**: Administrative console for creating users, dispatching secure invitation tokens, assigning roles, and revoking system access.
16. `/admin/registry` — **Field Registry & Rules Manager (Admin Only)**: Configuration console for managing canonical field definitions, procedure Option 1–4 matrices, and district-to-zone geographical mappings.

---

## 2. Navigation Architecture & Global Layout Structure

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       GLOBAL TOP NAVBAR                                          │
│  [Logo] QuotePulse GMC  │  Breadcrumbs: Dashboard > Apex Logistics (CASE-9021) > Quote  │  [User]│
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────┬───────────────────────────────────────────────────────────────────────────┐
│  LEFT SIDEBAR        │  SUB-TAB WORKBENCH HEADER                                                 │
│  (Collapsible 240px) │  [Quotation]  [Treatments]  [Sub-Limits]  [Demography]  [Exceptions] [Audit]│
│                      ├───────────────────────────────────────────────────────────────────────────┤
│  • Dashboard         │  ACTIVE VIEWPORT (Virtualized Grid / Form / Drawer Canvas)                │
│  • + New Case        │                                                                           │
│  • Exceptions (3)    │  Column 1: Quote Fields                                                   │
│  • Settings          │  Column 2: Coverage Details (Current)                                     │
│                      │  Column 3: Proposed Details (Requested)                                   │
│  ADMIN CONSOLE       │  Column 4: Source Status (Pill Badge)                                     │
│  • User Management   │  Column 5: Confidence (High/Med/Low + Evidence Link)                      │
│  • Registry Rules    │                                                                           │
└──────────────────────┴───────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Navigation Types by Viewport
* **Public / Auth Screens (`/`, `/login`, `/invite/accept`):** Minimalist top header displaying the QuotePulse logo, SOC2/Zero Data Retention badge, and an operational status indicator (`All Systems Operational`).
* **Desktop Application View (`/dashboard`, `/cases/*`, `/settings`, `/admin/*`):**
  * **Top Navbar (Height: 56px):** Persistent breadcrumb trail (e.g., `Dashboard > Apex Logistics Ltd > Quotation Details`), global case search bar (`Cmd+K` / `Ctrl+K`), storage mode indicator (`LOCAL_STORAGE` vs. `AWS_S3`), and user profile avatar with sign-out.
  * **Left Sidebar (Width: 240px, Collapsible to 64px):** Primary app navigation with active route indicators, count badges for unresolved exceptions, and an administrative section for authorized users.
  * **Workbench Sub-Tabs (`/cases/[id]/*`):** Secondary sticky tab bar directly synced with URL search parameters via `nuqs` (`/cases/[id]/quote`, `/cases/[id]/demography`, etc.).
* **Tablet / Mobile Viewport:**
  * Sidebar collapses into an off-canvas slide-out sheet triggered by a top hamburger icon.
  * The 5-column quote review table switches to a mobile-responsive stacked view with an expandable comparison card.

---

## 3. First Screen Experience

### 3.1 Brand-New Unauthenticated Visitor
* **URL:** `/`
* **Visual Display:** A clean, high-contrast landing page. The hero section displays: *"Automate GMC Quote Preparation & Demography Standardization with Precision AI"*. Trust badges indicate **OpenAI Zero Data Retention (ZDR)** and **In-Memory RAM Decryption**.
* **Call to Action (CTA):** A single primary blue button labeled **"Sign In with Corporate SSO"**. There are no self-registration or "Sign Up" links anywhere on the page.

### 3.2 Deep-Link Visitor
* **Scenario:** An unauthenticated underwriter clicks a shared case link (e.g., `/cases/CASE-9021/quote`).
* **Behavior:** The Next.js 15 middleware intercepts the request, notes the destination, and redirects to `/login?redirect=/cases/CASE-9021/quote`. Upon successful authentication, the user is redirected immediately to the targeted case view.

### 3.3 Authenticated User
* **URL:** `/dashboard`
* **Visual Display:** The user lands directly on the Cases Dashboard, displaying metrics cards (*Total Quotes Prepared*, *Pending Underwriter Review*, *Average TAT*) and a filterable table of active cases.

---

## 4. Authentication & User Provisioning Flow (Strictly Invite-Only)

Self-registration is strictly prohibited. The system enforces an administrator-governed onboarding pipeline:

```
[ Admin at /admin/users ] ── Dispatches Invite with Role ──▶ [ System emails secure signed token link ]
                                                                                │
                                                                                ▼
[ /dashboard ] ◀── [ /onboarding ] ◀── [ /login ] ◀── [ User clicks email link: /invite/accept?token=... ]
```

1. **Admin Invitation (`/admin/users`):** The administrator clicks **"+ Invite User"**, enters the corporate email address (`priya.sharma@company.com`), assigns a system role (`Sales RM` or `Senior Underwriter`), and clicks **"Send Invitation"**.
2. **Automated Notification:** The invitee receives an email containing a signed, time-limited token (`https://quote.company.com/invite/accept?token=inv_tok_998124`).
3. **Account Activation (`/invite/accept`):** The user clicks the link, confirms their email, configures their corporate SSO login or password, accepts the company data privacy policy, and clicks **"Activate Account"**.
4. **First-Time Profile Setup (`/onboarding`):** The user is routed to `/onboarding`. They confirm their full name, underwriting branch (`Mumbai Corporate`), default brokerage tier, and phone extension, then click **"Complete Setup"**.
   * *Middleware Enforcement:* Direct navigation to `/dashboard` is blocked if `user.metadata.onboarding_completed == false`.
5. **Dashboard Access:** The system sets `onboarding_completed: true` in user metadata, displays a green success toast for 3 seconds, and redirects the user to `/dashboard`.

---

## 5. Core User Journeys (Narrative Stories)

### Journey 1: Sales RM Ingests an RFQ Pack, Edits In-Flight Fields, and Exports a Quote Sheet

*Priya (Sales Relationship Manager) wants to upload a broker RFQ package and password-protected census, enter manual commercial terms, review extracted coverage, and download the finalized quote summary.*

1. Priya logs into QuotePulse GMC and lands on `/dashboard`. She clicks the primary blue **"+ New Quote Case"** button in the top-right corner.
2. A modal dialog titled *"Create New Quotation Case"* opens. Priya enters `"Apex Logistics Ltd"` in the Company Name field, selects `"Roll Over"` from the Proposal Type dropdown, and drags two files into the dropzone: a 38-page PDF (`RFQ_Apex_2026.pdf`) and an encrypted Excel file (`Apex_Census_Locked.xlsx`).
3. The dropzone detects file properties. A lock icon appears next to `Apex_Census_Locked.xlsx` with an inline alert: *"File is password-protected. Enter password to decrypt."* Priya types `"Apex@2026"` and clicks **"Start Ingestion"**.
4. The modal closes, raw files are saved to storage (`./storage/inputs/raw/CASE-9021/` in local mode or S3 in production), and Priya is redirected to `/cases/CASE-9021`.
5. She observes the 4-step live pipeline stepper:
   * `[✓] Document Layout & Text Parsed via Docling (7.8s)`
   * `[⟳] Analyzing benefit clauses with gpt-5.4-mini (Page 14 of 38)...`
   * `[ ] Standardizing demographic census with Polars`
   * `[ ] Matching procedure sub-limits against Option 1–4 grid`
6. After 28 seconds, all steps turn green with checkmarks. A banner slides down: *"Processing complete in 28.4 seconds. 1 item flagged for review."* The screen transitions automatically to `/cases/CASE-9021/quote`.
7. Priya reviews the 5-column table:
   * `Quote Fields`: Lists canonical fields (Sum Insured, Policy Tenure, PED, Room Rent Normal, Room Rent ICU).
   * `Coverage Details`: Displays expiring policy terms.
   * `Proposed Details`: Displays requested renewal terms.
   * `Source Status`: Displays green `RFQ Data` badges.
   * `Confidence`: Displays `High (98%)` badges with clickable evidence links.
8. Priya moves to the editable manual input rows:
   * **`Rater Type`**: She clicks the cell, replaces the default placeholder `-` with `"Corporate Floater Rater v2"`, and presses `Enter`.
   * **`Brokerage %`**: She types `5.00%` and presses `Tab`.
   * **`PINCODE`**: The extracted PIN shows `400001`. She updates it to `400051` (Bandra Kurla Complex office).
   * **`State` & `District`**: She verifies `Maharashtra` and `Mumbai Suburban`.
   * *Instant Auto-Derivation:* The derived **`Zone`** field recalculates from `Zone B` to `Zone A` within 200ms. A bottom-right toast confirms: *"Zone updated to Zone A based on PIN 400051."*
9. Priya clicks the top-right **"Export"** dropdown and chooses **"Download Reviewed Quote Sheet (.xlsx)"**. The system generates the file in 1.2 seconds, triggers the browser download, and logs the export event to the audit trail.

---

### Journey 2: Senior Underwriter Triages an Unmatched Sub-Limit Exception with Evidence Inspection

*Rajesh (Senior Underwriter) needs to review a flagged surgical sub-limit, inspect the exact clause in the broker's PDF, and apply an authorized underwriting override.*

1. Rajesh logs in and opens `/dashboard`. He clicks the **"Needs Review"** filter pill above the case table. The view updates instantly to display two flagged cases. He clicks on row `CASE-9021 (Apex Logistics Ltd)`.
2. He arrives at `/cases/CASE-9021/quote`. On the workbench sub-tab bar, the **"Exceptions"** tab displays an amber counter: `Exceptions (1)`. He clicks the tab, transitioning to `/cases/CASE-9021/exceptions`.
3. An exception card displays: `Procedure Sub-Limit: Cataract (one eye) = ₹30,000 — Unmatched / Review Required`. A diagnostic note explains: *"Extracted amount ₹30,000 does not match approved Option 1 (₹35k), Option 2 (₹25k), Option 3 (₹20k), or Option 4 (₹15k)."*
4. Rajesh clicks the blue **"View Source Evidence"** button on the card. A slide-out drawer (500px wide) opens from the right edge of the screen, rendering Page 19 of `RFQ_Apex_2026.pdf` with a yellow highlighted box surrounding the text: *"Cataract surgery is capped at a maximum of ₹30,000 per eye inclusive of intraocular lens."*
5. He closes the drawer by clicking the "X" button. On the exception card, he opens the **"Resolve Exception"** dropdown and selects **"Map to Option 2 (₹25,000) with Special Approval"**.
6. A confirmation modal prompts for underwriting justification. Rajesh enters: *"Concession approved under Western Zone corporate broker treaty"* and clicks the blue **"Apply Override"** button.
7. The modal closes, the exception card animates away, and the amber counter on the Exceptions tab decrements to `0`. A green notification appears for 4 seconds: *"Exception resolved and recorded in audit log."*
8. Rajesh clicks the **"Audit"** tab (`/cases/CASE-9021/audit`). The top row of the audit table displays his user email, the exact timestamp, the field name (`sublimits.cataract`), the previous status (`Unmatched`), the new status (`Option 2 - Special Approval`), and his justification comment.

---

### Journey 3: Operations Analyst Toggles the Demography Age Reference Date

*Neha (Operations Analyst) needs to recalculate member age brackets against the actual policy proposal inception date rather than the current date.*

1. Neha opens `/dashboard` and clicks case `CASE-9021`.
2. She clicks the **"Demography"** tab, routing to `/cases/CASE-9021/demography`.
3. A virtualized data grid renders 3,840 member rows in the strict 7-column order: `Age`, `Date of Birth`, `Sum Insured`, `Relationship`, `Name`, `EmpCode`, and `Gender`.
4. Neha checks the summary banner above the table: `Total Lives: 3,840`, `Primary Members: 1,200`, `SME Flag: No (>250 Primary Lives)`, and `Age Calculation Basis: Current Date (29-Oct-2026)`.
5. She clicks the **"Age Basis"** toggle switch, changing it from *Current Date* to *Policy Proposal Start Date*. A date picker appears. She selects `01-01-2027` (the upcoming policy renewal date) and clicks the blue **"Recalculate Ages"** button.
6. The button displays a spinning loader and changes text to *"Recalculating 3,840 records..."*. In 1.1 seconds, Polars recalculates all member ages on the backend using the completed-year floor formula:
   $$\text{Age} = \left\lfloor \frac{\text{01-01-2027} - \text{DOB}}{365.25} \right\rfloor$$
7. The table smoothly re-renders with the revised age values. A toast message appears: *"Demography ages recalculated based on inception date 01-01-2027. 48 members moved to the next age band."*
8. She clicks **"Download Standardized Demography (.xlsx)"**. The sanitized 7-column spreadsheet downloads immediately.

---

## 6. Empty States Catalog

| View / Component | Visual Representation | Primary Headline | Sub-Text / Context | Primary Action CTA |
| :--- | :--- | :--- | :--- | :--- |
| **Dashboard (`/dashboard`)** | Centered folder outline icon with subtle pulse animation. | `"No quotation cases found"` | `"Upload an RFQ tender package and member census to generate your first automated GMC quote."` | Blue button: **"+ Create First Quote Case"** (opens `/cases/new`). |
| **Exceptions Queue (`/cases/[id]/exceptions`)** | Green circular badge with an animated checkmark icon. | `"All exceptions resolved"` | `"All extracted clauses, demographic records, and procedure sub-limits conform to standard underwriting rules."` | Gray button: **"View Final Quote Summary"** (routes to `/cases/[id]/quote`). |
| **Case Search Results** | Magnifying glass icon with an exclamation point. | `"No cases match your search"` | `"We couldn't find any cases matching '[query]'. Check the spelling or clear active filters."` | Text button: **"Clear All Filters"** (resets search parameters). |
| **Audit Trail (`/cases/[id]/audit`)** | Clock icon with a list outline. | `"Audit trail initialized"` | `"System ingestion logged at [timestamp]. Future manual overrides and reviewer actions will be tracked here in real time."` | None (informational state). |

---

## 7. Error States & User Recovery Paths

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ERROR INTERCEPTION FLOW                         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
[ Password Error ]           [ Proxy / AI Timeout ]       [ Layout Mismatch ]
Horizontal shake alert       Amber alert banner           Warning card
"Incorrect password (1/3)"   "504 Gateway Timeout"        "2 mandatory columns missing"
       │                            │                            │
       ▼                            ▼                            ▼
[ Re-enter password or       [ Click 'Retry Step'         [ Launch Header Mapping ]
  upload clear file ]          (re-uses cached S3 files)]   Tool Modal ]
```

* **Incorrect File Password:**
  * *Visual Behavior:* The password input field shakes horizontally, turns red, and displays helper text: *"Incorrect password. The file could not be opened (Attempt 1 of 3)."*
  * *Recovery Path:* The user can clear and re-enter the password or click *"Remove file and upload an unencrypted file"* to proceed without blocking the case.
* **Outbound Proxy / OpenAI Egress Timeout:**
  * *Visual Behavior:* The stepper pauses on Step 2 with an amber warning triangle. A top alert banner appears: *"Corporate Egress Proxy Timeout (504): Unable to reach AI extraction service."*
  * *Recovery Path:* An inline blue button labeled **"Retry Extraction Step"** appears. The raw files already stored in storage are re-submitted to the Celery queue without requiring the user to re-upload files.
* **Corrupt Demography Layout (Missing Mandatory Columns):**
  * *Visual Behavior:* The Demography tab shows an alert card: *"Unrecognized Census Layout: 2 mandatory columns (Date of Birth, Relationship) could not be identified."*
  * *Recovery Path:* A button labeled **"Open Header Mapping Tool"** launches a modal showing raw spreadsheet headers on the left and dropdown selectors on the right, allowing the user to map source columns manually.
* **Case Not Found (404 Error):**
  * *Visual Behavior:* A full-page 404 screen displaying an insurance policy icon with an exclamation point and the message: *"Quotation Case Not Found"*.
  * *Recovery Path:* A single primary blue button labeled **"Back to Cases Dashboard"** that routes the user to `/dashboard`.

---

## 8. Modal, Drawer & Overlay Hierarchy

```
Level 0: Base Page Viewport (Dashboard, Workbench Tables)
  ├── Level 1: Modals & Slide-out Drawers
  │     ├── New Case Ingestion Modal (`/cases/new`)
  │     ├── Password Decryption Prompt Modal (Z-Index: 50, Focus Trapped)
  │     ├── Source Evidence Inspector Drawer (Right-side 500px, Z-Index: 40)
  │     └── Header Mapping Tool Modal (Z-Index: 45)
  └── Level 2: Confirmations & Toasts
        ├── Underwriting Override Confirmation Dialog (Z-Index: 60)
        └── Global Toast Notifications via Sonner (Bottom-right, Z-Index: 70)
```

1. **Password Decryption Prompt Modal (Z-Index: 50):** A focused modal with a dimmed backdrop overlay. Traps keyboard focus until the user submits a password or cancels file ingestion.
2. **Source Evidence Inspector Drawer (Z-Index: 40):** A 500px wide slide-out drawer from the right edge that displays the source document page with highlighted text bounding boxes without navigating away from the review table.
3. **Underwriting Override Confirmation Dialog (Z-Index: 60):** An alert dialog requiring a mandatory justification comment before saving any override to a medical coverage clause or procedure sub-limit.
4. **Global Toast Notifications (Z-Index: 70):** Ephemeral toasts in the bottom-right corner confirming actions (e.g., *"Brokerage percentage updated to 5.0%"* or *"Zone updated to Zone A"*).

---

## 9. AI Loading & Processing States

The application enforces three distinct feedback patterns tailored to task duration:

1. **Document Ingestion Stepper (`/cases/[id]`):** An animated vertical stepper fed by Server-Sent Events (SSE) tracking extraction phases:
   * `[✓] Document layout and text parsed via Docling (7.8s)`
   * `[⟳] Analyzing clauses with gpt-5.4-mini (Processing page 18 of 38)...`
   * `[ ] Standardizing demographic census with Polars`
   * `[ ] Validating procedure sub-limits against Option 1–4 grid`
2. **Table Shimmer Skeletons:** While the 5-column review table or demography grid fetches data, table cells render pulsing light-gray skeleton rectangles (`<Skeleton className="h-6 w-full" />`). Once data arrives, skeleton placeholders are replaced by formatted text and status pills with zero layout shift.
3. **Action Button Spinners:** When the user triggers short computational tasks (e.g., clicking **"Recalculate Ages"** or **"Save Override"**), the button disables immediately, displays a 16px spinning loader icon, and updates its label to an active state (e.g., *"Saving..."*).

---

## 10. Complete Redirect Matrix

| Trigger / User Action | Current Route | Destination Route | Conditions & Parameters |
| :--- | :--- | :--- | :--- |
| **Successful SSO Login** | `/login` | `/dashboard` | Default redirect when no prior destination is specified. |
| **Deep-Link SSO Login** | `/login` | `/[target_route]` | Preserves destination parameter (e.g., `?redirect=/cases/CASE-9021/quote`). |
| **Direct Sign-Up Attempt** | `/signup` (or public register) | `/login` | User self-registration is disabled; redirects with toast: *"Account registration is invite-only."* |
| **User Sign-Out** | Any authenticated route | `/` | Clears session cookies, invalidates Clerk JWT, and flushes client cache. |
| **Unauthenticated Route Access** | `/dashboard`, `/cases/*` | `/login` | Appends current path to query string: `?redirect={current_path}`. |
| **First-Time User Login** | `/login` | `/onboarding` | Triggered when `user.metadata.onboarding_completed == false`. |
| **Bypass Attempt on Onboarding** | Direct navigation to `/dashboard` | `/onboarding` | Intercepted by middleware if onboarding metadata is incomplete. |
| **Successful Case Submission** | `/cases/new` | `/cases/[id]` | Automatically routes user to the active processing pipeline screen. |
| **Pipeline Processing Completed** | `/cases/[id]` | `/cases/[id]/quote` | Automatically transitions from progress stepper to the 5-column review table. |
| **Unauthorized Role Access** | `/admin/*` | `/dashboard` | Non-admin users are blocked with an error toast: *"Administrator privileges required."* |