# DOCUMENT 04: UI/UX DESIGN BRIEF & COMPONENT SYSTEM
## Application Name: QuotePulse GMC (AI-Driven Quote Preparation & Demography Workbench)

| Specification Field | Design System Standard |
| :--- | :--- |
| **Document Version** | 4.0 (Master Engineering Baseline) |
| **Document Type** | UI/UX Design Brief & Frontend Component Specification |
| **Date** | 29 October 2026 |
| **Aesthetic Direction** | **Clinical, high-density, precision-engineered fintech** — inspired by Linear and Bloomberg Terminal. Built for intense side-by-side data verification, rapid commercial edits, and zero visual clutter. |
| **Primary Color** | `#0052CC` (**Pacific Cobalt**) — Deep, authoritative enterprise blue communicating institutional security and underwriting rigor. |
| **Background** | `#F8FAFC` (**Clean Canvas**) — Neutral slate-white minimizing eye strain during multi-hour underwriting review sessions. |
| **Text Colors** | **Primary:** `#0F172A` (Slate 900) <br> **Secondary:** `#334155` (Slate 700) <br> **Muted / Sub-label:** `#64748B` (Slate 500) <br> **Border / Divider:** `#E2E8F0` (Slate 200) |
| **Accent / CTA** | `#0066FF` (**Electric Royal**) — Single high-visibility accent color used exclusively for primary CTAs, active tab indicators, and focus rings. |
| **Font — Heading** | **Sora** (`font-sans`, weights: 600, 700) — Modern, geometric sans with character and structural clarity for section headers and KPI banners. |
| **Font — Body** | **Geist** (`font-sans`, weights: 400, 500) — Optimized for high-legibility textual reading, dense form controls, and descriptive underwriting clauses. |
| **Font — Mono** | **JetBrains Mono** (`font-mono`, weights: 400, 500, 600) — Tabular numeric font for financial currencies (₹), postal PIN codes, percentages, and demographic IDs. |
| **UI Components** | **shadcn/ui** built on **Radix UI primitives** and styled with **Tailwind CSS v4**. Custom overrides applied to Table, Dialog, Sheet (Drawer), Badge, and Input. |
| **Border Radius** | Consistently applied tokens: `6px` (`rounded-md`) for cards and dialogs; `4px` (`rounded`) for table cells and inputs; `50%` (`rounded-full`) for status indicator pills and avatars. |
| **Shadows** | **Border-first, shadow-subtle philosophy**: `0 1px 2px 0 rgba(0, 0, 0, 0.05)` for floating dropdowns and cards; `box-shadow: none` for data tables (relying on crisp 1px borders). No heavy drop shadows. |
| **Animations** | **Instant, non-spring transitions**: `150ms cubic-bezier(0.16, 1, 0.3, 1)` for drawer slide-ins, modal scale fades, and hover micro-states. Zero bouncy springs or playful physics. |
| **Reference Apps** | **Linear** (high density, clean keyboard shortcuts, fast triage) and **Ramp / Brex** (clinical corporate fintech aesthetics). |

---

## 1. Visual Identity & Complete Color Palette (Tokens)

All color tokens are exposed via Tailwind CSS v4 CSS variables (`globals.css`):

```css
:root {
  /* Brand Tokens */
  --primary: #0052CC;               /* Pacific Cobalt */
  --primary-hover: #0043A8;
  --accent: #0066FF;                /* Electric Royal CTA */
  --accent-hover: #0052CC;
  
  /* Neutral Canvas & Surfaces */
  --background: #F8FAFC;            /* Slate 50 Canvas */
  --surface-card: #FFFFFF;          /* Pure White Container */
  --surface-subtle: #F1F5F9;        /* Slate 100 Hover/Muted */
  --border: #E2E8F0;                /* Slate 200 Border */
  --border-active: #94A3B8;         /* Slate 400 Active Border */

  /* Typography */
  --text-primary: #0F172A;          /* Slate 900 Primary Text */
  --text-secondary: #334155;        /* Slate 700 Secondary Text */
  --text-muted: #64748B;            /* Slate 500 Sub-label / Notes */
  --text-inverse: #FFFFFF;

  /* Focus & Focus Rings */
  --ring: #0066FF;
}
```

