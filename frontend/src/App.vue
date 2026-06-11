<template>
	<router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';

const auth = useAuthStore();
const router = useRouter();

onMounted(async () => {
	if (auth.isAuthenticated && !auth.user) {
		auth.fetchUser();
	}

	// Handle Capacitor deep link callbacks (native app only)
	try {
		const { App: CapApp } = await import('@capacitor/app');
		await CapApp.addListener('appUrlOpen', async (event: { url: string }) => {
			console.log('[OAuth] appUrlOpen fired');
			// new URL() throws for custom schemes in Android WebView — use regex instead
			const match = event.url.match(/[?&]token=([^&]+)/);
			const token = match ? decodeURIComponent(match[1]) : null;
			console.log('[OAuth] token found:', !!token);
			if (token) {
				try {
					const { Browser } = await import('@capacitor/browser');
					await Browser.close();
				} catch { /* ignore if already closed */ }
				auth.setToken(token);
				try {
					await auth.fetchUser();
					console.log('[OAuth] fetchUser success, user:', auth.user?.email);
				} catch (e) {
					console.error('[OAuth] fetchUser failed:', e);
				}
				console.log('[OAuth] isAuthenticated:', auth.isAuthenticated, '— pushing /');
				router.push('/');
			}
		});
	} catch {
		// Not running in a Capacitor environment
	}
});
</script>
