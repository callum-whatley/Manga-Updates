import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.mangaupdates.app',
  appName: 'Manga Updates',
  webDir: 'dist',
  plugins: {
    Browser: {
      presentationStyle: 'popover',
    },
  },
};

export default config;
