<template>
	<form class="add-form" @submit.prevent="handleSubmit">
		<input
			v-model="title"
			class="add-input"
			type="text"
			placeholder="Add manga by title…"
			:disabled="adding"
			autocomplete="off"
		/>
		<button class="add-btn" type="submit" :disabled="!title.trim() || adding">
			{{ adding ? '…' : '+' }}
		</button>
		<p v-if="error" class="add-error">{{ error }}</p>
	</form>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useMangaStore } from '@/stores/manga';

const manga = useMangaStore();
const title = ref('');
const adding = ref(false);
const error = ref('');

async function handleSubmit() {
	const t = title.value.trim();
	if (!t) return;
	adding.value = true;
	error.value = '';
	const result = await manga.addManga(t);
	if (result) {
		title.value = '';
	} else {
		error.value = manga.error || 'Failed to add manga';
	}
	adding.value = false;
}
</script>

<style scoped>
.add-form {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	flex-wrap: wrap;
	position: relative;
}

.add-input {
	flex: 1;
	min-width: 200px;
	background: var(--surface);
	border: 1px solid var(--border);
	border-radius: 4px;
	padding: 0.6rem 1rem;
	color: var(--text);
	font-family: inherit;
	font-size: 0.875rem;
	outline: none;
	transition: border-color 0.2s;
}

.add-input:focus {
	border-color: var(--accent);
}

.add-input::placeholder {
	color: var(--muted);
}

.add-btn {
	width: 36px;
	height: 36px;
	border-radius: 4px;
	border: 1px solid var(--accent);
	background: var(--accent-dim);
	color: var(--accent);
	font-size: 1.2rem;
	display: flex;
	align-items: center;
	justify-content: center;
	flex-shrink: 0;
	transition: background 0.2s;
}

.add-btn:hover:not(:disabled) {
	background: var(--accent-glow);
}

.add-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

.add-error {
	width: 100%;
	font-size: 0.75rem;
	color: var(--accent);
	margin-top: 0.25rem;
}
</style>
