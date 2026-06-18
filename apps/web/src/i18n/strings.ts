// UI-string maps for i18n (unit 029). Adding a language is a matter of providing its map here
// (FR-002). Only UI chrome is localized — assistant/agent content is never translated (FR-004).

export type Locale = "en" | "zh-TW";

export const en: Record<string, string> = {
  "composer.send": "Send",
  "composer.placeholder": "Message LoopPlane...",
  "header.idle": "Idle",
  "header.running": "Running",
  "header.terminated": "Ended",
  "header.error": "Disconnected",
  "header.stop": "Stop",
  "header.inspect": "Inspect",
  "sidebar.newChat": "+ New chat",
  "sidebar.empty": "No sessions yet.",
  "login.subtitle": "Sign in with your access token to continue.",
  "login.token": "Access token",
  "login.submit": "Log in",
};

export const zhTW: Record<string, string> = {
  "composer.send": "傳送",
  "composer.placeholder": "傳訊息給 LoopPlane...",
  "header.idle": "閒置",
  "header.running": "執行中",
  "header.terminated": "已結束",
  "header.error": "已斷線",
  "header.stop": "停止",
  "header.inspect": "檢視",
  "sidebar.newChat": "+ 新對話",
  "sidebar.empty": "尚無工作階段。",
  "login.subtitle": "請輸入存取權杖以繼續。",
  "login.token": "存取權杖",
  "login.submit": "登入",
};

export const LOCALES: { id: Locale; label: string }[] = [
  { id: "en", label: "English" },
  { id: "zh-TW", label: "繁體中文" },
];
