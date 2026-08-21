/**
 * Desktop chrome strings.
 *
 * The shared components already translate through `PresentationI18nProvider`
 * (Web's wrappers supply their own maps), and both apps persist the choice under
 * the same key, so one switch changes everything. This file only covers the
 * chrome Desktop owns: the sidebar, the header, the composer, the first-run
 * guidance, the provider settings, and backup and restore.
 *
 * The backup disclosure and the public error catalogue are translated literally
 * rather than smoothed. That screen is the one place a person is told what
 * leaves their machine and what cannot be recovered, and the error keys are a
 * fixed set the sidecar is allowed to surface — `BackupRestoreView` checks
 * membership before looking one up, so an unrecognized key can never render as
 * itself.
 */

import {
  PresentationI18nProvider,
  useTranslation as useSharedTranslation,
} from "@loopplane/cowork-presentation";
import type { ReactNode } from "react";

export type DesktopLocale = "en" | "zh-TW";

/** Shared with Web so a choice made in either surface is the same choice. */
const STORAGE_KEY = "loopplane-locale";

export const DESKTOP_LOCALES: ReadonlyArray<{
  id: DesktopLocale;
  label: string;
}> = [
  { id: "en", label: "English" },
  { id: "zh-TW", label: "繁體中文" },
];

const en: Record<string, string> = {
  "sidebar.newSession": "New session",
  "sidebar.search": "Search",
  "sidebar.searchLabel": "Search sessions",
  "sidebar.starred": "Starred",
  "sidebar.allSessions": "All sessions",
  "sidebar.noSessions": "No sessions yet",
  "sidebar.noMatches": "No sessions match",
  "sidebar.projects": "Projects",
  "sidebar.newProject": "New project",
  "sidebar.noProjects": "No projects",
  "sidebar.projectHint":
    "Removing a project ungroups sessions; it does not delete them.",
  "sidebar.removeProject": "Remove",
  "sidebar.removeProjectLabel": "Remove project {name}",
  "sidebar.noFolder": "No folder bound",
  "sidebar.bindFolder": "Bind a folder…",
  "sidebar.relink": "Relink…",
  "sidebar.noWorkspaces": "No workspaces bound",
  "sidebar.settings": "Settings",
  "sidebar.backup": "Backup and restore",
  "sidebar.toLight": "Switch to light theme",
  "sidebar.toDark": "Switch to dark theme",
  "sidebar.star": "Star session",
  "sidebar.unstar": "Unstar session",
  "sidebar.fork": "Fork session",
  "sidebar.delete": "Delete session",
  "sidebar.language": "Language",

  "workspace.ready": "Ready",
  "workspace.moved": "Folder moved",
  "workspace.missing": "Folder missing",

  "header.newSession": "New session",
  "status.ready": "Ready",
  "status.starting": "Starting…",
  "status.running": "Running…",
  "status.cancelling": "Cancelling…",
  "status.disconnected": "Disconnected",
  "status.unavailable": "Runtime unavailable",
  "status.finished": "Finished",

  "composer.placeholder": "Message LoopPlane…",
  "composer.send": "Send",
  "composer.cancel": "Cancel",

  "provider.bannerText": "No model provider is set up, so replies are placeholders.",
  "provider.bannerAction": "Set up a provider",
  "provider.tab": "Model provider",
  "provider.saveRestart": "Save & restart",
  "provider.runBlocked":
    "Wait for the current run to finish before switching models.",

  "runtime.unavailable": "Local runtime unavailable.",
  "runtime.unavailableRestart": "Local runtime unavailable. Restart LoopPlane.",
  "runtime.retry": "Disconnected — please retry.",

  // Backup and restore. The disclosure is the one place in this application
  // where a person is told what leaves their machine and what cannot be
  // recovered, so the English is kept exactly as it was and the translation is
  // literal rather than smoothed.
  "backup.back": "Back to chat",
  "backup.title": "Backup and restore",
  "backup.createHeading": "Create a portable backup",
  "backup.disclosureContents":
    "The archive is not application-encrypted. Full session history, including user, model, and tool conversation content, and eligible artifacts are preserved losslessly. They may contain credentials, secrets, personal data, absolute paths, or copied workspace excerpts.",
  "backup.disclosureExclusions":
    "Unsent drafts are excluded and cannot be recovered. LoopPlane-owned provider credentials or tokens, private capability configuration, private workspace path mappings, logs, raw internal errors, PIDs, caches, transient run state, and arbitrary workspace contents are also excluded.",
  "backup.disclosureDestination":
    "Choose and protect the destination through the operating system. Integrity hashes detect corruption but do not encrypt or authenticate the archive, or protect it from someone who can rewrite the complete archive.",
  "backup.acknowledge": "I understand this backup is unencrypted",
  "backup.chooseDestination": "Choose backup destination",
  "backup.creating": "Creating backup…",
  "backup.cancelled": "Backup cancelled.",
  "backup.complete": "Backup complete.",
  "backup.unavailable": "Backup and restore unavailable.",

  "restore.heading": "Restore a portable backup",
  "restore.choose": "Choose backup to restore",
  "restore.preview": "Restore preview",
  "restore.reservationActive": "Restore reservation active.",
  "restore.projects": "Projects",
  "restore.sessions": "Sessions",
  "restore.artifacts": "Artifacts",
  "restore.draftsExcluded": "Unsent drafts excluded",
  "restore.relinkRequired": "Workspace relink required",
  "restore.replaceProfile": "Replace this profile",
  "restore.commit": "Commit restore",
  "restore.cancel": "Cancel restore",
  "restore.validating": "Validating backup…",
  "restore.selectionCancelled": "Restore selection cancelled.",
  "restore.restoring": "Restoring profile…",
  "restore.complete": "Restore complete. Workspace relink required.",
  "restore.cancelling": "Cancelling restore…",
  "restore.reservationCancelled": "Restore reservation cancelled.",

  "desktop.error.invalid_params": "The request was invalid.",
  "backup.error.unsafe_archive": "This backup cannot be used safely.",
  "backup.error.incompatible": "This backup is incompatible. Contact support.",
  "backup.error.integrity_failed": "Backup integrity validation failed.",
  "backup.error.limit_exceeded": "This backup exceeds restore safety limits.",
  "backup.error.profile_busy": "The profile is busy. Wait and try again.",
  "backup.error.insufficient_space":
    "There is insufficient space. Free space and retry.",
  "restore.error.durability_unsupported":
    "Restore is not supported on this storage. Contact support.",
  "restore.error.publication_failed_retryable":
    "Restore could not be published. Retry.",
  "restore.error.publication_failed_restart":
    "Restore state is uncertain. Restart the runtime.",
  "restore.error.rolled_back": "Restore was rolled back. Retry.",
  "backup.error.cancelled": "The operation was cancelled.",
  "desktop.error.internal_failure":
    "An internal failure occurred. Restart the runtime.",

  "example.whatProject": "What does this project do?",
  "example.recentFiles": "Which files changed most recently?",
  "example.listTools": "List the tools you can use",
  "example.whatHelp": "What can you help me with?",
  "example.whenEdit": "What happens when you edit a file?",

  "empty.hintFolder": "Ask about {folder}, or choose a starting point.",
  "empty.hintNoFolder": "Ask a question, or bind a folder for LoopPlane to work in.",

  "cost.sessionLabel": "Session spend",
  "cost.partial": "partially priced",
  "cost.unpriced": "Unpriced",
  "cost.unknown": "Cost unknown",
  "cost.unavailable": "Cost unavailable",
  "cost.monthly": "Month-to-date",
  "cost.monthlyUnavailable": "Month-to-date spend unavailable",

  "settings.statusUnavailable": "Settings status is unavailable.",
  "settings.readOnly": "Read only",
  "settings.loading": "Loading...",
  "settings.tab.memory": "Memory",
  "settings.tab.skills": "Skills",
  "settings.tab.mcp": "MCP",
  "settings.action.open": "Open",
  "settings.action.delete": "Delete",
  "settings.action.reconnect": "Reconnect",
  "settings.detail.title": "details",
  "settings.detail.close": "Close",
  "settings.detail.kind": "Kind",
  "settings.detail.description": "Description",
  "settings.detail.snippet": "Snippet",
  "settings.detail.status": "Status",
  "settings.detail.transport": "Transport",
  "settings.detail.tools": "Tools",
  "settings.detail.toolCount": "Tool count",
  "settings.detail.source": "Source",
  "settings.detail.unavailable": "Unavailable",
  "settings.memory.name": "Memory name",
  "settings.memory.content": "Memory content",
  "settings.memory.save": "Save memory",
  "settings.memory.search": "Search memory",
  "settings.memory.noMatches": "No memory entries match.",
  "settings.memory.deleteConfirm": "Delete this memory entry?",
  "settings.memory.empty": "No memory entries configured.",
  "settings.memory.unavailable": "Memory settings are unavailable.",
  "settings.memory.detailsUnavailable": "Memory details are unavailable.",
  "settings.skills.name": "Skill name",
  "settings.skills.instructions": "Skill instructions",
  "settings.skills.save": "Save skill",
  "settings.skills.import": "Import skill",
  "settings.skills.deleteConfirm": "Delete this skill?",
  "settings.skills.empty": "No skills configured.",
  "settings.skills.unavailable": "Skill settings are unavailable.",
  "settings.skills.detailsUnavailable": "Skill details are unavailable.",
  "settings.mcp.name": "MCP name",
  "settings.mcp.transport": "MCP transport",
  "settings.mcp.endpoint": "MCP endpoint",
  "settings.mcp.save": "Save MCP",
  "settings.mcp.deleteConfirm": "Delete this MCP configuration?",
  "settings.mcp.empty": "No MCP configurations configured.",
  "settings.mcp.unavailable": "MCP settings are unavailable.",
  "settings.mcp.detailsUnavailable": "MCP details are unavailable.",
  "settings.mcp.reconnectUnavailable": "MCP reconnect is unavailable.",
  "settings.tab.workspace": "Workspace",
  "settings.tab.schedules": "Schedules",
  "settings.tab.modelDefault": "Model default",
  "settings.action.bind": "Bind",
  "settings.action.runNow": "Run now",
  "settings.action.enable": "Enable",
  "settings.action.disable": "Disable",
  "settings.detail.workspaceLabel": "Workspace label",
  "settings.workspace.name": "Workspace name",
  "settings.workspace.label": "Workspace label",
  "settings.workspace.save": "Save workspace",
  "settings.workspace.deleteConfirm": "Delete this workspace context?",
  "settings.workspace.empty": "No workspace contexts configured.",
  "settings.workspace.unavailable": "Workspace settings are unavailable.",
  "settings.workspace.detailsUnavailable": "Workspace details are unavailable.",
  "settings.workspace.bindingUnavailable": "Workspace binding is unavailable.",
  "settings.workspace.sessionRequired": "An active session is required.",
  "settings.schedules.name": "Schedule name",
  "settings.schedules.trigger": "Schedule trigger",
  "settings.schedules.instruction": "Schedule instruction",
  "settings.schedules.enabled": "Schedule enabled",
  "settings.schedules.save": "Save schedule",
  "settings.schedules.deleteConfirm": "Delete this schedule?",
  "settings.schedules.empty": "No schedules configured.",
  "settings.schedules.unavailable": "Schedule settings are unavailable.",
  "settings.schedules.detailsUnavailable": "Schedule details are unavailable.",
  "settings.schedules.runUnavailable": "Schedule run is unavailable.",
  "settings.model.label": "Default model",
  "settings.model.hostDefault": "Use host default",
  "settings.model.save": "Save default model",
  "settings.model.clear": "Clear default model",
  "settings.model.empty": "No models configured.",
  "settings.model.unavailable": "Model default is unavailable.",
  "command.hint": "Host commands:",
  "command.unavailable": "The command could not be answered.",
};

