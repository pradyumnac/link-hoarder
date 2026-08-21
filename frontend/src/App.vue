<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import {
  createBookmark,
  deleteBookmark,
  importBookmarkFile,
  listBookmarks,
  updateBookmark,
  type Bookmark,
} from "./api/client";

const FETCH_SIZE = 1000;
const PAGE_SIZE_OPTIONS = [10, 25, 50] as const;
const SEARCH_DELAY_MS = 300;
const SETTINGS_KEY = "link-hoarder.browser-settings";

type BookmarkType = "all" | "bookmark" | "bookmarklet";
type PageSize = (typeof PAGE_SIZE_OPTIONS)[number];
type ViewMode = "gallery" | "list";

interface BrowserSettings {
  defaultView: ViewMode;
  pageSize: PageSize;
}

interface NotificationEvent {
  id: number;
  message: string;
  operation: string;
  occurredAt: Date;
  unread: boolean;
}

function isBrowserSettings(value: unknown): value is BrowserSettings {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    PAGE_SIZE_OPTIONS.some((option) => option === candidate.pageSize) &&
    (candidate.defaultView === "gallery" || candidate.defaultView === "list")
  );
}

function loadBrowserSettings(): BrowserSettings {
  try {
    const stored = window.localStorage.getItem(SETTINGS_KEY);
    if (stored !== null) {
      const candidate: unknown = JSON.parse(stored);
      if (isBrowserSettings(candidate)) {
        return candidate;
      }
    }
  } catch {
    // Use defaults when browser-local storage is unavailable or malformed.
  }
  return { defaultView: "list", pageSize: 10 };
}

const initialSettings = loadBrowserSettings();
const bookmarks = ref<Bookmark[]>([]);
const offset = ref(0);
const query = ref("");
const selectedFolder = ref("");
const folderInput = ref("");
const folderComboboxOpen = ref(false);
const selectedTag = ref("");
const selectedType = ref<BookmarkType>("all");
const settings = reactive<BrowserSettings>({ ...initialSettings });
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
const notificationEvents = ref<NotificationEvent[]>([]);
const form = reactive({ folder: "", tags: "", title: "", url: "" });
let nextLoadId = 1;
let nextNotificationEventId = 1;
let searchTimer: ReturnType<typeof window.setTimeout> | null = null;

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
const filteredBookmarks = computed(() =>
  bookmarks.value.filter((bookmark) => {
    const isBookmarklet = bookmark.url.toLowerCase().startsWith("javascript:");
    return (
      (!selectedFolder.value ||
        bookmark.folder === selectedFolder.value ||
        bookmark.folder?.startsWith(`${selectedFolder.value}/`)) &&
      (!selectedTag.value || bookmark.tags?.includes(selectedTag.value)) &&
      (selectedType.value === "all" ||
        (selectedType.value === "bookmarklet" ? isBookmarklet : !isBookmarklet))
    );
  }),
);
const total = computed(() => filteredBookmarks.value.length);
const visibleBookmarks = computed(() =>
  filteredBookmarks.value.slice(offset.value, offset.value + settings.pageSize),
);
const currentPage = computed(() => Math.floor(offset.value / settings.pageSize) + 1);
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / settings.pageSize)));
const unreadEventCount = computed(
  () => notificationEvents.value.filter((event) => event.unread).length,
);

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

