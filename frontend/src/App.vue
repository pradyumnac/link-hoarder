<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import {
  createBookmark,
  deleteBookmark,
  importBookmarkFile,
  importBookmarkJson,
  listBookmarks,
  updateBookmark,
  type Bookmark,
  type BookmarkSort,
} from "./api/client";

const DEFAULT_ACCENT_COLOR = "#0d684d";
const FETCH_SIZE = 1000;
const PAGE_SIZE_OPTIONS = [10, 25, 50] as const;
const RECENT_WINDOW_MS = 30 * 24 * 60 * 60 * 1000;
const SEARCH_DELAY_MS = 300;
const SETTINGS_KEY = "link-hoarder.browser-settings";
const VARIANT_COOKIE = "link_hoarder_variant";

type BookmarkType = "all" | "bookmark" | "bookmarklet";
type LibraryDestination = "all" | "needs-organization" | "recent";
type UiVariant = "stable" | "staging";

const LIBRARY_DESTINATIONS = [
  { label: "All", value: "all" },
  { label: "Recent", value: "recent" },
  { label: "Needs organization", value: "needs-organization" },
] as const satisfies ReadonlyArray<{ label: string; value: LibraryDestination }>;
type PageSize = (typeof PAGE_SIZE_OPTIONS)[number];
type ViewMode = "gallery" | "list";

interface BrowserSettings {
  accentColor: string;
  defaultView: ViewMode;
  pageSize: PageSize;
  sortOrder: BookmarkSort;
}

interface NotificationEvent {
  id: number;
  message: string;
  operation: string;
  occurredAt: Date;
  unread: boolean;
}

function parseBrowserSettings(value: unknown): BrowserSettings | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const candidate = value as Record<string, unknown>;
  if (
    !PAGE_SIZE_OPTIONS.some((option) => option === candidate.pageSize) ||
    (candidate.defaultView !== "gallery" && candidate.defaultView !== "list")
  ) {
    return null;
  }
  const accentColor =
    typeof candidate.accentColor === "string" && /^#[0-9a-f]{6}$/i.test(candidate.accentColor)
      ? candidate.accentColor.toLowerCase()
      : DEFAULT_ACCENT_COLOR;
  return {
    accentColor,
    defaultView: candidate.defaultView,
    pageSize: candidate.pageSize as PageSize,
    sortOrder: candidate.sortOrder === "oldest" ? "oldest" : "newest",
  };
}

function loadBrowserSettings(): BrowserSettings {
  try {
    const stored = window.localStorage.getItem(SETTINGS_KEY);
    if (stored !== null) {
      const settings = parseBrowserSettings(JSON.parse(stored) as unknown);
      if (settings !== null) {
        return settings;
      }
    }
  } catch {
    // Use defaults when browser-local storage is unavailable or malformed.
  }
  return { accentColor: DEFAULT_ACCENT_COLOR, defaultView: "list", pageSize: 10, sortOrder: "newest" };
}

function applyAccentColor(accentColor: string): void {
  const red = Number.parseInt(accentColor.slice(1, 3), 16);
  const green = Number.parseInt(accentColor.slice(3, 5), 16);
  const blue = Number.parseInt(accentColor.slice(5, 7), 16);
  const brightness = (red * 299 + green * 587 + blue * 114) / 1000;
  document.documentElement.style.setProperty("--accent", accentColor);
  document.documentElement.style.setProperty(
    "--accent-contrast",
    brightness > 150 ? "#19332c" : "#ffffff",
  );
}