### 1.1 Semantic Status Palette (Provenance & Audit Badges)
Every extracted field on the workbench must render with an explicit semantic pill indicating its computational provenance:

| Semantic Status | Background Hex | Text Hex | Border Hex | Description & Usage |
| :--- | :--- | :--- | :--- | :--- |
| **RFQ Data** | `#DCFCE7` | `#166534` | `#BBF7D0` | Extracted directly from RFQ text with verified Pass 2 reflection. |
| **Default Data** | `#EFF6FF` | `#1E40AF` | `#BFDBFE` | Populated via corporate business default rule (e.g., Tenure: 1 Year). |
| **AI Derived** | `#F0FDFA` | `#115E59` | `#99F6E4` | Contextually derived by system logic (e.g., Zone derived from PIN). |
| **Demography Derived** | `#FAF5FF` | `#6B21A8` | `#E9D5FF` | Calculated from the demographic roster (Group Size, SME Flag). |
| **Manual** | `#FEF3C7` | `#92400E` | `#FDE68A` | Manually entered or modified by Sales RM / Underwriter. |
| **Fixed** | `#F1F5F9` | `#475569` | `#CBD5E1` | System constant placeholder (e.g., Rater Type default `-`). |
| **Not Found** | `#FEE2E2` | `#991B1B` | `#FECACA` | Field searched but absent in uploaded RFQ documents. |
| **Ambiguous / Conflict** | `#FDF4FF` | `#86198F` | `#F5D0FE` | Conflicting values discovered across multi-document attachments. |
| **Review Required** | `#FFF7ED` | `#9A3412` | `#FFEDD5` | Mismatched procedure sub-limit or AI confidence score $<75\%$. |

---

## 2. Typography Hierarchy & Sizing Scale

* **Headings (Sora):** Crisp, geometric, structural.
* **Body (Geist):** Clean, high-readability sans-serif.
* **Tabular / Numbers (JetBrains Mono):** Monospaced, zero proportional jitter for numbers, currency signs, and member IDs.

| Style Token | Font Family | Size (px / rem) | Line Height | Weight | Tracking | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Display H1** | Sora | 28px / 1.75rem | 36px | 700 (Bold) | -0.02em | Case Title, Top Dashboard Header |
| **Section H2** | Sora | 20px / 1.25rem | 28px | 600 (SemiBold) | -0.01em | Table Group Headers, Modal Titles |
| **Card H3** | Sora | 15px / 0.9375rem | 22px | 600 (SemiBold) | 0.00em | KPI Metric Cards, Drawer Headers |
| **Body Primary** | Geist | 14px / 0.875rem | 20px | 400 (Regular) | 0.00em | Standard table row cell text, form labels |
| **Body Medium** | Geist | 14px / 0.875rem | 20px | 500 (Medium) | 0.00em | Active navigation links, button text |
| **Body Small** | Geist | 12px / 0.75rem | 16px | 400 (Regular) | 0.00em | Evidence citations, footer breadcrumbs |
| **Mono Table** | JetBrains Mono | 13px / 0.8125rem | 18px | 500 (Medium) | -0.01em | Currencies (₹), PIN codes, Dates, SI |
| **Badge Mono** | JetBrains Mono | 11px / 0.6875rem | 14px | 600 (SemiBold) | 0.02em | Status pill labels, Option 1–4 badges |

---

## 3. Core Workbench Grids Specification