function setViewMode(mode: ViewMode): void {
  viewMode.value = mode;
  settings.defaultView = mode;
  persistSettings();
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
      const page = await listBookmarks(query.value, FETCH_SIZE, loaded.length);
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

function applyFilters(): void {
  offset.value = 0;
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

async function runImport(): Promise<void> {
  if (importFile.value === null) {
    error.value = "Select a bookmark HTML export file.";
    recordEvent("Import bookmarks", error.value);
    return;
  }
  try {
    const result = await importBookmarkFile(importFile.value);
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

onMounted(loadBookmarks);
onBeforeUnmount(() => {
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer);
  }
});
</script>

<template>
  <main class="shell">
    <header class="hero">
      <p class="eyebrow">Personal bookmark archive</p>
      <h1>Link Hoarder</h1>
      <p>Search, classify, and import bookmarks from one private workspace.</p>
      <div class="notifications">
        <button
          class="settings-button icon-button"
          type="button"
          aria-controls="settings-panel"
          :aria-expanded="settingsOpen"
          aria-label="Settings"
          @click="settingsOpen = !settingsOpen"
        >⚙</button>
        <button
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
        <section
          v-if="settingsOpen"
          id="settings-panel"
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
        </section>
        <section
          v-if="notificationOpen"
          id="notification-panel"
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
          <div><p class="eyebrow">Browser export</p><h2 id="import-heading">Import bookmark HTML</h2></div>
          <button class="modal-close import-modal-close" type="button" aria-label="Close import" @click="closeImport">×</button>
        </div>
        <form class="import-form" @submit.prevent="runImport">
          <label>Bookmark export<input type="file" accept=".html,.htm,text/html" required @change="selectImportFile" /></label>
          <button class="secondary" type="submit">Import bookmarks</button>
        </form>
      </section>
    </div>

    <section class="panel collection" aria-labelledby="collection-heading">
      <div class="section-heading collection-heading">
        <div><p class="eyebrow">{{ total }} saved</p><h2 id="collection-heading">Collection</h2></div>
        <form class="search collection-actions" role="search" @submit.prevent="search">
          <input v-model="query" aria-label="Search bookmarks" placeholder="Search title, URL, or tag" @input="scheduleSearch" />
          <button class="secondary icon-button search-button" type="submit" aria-label="Search bookmarks">⌕</button>
          <button class="primary icon-button add-bookmark" type="button" aria-label="Add bookmark" @click="openCreateBookmark">＋</button>
          <button class="secondary icon-button import-bookmarks" type="button" aria-label="Import bookmarks" @click="importOpen = true">⇩</button>
        </form>
      </div>

      <div class="collection-layout">
        <aside class="collection-sidebar" aria-label="Collection navigation">
          <nav aria-label="Library">
            <p class="sidebar-heading">Library</p>
            <button
              class="sidebar-link"
              :class="{ active: selectedFolder === '' }"
              type="button"
              :aria-current="selectedFolder === '' ? 'page' : undefined"
              @click="navigateToFolder('')"
            >All bookmarks</button>
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
          </nav>
          <div class="sidebar-filters" aria-label="Bookmark filters">
            <p class="sidebar-heading">Filters</p>
            <label>Tag
              <select v-model="selectedTag" aria-label="Filter by tag" :disabled="tagOptions.length === 0" @change="applyFilters">
                <option value="">All tags</option>
                <option v-for="tag in tagOptions" :key="tag" :value="tag">{{ tag }}</option>
              </select>
            </label>
            <label>Type
              <select v-model="selectedType" aria-label="Filter by bookmark type" @change="applyFilters">
                <option value="all">All types</option>
                <option value="bookmark">Bookmarks</option>
                <option value="bookmarklet">Bookmarklets</option>
              </select>
            </label>
            <label>Folder
              <div class="folder-combobox">
                <input
                  v-model="folderInput"
                  type="search"
                  role="combobox"
                  aria-label="Filter by folder"
                  aria-autocomplete="list"
                  aria-controls="folder-filter-options"
                  :aria-expanded="folderComboboxOpen"
                  :disabled="folderOptions.length === 0"
                  placeholder="Type a folder"
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
            </label>
          </div>
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
              <div class="bookmark-copy">
                <div class="title-row">
                  <h3>{{ bookmark.title }}</h3>
                  <span v-if="bookmark.url.startsWith('javascript:')" class="bookmarklet">Bookmarklet</span>
                </div>
                <a v-if="!bookmark.url.startsWith('javascript:')" :href="bookmark.url" target="_blank" rel="noreferrer">{{ bookmark.url }}</a>
                <code v-else>{{ bookmark.url }}</code>
                <p v-if="bookmark.folder" class="folder">{{ bookmark.folder }}</p>
                <div v-if="bookmark.tags?.length" class="tags"><span v-for="tag in bookmark.tags" :key="tag">{{ tag }}</span></div>
              </div>
              <div class="actions"><button class="text-button icon-button edit-bookmark" type="button" :aria-label="`Edit ${bookmark.title}`" @click="editBookmark(bookmark)">✎</button><button class="danger icon-button delete-bookmark" type="button" :aria-label="`Delete ${bookmark.title}`" @click="removeBookmark(bookmark)">×</button></div>
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
