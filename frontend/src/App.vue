<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  createBookmark,
  deleteBookmark,
  importBookmarkFile,
  listBookmarks,
  updateBookmark,
  type Bookmark,
} from "./api/client";

const PAGE_SIZE = 10;
const bookmarks = ref<Bookmark[]>([]);
const total = ref(0);
const offset = ref(0);
const query = ref("");
const error = ref("");
const notice = ref("");
const loading = ref(false);
interface NotificationEvent {
  id: number;
  message: string;
  operation: string;
  occurredAt: Date;
  unread: boolean;
}

const editingId = ref<number | null>(null);
const importFile = ref<File | null>(null);
const notificationOpen = ref(false);
const notificationEvents = ref<NotificationEvent[]>([]);
const form = reactive({ folder: "", tags: "", title: "", url: "" });
let nextNotificationEventId = 1;

const currentPage = computed(() => Math.floor(offset.value / PAGE_SIZE) + 1);
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));
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
  loading.value = true;
  error.value = "";
  try {
    const page = await listBookmarks(query.value, PAGE_SIZE, offset.value);
    bookmarks.value = page.items;
    total.value = page.total;
  } catch (caught) {
    error.value = messageFrom(caught);
    recordEvent("Load bookmarks", error.value);
  } finally {
    loading.value = false;
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
    resetForm();
    await loadBookmarks();
  } catch (caught) {
    error.value = messageFrom(caught);
    recordEvent(editingId.value === null ? "Create bookmark" : "Update bookmark", error.value);
  }
}

function editBookmark(bookmark: Bookmark): void {
  editingId.value = bookmark.id;
  form.folder = bookmark.folder ?? "";
  form.tags = (bookmark.tags ?? []).join(", ");
  form.title = bookmark.title;
  form.url = bookmark.url;
  window.scrollTo({ behavior: "smooth", top: 0 });
}

async function removeBookmark(bookmark: Bookmark): Promise<void> {
  if (!window.confirm(`Delete ${bookmark.title}?`)) {
    return;
  }
  try {
    await deleteBookmark(bookmark.id);
    notice.value = "Bookmark deleted.";
    if (bookmarks.value.length === 1 && offset.value > 0) {
      offset.value = Math.max(0, offset.value - PAGE_SIZE);
    }
    await loadBookmarks();
  } catch (caught) {
    error.value = messageFrom(caught);
    recordEvent("Delete bookmark", error.value);
  }
}

function resetForm(): void {
  editingId.value = null;
  form.folder = "";
  form.tags = "";
  form.title = "";
  form.url = "";
}

async function search(): Promise<void> {
  offset.value = 0;
  await loadBookmarks();
}

async function changePage(direction: -1 | 1): Promise<void> {
  offset.value += direction * PAGE_SIZE;
  await loadBookmarks();
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
</script>

<template>
  <main class="shell">
    <header class="hero">
      <p class="eyebrow">Personal bookmark archive</p>
      <h1>Link Hoarder</h1>
      <p>Search, classify, and import bookmarks from one private workspace.</p>
      <div class="notifications">
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

    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-if="notice" class="message notice" role="status">{{ notice }}</p>

    <section class="panel" aria-labelledby="editor-heading">
      <div class="section-heading">
        <div>
          <p class="eyebrow">{{ editingId === null ? "New entry" : "Edit entry" }}</p>
          <h2 id="editor-heading">{{ editingId === null ? "Save a bookmark" : "Update bookmark" }}</h2>
        </div>
        <button v-if="editingId !== null" class="text-button" type="button" @click="resetForm">Cancel</button>
      </div>
      <form class="bookmark-form" @submit.prevent="saveBookmark">
        <label>URL<input v-model="form.url" required placeholder="https://example.com" /></label>
        <label>Title<input v-model="form.title" required placeholder="Useful reference" /></label>
        <label>Folder<input v-model="form.folder" placeholder="Research/Reading" /></label>
        <label>Tags<input v-model="form.tags" placeholder="docs, tools" /></label>
        <button class="primary" type="submit">{{ editingId === null ? "Save bookmark" : "Save changes" }}</button>
      </form>
    </section>

    <section class="panel" aria-labelledby="import-heading">
      <div class="section-heading">
        <div><p class="eyebrow">Browser export</p><h2 id="import-heading">Import bookmark HTML</h2></div>
      </div>
      <form class="import-form" @submit.prevent="runImport">
        <label>Bookmark export<input type="file" accept=".html,.htm,text/html" required @change="selectImportFile" /></label>
        <button class="secondary" type="submit">Import bookmarks</button>
      </form>
    </section>

    <section class="panel collection" aria-labelledby="collection-heading">
      <div class="section-heading collection-heading">
        <div><p class="eyebrow">{{ total }} saved</p><h2 id="collection-heading">Collection</h2></div>
        <form class="search" role="search" @submit.prevent="search">
          <input v-model="query" aria-label="Search bookmarks" placeholder="Search title, URL, or tag" />
          <button class="secondary" type="submit">Search</button>
        </form>
      </div>

      <p v-if="loading" class="empty">Loading bookmarks…</p>
      <p v-else-if="bookmarks.length === 0" class="empty">No bookmarks match this view.</p>
      <ul v-else class="bookmark-list">
        <li v-for="bookmark in bookmarks" :key="bookmark.id" class="bookmark-card">
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
          <div class="actions"><button class="text-button" type="button" @click="editBookmark(bookmark)">Edit</button><button class="danger" type="button" @click="removeBookmark(bookmark)">Delete</button></div>
        </li>
      </ul>

      <nav class="pagination" aria-label="Bookmark pages">
        <button class="text-button" type="button" :disabled="offset === 0" @click="changePage(-1)">Previous</button>
        <span>Page {{ currentPage }} of {{ pageCount }}</span>
        <button class="text-button" type="button" :disabled="offset + PAGE_SIZE >= total" @click="changePage(1)">Next</button>
      </nav>
    </section>
  </main>
</template>
