// Clerk component theme mapped to the UI/UX brief palette (Pacific Cobalt).
export const clerkAppearance = {
  variables: {
    colorPrimary: "#0052CC",
    colorBackground: "#FFFFFF",
    colorForeground: "#0F172A",
    colorMutedForeground: "#64748B",
    colorBorder: "#E2E8F0",
    colorRing: "#0066FF",
    borderRadius: "0.5rem",
  },
  elements: {
    // Invite-only: hide the "Don't have an account? Sign up" footer.
    footerAction: { display: "none" },
  },
};