const zhTW: Record<string, string> = {
  "sidebar.newSession": "新工作階段",
  "sidebar.search": "搜尋",
  "sidebar.searchLabel": "搜尋工作階段",
  "sidebar.starred": "已加星號",
  "sidebar.allSessions": "全部工作階段",
  "sidebar.noSessions": "還沒有任何工作階段",
  "sidebar.noMatches": "沒有符合的工作階段",
  "sidebar.projects": "專案",
  "sidebar.newProject": "新增專案",
  "sidebar.noProjects": "沒有專案",
  "sidebar.projectHint": "移除專案只會取消分組,不會刪除裡面的工作階段。",
  "sidebar.removeProject": "移除",
  "sidebar.removeProjectLabel": "移除專案 {name}",
  "sidebar.noFolder": "尚未綁定資料夾",
  "sidebar.bindFolder": "綁定資料夾…",
  "sidebar.relink": "重新連結…",
  "sidebar.noWorkspaces": "尚未綁定工作區",
  "sidebar.settings": "設定",
  "sidebar.backup": "備份與還原",
  "sidebar.toLight": "切換成淺色佈景",
  "sidebar.toDark": "切換成深色佈景",
  "sidebar.star": "加星號",
  "sidebar.unstar": "取消星號",
  "sidebar.fork": "分支這個工作階段",
  "sidebar.delete": "刪除這個工作階段",
  "sidebar.language": "語言",

  "workspace.ready": "可用",
  "workspace.moved": "資料夾已移動",
  "workspace.missing": "找不到資料夾",

  "header.newSession": "新工作階段",
  "status.ready": "就緒",
  "status.starting": "啟動中…",
  "status.running": "執行中…",
  "status.cancelling": "取消中…",
  "status.disconnected": "已中斷連線",
  "status.unavailable": "執行環境無法使用",
  "status.finished": "已完成",

  "composer.placeholder": "傳訊息給 LoopPlane…",
  "composer.send": "送出",
  "composer.cancel": "取消",

  "provider.bannerText": "尚未設定模型供應商,目前的回覆只是預留的範例文字。",
  "provider.bannerAction": "設定供應商",
  "provider.tab": "模型供應商",
  "provider.saveRestart": "儲存並重啟",
  "provider.runBlocked": "等目前這輪執行結束後再切換模型。",

  "runtime.unavailable": "本機執行環境無法使用。",
  "runtime.unavailableRestart": "本機執行環境無法使用,請重新啟動 LoopPlane。",
  "runtime.retry": "已中斷連線 —— 請重試。",

  // 備份與還原。這段揭露文字是整個應用程式裡唯一告訴使用者「什麼會離開這台
  // 電腦、什麼救不回來」的地方,所以逐句直譯,不做語氣上的軟化。
  "backup.back": "回到對話",
  "backup.title": "備份與還原",
  "backup.createHeading": "建立可攜備份",
  "backup.disclosureContents":
    "這個封存檔沒有經過應用程式加密。完整的工作階段歷史 —— 包含你、模型與工具的對話內容,以及符合條件的產出物 —— 都會被無損保留。這些內容可能包含憑證、機密、個人資料、絕對路徑,或是從工作區複製出來的片段。",
  "backup.disclosureExclusions":
    "尚未送出的草稿不會被包含,也無法還原回來。LoopPlane 自己保管的供應商憑證或權杖、私有的功能設定、私有的工作區路徑對應、日誌、原始內部錯誤、行程編號、快取、暫時的執行狀態,以及任意的工作區內容,同樣不會被包含。",
  "backup.disclosureDestination":
    "請透過作業系統選擇並保護存放位置。完整性雜湊只能偵測檔案是否損毀,不會加密或驗證這個封存檔,也擋不住有能力整份重寫它的人。",
  "backup.acknowledge": "我了解這份備份沒有加密",
  "backup.chooseDestination": "選擇備份存放位置",
  "backup.creating": "正在建立備份…",
  "backup.cancelled": "已取消建立備份。",
  "backup.complete": "備份完成。",
  "backup.unavailable": "目前無法使用備份與還原。",

  "restore.heading": "從可攜備份還原",
  "restore.choose": "選擇要還原的備份",
  "restore.preview": "還原預覽",
  "restore.reservationActive": "還原保留中。",
  "restore.projects": "專案",
  "restore.sessions": "工作階段",
  "restore.artifacts": "產出物",
  "restore.draftsExcluded": "不含尚未送出的草稿",
  "restore.relinkRequired": "還原後需要重新連結工作區",
  "restore.replaceProfile": "取代目前的設定檔",
  "restore.commit": "確定還原",
  "restore.cancel": "取消還原",
  "restore.validating": "正在驗證備份…",
  "restore.selectionCancelled": "已取消選擇要還原的備份。",
  "restore.restoring": "正在還原設定檔…",
  "restore.complete": "還原完成。需要重新連結工作區。",
  "restore.cancelling": "正在取消還原…",
  "restore.reservationCancelled": "已取消還原保留。",

  "desktop.error.invalid_params": "這個請求無效。",
  "backup.error.unsafe_archive": "這份備份無法安全使用。",
  "backup.error.incompatible": "這份備份不相容。請聯絡支援。",
  "backup.error.integrity_failed": "備份的完整性驗證失敗。",
  "backup.error.limit_exceeded": "這份備份超出還原的安全上限。",
  "backup.error.profile_busy": "設定檔正在使用中。請稍候再試一次。",
  "backup.error.insufficient_space": "空間不足。請先釋出空間再試一次。",
  "restore.error.durability_unsupported": "這個儲存位置不支援還原。請聯絡支援。",
  "restore.error.publication_failed_retryable": "還原沒有完成。請再試一次。",
  "restore.error.publication_failed_restart":
    "還原後的狀態無法確定。請重新啟動執行環境。",
  "restore.error.rolled_back": "還原已復原到原本的狀態。請再試一次。",
  "backup.error.cancelled": "操作已取消。",
  "desktop.error.internal_failure": "發生內部錯誤。請重新啟動執行環境。",

  "example.whatProject": "這個專案是做什麼的?",
  "example.recentFiles": "最近改動過哪些檔案?",
  "example.listTools": "列出你可以使用的工具",
  "example.whatHelp": "你可以幫我做什麼?",
  "example.whenEdit": "你編輯檔案的時候會發生什麼事?",

  "empty.hintFolder": "問問關於 {folder} 的事,或從下面挑一個開始。",
  "empty.hintNoFolder": "直接發問,或先綁定一個資料夾讓 LoopPlane 在裡面工作。",

  // Shared vocabulary (packages/cowork-presentation/src/vocabulary.ts). The
  // approval wording matters most: it is where someone decides what the agent
  // may do to their machine, so it stays literal rather than reassuring.
  "posture.asksFirst": "每次動作前都會先問",
  "posture.plan": "只做規劃,不會更動任何東西",
  "posture.acceptEdits": "會直接改檔案,不再詢問",
  "posture.dontAsk": "會直接使用已允許的工具,不再詢問",
  "posture.bypassPermissions": "已略過所有核准",

  "pane.driving": "正在執行這個工作階段",
  "pane.readOnly": "唯讀",
  "pane.interactive": "可互動",
  "pane.unknown": "未知",
  "pane.otherRunning": "另一個分頁正在執行。",
  "pane.noneRunning": "目前沒有分頁在執行。",
  "pane.takeOver": "接手",
  "pane.readOnlyBanner": "這個分頁是唯讀的。",
  "pane.thisPane": "這個分頁",

  "inspection.heading": "檢視",
  "inspection.unavailable": "無法取得檢視資訊。",
  "inspection.session": "工作階段",
  "inspection.cost": "花費",
  "inspection.context": "脈絡",
  "inspection.uploads": "上傳檔案",
  "inspection.artifacts": "產出物",
  "inspection.posture": "權限狀態",
  "inspection.pricing": "計價",
  "inspection.capabilities": "功能",
  "inspection.detail": "細節",
  "value.unavailable": "無法取得",
  "value.unknown": "未知",
  "value.unpriced": "無計價資料",

  "approval.question": "允許 LoopPlane 使用",
  "approval.allow": "允許",
  "approval.deny": "拒絕",
  "approval.alwaysAllow": "這個工作階段都允許",
  "tool.write_file": "這會在你的工作區建立或覆寫一個檔案。",
  "tool.edit_file": "這會修改你工作區裡的一個檔案。",
  "tool.notebook_edit": "這會修改你工作區裡的一個 notebook。",
  "tool.undo_file": "這會把一個檔案還原成先前編輯之前的樣子。",
  "tool.run_command": "這會在這台電腦上執行一道指令。",
  "tool.web_fetch": "這會從網際網路下載一個網頁。",
  "tool.web_search": "這會把你的查詢送到網際網路上的搜尋服務。",
  "tool.spawn_subagent": "這會另外啟動一個 agent 執行。",
  "tool.memory_write": "這會寫下一則記事,之後的工作階段都看得到。",
  "tool.message_send": "這會傳訊息給另一個 agent。",
  "tool.swarm_dispatch": "這會把工作交給另一個 agent。",
  "tool.schedule_create": "這會排定稍後自動執行的工作,屆時不會再問你。",
  "tool.schedule_cancel": "這會取消已排定的工作。",
  "tool.task_create": "這會啟動一個持續在背景執行的工作。",
  "tool.task_stop": "這會停止背景工作。",
  "tool.read_file": "這會讀取你工作區裡的一個檔案。",
  "tool.glob_files": "這會列出你工作區裡的檔案。",
  "tool.search_files": "這會在你的工作區裡尋找檔案。",
  "tool.grep": "這會搜尋你工作區裡各檔案的內容。",

  "cost.sessionLabel": "本次工作階段花費",
  "cost.partial": "部分定價",
  "cost.unpriced": "未定價",
  "cost.unknown": "花費未知",
  "cost.unavailable": "花費無法取得",
  "cost.monthly": "本月至今",
  "cost.monthlyUnavailable": "本月累計花費無法取得",

  "settings.statusUnavailable": "無法載入設定狀態。",
  "settings.readOnly": "唯讀",
  "settings.loading": "載入中...",
  "settings.tab.memory": "記憶",
  "settings.tab.skills": "技能",
  "settings.tab.mcp": "MCP",
  "settings.action.open": "開啟",
  "settings.action.delete": "刪除",
  "settings.action.reconnect": "重新連線",
  "settings.detail.title": "詳細資料",
  "settings.detail.close": "關閉",
  "settings.detail.kind": "類型",
  "settings.detail.description": "說明",
  "settings.detail.snippet": "摘要",
  "settings.detail.status": "狀態",
  "settings.detail.transport": "傳輸方式",
  "settings.detail.tools": "工具",
  "settings.detail.toolCount": "工具數量",
  "settings.detail.source": "來源",
  "settings.detail.unavailable": "無法使用",
  "settings.memory.name": "記憶名稱",
  "settings.memory.content": "記憶內容",
  "settings.memory.save": "儲存記憶",
  "settings.memory.search": "搜尋記憶",
  "settings.memory.noMatches": "沒有符合的記憶項目。",
  "settings.memory.deleteConfirm": "要刪除此記憶項目嗎?",
  "settings.memory.empty": "尚未設定記憶項目。",
  "settings.memory.unavailable": "無法使用記憶設定。",
  "settings.memory.detailsUnavailable": "無法使用記憶詳細資料。",
  "settings.skills.name": "技能名稱",
  "settings.skills.instructions": "技能指示",
  "settings.skills.save": "儲存技能",
  "settings.skills.import": "匯入技能",
  "settings.skills.deleteConfirm": "要刪除此技能嗎?",
  "settings.skills.empty": "尚未設定技能。",
  "settings.skills.unavailable": "無法使用技能設定。",
  "settings.skills.detailsUnavailable": "無法使用技能詳細資料。",
  "settings.mcp.name": "MCP 名稱",
  "settings.mcp.transport": "MCP 傳輸方式",
  "settings.mcp.endpoint": "MCP 端點",
  "settings.mcp.save": "儲存 MCP",
  "settings.mcp.deleteConfirm": "要刪除此 MCP 設定嗎?",
  "settings.mcp.empty": "尚未設定 MCP。",
  "settings.mcp.unavailable": "無法使用 MCP 設定。",
  "settings.mcp.detailsUnavailable": "無法使用 MCP 詳細資料。",
  "settings.mcp.reconnectUnavailable": "無法重新連線 MCP。",
  "settings.tab.workspace": "工作區",
  "settings.tab.schedules": "排程",
  "settings.tab.modelDefault": "預設模型",
  "settings.action.bind": "綁定",
  "settings.action.runNow": "立即執行",
  "settings.action.enable": "啟用",
  "settings.action.disable": "停用",
  "settings.detail.workspaceLabel": "工作區標籤",
  "settings.workspace.name": "工作區名稱",
  "settings.workspace.label": "工作區標籤",
  "settings.workspace.save": "儲存工作區",
  "settings.workspace.deleteConfirm": "要刪除此工作區情境嗎?",
  "settings.workspace.empty": "尚未設定工作區情境。",
  "settings.workspace.unavailable": "無法使用工作區設定。",
  "settings.workspace.detailsUnavailable": "無法使用工作區詳細資料。",
  "settings.workspace.bindingUnavailable": "無法綁定工作區。",
  "settings.workspace.sessionRequired": "需要使用中的工作階段。",
  "settings.schedules.name": "排程名稱",
  "settings.schedules.trigger": "排程觸發條件",
  "settings.schedules.instruction": "排程指示",
  "settings.schedules.enabled": "啟用排程",
  "settings.schedules.save": "儲存排程",
  "settings.schedules.deleteConfirm": "要刪除此排程嗎?",
  "settings.schedules.empty": "尚未設定排程。",
  "settings.schedules.unavailable": "無法使用排程設定。",
  "settings.schedules.detailsUnavailable": "無法使用排程詳細資料。",
  "settings.schedules.runUnavailable": "無法執行排程。",
  "settings.model.label": "預設模型",
  "settings.model.hostDefault": "使用主機預設值",
  "settings.model.save": "儲存預設模型",
  "settings.model.clear": "清除預設模型",
  "settings.model.empty": "尚未設定模型。",
  "settings.model.unavailable": "無法使用預設模型。",
  "command.hint": "主機指令:",
  "command.unavailable": "無法回應這個指令。",
};

const MESSAGES: Record<DesktopLocale, Record<string, string>> = {
  en,
  "zh-TW": zhTW,
};

/** Exported for the coverage test that every English key has a zh-TW entry. */
export const __messages = MESSAGES;

export function DesktopI18nProvider({ children }: { children: ReactNode }) {
  return (
    <PresentationI18nProvider messages={MESSAGES} storageKey={STORAGE_KEY}>
      {children}
    </PresentationI18nProvider>
  );
}

export interface DesktopTranslation {
  t: (key: string, values?: Record<string, string>) => string;
  locale: DesktopLocale;
  setLocale: (locale: DesktopLocale) => void;
}

export function useTranslation(): DesktopTranslation {
  const shared = useSharedTranslation();
  const locale = (shared.locale as DesktopLocale) ?? "en";
  return {
    locale,
    t: (key, values) => {
      const raw = MESSAGES[locale]?.[key] ?? en[key] ?? key;
      if (!values) return raw;
      return Object.entries(values).reduce(
        (text, [name, value]) => text.replaceAll(`{${name}}`, value),
        raw,
      );
    },
    setLocale: shared.setLocale as (locale: DesktopLocale) => void,
  };
}
