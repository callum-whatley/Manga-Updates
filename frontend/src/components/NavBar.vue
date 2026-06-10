<template>
	<header class="navbar">
		<div class="navbar-inner">
			<div class="brand">
				<span class="brand-mark">巻</span>
				<span class="brand-name">Manga Updates</span>
			</div>
			<div class="navbar-right">
				<button v-if="auth.user?.isAdmin" class="add-source-btn" @click="$emit('open-scraper')" title="Add source site">
				<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5">
					<circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="16" /><line x1="8" y1="12" x2="16" y2="12" />
				</svg>
				<span>Add Source</span>
			</button>
			<button v-if="auth.user?.isAdmin" class="manage-sources-btn" @click="$emit('open-manage')" title="Manage source sites">
				<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5">
					<line x1="8" y1="6" x2="21" y2="6"/>
					<line x1="8" y1="12" x2="21" y2="12"/>
					<line x1="8" y1="18" x2="21" y2="18"/>
					<line x1="3" y1="6" x2="3.01" y2="6"/>
					<line x1="3" y1="12" x2="3.01" y2="12"/>
					<line x1="3" y1="18" x2="3.01" y2="18"/>
				</svg>
				<span>Sources</span>
			</button>
			<button class="check-all-btn" :class="{ loading }" @click="handleCheckAll" title="Check all for updates">
					<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
						<polyline points="23 4 23 10 17 10" />
						<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
					</svg>
					<span>{{ loading ? 'Checking…' : 'Check All' }}</span>
				</button>
				<div class="avatar" :title="user?.displayName">
					<img v-if="user?.avatarUrl" :src="user.avatarUrl" :alt="user.displayName" />
					<span v-else>{{ initials }}</span>
				</div>
				<button class="logout-btn" @click="handleLogout">Sign out</button>
			</div>
		</div>
	</header>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useMangaStore } from '@/stores/manga';

defineEmits<{ 'open-scraper': [], 'open-manage': [] }>();

const auth = useAuthStore();
const manga = useMangaStore();
const router = useRouter();

const user = computed(() => auth.user);
const loading = computed(() => manga.loading);

const initials = computed(() => {
	const name = user.value?.displayName || '';
	return name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase();
});

async function handleCheckAll() {
	await manga.checkAll();
}

function handleLogout() {
	auth.logout();
	router.push({ name: 'login' });
}
</script>

<style scoped>
.navbar {
	position: sticky;
	top: 0;
	z-index: 50;
	background: rgba(13,13,13,0.9);
	backdrop-filter: blur(12px);
	border-bottom: 1px solid var(--border);
}

.navbar-inner {
	max-width: 1200px;
	margin: 0 auto;
	padding: 0 2rem;
	height: 60px;
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.brand {
	display: flex;
	align-items: center;
	gap: 0.6rem;
}

.brand-mark {
	font-size: 1.4rem;
	color: var(--accent);
}

.brand-name {
	font-family: 'Cinzel', serif;
	font-size: 1rem;
	font-weight: 600;
	letter-spacing: 0.08em;
	color: var(--text);
}

.navbar-right {
	display: flex;
	align-items: center;
	gap: 1rem;
}

.add-source-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.45rem 0.85rem;
	border-radius: 4px;
	border: 1px solid var(--accent-glow);
	background: var(--accent-dim);
	color: var(--accent);
	font-size: 0.75rem;
	letter-spacing: 0.04em;
	transition: background 0.2s;
}

.add-source-btn:hover {
	background: rgba(230,57,70,0.2);
}

.manage-sources-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.45rem 0.85rem;
	border-radius: 4px;
	border: 1px solid var(--border);
	background: transparent;
	color: var(--muted);
	font-size: 0.75rem;
	letter-spacing: 0.04em;
	transition: color 0.2s, border-color 0.2s;
}

.manage-sources-btn:hover {
	color: var(--text);
	border-color: rgba(255,255,255,0.15);
}

.check-all-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.45rem 0.85rem;
	border-radius: 4px;
	border: 1px solid var(--border);
	background: transparent;
	color: var(--muted);
	font-size: 0.75rem;
	letter-spacing: 0.04em;
	transition: color 0.2s, border-color 0.2s;
}

.check-all-btn:hover:not(.loading) {
	color: var(--text);
	border-color: var(--accent);
}

.check-all-btn.loading {
	opacity: 0.5;
	cursor: wait;
}

.avatar {
	width: 32px;
	height: 32px;
	border-radius: 50%;
	background: var(--accent-dim);
	border: 1px solid var(--accent-glow);
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 0.7rem;
	font-weight: 500;
	color: var(--accent);
	overflow: hidden;
}

.avatar img {
	width: 100%;
	height: 100%;
	object-fit: cover;
}

.logout-btn {
	font-size: 0.75rem;
	color: var(--muted);
	background: none;
	border: none;
	padding: 0;
	transition: color 0.2s;
}

.logout-btn:hover {
	color: var(--accent);
}
</style>
