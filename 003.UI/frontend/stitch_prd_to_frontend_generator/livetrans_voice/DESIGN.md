---
name: LiveTrans Voice
colors:
  surface: '#faf9fa'
  surface-dim: '#dadadb'
  surface-bright: '#faf9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f3f4'
  surface-container: '#eeedee'
  surface-container-high: '#e9e8e9'
  surface-container-highest: '#e3e2e3'
  on-surface: '#1a1c1d'
  on-surface-variant: '#414751'
  inverse-surface: '#2f3032'
  inverse-on-surface: '#f1f0f1'
  outline: '#717782'
  outline-variant: '#c1c7d2'
  surface-tint: '#0061a5'
  primary: '#005ea1'
  on-primary: '#ffffff'
  primary-container: '#2b78bf'
  on-primary-container: '#fdfcff'
  inverse-primary: '#a0caff'
  secondary: '#006e1c'
  on-secondary: '#ffffff'
  secondary-container: '#91f78e'
  on-secondary-container: '#00731e'
  tertiary: '#874e00'
  on-tertiary: '#ffffff'
  tertiary-container: '#aa6400'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d2e4ff'
  primary-fixed-dim: '#a0caff'
  on-primary-fixed: '#001c37'
  on-primary-fixed-variant: '#00497e'
  secondary-fixed: '#94f990'
  secondary-fixed-dim: '#78dc77'
  on-secondary-fixed: '#002204'
  on-secondary-fixed-variant: '#005313'
  tertiary-fixed: '#ffdcbe'
  tertiary-fixed-dim: '#ffb870'
  on-tertiary-fixed: '#2c1600'
  on-tertiary-fixed-variant: '#693c00'
  background: '#faf9fa'
  on-background: '#1a1c1d'
  surface-variant: '#e3e2e3'
  ink-deep: '#1A1A1A'
  ink-subdued: '#8B8B8B'
  success-dim: rgba(76, 175, 80, 0.6)
  alert-red: '#EF4444'
  accent-purple: '#8B5CF6'
typography:
  display-current-source:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  display-current-trans:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-history-source:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
  body-history-trans:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  label-tag:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  caption-timestamp:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-mobile: 20px
  margin-desktop: 40px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 24px
---

## Brand & Style

The brand personality is **Academic, Utility-driven, and Empathetic**. Designed specifically for students in high-pressure classroom environments, the interface prioritizes cognitive ease and focus. The design narrative follows a **"Subtitle-First"** approach, mimicking the immersive experience of cinema to ensure that real-time translation is the primary focal point.

The chosen design style is **Minimalist with a Focus on Functional Motion**. It utilizes heavy whitespace to reduce eye fatigue and employs subtle transitions to handle the "living" nature of streaming text. The aesthetic is clean and professional, ensuring that the technology recedes into the background while the content remains front and center.

## Colors

The color palette is functionally mapped to classroom utility. **Trustworthy Blue** acts as the primary brand touchpoint for actions and identification. **Clear Green** is reserved for translation and success states, providing a positive reinforcement of clarity.

- **Contrast for Focus:** Current, active sentences use **Ink Deep** for maximum legibility against the **Anti-fatigue Light Grey** background.
- **Temporal Fading:** As content moves into history, the color shifts to **Ink Subdued** or **Success Dim**, naturally drawing the eye toward the most recent, high-contrast information.
- **Categorization:** High-visibility colors like **Insightful Orange** (Important) and **Alert Red** (Exam Points) are used sparingly to tag key moments without overwhelming the transcript.

## Typography

This design system utilizes **Inter** for its exceptional legibility and neutral character, which prevents font-style fatigue during long lectures. 

The system employs **Temporal Typography**:
- **Streaming State:** Text is rendered in *Italics* while the ASR (Speech-to-Text) engine is processing.
- **Finalized State:** Text transitions to **Regular** or **Bold** weight once the result is confirmed.
- **Hierarchy of Age:** Font size and weight decrease as content moves from "Current" to "History," creating a natural visual path for the user to follow the lecture's progress.

## Layout & Spacing

The layout follows a **Fixed Grid** model optimized for reading. On mobile, the transcript occupies the full width minus the 20px margins to maximize line length for readability. 

- **Vertical Rhythm:** A 4px baseline grid ensures consistent spacing between source text and its translation.
- **Bilingual Grouping:** Source and translation pairs are treated as a single "block" with an 8px (stack-sm) gap between them. Consecutive blocks are separated by 24px (stack-lg) to distinguish between speaker breaths or sentence breaks.
- **Sticky Elements:** The top status bar and bottom control toolbar are fixed, ensuring that the recording status and "Knowledge Card" triggers are always accessible regardless of scroll depth.

## Elevation & Depth

The design system uses **Tonal Layers** rather than heavy shadows to maintain a clean, academic feel. 

- **Surface Levels:** The primary background uses the "Anti-fatigue" grey. Functional overlays, such as Toasts and the Bottom Toolbar, use a subtle white surface with a very soft, diffused shadow (4px blur, 5% opacity) to denote they sit above the scrollable content.
- **Depth through Transparency:** Historical text uses diminishing opacity to create a "z-axis" feel, where older content appears to recede into the distance.
- **Active Recording:** The recording button utilizes a **Pulse Animation**—a radiating green ring with 60% opacity—to create "active depth" without requiring a physical 3D lift.

## Shapes

The shape language is **Rounded**, providing a soft and approachable feel that counters the technical complexity of real-time translation. 

- **Interactive Elements:** Buttons and Input fields use a 0.5rem (8px) radius.
- **Special Elements:** The main Recording Button is a perfect circle (pill-shaped logic) to emphasize its primary importance and distinct action.
- **Knowledge Cards:** Snippets and saved items use a 1rem (16px) radius to distinguish them as "containers" of information rather than simple text blocks.

## Components

### Waveform Visualizer
A real-time rhythmic visualization of audio input. It should use the **Primary Blue** and be rendered as vertical bars with rounded caps, centered horizontally above the control bar.

### Transcription Bubbles (Bilingual)
These are not boxed in containers but separated by whitespace. The source text sits on top in **Ink Deep**, with the translation immediately below in **Clear Green**. In history, these pairs should have a subtle horizontal divider every 5 minutes of conversation.

### Pulse Recording Button
A large circular button. When inactive, it is white with a primary-colored icon. When active, it pulses with a **Success Green** breath effect (2000ms loop) to signify it is "listening."

### Knowledge Card Tags
Small, high-contrast labels used for categorizing transcription snippets:
- **Important (Star):** Insightful Orange background with white text/icon.
- **Question (?):** Primary Blue background with white text/icon.
- **Exam (Target):** Alert Red background with white text/icon.
- **Definition (Book):** Accent Purple background with white text/icon.

### Interaction Feedback
Use a **200ms ease-out** for all state transitions. The "Favorite" star must use an **Elastic Scale** animation when toggled to provide a tactile sense of accomplishment for the student.