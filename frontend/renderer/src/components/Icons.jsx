// 内联 SVG 图标库：统一 24 viewBox / currentColor，杜绝 emoji 图标。
const I = ({ children, size = 16, ...rest }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round"
    strokeLinejoin="round" aria-hidden="true" {...rest}>
    {children}
  </svg>
);

export const IconDashboard = (p) => (
  <I {...p}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></I>
);
export const IconLearn = (p) => (
  <I {...p}><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></I>
);
export const IconGraph = (p) => (
  <I {...p}><circle cx="12" cy="5" r="2.5" /><circle cx="5" cy="18" r="2.5" /><circle cx="19" cy="18" r="2.5" /><path d="M10.7 7.2 6.5 15.8M13.3 7.2l4.2 8.6M7.5 18h9" /></I>
);
export const IconReview = (p) => (
  <I {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l3 2" /></I>
);
export const IconSettings = (p) => (
  <I {...p}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5h.1a1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></I>
);
export const IconGraduation = (p) => (
  <I {...p}><path d="M22 9 12 4 2 9l10 5 10-5Z" /><path d="M6 11.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-4.5" /></I>
);
export const IconBolt = (p) => (<I {...p}><path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" /></I>);
export const IconPulse = (p) => (<I {...p}><path d="M3 12h4l2.5-7 5 14 2.5-7h4" /></I>);
export const IconLink = (p) => (<I {...p}><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7" /><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7" /></I>);
export const IconInbox = (p) => (<I {...p}><path d="M22 12h-6l-2 3h-4l-2-3H2" /><path d="M5.4 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.4-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.8 1.1Z" /></I>);
export const IconAlert = (p) => (<I {...p}><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" /></I>);
export const IconCheck = (p) => (<I {...p}><path d="M20 6 9 17l-5-5" /></I>);
export const IconClock = (p) => (<I {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></I>);
export const IconDatabase = (p) => (<I {...p}><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></I>);
export const IconSearch = (p) => (<I {...p}><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></I>);
export const IconSend = (p) => (<I {...p}><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></I>);
export const IconPlus = (p) => (<I {...p}><path d="M12 5v14M5 12h14" /></I>);
export const IconBook = (p) => (<I {...p}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" /></I>);
export const IconBrain = (p) => (
  <I {...p}><path d="M12 5a3 3 0 1 0-5.9.8 3 3 0 0 0-1.9 5.4A3 3 0 0 0 6 16.7 3 3 0 0 0 12 19Z" /><path d="M12 5a3 3 0 1 1 5.9.8 3 3 0 0 1 1.9 5.4A3 3 0 0 1 18 16.7 3 3 0 0 1 12 19Z" /><path d="M12 5v14" /></I>
);
export const IconSpark = (p) => (<I {...p}><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" /><circle cx="12" cy="12" r="3" /></I>);
export const IconTarget = (p) => (<I {...p}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" /></I>);
export const IconArrowRight = (p) => (<I {...p}><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></I>);
export const IconReset = (p) => (<I {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /></I>);
export const IconX = (p) => (<I {...p}><path d="M18 6 6 18M6 6l12 12" /></I>);
export const IconSmile = (p) => (<I {...p}><circle cx="12" cy="12" r="9" /><path d="M8 14s1.5 2 4 2 4-2 4-2" /><path d="M9 9h.01M15 9h.01" /></I>);
export const IconMeh = (p) => (<I {...p}><circle cx="12" cy="12" r="9" /><path d="M8 15h8" /><path d="M9 9h.01M15 9h.01" /></I>);
export const IconFrown = (p) => (<I {...p}><circle cx="12" cy="12" r="9" /><path d="M16 16s-1.5-2-4-2-4 2-4 2" /><path d="M9 9h.01M15 9h.01" /></I>);
