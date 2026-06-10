import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import api from '@/composables/useApi';
import type { User } from '@/types';

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'));
  const user = ref<User | null>(null);
  const loading = ref(false);

  const isAuthenticated = computed(() => !!token.value);

  async function fetchUser() {
    if (!token.value) return;
    try {
      loading.value = true;
      const { data } = await api.get('/user/me');
      user.value = data;
    } catch {
      logout();
    } finally {
      loading.value = false;
    }
  }

  function setToken(t: string) {
    token.value = t;
    localStorage.setItem('token', t);
  }

  function logout() {
    token.value = null;
    user.value = null;
    localStorage.removeItem('token');
  }

  return { token, user, loading, isAuthenticated, fetchUser, setToken, logout };
});