### 3.1 The 5-Column Quote Review Grid (`/cases/[id]/quote`)
The primary review interface renders five strictly ordered columns. Row height is fixed at **40px** to ensure high density.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ QUOTATION REVIEW GRID                                                                     [Export Quote Sheet ▾] │
├──────────────────────┬──────────────────────┬──────────────────────┬─────────────────────┬───────────────────────┤
│ Quote Fields         │ Coverage Details     │ Proposed Details     │ Source Status       │ Confidence            │
│ (Width: 260px)       │ (Current) [320px]    │ (Requested) [320px]  │ (Width: 160px)      │ (Width: 160px)        │
├──────────────────────┼──────────────────────┼──────────────────────┼─────────────────────┼───────────────────────┤
│ Sum Insured (SI)     │ ₹3,00,000            │ ₹5,00,000            │ [ RFQ Data ]        │ [ High 98% ↗ ]        │
│ Room Rent Normal     │ 1% of SI per day     │ No Capping / Actuals │ [ RFQ Data ]        │ [ High 96% ↗ ]        │
│ Rater Type           │ [ -                ] │ [ Floater Rater v2 ] │ [ Manual ]          │ [ User Input ]        │
│ Brokerage %          │ [ -                ] │ [ 5.00%            ] │ [ Manual ]          │ [ User Input ]        │
│ PINCODE              │ 400001               │ [ 400051           ] │ [ Manual Override ] │ [ Modified ]          │
│ State                │ Maharashtra          │ [ Maharashtra      ] │ [ RFQ Data ]        │ [ High 99% ↗ ]        │
│ District             │ Mumbai               │ [ Mumbai Suburban  ] │ [ RFQ Data ]        │ [ High 99% ↗ ]        │
│ Zone                 │ Zone B               │ [ Zone A           ] │ [ AI Derived ]      │ [ Derived from PIN ]  │
└──────────────────────┴──────────────────────┴──────────────────────┴─────────────────────┴───────────────────────┘
```

#### Detailed Column Behaviors:
1. **Quote Fields (260px, Sticky Left):** Canonical title with an optional question mark tooltip explaining the underwriting definition.
2. **Coverage Details (Current) (320px):** Rendered in muted slate (`#334155`). Displays terms expiring from the existing policy.
3. **Proposed Details (Requested) (320px):** Rendered in dark slate (`#0F172A`) with semi-bold font. Displays requested renewal/tender terms.
4. **Source Status (160px):** Renders the approved semantic badge pill with a 1px border.
5. **Confidence (160px):** Visual progress dot + percentage label + external link icon (`↗`). Clicking opens the **Source Evidence Drawer**.

---

### 3.2 Editable Manual Input Fields Specification
Five designated fields feature direct inline-editable inputs on the Proposed Details column:
* **`Rater Type`**: Text input (`<Input className="h-8 font-mono text-xs" />`). Defaults to `-`.
* **`Brokerage %`**: Formatted percentage input. Automatically formats on blur (e.g., entering `5` formats to `5.00%`).
* **`PINCODE`**: 6-digit numeric input with live regex validation (`^[1-9][0-9]{5}$`).
* **`State`**: Searchable popover dropdown with keyboard navigation.
* **`District`**: Searchable popover dropdown populated dynamically based on the selected `State`.

#### Micro-Interaction: Inline Edit & Derived Zone Update
```
[ User edits PINCODE to '400051' ]
       │
       ├── 1. Cell border turns Electric Blue (#0066FF) with 150ms transition.
       ├── 2. Background flashes subtle green (#F0FDF4) for 400ms upon Enter/Tab.
       ├── 3. Status pill transitions from [ RFQ Data ] to [ Manual Override ].
       ├── 4. An asynchronous trigger updates the 'Zone' row:
       │      • Zone cell displays a subtle pulse shimmer.
       │      • Value updates to 'Zone A'.
       │      • Status updates to [ AI Derived ].
       └── 5. A Sonner toast appears at bottom-right: "Zone updated to Zone A (PIN 400051)".
```

---

### 3.3 The 7-Column Standardized Demography Grid (`/cases/[id]/demography`)
The demography grid utilizes `@tanstack/react-virtual` to render member censuses of up to 100,000 lives with smooth, jitter-free scrolling. Table row height is locked to **36px**.

