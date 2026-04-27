# Requirements Document

## Introduction

This feature adds dark mode support to the Strategy Optimization Platform (Next.js 14 app in `re_web/`). The app already has Tailwind CSS configured with `darkMode: ["class"]` and CSS variables defined for both light and dark themes in `globals.css`. The feature requires wiring up theme toggling, persisting the user's preference in localStorage, preventing flash of wrong theme on page load, and exposing a toggle button in the navigation bar.

## Glossary

- **Theme_Manager**: The client-side module responsible for reading, writing, and applying the active theme.
- **Theme_Toggle**: The UI button component that allows users to switch between light and dark mode.
- **Theme_Store**: The Zustand store slice that holds the active theme state in memory.
- **Active_Theme**: The currently applied theme value, either `"light"` or `"dark"`.
- **System_Preference**: The operating system's color scheme preference, as reported by the `prefers-color-scheme` media query.
- **Flash_Of_Wrong_Theme**: A visible flicker caused by the page rendering in the wrong theme before JavaScript applies the correct one.

---

## Requirements

### Requirement 1: Theme Persistence

**User Story:** As a user, I want my theme preference to be saved, so that I do not have to re-select my preferred theme every time I visit the app.

#### Acceptance Criteria

1. WHEN a user selects a theme, THE Theme_Manager SHALL write the selected theme value (`"light"` or `"dark"`) to `localStorage` under the key `"theme"`.
2. WHEN the app loads and a `"theme"` key exists in `localStorage`, THE Theme_Manager SHALL read that value and apply it as the Active_Theme.
3. IF the `"theme"` key is absent from `localStorage`, THEN THE Theme_Manager SHALL apply the System_Preference as the Active_Theme.
4. IF the `"theme"` key in `localStorage` contains a value other than `"light"` or `"dark"`, THEN THE Theme_Manager SHALL fall back to the System_Preference as the Active_Theme.

---

### Requirement 2: Theme Application

**User Story:** As a user, I want the correct theme to be visually applied across the entire app, so that all pages and components render consistently in my chosen mode.

#### Acceptance Criteria

1. WHEN the Active_Theme is `"dark"`, THE Theme_Manager SHALL add the `"dark"` CSS class to the `<html>` element.
2. WHEN the Active_Theme is `"light"`, THE Theme_Manager SHALL remove the `"dark"` CSS class from the `<html>` element.
3. THE Theme_Manager SHALL apply the Active_Theme to the `<html>` element before the browser paints the first frame, eliminating Flash_Of_Wrong_Theme.
4. WHILE the Active_Theme is `"dark"`, THE Theme_Manager SHALL ensure all CSS custom properties defined under the `.dark` selector in `globals.css` are active.

---

### Requirement 3: Flash of Wrong Theme Prevention

**User Story:** As a user, I want the correct theme to appear immediately on page load, so that I do not see a white flash before the dark theme is applied.

#### Acceptance Criteria

1. THE Theme_Manager SHALL inject an inline `<script>` into the `<head>` of the HTML document that reads `localStorage` and applies the `"dark"` class to `<html>` synchronously before any rendering occurs.
2. WHEN the inline script executes and no stored preference exists, THE Theme_Manager SHALL read the System_Preference via `window.matchMedia("(prefers-color-scheme: dark)")` and apply the matching class.
3. THE inline script SHALL execute before any stylesheet or component hydration, ensuring zero visible theme flicker on initial page load.

---

### Requirement 4: Theme Toggle UI

**User Story:** As a user, I want a clearly visible toggle button in the navigation bar, so that I can switch between light and dark mode at any time.

#### Acceptance Criteria

1. THE Theme_Toggle SHALL be rendered inside the navigation bar on every page of the application.
2. WHEN the Active_Theme is `"light"`, THE Theme_Toggle SHALL display a moon icon (from `lucide-react`) to indicate that clicking will switch to dark mode.
3. WHEN the Active_Theme is `"dark"`, THE Theme_Toggle SHALL display a sun icon (from `lucide-react`) to indicate that clicking will switch to light mode.
4. WHEN a user clicks the Theme_Toggle, THE Theme_Store SHALL update the Active_Theme to the opposite value.
5. THE Theme_Toggle SHALL include an accessible `aria-label` attribute that describes the action it will perform (e.g., `"Switch to dark mode"` or `"Switch to light mode"`).

---

### Requirement 5: Theme State Management

**User Story:** As a developer, I want theme state managed through Zustand, so that any component in the app can read or update the Active_Theme consistently.

#### Acceptance Criteria

1. THE Theme_Store SHALL expose the Active_Theme value and a `toggleTheme` action.
2. WHEN `toggleTheme` is called, THE Theme_Store SHALL update the Active_Theme from `"light"` to `"dark"` or from `"dark"` to `"light"`.
3. WHEN the Active_Theme changes in the Theme_Store, THE Theme_Manager SHALL synchronously update the `"dark"` class on the `<html>` element and write the new value to `localStorage`.
4. THE Theme_Store SHALL initialize the Active_Theme by reading from `localStorage` on the client, falling back to System_Preference, and then falling back to `"light"`.

---

### Requirement 6: System Preference Synchronization

**User Story:** As a user, I want the app to respect my OS-level dark mode setting when I have not set an explicit preference, so that the app feels native to my environment.

#### Acceptance Criteria

1. WHEN no stored preference exists in `localStorage`, THE Theme_Manager SHALL apply the Active_Theme that matches the System_Preference.
2. WHEN the System_Preference changes at runtime (e.g., the user switches OS theme), THE Theme_Manager SHALL update the Active_Theme to match the new System_Preference, provided no explicit `localStorage` preference has been set.
