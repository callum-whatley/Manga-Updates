<template>
	<div class="join-page">
		<div class="join-card">
			<h1 class="title">Manga Updates</h1>
			<p class="subtitle">You've been invited. Choose how to sign in.</p>

			<div v-if="!validCode" class="invalid">
				<p>This invite link is invalid or has already been used.</p>
			</div>

			<div v-else class="providers">
				<a :href="`/auth/google?invite=${code}`" class="provider-btn google">
					<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
						<path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
						<path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
						<path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
						<path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
					</svg>
					Continue with Google
				</a>
				<a :href="`/auth/github?invite=${code}`" class="provider-btn github">
					<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
						<path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
					</svg>
					Continue with GitHub
				</a>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const code = computed(() => (route.query.code as string) || '');
const validCode = computed(() => !!code.value);
</script>

<style scoped>
.join-page {
	min-height: 100vh;
	display: flex;
	align-items: center;
	justify-content: center;
	background: var(--bg);
	padding: 2rem;
}

.join-card {
	width: 100%;
	max-width: 400px;
	text-align: center;
}

.title {
	font-family: 'Cinzel', serif;
	font-size: clamp(1.8rem, 5vw, 2.4rem);
	font-weight: 600;
	color: var(--text);
	letter-spacing: 0.08em;
	margin-bottom: 0.5rem;
}

.subtitle {
	color: var(--muted);
	font-size: 0.875rem;
	margin-bottom: 2.5rem;
}

.invalid {
	color: var(--accent);
	font-size: 0.875rem;
}

.providers {
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.provider-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.75rem;
	padding: 0.85rem 1.5rem;
	border-radius: 4px;
	border: 1px solid var(--border);
	background: var(--surface);
	color: var(--text);
	font-size: 0.875rem;
	font-weight: 400;
	letter-spacing: 0.03em;
	transition: border-color 0.2s, background 0.2s;
}

.provider-btn:hover {
	background: var(--surface-2);
	border-color: var(--accent);
}
</style>