$$\text{Col 1: Age} \;\vert\; \text{Col 2: Date of Birth} \;\vert\; \text{Col 3: Sum Insured} \;\vert\; \text{Col 4: Relationship} \;\vert\; \text{Col 5: Name} \;\vert\; \text{Col 6: EmpCode} \;\vert\; \text{Col 7: Gender}$$

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Total Lives: 3,840  │  Primary Members: 1,200  │  SME Flag: No (>250)  │ Age Mode: [ Current Date ▾ ] [Recalc]  │
├───────┬──────────────┬──────────────┬──────────────┬────────────────────────┬──────────────┬────────────────────┤
│ Age   │ Date of Birth│ Sum Insured  │ Relationship │ Name                   │ EmpCode      │ Gender             │
│ (80px)│ (120px)      │ (130px)      │ (120px)      │ (240px)                │ (110px)      │ (90px)             │
├───────┼──────────────┼──────────────┼──────────────┼────────────────────────┼──────────────┼────────────────────┤
│ 34    │ 14-06-1992   │ ₹5,00,000    │ Employee     │ Rajesh Verma           │ EMP-00109    │ Male               │
│ 31    │ 22-09-1995   │ ₹5,00,000    │ Spouse       │ Sunita Verma           │ EMP-00109    │ Female             │
│ 04    │ 11-03-2022   │ ₹5,00,000    │ Child        │ Aarav Verma            │ EMP-00109    │ Male               │
│ 17 !  │ 05-08-2009   │ ₹3,00,000    │ Employee     │ Vikram Singh           │ EMP-00844    │ Male [Flag: <18]   │
└───────┴──────────────┴──────────────┴──────────────┴────────────────────────┴──────────────┴────────────────────┘
```

* **Dynamic Age Mode Switcher:** A toolbar segmented toggle at the top of the grid:
  `[ Current Date (29-Oct-2026) ] | [ Policy Proposal Start Date (DD-MM-YYYY) ]`
* **Under-18 Exception Highlight:** Primary employees under 18 years of age display an amber warning icon (`!`) next to the age number with an inline tooltip: *"Worker under statutory age 18"*.

---

## 4. Key UI Components & Pattern Specifications

### 4.1 Slide-Out Source Evidence Drawer (Width: 500px)
When an underwriter clicks any confidence link (`↗`) on the quote review table, the Evidence Drawer slides in from the right viewport boundary:

```
┌────────────────────────────────────────────────────────┐
│ SOURCE EVIDENCE INSPECTOR                          [✕] │
├────────────────────────────────────────────────────────┤
│ Target Field: Medical Expenses > Maternity C-Section   │
│ Current Extracted Value: ₹50,000                       │
│ Provenance: RFQ Data (Confidence: 98%)                 │
├────────────────────────────────────────────────────────┤
│ DOCUMENT CITATION                                      │
│ File: RFQ_Apex_Logistics_2026.pdf                      │
│ Location: Page 14, Section 4.2 (Table 3, Row 2)        │
├────────────────────────────────────────────────────────┤
│ VERBATIM SNIPPET                                       │
│ ┌────────────────────────────────────────────────────┐ │
│ │ "Maternity benefit is covered up to ₹50,000 for    │ │
│ │  Normal Delivery and ₹50,000 for Caesarean Section │ │
│ │  deliveries, restricted to the first two children."│ │
│ └────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────┤
│ DOCUMENT PREVIEW CANVAS                                │
│ [ Embedded PDF Canvas snippet with yellow boundary ]   │
│ [ surrounding the cited text clause                ]   │
├────────────────────────────────────────────────────────┤
│ ACTIONS                                                │
│ [ Copy Verbatim Text ]       [ Accept & Verify Field ] │
└────────────────────────────────────────────────────────┘
```

* **Animation:** Slide-in from right edge in `150ms` (`transform: translateX(0)` with `opacity: 1`).
* **Backdrop:** Light semi-transparent scrim (`rgba(15, 23, 42, 0.2)` with `backdrop-filter: blur(2px)`).

---

### 4.2 Zero-Persistence Decryption Challenge Modal
When a password-protected PDF or Excel file is dragged into the case dropzone, a high-priority challenge modal traps focus:

```
┌────────────────────────────────────────────────────────┐
│ 🔒 Protected File Detected                             │
├────────────────────────────────────────────────────────┤
│ File 'Apex_Employee_Census_Locked.xlsx' is encrypted.  │
│ Enter the decryption password to proceed with intake.  │
│                                                        │
│ Password                                               │
│ [ •••••••••••••••••••••• ] [ 👁 ]                      │
│                                                        │
│ 🛡 Zero-Persistence Security Notice:                    │
│ Passwords are decrypted exclusively in ephemeral RAM   │
│ and are never saved to disk, database, or logs.        │
├────────────────────────────────────────────────────────┤
│ [ Cancel & Remove File ]          [ Decrypt & Continue ]│
└────────────────────────────────────────────────────────┘
```

* **Error Handling Micro-Interaction:** If an incorrect password is entered, the modal performs a subtle 3-cycle horizontal shake (`translateX(-4px)` to `translateX(4px)` over 250ms), turns the input border red (`#EF4444`), and displays helper text: *"Incorrect password (Attempt 1 of 3)"*.

