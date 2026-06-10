<template>
	<div class="callback">
		<p v-if="error" class="error">{{ error }}</p>
		<p v-else class="loading">Signing you in…</p>
	</div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();
const error = ref('');

onMounted(async () => {
	const token = window.location.hash.slice(1) || undefined;
	if (!token) {
		error.value = 'Authentication failed — no token received.';
		return;
	}
	auth.setToken(token);
	await auth.fetchUser();
	router.replace({ name: 'home' });
});
</script>

<style scoped>
.callback {
	display: flex;
	align-items: center;
	justify-content: center;
	min-height: 100vh;
	background: var(--bg);
}

.loading {
	color: var(--muted);
	font-size: 0.9rem;
	letter-spacing: 0.1em;
}

.error {
	color: var(--accent);
}
</style>
