<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import {
  createBookmark,
  deleteBookmark,
  importBrowserFile,
  listBookmarks,
  updateBookmark,
  type Bookmark,
  type Browser,
} from "./api/client";

const PAGE_SIZE = 10;
const bookmarks = ref<Bookmark[]>([]);
const total = ref(0);
const offset = ref(0);
const query = ref("");
const error = ref("");
const notice = ref("");
const loading = ref(false);
const editingId = ref<number | null>(null);
const importBrowser = ref<Browser>("chrome");
const importFile = ref<File | null>(null);
const form = reactive({ folder: "", tags: "", title: "", url: "" });

const currentPage = computed(() => Math.floor(offset.value / PAGE_SIZE) + 1);
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));

async function loadBookmarks(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const page = await listBookmarks(query.value, PAGE_SIZE, offset.value);
    bookmarks.value = page.items;
    total.value = page.total;
  } catch (caught) {
    error.value = messageFrom(caught);
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
    error.value = "Select a browser profile file.";
    return;
  }
  try {
    const result = await importBrowserFile(importBrowser.value, importFile.value);
    const summary = `Imported ${result.imported}; skipped ${result.skipped}.`;
    const warnings = (result.warnings ?? [])
      .map((warning) => warning.message)
      .join(" ");
    notice.value = warnings ? `${summary} Warnings: ${warnings}` : summary;
    await loadBookmarks();
  } catch (caught) {
    error.value = messageFrom(caught);
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
        <div><p class="eyebrow">Browser data</p><h2 id="import-heading">Import a profile</h2></div>
      </div>
      <form class="import-form" @submit.prevent="runImport">
        <label>Browser<select v-model="importBrowser"><option value="chrome">Chrome</option><option value="chromium">Chromium</option><option value="edge">Edge</option><option value="firefox">Firefox</option></select></label>
        <label>Profile file<input type="file" required @change="selectImportFile" /></label>
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
