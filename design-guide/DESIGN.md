---
name: Academic Clarity
colors:
  surface: '#f9f9fc'
  surface-dim: '#dadadc'
  surface-bright: '#f9f9fc'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f6'
  surface-container: '#eeeef0'
  surface-container-high: '#e8e8ea'
  surface-container-highest: '#e2e2e5'
  on-surface: '#1a1c1e'
  on-surface-variant: '#434652'
  inverse-surface: '#2f3133'
  inverse-on-surface: '#f0f0f3'
  outline: '#737783'
  outline-variant: '#c3c6d4'
  surface-tint: '#2b5bb5'
  primary: '#003178'
  on-primary: '#ffffff'
  primary-container: '#0d47a1'
  on-primary-container: '#a1bbff'
  inverse-primary: '#b0c6ff'
  secondary: '#006a62'
  on-secondary: '#ffffff'
  secondary-container: '#81f3e5'
  on-secondary-container: '#006f66'
  tertiary: '#323538'
  on-tertiary: '#ffffff'
  tertiary-container: '#494c4f'
  on-tertiary-container: '#babcbf'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d9e2ff'
  primary-fixed-dim: '#b0c6ff'
  on-primary-fixed: '#001945'
  on-primary-fixed-variant: '#00429c'
  secondary-fixed: '#84f5e8'
  secondary-fixed-dim: '#66d9cc'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#005049'
  tertiary-fixed: '#e0e3e6'
  tertiary-fixed-dim: '#c4c7ca'
  on-tertiary-fixed: '#191c1e'
  on-tertiary-fixed-variant: '#44474a'
  background: '#f9f9fc'
  on-background: '#1a1c1e'
  surface-variant: '#e2e2e5'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-sm:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-reading-lg:
    fontFamily: Source Serif 4
    fontSize: 20px
    fontWeight: '400'
    lineHeight: 32px
  body-reading-md:
    fontFamily: Source Serif 4
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-ui:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-caps:
    fontFamily: Hanken Grotesk
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  code:
    fontFamily: jetbrainsMono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  container-max: 1280px
  reading-max: 720px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
---

## Brand & Style

The design system is centered on the concept of "Educational Zen"—a state of focused, frictionless learning. The target audience includes professionals, students, and lifelong learners who prioritize deep comprehension over superficial browsing. The UI must evoke a sense of calm authority and meticulous organization.

We employ a **Corporate / Modern** style infused with **Minimalist** principles. By prioritizing heavy whitespace and a restricted color palette, we remove cognitive load, allowing the instructional content to remain the primary focus. The aesthetic is "Academic-Chic": it feels as structured as a textbook but as fluid as a modern SaaS application.

## Colors

The palette is anchored by a deep **Oxford Blue** (Primary), chosen for its associations with stability and institutional trust. A **Professional Teal** (Secondary) is used sparingly for success states, progress indicators, and interactive highlights to maintain an approachable energy.

The background uses a subtle off-white to reduce eye strain during long-form reading sessions. High-contrast neutral tones are reserved for body text to ensure WCAG AAA compliance, while lighter grays handle borders and secondary UI metadata.

## Typography

This design system utilizes a dual-font strategy. **Hanken Grotesk** is the functional workhorse, used for navigation, buttons, and UI metadata to provide a sharp, contemporary feel. 

For the core educational experience, **Source Serif 4** is employed. This typeface is specifically optimized for digital long-form reading, featuring generous x-heights and distinct letterforms that prevent fatigue. Reading widths for serif text blocks should be constrained to a maximum of 720px to maintain an ideal characters-per-line count (65-75 characters).

## Layout & Spacing

The layout follows a **Fixed Grid** model for desktop to ensure content remains centered and readable, preventing line lengths from becoming too wide on ultra-wide monitors. 

- **Desktop (1280px+):** 12-column grid with 24px gutters. The main reading area should typically occupy the central 8 columns, with supplemental navigation or progress tracking in the sidebars.
- **Tablet (768px - 1024px):** 8-column grid. Sidebars collapse into off-canvas drawers or bottom-pinned navigation.
- **Mobile (<768px):** 4-column grid with 16px margins. Vertical stack is mandatory, with increased line-height for body text to aid legibility.

## Elevation & Depth

To maintain a clean, academic feel, we use **Tonal Layers** combined with **Ambient Shadows**. Depth is used purposefully to indicate interactivity and information hierarchy rather than for decoration.

- **Level 0 (Base):** Background color (`#F5F7FA`), used for the canvas.
- **Level 1 (Surface):** White cards or sections that hold content.
- **Level 2 (Hover/Active):** Surfaces receive a soft, highly diffused shadow (0px 4px 20px rgba(13, 71, 161, 0.08)) to indicate they are liftable or interactive.
- **Overlays:** Modals and dropdowns use a crisp Level 3 shadow with a subtle Primary-tinted border (1px solid rgba(13, 71, 161, 0.1)).

## Shapes

The shape language is "Softly Structured." A standard radius of **8px (0.5rem)** is applied to primary UI elements like buttons, input fields, and cards. This balance of geometric precision and rounded corners strikes a tone that is professional yet modern. Larger containers, such as course hero sections, may use **16px (1rem)** to create a distinct visual frame.

## Components

### Buttons & Controls
- **Primary Button:** Solid Oxford Blue background with white text. 8px radius. High-contrast.
- **Secondary Button:** Ghost style with a 1.5px Oxford Blue border.
- **Progress Indicators:** Linear bars using the Secondary Teal. Progress should be persistent at the top of the reading pane.

### Content Cards
- **Course Cards:** Feature a top-aligned image, followed by a Hanken Grotesk headline. Use a subtle Level 1 shadow on hover.
- **Lesson Lists:** Use a "zebra-stripe" or thin-border divider approach. Active lessons are highlighted with a vertical 4px Teal bar on the left edge.

### Inputs & Forms
- **Fields:** Subtle gray background (`#EDF2F7`) that shifts to white on focus with a 2px Oxford Blue border.
- **Checkboxes:** Square with 4px radius, filling with Teal when selected to signify completion.

### Instructional Elements
- **Callouts/Notes:** Use a light Teal or Blue tinted background with a matching left-accent border to distinguish from the main reading flow.
- **Navigation:** A sticky left-hand sidebar for course curriculum, using Hanken Grotesk at `body-ui` size for density and clarity.