---

### 4.3 Exceptions Triage Card Pattern (`/cases/[id]/exceptions`)
Unmatched sub-limits and demographic anomalies are displayed as actionable triage cards:

```
┌────────────────────────────────────────────────────────────────────────┐
│ ⚠️ UNMATCHED PROCEDURE SUBLIMIT                       [ Review Required]│
├────────────────────────────────────────────────────────────────────────┤
│ Procedure: Cataract (one eye)                                          │
│ Extracted Amount: ₹30,000                                              │
│ Reason: Amount deviates from standard Option 1–4 matrix:               │
│         Option 1 (₹35k) | Option 2 (₹25k) | Option 3 (₹20k) | Opt 4    │
│ Source: RFQ_Apex_2026.pdf (Page 19, Line 4)                            │
├────────────────────────────────────────────────────────────────────────┤
│ Action: [ Select Resolution Option ▾                        ]          │
│         • Retain ₹30,000 (Refer to Underwriting Committee)             │
│         • Map to Option 2 (₹25,000 with Broker Treaty Concession)      │
│         • Mark as Not Applicable                                       │
│                                                                        │
│ Underwriting Justification (Mandatory):                                │
│ [ Concession approved under Western Zone Broker Treaty       ]          │
├────────────────────────────────────────────────────────────────────────┤
│ [ View Source Evidence ↗ ]                        [ Apply Override & Log ]│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Mobile & Tablet Responsiveness Strategy

While QuotePulse GMC is primarily a desktop workstation tool, it gracefully adapts to tablet and laptop viewports:

| Viewport Width | Navigation Layout | Table & Grid Adaptation | Drawer & Modal Behavior |
| :--- | :--- | :--- | :--- |
| **Desktop ($\ge 1280\text{px}$)** | Persistent left sidebar (240px) + full top navbar. | Full 5-column quote form and 7-column virtualized demography grid rendered side-by-side. | 500px side-drawer opens beside table without overlapping primary data. |
| **Tablet ($768\text{px} - 1279\text{px}$)** | Sidebar collapses to 64px icon bar (expandable on click). | Horizontal scroll enabled on tables; Quote Fields and Proposed Details remain sticky. | Drawer opens as an overlay modal covering 70% of viewport width. |
| **Mobile ($< 768\text{px}$)** | Top hamburger header; sidebar collapses to an off-canvas drawer. | Review tables transform into vertical comparison cards (Current vs. Proposed stacked vertically). | Drawer transforms into a bottom-sheet sliding up from the bottom edge. |

---

## 6. Micro-Interactions, Feedback & Motion Philosophy

* **Guiding Principle:** **Instantaneous, informative, purposeful.** Avoid ornamental animations. Motion is used solely to signal state transitions and spatial hierarchy.
* **Duration Standard:** All transitions are pinned to **`150ms`**.
* **Timing Curve:** `cubic-bezier(0.16, 1, 0.3, 1)` (ease-out curve delivering crisp, snap-action responsiveness).
* **Toast Feedback (Sonner):**
  * Position: `bottom-right`.
  * Success Toast (`150ms` slide-up, auto-dismiss in `3000ms`): Green accent bar + check icon.
  * Error Toast (persistent until dismissed or `5000ms`): Red accent bar + error icon.
* **Skeleton Shimmers:** Pulsing CSS linear-gradient animation on slate-100 backgrounds indicating data loading:
  ```css
  @keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
  }
  .skeleton {
    background: linear-gradient(90deg, #F1F5F9 25%, #E2E8F0 50%, #F1F5F9 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
  }
  ```