function loadUiVariant(): UiVariant {
  const variant = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${VARIANT_COOKIE}=`))
    ?.split("=", 2)[1];
  return variant === "staging" ? "staging" : "stable";
}

function variantUrl(variant: UiVariant): string {
  const target = new URL(window.location.href);
  target.searchParams.set("version", variant);
  return `${target.pathname}${target.search}${target.hash}`;
}

const abSwitchingEnabled = __AB_SWITCHING_ENABLED__;
const initialSettings = loadBrowserSettings();
applyAccentColor(initialSettings.accentColor);
const bookmarks = ref<Bookmark[]>([]);
const offset = ref(0);
const query = ref("");
const searchInput = ref<HTMLInputElement | null>(null);
const selectedFolder = ref("");
const folderInput = ref("");
const folderComboboxOpen = ref(false);
const selectedTag = ref("");
const selectedType = ref<BookmarkType>("all");
const selectedLibraryDestination = ref<LibraryDestination>("all");
const selectedSource = ref("");
const settings = reactive<BrowserSettings>({ ...initialSettings });
const uiVariant = ref<UiVariant>(loadUiVariant());
const viewMode = ref<ViewMode>(initialSettings.defaultView);
const error = ref("");
const notice = ref("");
const loading = ref(false);
const editingId = ref<number | null>(null);
const editorOpen = ref(false);
const importFile = ref<File | null>(null);
const importOpen = ref(false);
const notificationOpen = ref(false);
const settingsOpen = ref(false);
const navigationOpen = ref(false);
const notificationButton = ref<HTMLButtonElement | null>(null);
const notificationPanel = ref<HTMLElement | null>(null);
const settingsButton = ref<HTMLButtonElement | null>(null);
const settingsPanel = ref<HTMLElement | null>(null);
const notificationEvents = ref<NotificationEvent[]>([]);
const form = reactive({ folder: "", tags: "", title: "", url: "" });
let nextLoadId = 1;
let nextNotificationEventId = 1;
let searchTimer: ReturnType<typeof window.setTimeout> | null = null;

const failedThumbnailIds = reactive(new Set<number>());

const folderOptions = computed(() =>
  [...new Set(bookmarks.value.flatMap((bookmark) => bookmark.folder ?? []))].sort(),
);
const matchingFolderOptions = computed(() => {
  const query = folderInput.value.trim().toLowerCase();
  return folderOptions.value.filter((folder) => folder.toLowerCase().includes(query));
});
const folderBreadcrumbs = computed(() => {
  const breadcrumbs = [{ label: "All folders", path: "" }];
  let path = "";
  for (const segment of selectedFolder.value.split("/").filter(Boolean)) {
    path = path ? `${path}/${segment}` : segment;
    breadcrumbs.push({ label: segment, path });
  }
  return breadcrumbs;
});
const childFolders = computed(() => {
  const prefix = selectedFolder.value ? `${selectedFolder.value}/` : "";
  const children = new Map<string, string>();
  for (const folder of folderOptions.value) {
    if (!folder.startsWith(prefix) || folder === selectedFolder.value) {
      continue;
    }
    const segment = folder.slice(prefix.length).split("/")[0];
    if (segment) {
      children.set(segment, `${prefix}${segment}`);
    }
  }
  return [...children].map(([label, path]) => ({ label, path }));
});
const tagOptions = computed(() =>
  [...new Set(bookmarks.value.flatMap((bookmark) => bookmark.tags ?? []))].sort(),
);
const sourceOptions = computed(() => {
  const sources = new Map<string, { count: number; faviconUrl: string | null }>();
  for (const bookmark of bookmarks.value) {
    const source = bookmarkSource(bookmark);
    if (source !== null) {
      const current = sources.get(source);
      sources.set(source, {
        count: (current?.count ?? 0) + 1,
        faviconUrl: current?.faviconUrl ?? bookmark.favicon_url ?? null,
      });
    }
  }
  return [...sources]
    .filter(([, value]) => value.count > 5)
    .map(([source, value]) => ({
      count: value.count,
      faviconUrl: value.faviconUrl,
      label: sourceLabel(source),
      source,
    }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
});
const filteredBookmarks = computed(() => {
  const recentCutoff = Date.now() - RECENT_WINDOW_MS;
  return bookmarks.value.filter((bookmark) => {
    const isBookmarklet = bookmark.url.toLowerCase().startsWith("javascript:");
    const matchesLibrary =
      selectedLibraryDestination.value === "all" ||
      (selectedLibraryDestination.value === "recent" &&
        Date.parse(bookmark.created_at) >= recentCutoff) ||
      (selectedLibraryDestination.value === "needs-organization" &&
        (!bookmark.folder || !bookmark.tags?.length));
    return (
      matchesLibrary &&
      (!selectedSource.value || bookmarkSource(bookmark) === selectedSource.value) &&
      (!selectedFolder.value ||
        bookmark.folder === selectedFolder.value ||
        bookmark.folder?.startsWith(`${selectedFolder.value}/`)) &&
      (!selectedTag.value || bookmark.tags?.includes(selectedTag.value)) &&
      (selectedType.value === "all" ||
        (selectedType.value === "bookmarklet" ? isBookmarklet : !isBookmarklet))
    );
  });
});
const total = computed(() => filteredBookmarks.value.length);
const visibleBookmarks = computed(() =>
  filteredBookmarks.value.slice(offset.value, offset.value + settings.pageSize),
);
const currentPage = computed(() => Math.floor(offset.value / settings.pageSize) + 1);
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / settings.pageSize)));
const unreadEventCount = computed(
  () => notificationEvents.value.filter((event) => event.unread).length,
);

function conciseBookmarkUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname.replace(/\/$/, "");
    const visible = `${parsed.hostname}${path}`;
    return visible.length > 56 ? `${visible.slice(0, 53)}…` : visible;
  } catch {
    return url;
  }
}

function hideThumbnail(bookmarkId: number): void {
  failedThumbnailIds.add(bookmarkId);
}

function bookmarkSource(bookmark: Bookmark): string | null {
  if (bookmark.url.toLowerCase().startsWith("javascript:")) {
    return null;
  }
  try {
    return new URL(bookmark.url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return null;
  }
}

function sourceLabel(source: string): string {
  const knownSources: Readonly<Record<string, string>> = {
    "github.com": "GitHub",
    "reddit.com": "Reddit",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
  };
  return knownSources[source] ?? source;
}

function recordEvent(operation: string, message: string): void {
  notificationEvents.value.unshift({
    id: nextNotificationEventId,
    message,
    operation,
    occurredAt: new Date(),
    unread: true,
  });
  nextNotificationEventId += 1;
}

function persistSettings(): void {
  try {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    error.value = "";
    notice.value = "Settings saved.";
  } catch (caught) {
    error.value = messageFrom(caught);
    recordEvent("Save settings", error.value);
  }
}

function updateSettings(): void {
  offset.value = 0;
  viewMode.value = settings.defaultView;
  persistSettings();
}

function updateAccentColor(): void {
  applyAccentColor(settings.accentColor);
  persistSettings();
}

function setViewMode(mode: ViewMode): void {
  viewMode.value = mode;
  settings.defaultView = mode;
  persistSettings();
}

function setSortOrder(order: BookmarkSort): void {
  settings.sortOrder = order;
  offset.value = 0;
  persistSettings();
  void loadBookmarks();
}

function markAllEventsRead(): void {
  for (const event of notificationEvents.value) {
    event.unread = false;
  }
}

function clearEvent(eventId: number): void {
  notificationEvents.value = notificationEvents.value.filter((event) => event.id !== eventId);
}

function formatEventTime(occurredAt: Date): string {
  return occurredAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

async function loadBookmarks(): Promise<void> {
  const loadId = nextLoadId;
  nextLoadId += 1;
  loading.value = true;
  error.value = "";
  try {
    const loaded: Bookmark[] = [];
    let available = 0;
    do {
      const page = await listBookmarks(query.value, FETCH_SIZE, loaded.length, settings.sortOrder);
      loaded.push(...page.items);
      available = page.total;
      if (page.items.length === 0) {
        break;
      }
    } while (loaded.length < available);
    if (loadId === nextLoadId - 1) {
      bookmarks.value = loaded;
    }
  } catch (caught) {
    if (loadId === nextLoadId - 1) {
      error.value = messageFrom(caught);
      recordEvent("Load bookmarks", error.value);
    }
  } finally {
    if (loadId === nextLoadId - 1) {
      loading.value = false;
    }
  }
}

async function saveBookmark(): Promise<void> {
  error.value = "";
  notice.value = "";
  const tags = form.tags
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  try {
    if (editingId.value === null) {
      await createBookmark({
        folder: form.folder || null,
        source: "manual",
        tags,
        title: form.title,
        url: form.url,
      });
      notice.value = "Bookmark created.";
    } else {
      await updateBookmark(editingId.value, {
        folder: form.folder || null,
        tags,
        title: form.title,
        url: form.url,
      });
      notice.value = "Bookmark updated.";
    }
    closeEditor();
    await loadBookmarks();
  } catch (caught) {
    error.value = messageFrom(caught);
    recordEvent(editingId.value === null ? "Create bookmark" : "Update bookmark", error.value);
  }
}

function openCreateBookmark(): void {
  resetForm();
  editorOpen.value = true;
}

function editBookmark(bookmark: Bookmark): void {
  editingId.value = bookmark.id;
  form.folder = bookmark.folder ?? "";
  form.tags = (bookmark.tags ?? []).join(", ");
  form.title = bookmark.title;
  form.url = bookmark.url;
  editorOpen.value = true;
}

async function removeBookmark(bookmark: Bookmark): Promise<void> {
  if (!window.confirm(`Delete ${bookmark.title}?`)) {
    return;
  }
  try {
    await deleteBookmark(bookmark.id);
    notice.value = "Bookmark deleted.";
    if (visibleBookmarks.value.length === 1 && offset.value > 0) {
      offset.value = Math.max(0, offset.value - settings.pageSize);
    }
    await loadBookmarks();
  } catch (caught) {
    error.value = messageFrom(caught);
    recordEvent("Delete bookmark", error.value);
  }
}

function closeEditor(): void {
  resetForm();
  editorOpen.value = false;
}

function resetForm(): void {
  editingId.value = null;
  form.folder = "";
  form.tags = "";
  form.title = "";
  form.url = "";
}

async function search(): Promise<void> {
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer);
    searchTimer = null;
  }
  offset.value = 0;
  await loadBookmarks();
}

function scheduleSearch(): void {
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer);
  }
  searchTimer = window.setTimeout(() => {
    searchTimer = null;
    void search();
  }, SEARCH_DELAY_MS);
}

function clearSearch(): void {
  query.value = "";
  void search();
  searchInput.value?.focus();
}

function focusSearch(event: KeyboardEvent): void {
  if (
    event.key !== "/" ||
    event.defaultPrevented ||
    event.altKey ||
    event.ctrlKey ||
    event.metaKey
  ) {
    return;
  }
  const target = event.target;
  if (
    target instanceof HTMLElement &&
    (target.matches("input, textarea, select") ||
      target.isContentEditable ||
      target.closest('[contenteditable]:not([contenteditable="false"])') !== null)
  ) {
    return;
  }
  const input = searchInput.value;
  if (input === null || !input.isConnected) {
    return;
  }
  event.preventDefault();
  input.focus();
}

function dismissHeaderPanels(event: PointerEvent): void {
  const target = event.target;
  if (!(target instanceof Node)) {
    return;
  }
  if (
    settingsOpen.value &&
    !settingsButton.value?.contains(target) &&
    !settingsPanel.value?.contains(target)
  ) {
    settingsOpen.value = false;
  }
  if (
    notificationOpen.value &&
    !notificationButton.value?.contains(target) &&
    !notificationPanel.value?.contains(target)
  ) {
    notificationOpen.value = false;
  }
}

function applyFilters(): void {
  offset.value = 0;
}

function selectLibraryDestination(destination: LibraryDestination): void {
  selectedLibraryDestination.value = destination;
  applyFilters();
}

function selectSource(source: string): void {
  selectedSource.value = source;
  applyFilters();
}

function closeFolderResults(event: FocusEvent): void {
  const container = event.currentTarget;
  if (container instanceof HTMLElement && !container.contains(event.relatedTarget as Node | null)) {
    folderComboboxOpen.value = false;
  }
}

function updateFolderInput(): void {
  selectedFolder.value = "";
  folderComboboxOpen.value = true;
  applyFilters();
}

function navigateToFolder(folder: string): void {
  selectedFolder.value = folder;
  folderInput.value = folder;
  folderComboboxOpen.value = false;
  applyFilters();
}

function changePage(direction: -1 | 1): void {
  offset.value += direction * settings.pageSize;
}

function closeImport(): void {
  importFile.value = null;
  importOpen.value = false;
}

function selectImportFile(event: Event): void {
  const input = event.target as HTMLInputElement;
  importFile.value = input.files?.[0] ?? null;
}

function isJsonImport(file: File): boolean {
  return file.name.toLowerCase().endsWith(".json") || file.type === "application/json";
}

async function runImport(): Promise<void> {
  if (importFile.value === null) {
    error.value = "Select a bookmark HTML or JSON export file.";
    recordEvent("Import bookmarks", error.value);
    return;
  }
  try {
    const file = importFile.value;
    const result = isJsonImport(file)
      ? await importBookmarkJson(file)
      : await importBookmarkFile(file);
    const summary = `Imported ${result.imported}; skipped ${result.skipped}.`;
    const warnings = result.warnings ?? [];
    for (const warning of warnings) {
      recordEvent("Import warning", warning.message);
    }
    const warningSummary = warnings.length === 1
      ? "1 warning is in Notifications."
      : `${warnings.length} warnings are in Notifications.`;
    recordEvent("Import complete", summary);
    notice.value = warnings.length > 0 ? `${summary} ${warningSummary}` : summary;
    closeImport();
    await loadBookmarks();
  } catch (caught) {
    error.value = messageFrom(caught);
    recordEvent("Import bookmarks", error.value);
  }
}

function messageFrom(caught: unknown): string {
  return caught instanceof Error ? caught.message : "An unexpected error occurred.";
}

onMounted(() => {
  document.addEventListener("keydown", focusSearch);
  document.addEventListener("pointerdown", dismissHeaderPanels);
  void loadBookmarks();
});
onBeforeUnmount(() => {
  document.removeEventListener("keydown", focusSearch);
  document.removeEventListener("pointerdown", dismissHeaderPanels);
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer);
  }
});
</script>

<template>
  <main class="shell">
    <header class="app-header">
      <div class="brand">
        <img class="brand-mark" src="/link-hoarder.svg" alt="" width="48" height="48" />
        <h1>Link Hoarder</h1>
      </div>
      <form class="header-search" role="search" @submit.prevent="search">
        <div class="search-field">
          <input
            ref="searchInput"
            v-model="query"
            type="search"
            aria-label="Search bookmarks"
            aria-keyshortcuts="/"
            placeholder="Search title, URL, or tag"
            @input="scheduleSearch"
          />
          <button
            v-if="query"
            class="clear-search"
            type="button"
            aria-label="Clear search"
            @click="clearSearch"
          >×</button>
        </div>
      </form>
      <div class="notifications header-actions">
        <button class="secondary icon-button add-bookmark" type="button" aria-label="Add bookmark" @click="openCreateBookmark">
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
            <path d="M12 7v6M9 10h6" />
          </svg>
        </button>
        <button class="secondary icon-button import-bookmarks" type="button" aria-label="Import bookmarks" @click="importOpen = true">
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
            <path d="M14 3v5h5M8 13h8M13 10l3 3-3 3" />
          </svg>
        </button>
        <nav v-if="abSwitchingEnabled" class="variant-switcher" aria-label="UI version">
          <span>Test UI</span>
          <a
            :class="{ active: uiVariant === 'stable' }"
            :href="variantUrl('stable')"
            :aria-current="uiVariant === 'stable' ? 'page' : undefined"
          >Stable</a>
          <a
            :class="{ active: uiVariant === 'staging' }"
            :href="variantUrl('staging')"
            :aria-current="uiVariant === 'staging' ? 'page' : undefined"
          >Staging</a>
        </nav>
        <button
          ref="settingsButton"
          class="settings-button icon-button"
          type="button"
          aria-controls="settings-panel"
          :aria-expanded="settingsOpen"
          aria-label="Settings"
          @click="settingsOpen = !settingsOpen"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" />
          </svg>
        </button>
        <button
          ref="notificationButton"
          class="notification-button"
          type="button"
          aria-controls="notification-panel"
          :aria-expanded="notificationOpen"
          aria-label="Notifications"
          @click="notificationOpen = !notificationOpen"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
          </svg>
          <span v-if="unreadEventCount > 0" class="notification-count">{{ unreadEventCount }}</span>
        </button>
        <button
          class="navigation-toggle secondary icon-button"
          type="button"
          aria-label="Open collection navigation"
          aria-controls="collection-navigation"
          :aria-expanded="navigationOpen"
          @click="navigationOpen = true"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <section
          v-if="settingsOpen"
          id="settings-panel"
          ref="settingsPanel"
          class="notification-panel settings-panel"
          aria-labelledby="settings-heading"
        >
          <h2 id="settings-heading">Browser settings</h2>
          <label>Bookmarks per page
            <select v-model.number="settings.pageSize" @change="updateSettings">
              <option v-for="size in PAGE_SIZE_OPTIONS" :key="size" :value="size">{{ size }}</option>
            </select>
          </label>
          <label>Default view
            <select v-model="settings.defaultView" @change="updateSettings">
              <option value="list">List</option>
              <option value="gallery">Gallery</option>
            </select>
          </label>
          <label>Accent color
            <span class="accent-picker">
              <input
                v-model="settings.accentColor"
                type="color"
                aria-label="Accent color"
                @change="updateAccentColor"
              />
              <output>{{ settings.accentColor.toUpperCase() }}</output>
            </span>
          </label>
        </section>
        <section
          v-if="notificationOpen"
          id="notification-panel"
          ref="notificationPanel"
          class="notification-panel"
          aria-labelledby="notification-heading"
        >
          <div class="notification-heading">
            <h2 id="notification-heading">Events</h2>
            <button
              class="text-button mark-read"
              type="button"
              :disabled="unreadEventCount === 0"
              @click="markAllEventsRead"
            >Mark all read</button>
          </div>
          <p v-if="notificationEvents.length === 0" class="notification-empty">No events.</p>
          <ul v-else class="notification-list">
            <li v-for="event in notificationEvents" :key="event.id" :class="{ unread: event.unread }">
              <div>
                <strong>{{ event.operation }}</strong>
                <p>{{ event.message }}</p>
                <time :datetime="event.occurredAt.toISOString()">{{ formatEventTime(event.occurredAt) }}</time>
              </div>
              <button
                class="clear-notification"
                type="button"
                :aria-label="`Clear ${event.operation} event`"
                @click="clearEvent(event.id)"
              >×</button>
            </li>
          </ul>
        </section>
      </div>
    </header>

    <div v-if="error" class="message error" role="alert">
      <span>{{ error }}</span>
      <button class="message-dismiss" type="button" aria-label="Dismiss alert" @click="error = ''">×</button>
    </div>
    <div v-if="notice" class="message notice" role="status">
      <span>{{ notice }}</span>
      <button class="message-dismiss" type="button" aria-label="Dismiss notice" @click="notice = ''">×</button>
    </div>

    <div v-if="editorOpen" class="modal-backdrop" @click.self="closeEditor" @keydown.esc="closeEditor">
      <section class="bookmark-modal" role="dialog" aria-modal="true" aria-labelledby="editor-heading">
        <div class="section-heading">
          <div>
            <p class="eyebrow">{{ editingId === null ? "New entry" : "Edit entry" }}</p>
            <h2 id="editor-heading">{{ editingId === null ? "Save a bookmark" : "Update bookmark" }}</h2>
          </div>
          <button class="modal-close" type="button" aria-label="Close bookmark editor" @click="closeEditor">×</button>
        </div>
        <form class="bookmark-form" @submit.prevent="saveBookmark">
          <label>URL<input v-model="form.url" required autofocus placeholder="https://example.com" /></label>
          <label>Title<input v-model="form.title" required placeholder="Useful reference" /></label>
          <label>Folder<input v-model="form.folder" placeholder="Research/Reading" /></label>
          <label>Tags<input v-model="form.tags" placeholder="docs, tools" /></label>
          <button class="primary" type="submit">{{ editingId === null ? "Save bookmark" : "Save changes" }}</button>
        </form>
      </section>
    </div>

    <div v-if="importOpen" class="modal-backdrop" @click.self="closeImport" @keydown.esc="closeImport">
      <section class="bookmark-modal import-modal" role="dialog" aria-modal="true" aria-labelledby="import-heading">
        <div class="section-heading">
          <div><p class="eyebrow">Bookmark export</p><h2 id="import-heading">Import bookmarks</h2></div>
          <button class="modal-close import-modal-close" type="button" aria-label="Close import" @click="closeImport">×</button>
        </div>
        <form class="import-form" @submit.prevent="runImport">
          <label>Bookmark export<input type="file" accept=".html,.htm,.json,text/html,application/json" required @change="selectImportFile" /></label>
          <button class="secondary" type="submit">Import bookmarks</button>
        </form>
      </section>
    </div>

    <section class="panel collection" aria-labelledby="collection-heading">
      <div class="section-heading collection-heading">
        <div><p class="eyebrow">{{ total }} saved</p><h2 id="collection-heading">Collection</h2></div>
      </div>

      <button
        v-if="navigationOpen"
        class="navigation-backdrop"
        type="button"
        aria-label="Close collection navigation"
        @click="navigationOpen = false"
      ></button>
      <div class="collection-layout">
        <aside
          id="collection-navigation"
          class="collection-sidebar"
          :class="{ open: navigationOpen }"
          aria-label="Collection navigation"
        >
          <div class="drawer-heading">
            <button type="button" aria-label="Close collection navigation" @click="navigationOpen = false">×</button>
          </div>
          <div class="drawer-actions" aria-label="Mobile actions">
            <button
              class="drawer-import icon-button"
              type="button"
              aria-label="Import bookmarks"
              @click="navigationOpen = false; importOpen = true"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24">
                <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                <path d="M14 3v5h5M8 13h8M13 10l3 3-3 3" />
              </svg>
            </button>
            <button
              class="drawer-settings icon-button"
              type="button"
              aria-label="Settings"
              @click="navigationOpen = false; settingsOpen = true"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24">
                <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" />
              </svg>
            </button>
          </div>
          <nav class="library-destinations" aria-label="Library">
            <p class="sidebar-heading">Library</p>
            <button
              v-for="destination in LIBRARY_DESTINATIONS"
              :key="destination.value"
              class="sidebar-link"
              :class="{ active: selectedLibraryDestination === destination.value }"
              type="button"
              :data-library-destination="destination.value"
              :aria-current="selectedLibraryDestination === destination.value ? 'page' : undefined"
              @click="selectLibraryDestination(destination.value)"
            >{{ destination.label }}</button>
          </nav>
          <details class="sidebar-sources" aria-label="Sources" open>
            <summary class="sidebar-heading">Sources</summary>
            <div class="source-options">
              <button
                class="source-link"
                :class="{ active: selectedSource === '' }"
                type="button"
                data-source=""
                @click="selectSource('')"
              >All sources</button>
              <button
                v-for="source in sourceOptions"
                :key="source.source"
                class="source-link"
                :class="{ active: selectedSource === source.source }"
                type="button"
                :data-source="source.source"
                @click="selectSource(source.source)"
              >
                <span class="source-name">
                  <img
                    v-if="source.faviconUrl"
                    :src="source.faviconUrl"
                    alt=""
                    width="18"
                    height="18"
                    loading="lazy"
                  />
                  {{ source.label }}
                </span>
                <span>{{ source.count }}</span>
              </button>
            </div>
          </details>
          <div class="sidebar-filters" aria-label="Browse bookmarks">
            <p class="sidebar-heading">Browse</p>
            <details class="browse-group">
              <summary>Folders</summary>
              <div class="browse-group-content">
                <div class="folder-combobox" @focusout="closeFolderResults">
                  <input
                    v-model="folderInput"
                    type="search"
                    role="combobox"
                    aria-label="Filter by folder"
                    aria-autocomplete="list"
                    aria-controls="folder-filter-options"
                    :aria-expanded="folderComboboxOpen"
                    :disabled="folderOptions.length === 0"
                    placeholder="Find a folder"
                    @focus="folderComboboxOpen = true"
                    @input="updateFolderInput"
                    @keydown.esc="folderComboboxOpen = false"
                  />
                  <ul v-if="folderComboboxOpen" id="folder-filter-options" class="combobox-options" role="listbox">
                    <li v-for="folder in matchingFolderOptions" :key="folder">
                      <button type="button" role="option" @click="navigateToFolder(folder)">{{ folder }}</button>
                    </li>
                    <li v-if="matchingFolderOptions.length === 0" class="combobox-empty">No matching folders.</li>
                  </ul>
                </div>
                <div v-if="childFolders.length" class="folder-tree">
                  <button
                    v-for="folder in childFolders"
                    :key="folder.path"
                    class="folder-link"
                    type="button"
                    :data-folder="folder.path"
                    @click="navigateToFolder(folder.path)"
                  >{{ folder.label }}</button>
                </div>
              </div>
            </details>
            <details class="browse-group">
              <summary>Tags</summary>
              <div class="browse-group-content">
                <select v-model="selectedTag" aria-label="Filter by tag" :disabled="tagOptions.length === 0" @change="applyFilters">
                  <option value="">All tags</option>
                  <option v-for="tag in tagOptions" :key="tag" :value="tag">{{ tag }}</option>
                </select>
              </div>
            </details>
          </div>
          <details class="type-filter" open>
            <summary class="sidebar-heading">Filters</summary>
            <div class="browse-group-content">
              <label>Type
                <select v-model="selectedType" aria-label="Filter by bookmark type" @change="applyFilters">
                  <option value="all">All types</option>
                  <option value="bookmark">Bookmarks</option>
                  <option value="bookmarklet">Bookmarklets</option>
                </select>
              </label>
            </div>
          </details>
          <div class="view-picker" aria-label="Collection view">
            <p class="sidebar-heading">View</p>
            <div class="view-options">
              <button
                type="button"
                aria-label="Show list view"
                :aria-pressed="viewMode === 'list'"
                @click="setViewMode('list')"
              >List</button>
              <button
                type="button"
                aria-label="Show gallery view"
                :aria-pressed="viewMode === 'gallery'"
                @click="setViewMode('gallery')"
              >Gallery</button>
            </div>
          </div>
          <div class="view-picker" aria-label="Collection sort order">
            <p class="sidebar-heading">Sort</p>
            <div class="view-options">
              <button
                type="button"
                aria-label="Sort newest first"
                :aria-pressed="settings.sortOrder === 'newest'"
                @click="setSortOrder('newest')"
              >Newest</button>
              <button
                type="button"
                aria-label="Sort oldest first"
                :aria-pressed="settings.sortOrder === 'oldest'"
                @click="setSortOrder('oldest')"
              >Oldest</button>
            </div>
          </div>
        </aside>

        <div class="collection-content">
          <nav class="breadcrumbs" aria-label="Folder breadcrumbs">
            <template v-for="(breadcrumb, index) in folderBreadcrumbs" :key="breadcrumb.path">
              <span v-if="index > 0" aria-hidden="true">/</span>
              <button
                class="breadcrumb-link"
                type="button"
                :data-folder="breadcrumb.path"
                :aria-current="index === folderBreadcrumbs.length - 1 ? 'page' : undefined"
                @click="navigateToFolder(breadcrumb.path)"
              >{{ breadcrumb.label }}</button>
            </template>
          </nav>
          <p v-if="loading" class="empty">Loading bookmarks…</p>
          <p v-else-if="visibleBookmarks.length === 0" class="empty">No bookmarks match this view.</p>
          <ul v-else class="bookmark-list" :class="`${viewMode}-view`">
            <li v-for="bookmark in visibleBookmarks" :key="bookmark.id" class="bookmark-card">
              <div v-if="viewMode === 'gallery'" class="bookmark-thumbnail">
                <img
                  v-if="bookmark.thumbnail_url && !failedThumbnailIds.has(bookmark.id)"
                  :src="bookmark.thumbnail_url"
                  alt=""
                  loading="lazy"
                  @error="hideThumbnail(bookmark.id)"
                />
                <!-- The favicon is already loaded for the row icon, so this
                     costs no extra request. The API falls back to a generated
                     per-domain icon, which keeps each card distinct. -->
                <img
                  v-else
                  class="bookmark-thumbnail-fallback"
                  :src="bookmark.favicon_url ?? '/link-hoarder.svg'"
                  alt=""
                  width="28"
                  height="28"
                />
              </div>
              <div class="bookmark-main">
                <img
                  v-if="bookmark.favicon_url"
                  class="bookmark-icon"
                  :src="bookmark.favicon_url"
                  alt=""
                  width="40"
                  height="40"
                  loading="lazy"
                />
                <div class="bookmark-copy">
                  <div class="title-row">
                    <h3>{{ bookmark.title }}</h3>
                    <span v-if="bookmark.url.startsWith('javascript:')" class="bookmarklet">Bookmarklet</span>
                  </div>
                  <div class="meta-row">
                    <a
                      v-if="!bookmark.url.startsWith('javascript:')"
                      class="bookmark-url"
                      :href="bookmark.url"
                      :title="bookmark.url"
                      :aria-label="bookmark.url"
                      target="_blank"
                      rel="noreferrer"
                    >{{ conciseBookmarkUrl(bookmark.url) }}</a>
                    <code v-else class="bookmark-url" :title="bookmark.url">{{ bookmark.url }}</code>
                    <span v-if="bookmark.folder" class="folder" :title="bookmark.folder">{{ bookmark.folder }}</span>
                  </div>
                  <div v-if="bookmark.tags?.length" class="tags"><span v-for="tag in bookmark.tags" :key="tag">{{ tag }}</span></div>
                </div>
              </div>
              <div class="actions"><button class="text-button icon-button edit-bookmark" type="button" :aria-label="`Edit ${bookmark.title}`" @click="editBookmark(bookmark)">✎</button><button class="icon-button delete-bookmark" type="button" :aria-label="`Delete ${bookmark.title}`" @click="removeBookmark(bookmark)"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14H6L5 6M10 11v5M14 11v5" /></svg></button></div>
            </li>
          </ul>

          <nav class="pagination" aria-label="Bookmark pages">
            <button class="text-button" type="button" :disabled="offset === 0" @click="changePage(-1)">Previous</button>
            <span>Page {{ currentPage }} of {{ pageCount }}</span>
            <button class="text-button" type="button" :disabled="offset + settings.pageSize >= total" @click="changePage(1)">Next</button>
          </nav>
        </div>
      </div>
    </section>
  </main>
</template>
