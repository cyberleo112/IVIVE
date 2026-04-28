// Firebase Web SDK initialization for the IVIVE static frontend.
// Loaded as an ES module from index.html.
// Note: API key here is a public client identifier (not a secret) — Firebase
// access is controlled by Security Rules and authorized domains in the console.

import { initializeApp } from "https://www.gstatic.com/firebasejs/12.12.1/firebase-app.js";
import {
  getAnalytics,
  isSupported as isAnalyticsSupported,
} from "https://www.gstatic.com/firebasejs/12.12.1/firebase-analytics.js";

const firebaseConfig = {
  apiKey: "AIzaSyCOUFB1wZZVCIv9qzcIsqM-lE_wpCl4MUM",
  authDomain: "ivive-2273c.firebaseapp.com",
  projectId: "ivive-2273c",
  storageBucket: "ivive-2273c.firebasestorage.app",
  messagingSenderId: "852751975563",
  appId: "1:852751975563:web:12d48949c6372391fa008e",
  measurementId: "G-TZY84T6DMQ",
};

const app = initializeApp(firebaseConfig);

isAnalyticsSupported()
  .then((ok) => {
    if (ok) {
      getAnalytics(app);
    }
  })
  .catch(() => {
    /* analytics is optional; ignore (e.g. localhost / unsupported env) */
  });

export { app };
